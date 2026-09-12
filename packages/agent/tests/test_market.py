"""Market-order builder behavior: the index-0 law, sell-often staples, reserves.

Index-0 law (strategy doc, verified edge): market orders resolve by queue-slot
index across both players; an order at slot 0 fully executes (moving price)
before either player's slot-1 order. Crashable goods therefore always sell at
index 0. Wheat/egg are glut-proof (log above-curve) and sell every turn.

``hour=0`` is used as the default across tests that aren't specifically about
the M2b satellite-batching gate -- 0 is always outside the blocked batch-hour
window (``MELON_MILK_WOOL_BATCH_BLOCKED_HOURS``), so it reproduces the pre-M2b
"whenever the floor/cap say so" behavior exactly.
"""

from __future__ import annotations

from itertools import product

from agent.market import (
    FERT_MIN_PRICE,
    HIRE_SLOT_FLOOR,
    MAX_ORDERS,
    MELON_MILK_WOOL_BATCH_BLOCKED_HOURS,
    MELON_MILK_WOOL_BATCH_EXEMPT_DAY,
    MELON_MIN_PRICE,
    MILK_MIN_PRICE,
    STRAWBERRY_MIN_PRICE,
    WOOL_MIN_PRICE,
    build_orders,
)
from kaggle_environments.envs.kaggriculture.kaggriculture import MARKET_PARAMS, market_price


def test_clone_front_run_products_bypass_waits_but_keep_normal_caps() -> None:
    orders = build_orders(
        shed={"MELON": 12, "STRAWBERRY": 12, "MILK": 12, "WOOL": 12},
        prices={"MELON": 0.0, "STRAWBERRY": 0.0, "MILK": 0.0, "WOOL": 0.0},
        day=6,
        hour=6,
        wheat_reserve=0,
        buys=[],
        front_run_products=frozenset({"MELON", "STRAWBERRY", "MILK", "WOOL"}),
    )

    assert orders == [
        ["SELL", "MELON", 2],
        ["SELL", "STRAWBERRY", 2],
        ["SELL", "MILK", 4],
        ["SELL", "WOOL", 4],
    ]


def test_clone_front_run_default_off_and_unrelated_product_preserve_waits() -> None:
    common = dict(
        shed={"MELON": 12},
        prices={"MELON": 0.0},
        day=6,
        hour=6,
        wheat_reserve=0,
        buys=[],
    )
    assert build_orders(**common) == []
    assert build_orders(**common, front_run_products=frozenset({"MILK"})) == []


def test_clone_front_run_bypasses_melon_ramp_floor() -> None:
    orders = build_orders(
        shed={"MELON": 12},
        prices={"MELON": 0.0},
        day=28,
        hour=6,
        wheat_reserve=0,
        buys=[],
        front_run_products=frozenset({"MELON"}),
    )

    assert orders == [["SELL", "MELON", 2]]


def test_crashable_fertilizer_sell_is_index_zero() -> None:
    orders = build_orders(
        shed={"WHEAT": 10, "EGG": 2, "FERTILIZER": 3},
        prices={"FERTILIZER": 100.0, "WHEAT": 25.0, "EGG": 50.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
    )
    assert orders[0] == ["SELL", "FERTILIZER", 3]  # below the 4/turn cap: exact shed count
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders
    assert len(orders) <= 10


def test_fertilizer_held_when_price_crashed_but_dumped_at_liquidation() -> None:
    # M2c: FERT_MIN_PRICE dropped from $55 to $15 (the valve, not the floor,
    # now covers a genuine backlog) -- $10 is below even the lowered floor.
    crashed = {"FERTILIZER": 10.0, "WHEAT": 25.0, "EGG": 50.0}
    held = build_orders(
        shed={"FERTILIZER": 5}, prices=crashed, day=10, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "FERTILIZER" for o in held)

    dumped = build_orders(
        shed={"FERTILIZER": 5}, prices=crashed, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert dumped[0] == ["SELL", "FERTILIZER", 5]  # liquidation ignores both floor and per-turn cap


def test_fertilizer_sell_capped_at_four_even_with_more_in_shed() -> None:
    # 15 animals collect ~15 fertilizer/day; an uncapped dump would walk the
    # linear-above-curve price straight down. Cap holds even with 40 on hand.
    orders = build_orders(
        shed={"FERTILIZER": 40},
        prices={"FERTILIZER": 100.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
    )
    assert orders[0] == ["SELL", "FERTILIZER", 4]

    dumped = build_orders(
        shed={"FERTILIZER": 40},
        prices={"FERTILIZER": 100.0},
        day=29,
        hour=0,
        wheat_reserve=3,
        buys=[],
    )
    assert dumped[0] == ["SELL", "FERTILIZER", 40]  # liquidation ignores the cap


def test_wheat_feed_reserve_withheld_until_liquidation() -> None:
    prices = {"WHEAT": 25.0}
    held = build_orders(shed={"WHEAT": 2}, prices=prices, day=10, hour=0, wheat_reserve=3, buys=[])
    assert held == []

    dumped = build_orders(
        shed={"WHEAT": 2}, prices=prices, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert ["SELL", "WHEAT", 2] in dumped


def test_sells_survive_the_ten_order_cap() -> None:
    buys: list[list[object]] = [["BUY_SEED", "WHEAT", 1] for _ in range(9)]
    orders = build_orders(
        shed={"WHEAT": 10, "EGG": 1, "FERTILIZER": 1},
        prices={"FERTILIZER": 100.0, "WHEAT": 25.0, "EGG": 50.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=buys,
    )
    assert len(orders) == 10
    assert orders[0] == ["SELL", "FERTILIZER", 1]
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders


def test_melon_sell_respects_price_floor() -> None:
    below_floor = build_orders(
        shed={"MELON": 5}, prices={"MELON": 180.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in below_floor)

    above_floor = build_orders(
        shed={"MELON": 5}, prices={"MELON": 200.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "MELON", 2]


def test_melon_sell_capped_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(
        shed={"MELON": 9}, prices={"MELON": 250.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 2]


def test_melon_sell_below_cap_sells_the_exact_shed_count() -> None:
    orders = build_orders(
        shed={"MELON": 1}, prices={"MELON": 250.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 1]


def test_melon_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"MELON": 50.0}
    held = build_orders(shed={"MELON": 9}, prices=crashed, day=10, hour=0, wheat_reserve=3, buys=[])
    assert not any(o[1] == "MELON" for o in held)

    dumped = build_orders(
        shed={"MELON": 9}, prices=crashed, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert dumped[0] == ["SELL", "MELON", 9]  # liquidation ignores both floor and per-turn cap


def test_melon_sell_leads_even_fertilizer_at_index_zero() -> None:
    # No MILK/WOOL in the shed this turn, so they don't insert between melon
    # and fertilizer -- confirms melon leads regardless of what else is idle.
    orders = build_orders(
        shed={"MELON": 2, "FERTILIZER": 3},
        prices={"MELON": 250.0, "FERTILIZER": 100.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
    )
    assert orders[0] == ["SELL", "MELON", 2]
    assert orders[1] == ["SELL", "FERTILIZER", 3]


def test_no_melon_sell_when_shed_is_empty() -> None:
    orders = build_orders(
        shed={"FERTILIZER": 3}, prices={"MELON": 250.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in orders)


# --- Milk + wool (M2c: regime-conditional floors) --------------------------
#
# Same shape as melon's floor+cap: MILK is linear above-curve (base $160,
# -25% at ~+19 net oversupply), WOOL is quadratic (base $200, -25% at ~+29) --
# both currently under-supplied by the field, but crash-prone enough to earn
# their own per-turn cap the moment husbandry starts producing at scale.
#
# M2c (kaggriculture#59) replaces the old static-forever floors with a
# regime-conditional one: unlatched, the floor still holds exactly as before
# (WOOL stays at $150 -- a brief $200 default was itself a regression, since
# $200 is exactly WOOL's equilibrium quote; see
# test_shipped_floors_permit_meaningful_volume_before_equilibrium below --
# MILK unchanged at $120, cap raised 2 -> a shared 4); once
# ``wool_crashed``/``milk_crashed`` latches true (``agent.state.
# ProductCrashLatch``, driven by policy.py), the floor is waived and the
# product sells at any price. This is what actually fixes #59: a floor-free
# ranch dumper crashing the price no longer holds the backlog forever.


def test_milk_sell_respects_floor_while_unlatched() -> None:
    below_floor = build_orders(
        shed={"MILK": 4}, prices={"MILK": 110.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MILK" for o in below_floor)

    above_floor = build_orders(
        shed={"MILK": 4}, prices={"MILK": 130.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "MILK", 4]


def test_milk_sell_capped_at_four_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(
        shed={"MILK": 6}, prices={"MILK": 160.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MILK", 4]


def test_milk_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"MILK": 50.0}
    held = build_orders(shed={"MILK": 6}, prices=crashed, day=10, hour=0, wheat_reserve=3, buys=[])
    assert not any(o[1] == "MILK" for o in held)

    dumped = build_orders(
        shed={"MILK": 6}, prices=crashed, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert dumped[0] == ["SELL", "MILK", 6]


def test_milk_sells_floorless_once_crash_latched() -> None:
    # Latched: even $1 -- far under the $120 floor -- sells anyway.
    orders = build_orders(
        shed={"MILK": 4},
        prices={"MILK": 1.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        milk_crashed=True,
    )
    assert orders[0] == ["SELL", "MILK", 4]


def test_wool_sell_respects_floor_while_unlatched() -> None:
    # Prices mirror the $150 default floor (below_floor = floor - 10, at the
    # exact boundary for above_floor), same convention as the old $200-floor
    # version of this test.
    below_floor = build_orders(
        shed={"WOOL": 4}, prices={"WOOL": 140.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "WOOL" for o in below_floor)

    above_floor = build_orders(
        shed={"WOOL": 4}, prices={"WOOL": 150.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "WOOL", 4]


def test_wool_sell_capped_at_four_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(
        shed={"WOOL": 6}, prices={"WOOL": 250.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "WOOL", 4]


def test_wool_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"WOOL": 60.0}
    held = build_orders(shed={"WOOL": 6}, prices=crashed, day=10, hour=0, wheat_reserve=3, buys=[])
    assert not any(o[1] == "WOOL" for o in held)

    dumped = build_orders(
        shed={"WOOL": 6}, prices=crashed, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert dumped[0] == ["SELL", "WOOL", 6]


def test_wool_sells_floorless_once_crash_latched() -> None:
    orders = build_orders(
        shed={"WOOL": 4},
        prices={"WOOL": 1.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        wool_crashed=True,
    )
    assert orders[0] == ["SELL", "WOOL", 4]


def test_wool_floor_and_cap_are_independently_configurable() -> None:
    # A caller-supplied floor/cap (as policy.py threads from PolicyConfig)
    # overrides the module defaults.
    orders = build_orders(
        shed={"WOOL": 9},
        prices={"WOOL": 90.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        wool_floor=80.0,
        wool_milk_sell_cap=5,
    )
    assert orders[0] == ["SELL", "WOOL", 5]


def test_full_sell_priority_order_is_melon_milk_wool_fertilizer_egg_wheat() -> None:
    orders = build_orders(
        shed={"MELON": 2, "MILK": 2, "WOOL": 2, "FERTILIZER": 2, "EGG": 2, "WHEAT": 10},
        prices={"MELON": 250.0, "MILK": 160.0, "WOOL": 200.0, "FERTILIZER": 100.0, "EGG": 50.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
    )
    items_in_order = [o[1] for o in orders]
    assert items_in_order == ["MELON", "MILK", "WOOL", "FERTILIZER", "EGG", "WHEAT"]


# --- M2b: satellite sell batching (teeth-check d) ----------------------------
#
# MELON/MILK/WOOL sell every hour except the blocked deep-morning window
# (4-9) -- not the instant a turn's price clears the floor, but also not
# restricted to the narrow allowlist the first cut used (see market.py's
# module docstring for the empirical tuning note: the original 10-hour
# allowlist cost -5% solo-probed against frozen M2a for no offsetting
# benefit, so it was widened to a 6-hour blocklist).


def test_batching_blocks_melon_sell_at_hour_six_uncontested() -> None:
    orders = build_orders(
        shed={"MELON": 5}, prices={"MELON": 250.0}, day=6, hour=6, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in orders)


def test_batching_allows_melon_sell_at_hour_twelve_uncontested() -> None:
    orders = build_orders(
        shed={"MELON": 5}, prices={"MELON": 250.0}, day=6, hour=12, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 2]


def test_batching_blocked_hours_are_exactly_four_through_nine() -> None:
    assert MELON_MILK_WOOL_BATCH_BLOCKED_HOURS == frozenset({4, 5, 6, 7, 8, 9})


def test_batching_allows_every_hour_outside_the_blocked_window() -> None:
    for hour in range(24):
        if hour in MELON_MILK_WOOL_BATCH_BLOCKED_HOURS:
            continue
        orders = build_orders(
            shed={"MELON": 5}, prices={"MELON": 250.0}, day=6, hour=hour, wheat_reserve=3, buys=[]
        )
        assert orders[0] == ["SELL", "MELON", 2], f"hour={hour}"


def test_batching_blocks_every_hour_inside_the_blocked_window() -> None:
    for hour in MELON_MILK_WOOL_BATCH_BLOCKED_HOURS:
        orders = build_orders(
            shed={"MELON": 5}, prices={"MELON": 250.0}, day=6, hour=hour, wheat_reserve=3, buys=[]
        )
        assert not any(o[1] == "MELON" for o in orders), f"hour={hour}"


def test_batching_also_gates_milk_and_wool() -> None:
    orders = build_orders(
        shed={"MILK": 4, "WOOL": 4},
        prices={"MILK": 160.0, "WOOL": 200.0},
        day=6,
        hour=6,
        wheat_reserve=3,
        buys=[],
    )
    assert not any(o[1] in ("MILK", "WOOL") for o in orders)

    orders = build_orders(
        shed={"MILK": 4, "WOOL": 4},
        prices={"MILK": 160.0, "WOOL": 200.0},
        day=6,
        hour=13,
        wheat_reserve=3,
        buys=[],
    )
    assert ["SELL", "MILK", 4] in orders
    assert ["SELL", "WOOL", 4] in orders


def test_batching_does_not_gate_wheat_egg_or_fertilizer() -> None:
    orders = build_orders(
        shed={"WHEAT": 5, "EGG": 2, "FERTILIZER": 3},
        prices={"WHEAT": 25.0, "EGG": 50.0, "FERTILIZER": 100.0},
        day=6,
        hour=6,  # not a batch hour -- staples/fertilizer must be unaffected
        wheat_reserve=0,
        buys=[],
    )
    items = {o[1] for o in orders}
    assert {"WHEAT", "EGG", "FERTILIZER"} <= items


def test_batching_exempt_from_day_27_onward() -> None:
    assert MELON_MILK_WOOL_BATCH_EXEMPT_DAY == 27
    # Off-window hour, but day >= 27: any hour is fair game.
    orders = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 250.0},
        day=27,
        hour=6,
        wheat_reserve=3,
        buys=[],
    )
    assert any(o[1] == "MELON" for o in orders)

    # Same off-window hour, one day earlier: still gated.
    orders = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 250.0},
        day=26,
        hour=6,
        wheat_reserve=3,
        buys=[],
    )
    assert not any(o[1] == "MELON" for o in orders)


# --- M2b: melon liquidation ramp (teeth-check e) -----------------------------
#
# day 27 floor $100, day 28 floor $60, day >= 29 sells everything, uncapped.
# Distinct from the day-29 cliff every other product still uses.


def test_liquidation_ramp_sells_at_seventy_on_day_28_but_not_day_27() -> None:
    day_27 = build_orders(
        shed={"MELON": 9}, prices={"MELON": 70.0}, day=27, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in day_27)  # $70 < day-27's $100 floor

    day_28 = build_orders(
        shed={"MELON": 9}, prices={"MELON": 70.0}, day=28, hour=0, wheat_reserve=3, buys=[]
    )
    assert day_28[0] == ["SELL", "MELON", 2]  # $70 >= day-28's $60 floor, still capped at 2


def test_liquidation_ramp_day_27_sells_at_its_own_floor() -> None:
    below = build_orders(
        shed={"MELON": 9}, prices={"MELON": 95.0}, day=27, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in below)

    above = build_orders(
        shed={"MELON": 9}, prices={"MELON": 105.0}, day=27, hour=0, wheat_reserve=3, buys=[]
    )
    assert above[0] == ["SELL", "MELON", 2]


def test_liquidation_ramp_day_28_still_capped_at_two() -> None:
    orders = build_orders(
        shed={"MELON": 40}, prices={"MELON": 65.0}, day=28, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 2]


def test_liquidation_day_29_sells_all_no_floor_no_cap_ramp_unchanged() -> None:
    orders = build_orders(
        shed={"MELON": 40}, prices={"MELON": 1.0}, day=29, hour=6, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 40]


# --- M2b: contested dynamic floor (teeth-check b) ----------------------------


def test_melon_dynamic_floor_matches_static_floor_at_zero_days_contested() -> None:
    # rolling_max pinned to each call's own price so the peak gate (tested
    # separately below) never binds -- this isolates the floor-decay math.
    held = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 190.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=0,
        melon_rolling_max=190.0,
    )
    assert not any(o[1] == "MELON" for o in held)  # 190 < 195, same as the static floor

    sold = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 200.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=0,
        melon_rolling_max=200.0,
    )
    assert sold[0] == ["SELL", "MELON", 2]


def test_melon_dynamic_floor_decays_eight_per_day() -> None:
    # 5 days since contested: floor = 195 - 8*5 = 155.
    held = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 150.0},
        day=15,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=5,
        melon_rolling_max=160.0,
    )
    assert not any(o[1] == "MELON" for o in held)

    sold = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 160.0},
        day=15,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=5,
        melon_rolling_max=160.0,
    )
    assert sold[0] == ["SELL", "MELON", 2]


def test_melon_dynamic_floor_clamps_at_120() -> None:
    # 20 days since contested: naive decay is 195 - 160 = 35, but the floor
    # never drops below the $120 clamp.
    held = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 115.0},
        day=24,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=20,
        melon_rolling_max=125.0,
    )
    assert not any(o[1] == "MELON" for o in held)

    sold = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 125.0},
        day=24,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=20,
        melon_rolling_max=125.0,
    )
    assert sold[0] == ["SELL", "MELON", 2]

    # Even absurdly many days since contested still clamps at 120, never lower.
    sold_far = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 121.0},
        day=24,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=999,
        melon_rolling_max=121.0,
    )
    assert sold_far[0] == ["SELL", "MELON", 2]


# --- M2b: peak gate (teeth-check c) ------------------------------------------


def test_peak_gate_blocks_a_sell_twenty_under_rolling_max_even_above_floor() -> None:
    # Floor (day-0-contested, $195) easily clears at $230, but $230 is $20
    # under the $250 rolling max -- more than the $15 peak-gate margin.
    held = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 230.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=0,
        melon_rolling_max=250.0,
    )
    assert not any(o[1] == "MELON" for o in held)


def test_peak_gate_allows_a_sell_within_fifteen_of_rolling_max() -> None:
    sold = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 236.0},
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=True,
        melon_days_since_contested=0,
        melon_rolling_max=250.0,
    )
    assert sold[0] == ["SELL", "MELON", 2]


def test_peak_gate_only_applies_while_contested() -> None:
    # Uncontested: no rolling-max gate at all, just the flat static floor.
    orders = build_orders(
        shed={"MELON": 5},
        prices={"MELON": 200.0},  # above MELON_MIN_PRICE, far under a hypothetical high max
        day=10,
        hour=0,
        wheat_reserve=3,
        buys=[],
        melon_contested=False,
        melon_rolling_max=400.0,
    )
    assert orders[0] == ["SELL", "MELON", 2]


def test_melon_min_price_constant_is_the_uncontested_floor() -> None:
    assert MELON_MIN_PRICE == 195.0


# --- M2c: two-tier shed valve (kaggriculture#59) ------------------------------
#
# valve_tier=0 (the default) reproduces every test above exactly. Tier 1
# (soft) ignores every floor below -- melon's ramp/contested/peak-gate logic
# included -- and sells at market on a shared soft cap; tier 2 (hard) ignores
# floors AND per-product caps and sells the entire shed, except WHEAT, which
# keeps its feed reserve even at tier 2.


def test_valve_tier_zero_is_the_default_and_changes_nothing() -> None:
    # 140.0 is below the $150 default wool_floor -- unaffected by the exact
    # floor value, just needs to be genuinely below whatever it is.
    orders = build_orders(
        shed={"WOOL": 4}, prices={"WOOL": 140.0}, day=6, hour=0, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "WOOL" for o in orders)


def test_valve_tier_one_ignores_every_floor_including_melons_with_soft_cap() -> None:
    orders = build_orders(
        shed={"MELON": 20, "MILK": 20, "WOOL": 20, "FERTILIZER": 20},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0, "FERTILIZER": 1.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        valve_tier=1,
    )
    assert orders[0] == ["SELL", "MELON", 10]
    assert orders[1] == ["SELL", "MILK", 10]
    assert orders[2] == ["SELL", "WOOL", 10]
    assert orders[3] == ["SELL", "FERTILIZER", 10]


def test_valve_tier_one_uses_a_configurable_soft_cap() -> None:
    orders = build_orders(
        shed={"WOOL": 20},
        prices={"WOOL": 1.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        valve_tier=1,
        valve_soft_cap=3,
    )
    assert orders[0] == ["SELL", "WOOL", 3]


def test_valve_tier_two_sells_the_entire_shed_ignoring_floors_and_caps() -> None:
    orders = build_orders(
        shed={"MELON": 20, "MILK": 20, "WOOL": 20, "FERTILIZER": 20},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0, "FERTILIZER": 1.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        valve_tier=2,
    )
    assert orders[0] == ["SELL", "MELON", 20]
    assert orders[1] == ["SELL", "MILK", 20]
    assert orders[2] == ["SELL", "WOOL", 20]
    assert orders[3] == ["SELL", "FERTILIZER", 20]


def test_valve_tier_two_preserves_the_wheat_feed_reserve() -> None:
    # Explicit teeth-check for the wheat carve-out: tier 2 must sell only
    # the surplus above the feed reserve, not the whole stock -- unlike
    # every other product, which sells uncapped at tier 2.
    orders = build_orders(
        shed={"WHEAT": 10},
        prices={"WHEAT": 25.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        valve_tier=2,
    )
    assert orders == [["SELL", "WHEAT", 7]]


def test_valve_tier_ordering_is_still_melon_milk_wool_fert_egg_wheat() -> None:
    orders = build_orders(
        shed={"MELON": 2, "MILK": 2, "WOOL": 2, "FERTILIZER": 2, "EGG": 2, "WHEAT": 10},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0, "FERTILIZER": 1.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=[],
        valve_tier=2,
    )
    items_in_order = [o[1] for o in orders]
    assert items_in_order == ["MELON", "MILK", "WOOL", "FERTILIZER", "EGG", "WHEAT"]


def test_valve_tier_sells_still_survive_the_ten_order_cap() -> None:
    buys: list[list[object]] = [["BUY_SEED", "WHEAT", 1] for _ in range(9)]
    orders = build_orders(
        shed={"MELON": 5, "MILK": 5, "WOOL": 5, "FERTILIZER": 5, "EGG": 1, "WHEAT": 10},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0, "FERTILIZER": 1.0},
        day=6,
        hour=0,
        wheat_reserve=3,
        buys=buys,
        valve_tier=1,
    )
    assert len(orders) == 10
    assert orders[0][1] == "MELON"


def test_valve_tier_two_still_defers_to_liquidation_day_semantics() -> None:
    # day >= final_day is still the unconditional dump -- valve_tier is
    # irrelevant once liquidation itself is in effect (C in the design: day
    # 29 behavior is unchanged).
    orders = build_orders(
        shed={"MELON": 9}, prices={"MELON": 1.0}, day=29, hour=0, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 9]


def test_valve_tier_two_bypasses_the_batching_window_but_tier_one_does_not() -> None:
    # Batching is a price-timing optimization; it must never be allowed to
    # delay a destruction-prevention sale. Tier 2 (hard) sells in a blocked
    # hour (6, deep-morning); tier 1 (soft) -- an optimization trade, not an
    # emergency -- still respects the window, same as before.
    hour = 6
    assert hour in MELON_MILK_WOOL_BATCH_BLOCKED_HOURS

    tier_two = build_orders(
        shed={"MELON": 5, "MILK": 5, "WOOL": 5},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0},
        day=6,
        hour=hour,
        wheat_reserve=3,
        buys=[],
        valve_tier=2,
    )
    sold = {o[1] for o in tier_two if o[0] == "SELL"}
    assert {"MELON", "MILK", "WOOL"} <= sold

    tier_one = build_orders(
        shed={"MELON": 5, "MILK": 5, "WOOL": 5},
        prices={"MELON": 1.0, "MILK": 1.0, "WOOL": 1.0},
        day=6,
        hour=hour,
        wheat_reserve=3,
        buys=[],
        valve_tier=1,
    )
    assert not any(o[1] in ("MELON", "MILK", "WOOL") for o in tier_one)


# --- General guard: a shipped floor must sit meaningfully below equilibrium -
#
# kaggriculture#59 (M2c regression): WOOL_MIN_PRICE was raised to $200, which
# is exactly WOOL's engine `base` -- and `market_price(item, I0)` always
# equals `base` (I0 is the params' own equilibrium inventory point). A floor
# pinned at equilibrium clears for only the first couple of oversupply units
# before the quote dips a single dollar below it and the floor latches shut,
# so wool backlogs in the shared shed instead of selling steadily near $200.
#
# This isn't a wool-specific fact to pin -- it's a class of bug ("a floor at
# or above its own product's equilibrium quote") that can recur for MILK or
# FERTILIZER just as easily if either is ever retuned without checking this.
# The guard below re-derives "how many units does this floor actually permit"
# straight from the real engine for every floor the agent ships, so it fires
# on ANY of the three landing at/near equilibrium again -- not just wool's.

# Minimum cumulative units a shipped floor must permit before the engine's
# own quote drops below it. Calibrated against wool's own worst case: a
# 9-sheep ranch nets roughly 45 wool over a season, so a floor that only
# permits a double-digit fraction of that is already leaving real production
# unsellable at any price above the floor. 15 is chosen well under that full
# season number (so it doesn't demand near-full-season liquidity from a
# floor) but comfortably above both today's passing floors' margins of error
# and the ~3 units an equilibrium-pinned floor permits -- MILK_MIN_PRICE
# permits 20 units and FERT_MIN_PRICE permits in the hundreds, so 15 leaves
# real headroom without coming close to either boundary, while a floor even a
# few dollars off equilibrium (like the buggy $200 wool floor, which permits
# only 3) trips it immediately.
MIN_PERMITTED_UNITS = 15


def _permitted_units(item: str, floor: float) -> int:
    """How many units of cumulative oversupply (I0, I0+1, I0+2, ...) the real
    engine lets sell before `market_price(item, I0 + n)` drops below `floor`.
    """
    i0 = MARKET_PARAMS[item]["I0"]
    n = 0
    while market_price(item, i0 + n) >= floor:
        n += 1
    return n


def test_shipped_floors_permit_meaningful_volume_before_equilibrium() -> None:
    """Every static sell floor the agent ships (wool/milk/fert) must sit far
    enough below its product's own equilibrium quote (`market_price` at I0,
    which always equals the engine's `base`) to permit selling a meaningful
    volume -- not just the handful of units a floor pinned at or above
    equilibrium allows before it latches shut and the product backlogs the
    shared shed (see market.py's module docstring, M2c section, point 4).

    MELON is deliberately excluded: its floor is a dynamic, decaying value
    (``_melon_dynamic_floor``), not one of the static ``PolicyConfig``
    floors this guard covers.
    """
    floors = {"WOOL": WOOL_MIN_PRICE, "MILK": MILK_MIN_PRICE, "FERTILIZER": FERT_MIN_PRICE}
    for item, floor in floors.items():
        base = MARKET_PARAMS[item]["base"]
        permitted = _permitted_units(item, floor)
        assert permitted >= MIN_PERMITTED_UNITS, (
            f"{item}: base=${base} (equilibrium quote), floor=${floor} permits "
            f"only {permitted} cumulative units before market_price(item, I0 + n) "
            f"drops below the floor (need >= {MIN_PERMITTED_UNITS}) -- floor is "
            "too close to (or at/above) equilibrium and will latch shut almost "
            "immediately, backlogging the shared shed instead of selling"
        )


# --- Strawberry sell path + fertilizer reserve ----------------------------


def test_strawberry_sells_above_its_floor_and_holds_below() -> None:
    # Without a sell path at all, harvested strawberry just accumulates in a
    # 100-unit shed, trips the valve, and banks $0 -- growing the crop and
    # selling it are not separable features.
    sold = build_orders(
        shed={"STRAWBERRY": 5},
        prices={"STRAWBERRY": 120.0},
        day=12,
        hour=0,
        wheat_reserve=0,
        buys=[],
    )
    assert ["SELL", "STRAWBERRY", 2] in sold  # capped, not the whole shed

    held = build_orders(
        shed={"STRAWBERRY": 5},
        prices={"STRAWBERRY": 80.0},  # under the $90 floor
        day=12,
        hour=0,
        wheat_reserve=0,
        buys=[],
    )
    assert not any(o[1] == "STRAWBERRY" for o in held)


def test_strawberry_floor_permits_real_volume_before_it_latches() -> None:
    # A floor pinned at or above the product's equilibrium quote permits
    # almost nothing: market_price(item, I0) == base always, so every sale
    # walks the price below the floor immediately and the crop is never sold.
    # $90 sits at 75% of the $120 base, which the engine's own curve reaches
    # only after ~16 units of net oversupply.
    assert STRAWBERRY_MIN_PRICE < 120.0, "floor is at or above equilibrium: permits ~0 sales"
    assert STRAWBERRY_MIN_PRICE == 90.0


def test_strawberry_is_dumped_at_liquidation_regardless_of_floor() -> None:
    dumped = build_orders(
        shed={"STRAWBERRY": 9},
        prices={"STRAWBERRY": 20.0},  # far below the floor
        day=29,
        hour=0,
        wheat_reserve=0,
        buys=[],
    )
    assert ["SELL", "STRAWBERRY", 9] in dumped


def test_fertilizer_reserve_holds_back_input_units_from_the_sell_path() -> None:
    # Fertilizer is the one product that is also an INPUT: a reserved unit is
    # a doubled strawberry tick at age 9 or 13. Selling the shed to zero
    # between animal collections makes the FERTILIZE task a silent no-op --
    # the engine's handler bails when _inv_take fails and reports nothing.
    prices = {"FERTILIZER": 100.0}
    unreserved = build_orders(
        shed={"FERTILIZER": 6}, prices=prices, day=10, hour=0, wheat_reserve=0, buys=[]
    )
    assert ["SELL", "FERTILIZER", 4] in unreserved  # the usual 4/turn cap

    reserved = build_orders(
        shed={"FERTILIZER": 6},
        prices=prices,
        day=10,
        hour=0,
        wheat_reserve=0,
        buys=[],
        fert_reserve=4,
    )
    assert ["SELL", "FERTILIZER", 2] in reserved  # 6 held minus 4 reserved

    fully_reserved = build_orders(
        shed={"FERTILIZER": 3},
        prices=prices,
        day=10,
        hour=0,
        wheat_reserve=0,
        buys=[],
        fert_reserve=4,
    )
    assert not any(o[1] == "FERTILIZER" for o in fully_reserved)


def test_fertilizer_reserve_is_released_at_liquidation() -> None:
    # By the liquidation window there is no future tick left to fertilize
    # for, so a held-back unit is worth strictly more sold than kept.
    dumped = build_orders(
        shed={"FERTILIZER": 6},
        prices={"FERTILIZER": 100.0},
        day=29,
        hour=0,
        wheat_reserve=0,
        buys=[],
        fert_reserve=4,
    )
    assert ["SELL", "FERTILIZER", 6] in dumped


def test_default_fert_reserve_leaves_the_shipped_sell_path_untouched() -> None:
    # fert_reserve defaults to 0, so the pre-strawberry behavior is exact.
    prices = {"FERTILIZER": 100.0, "WHEAT": 25.0, "EGG": 50.0}
    shed = {"WHEAT": 10, "EGG": 2, "FERTILIZER": 3}
    assert build_orders(
        shed=shed, prices=prices, day=6, hour=0, wheat_reserve=3, buys=[]
    ) == build_orders(
        shed=shed, prices=prices, day=6, hour=0, wheat_reserve=3, buys=[], fert_reserve=0
    )


# --- hire_slot_floor: keep the first k HIRE orders out of the truncation ---
#
# MAX_ORDERS caps the WHOLE per-turn list at 10 and the engine silently drops
# the overflow (_process_market slices every queue to maxMarketOrdersPerTurn
# before it reads a single order). policy.decide packs HIRE orders at the very
# tail of ``buys`` on purpose -- "Buys first, hires last" -- so the truncation
# eats hires rather than a purchase. On the busiest turn of the game (a
# land-unlock day: seven sell lines, a BUY_LAND, and the animal buys) that
# costs the whole turn's hiring, and the agent runs ~10 hands on the SW-unlock
# day where the public leaders run 14.
#
# hire_slot_floor promotes up to k HIRE orders ahead of the OTHER buys --
# never ahead of a sell -- so the drop lands on a buy instead. 0 is
# DEFAULT-NEUTRAL and emits the pre-knob list exactly; see market.
# HIRE_SLOT_FLOOR for the full mechanism.


def test_hire_slot_floor_default_is_zero_so_shipped_behavior_is_unchanged() -> None:
    # Pinned against the module constant, the same pattern
    # test_rescue_water_default_is_off_so_shipped_behavior_is_unchanged uses
    # in test_dispatch.py, so an edit can never drift silently out of sync
    # with build_orders' own default.
    assert HIRE_SLOT_FLOOR == 0


# The busy-turn fixture the promotion tests share: seven sell lines (melon,
# strawberry, milk, wool, fertilizer, egg, wheat -- every sell this function
# can emit, verified against the live sell half by
# test_full_sell_priority_order_is_melon_milk_wool_fertilizer_egg_wheat and
# the strawberry tests above), leaving exactly three of the ten slots for
# buys. Prices sit above every floor and hour 0 is outside the batching
# window, so no sell line drops out and the truncation is the only thing
# deciding what survives.
_BUSY_SHED = {
    "MELON": 5,
    "STRAWBERRY": 5,
    "MILK": 5,
    "WOOL": 5,
    "FERTILIZER": 5,
    "EGG": 2,
    "WHEAT": 10,
}
_BUSY_PRICES = {
    "MELON": 250.0,
    "STRAWBERRY": 300.0,
    "MILK": 160.0,
    "WOOL": 200.0,
    "FERTILIZER": 100.0,
    "WHEAT": 25.0,
    "EGG": 50.0,
}
_BUSY_SELLS = [
    ["SELL", "MELON", 2],
    ["SELL", "STRAWBERRY", 2],
    ["SELL", "MILK", 4],
    ["SELL", "WOOL", 4],
    ["SELL", "FERTILIZER", 4],
    ["SELL", "EGG", 99999],
    ["SELL", "WHEAT", 10],
]
_LAND_UNLOCK_BUYS: list[list[object]] = [
    ["BUY_LAND", "SW"],
    ["BUY", "COW"],
    ["BUY", "SHEEP"],
    ["BUY_SEED", "WHEAT", 5],
]


def _busy_orders(buys: list[list[object]], **kwargs: object) -> list[list[object]]:
    return build_orders(
        shed=_BUSY_SHED,
        prices=_BUSY_PRICES,
        day=6,
        hour=0,
        wheat_reserve=0,
        buys=buys,
        **kwargs,  # type: ignore[arg-type]
    )


def test_hire_slot_floor_rescues_hires_the_ten_slot_cap_would_have_dropped() -> None:
    # The land-unlock turn: 7 sells + 4 buys + 2 hires = 13 orders for 10
    # slots. At the default the trailing hires are exactly what the engine
    # never sees -- three buys survive and the crew does not grow this turn.
    # At floor 2 the same two hires move ahead of the OTHER buys (still behind
    # every sell, and still behind the land purchase, which is exempt), so the
    # two animal buys that used to occupy slots 9-10 are the ones displaced.
    buys = [*_LAND_UNLOCK_BUYS, ["HIRE"], ["HIRE"]]

    shipped = _busy_orders(buys)
    assert shipped == [*_BUSY_SELLS, ["BUY_LAND", "SW"], ["BUY", "COW"], ["BUY", "SHEEP"]]
    assert shipped.count(["HIRE"]) == 0

    floored = _busy_orders(buys, hire_slot_floor=2)
    assert floored == [*_BUSY_SELLS, ["BUY_LAND", "SW"], ["HIRE"], ["HIRE"]]
    assert floored.count(["HIRE"]) == 2
    displaced = [order for order in shipped if order not in floored]
    assert displaced == [["BUY", "COW"], ["BUY", "SHEEP"]]


def test_hire_slot_floor_keeps_every_sell_ahead_of_a_promoted_hire() -> None:
    # The index-0 law is about SELLS: an order at an earlier slot fully
    # executes, moving the price, before either player's later order (see the
    # module docstring). A promoted hire that jumped a sell would hand that
    # slot -- and the price it moves -- to the opponent, so the promotion is
    # confined to the buy half of the list and must stay there at every legal
    # floor, including one large enough to ask for more hires than exist.
    buys = [*_LAND_UNLOCK_BUYS, ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"]]
    for floor in range(MAX_ORDERS + 1):
        orders = _busy_orders(buys, hire_slot_floor=floor)
        sells = [i for i, order in enumerate(orders) if order[0] == "SELL"]
        hires = [i for i, order in enumerate(orders) if order == ["HIRE"]]
        assert sells == list(range(len(_BUSY_SELLS))), (
            f"hire_slot_floor={floor} disturbed the sell half: {orders}"
        )
        assert not hires or min(hires) > max(sells), (
            f"hire_slot_floor={floor} promoted a hire ahead of a sell: {orders}"
        )


def test_hire_slot_floor_above_the_hires_requested_promotes_only_what_exists() -> None:
    # A floor larger than the turn's own hire_count is not an error and does
    # not reserve empty slots: it promotes the hires that exist and leaves
    # the rest of the buys in the caller's order behind them. 7 sells + 1
    # buy + 2 hires = 10 fits exactly, so nothing is dropped either -- only
    # reordered.
    buys: list[list[object]] = [["BUY_SEED", "WHEAT", 5], ["HIRE"], ["HIRE"]]
    orders = _busy_orders(buys, hire_slot_floor=10)
    assert orders == [*_BUSY_SELLS, ["HIRE"], ["HIRE"], ["BUY_SEED", "WHEAT", 5]]
    assert len(orders) == MAX_ORDERS


def test_hire_slot_floor_cannot_win_a_slot_the_sells_already_took() -> None:
    # The floor is a claim on the buy half of the list, not on the cap: the
    # seven sells leave three slots, the exempt land purchase takes the first,
    # so a floor of 10 against four requested hires lands two and the other
    # two are dropped exactly as before -- no IndexError, no list longer than
    # the cap, no sell evicted and no purchase starved to make room. The
    # shortfall self-heals next turn (plan_day recomputes hands_target -
    # hires_today fresh every turn); a dropped land purchase would not.
    buys = [*_LAND_UNLOCK_BUYS, ["HIRE"], ["HIRE"], ["HIRE"], ["HIRE"]]
    orders = _busy_orders(buys, hire_slot_floor=10)
    assert orders == [*_BUSY_SELLS, ["BUY_LAND", "SW"], ["HIRE"], ["HIRE"]]
    assert len(orders) == MAX_ORDERS
    assert orders.count(["HIRE"]) == 2


def test_hire_slot_floor_never_emits_more_orders_than_the_cap() -> None:
    # Every legal floor, against a request that overflows the cap from both
    # halves at once, must still emit a list the engine reads in full -- and
    # the same multiset of orders the caller handed over, never an invented
    # one (promotion reorders ``buys``, it does not duplicate an entry to
    # fill a floor).
    # _LAND_UNLOCK_BUYS leads with a BUY_LAND, which is exempt from
    # displacement and takes the first of the three surviving buy slots, so
    # the promotable ceiling is two rather than three.
    buys = [*_LAND_UNLOCK_BUYS, *([["HIRE"]] * 6)]
    promotable = MAX_ORDERS - len(_BUSY_SELLS) - 1
    for floor in range(MAX_ORDERS + 1):
        orders = _busy_orders(buys, hire_slot_floor=floor)
        assert len(orders) == MAX_ORDERS
        assert all(order in [*_BUSY_SELLS, *buys] for order in orders)
        assert orders.count(["HIRE"]) == min(floor, promotable)


def test_hire_slot_floor_does_not_mutate_the_callers_buy_list() -> None:
    # policy.decide hands over a list it built this turn and then reads the
    # emitted orders back for MelonMarketMemory attribution; a promotion that
    # reordered that list in place would be an invisible side effect on the
    # caller's own data.
    buys = [*_LAND_UNLOCK_BUYS, ["HIRE"], ["HIRE"]]
    snapshot = [list(order) for order in buys]
    _busy_orders(buys, hire_slot_floor=2)
    assert buys == snapshot


def test_hire_slot_floor_default_reproduces_the_shipped_order_list_across_a_matrix() -> None:
    """The no-op proof: at the default, every emitted list is still exactly
    the pre-knob composition -- this turn's sells, then ``buys`` in the
    caller's own order, truncated at MAX_ORDERS.

    Written as an identity against the function's own sell half rather than
    a golden table: the right-hand side passes ``buys=[]``, which leaves the
    promotion path nothing to reorder, so it re-derives what
    ``orders.extend(buys); return orders[:MAX_ORDERS]`` did before this knob
    existed without re-deriving (or freezing) a single sell rule. Any
    promotion that fires at the default -- or any lost truncation -- breaks
    the identity on the truncating cases below.

    The matrix sweeps the inputs that decide which sells exist and whether
    the cap bites at all: shed contents, prices above and below every floor,
    normal/ramp/liquidation days, in- and out-of-batching-window hours, the
    wheat feed reserve, all three valve tiers, buy-list length, and hire
    count. Both regimes are asserted covered at the end, so a fixture drift
    that quietly stopped truncating anything can never leave this test
    passing vacuously.
    """
    sheds: list[dict[str, int]] = [
        {},
        {"WHEAT": 10, "EGG": 2, "FERTILIZER": 3},
        dict(_BUSY_SHED),
        {"MELON": 40, "MILK": 40, "WOOL": 40, "FERTILIZER": 40, "WHEAT": 40, "EGG": 40},
    ]
    price_sets: list[dict[str, float]] = [
        dict(_BUSY_PRICES),
        # Under every floor: the sell half shrinks to the floorless lines
        # (egg, wheat) except where liquidation or a valve tier waives them.
        {
            "MELON": 10.0,
            "STRAWBERRY": 10.0,
            "MILK": 10.0,
            "WOOL": 10.0,
            "FERTILIZER": 1.0,
            "WHEAT": 1.0,
            "EGG": 1.0,
        },
    ]
    # (day, hour): a normal day inside and outside the batching window, a
    # mid-game hour, both melon ramp days, and the liquidation day itself.
    day_hours = [(6, 0), (6, 6), (12, 12), (27, 0), (28, 0), (29, 0)]
    buy_lines: list[list[list[object]]] = [
        [],
        [["BUY_SEED", "WHEAT", 5]],
        list(_LAND_UNLOCK_BUYS),
    ]
    truncating = 0
    fitting = 0
    for shed, prices, (day, hour), valve_tier, reserve, base_buys, hire_count in product(
        sheds, price_sets, day_hours, (0, 1, 2), (0, 3), buy_lines, (0, 1, 2, 4, 10)
    ):
        buys: list[list[object]] = [*base_buys, *([["HIRE"]] * hire_count)]
        case = dict(
            shed=shed,
            prices=prices,
            day=day,
            hour=hour,
            wheat_reserve=reserve,
            valve_tier=valve_tier,
        )
        sells = build_orders(buys=[], **case)  # type: ignore[arg-type]
        emitted = build_orders(buys=buys, **case)  # type: ignore[arg-type]
        assert emitted == [*sells, *buys][:MAX_ORDERS], (
            f"default hire_slot_floor changed the order list for {case} with buys={buys}"
        )
        if len(sells) + len(buys) > MAX_ORDERS:
            truncating += 1
        else:
            fitting += 1

    assert truncating > 0, "matrix never exercised the truncating regime"
    assert fitting > 0, "matrix never exercised the non-truncating regime"


# --- hire_slot_floor: a land purchase is never what gets displaced -----------
#
# The engine spends orders in LIST POSITION and both _do_hire and _do_buy_land
# silently return when farm["money"] < cost -- no error, no retry, the order is
# simply consumed and nothing happens. Hire cost is Fibonacci in the count
# already hired that day, so four promoted hires on the SW-unlock day draw
# roughly 89 + 144 + 233 + 377 = $843 before the BUY_LAND behind them. plan_day
# only guarantees budget >= LAND_PRICES["SW"] (2000) + LAND_RESERVE (500) =
# $2,500 when it decides to buy, and we hold about $2,520 on that day, so the
# land purchase is left facing ~$1,657 against a $2,000 price and fails in
# silence.
#
# A lost hire is cheap and self-heals next turn. A lost SW purchase is the
# strategic event of the mid-game -- it roughly doubles the board -- so land
# keeps ABSOLUTE priority over a promoted hire. Every other buy (animals,
# seeds, feed) stays displaceable: that is the trade the knob exists to make.
#
# Emitted order above the default:
#   [sells] [BUY_LAND] [up to k promoted HIREs] [other buys] [remaining HIREs]
# The last two segments are the caller's own order, and policy.decide always
# appends HIRE at the tail of ``buys`` (policy.decide: buys = list(plan.buys)
# then buys.extend([["HIRE"]] * plan.hire_count)), so in production the "other
# buys then remaining hires" split is exactly what comes out.


# plan_day emits the land order as a bare ``["BUY_LAND"]`` with no argument
# (plan.py, all three of the NE/SW/SE sites), and at most one per turn --
# _next_quadrant is pure over two parameters plan_day never reassigns, so the
# three quadrant gates are mutually exclusive. _LAND_UNLOCK_BUYS above carries
# the argument-bearing ``["BUY_LAND", "SW"]`` instead; both shapes are
# protected, and test_hire_slot_floor_protects_a_land_order_whatever_shape_it
# _carries pins that the guard is on the verb, not on an exact literal.
_LAND_TURN_BUYS: list[list[object]] = [
    ["BUY_LAND"],
    ["BUY_ANIMAL", "COW", 1],
    ["BUY_SEED", "WHEAT", 5],
]


def _quiet_orders(buys: list[list[object]], **kwargs: object) -> list[list[object]]:
    """build_orders on an empty shed: no sell line qualifies, so the emitted
    list IS the permuted buy half and the segment order is readable directly."""
    return build_orders(
        shed={},
        prices={},
        day=6,
        hour=0,
        wheat_reserve=0,
        buys=buys,
        **kwargs,  # type: ignore[arg-type]
    )


def test_hire_slot_floor_never_displaces_a_land_purchase() -> None:
    # The live case: the busy-turn sells leave three buy slots, and a floor of
    # 4 asks for more hires than that. Before land priority, all three
    # surviving slots went to hires and the BUY_LAND was truncated away
    # entirely -- the $2,000 purchase lost to $843 of wages plus a silent drop.
    buys: list[list[object]] = [*_LAND_TURN_BUYS, *([["HIRE"]] * 4)]

    orders = _busy_orders(buys, hire_slot_floor=4)

    assert ["BUY_LAND"] in orders, f"the land purchase was truncated away: {orders}"
    hires = [i for i, order in enumerate(orders) if order == ["HIRE"]]
    assert hires, "fixture promoted no hires -- the test would pass vacuously"
    assert orders.index(["BUY_LAND"]) < min(hires), (
        f"a promoted hire drew its wage ahead of the land purchase: {orders}"
    )


def test_hire_slot_floor_still_displaces_an_animal_buy() -> None:
    # The knob has to keep doing its job: exempting land must not turn into
    # exempting every buy. With no land order in the turn, three hires at
    # floor 3 take all three surviving slots and the animal/seed buys are the
    # ones the cap eats -- unchanged from the shipped promotion behavior.
    buys: list[list[object]] = [
        ["BUY_ANIMAL", "COW", 1],
        ["BUY_SEED", "WHEAT", 5],
        ["BUY_SEED", "MELON", 3],
        *([["HIRE"]] * 3),
    ]

    orders = _busy_orders(buys, hire_slot_floor=3)

    assert orders == [*_BUSY_SELLS, ["HIRE"], ["HIRE"], ["HIRE"]]
    assert ["BUY_ANIMAL", "COW", 1] not in orders


def test_hire_slot_floor_emits_land_then_promoted_hires_then_the_other_buys() -> None:
    # The whole segment order on one turn, read off an empty shed so nothing
    # truncates and every segment is visible: land, then the k promoted hires,
    # then the other buys in the caller's order, then the hires that did not
    # make the floor.
    buys: list[list[object]] = [*_LAND_TURN_BUYS, *([["HIRE"]] * 3)]

    orders = _quiet_orders(buys, hire_slot_floor=2)

    assert orders == [
        ["BUY_LAND"],
        ["HIRE"],
        ["HIRE"],
        ["BUY_ANIMAL", "COW", 1],
        ["BUY_SEED", "WHEAT", 5],
        ["HIRE"],
    ]


def test_hire_slot_floor_keeps_multiple_land_orders_in_their_original_order() -> None:
    # plan_day cannot emit two land orders in one turn (the NE/SW/SE gates are
    # mutually exclusive -- see the section comment), so this pins totality
    # rather than a live case: if that ever changes, the hoist must stay a
    # stable partition and not reverse or interleave the purchases.
    buys: list[list[object]] = [
        ["BUY_LAND", "NE"],
        ["BUY_SEED", "WHEAT", 5],
        ["BUY_LAND", "SW"],
        ["HIRE"],
        ["HIRE"],
    ]

    orders = _quiet_orders(buys, hire_slot_floor=2)

    assert orders == [
        ["BUY_LAND", "NE"],
        ["BUY_LAND", "SW"],
        ["HIRE"],
        ["HIRE"],
        ["BUY_SEED", "WHEAT", 5],
    ]


def test_hire_slot_floor_protects_a_land_order_whatever_shape_it_carries() -> None:
    # The guard reads the verb at index 0, not an exact literal: production
    # emits the bare ``["BUY_LAND"]`` today, and an argument added later (a
    # quadrant, a tile) must not silently drop the order back into the
    # displaceable pile. Both shapes lead their turn's promoted hires.
    for land in (["BUY_LAND"], ["BUY_LAND", "SW"]):
        buys: list[list[object]] = [land, ["BUY_SEED", "WHEAT", 5], ["HIRE"], ["HIRE"]]
        orders = _quiet_orders(buys, hire_slot_floor=2)
        assert orders == [land, ["HIRE"], ["HIRE"], ["BUY_SEED", "WHEAT", 5]], (
            f"land shape {land} was not protected: {orders}"
        )


def test_land_priority_is_still_a_permutation_of_the_callers_buys() -> None:
    # Nothing invented, nothing lost: the hoist partitions ``buys`` into land /
    # promoted / rest and concatenates, so every legal floor over every buy
    # shape must emit the same multiset the caller handed over. Compared on
    # repr because these are heterogeneous lists (``["HIRE"]`` against
    # ``["BUY_SEED", "WHEAT", 5]``) and sorted() needs a total order. Every
    # case stays at or under MAX_ORDERS so truncation cannot mask a loss.
    buy_shapes: list[list[list[object]]] = [
        [],
        [["BUY_LAND"]],
        [["HIRE"]],
        list(_LAND_TURN_BUYS),
        [["BUY_LAND"], ["BUY_LAND", "SW"], ["BUY_SEED", "WHEAT", 5]],
        [["BUY_SEED", "WHEAT", 5], ["HIRE"], ["BUY_LAND"], ["HIRE"], ["BUY_ANIMAL", "COW", 1]],
    ]
    for base, hire_count, floor in product(buy_shapes, (0, 1, 3), range(MAX_ORDERS + 1)):
        buys: list[list[object]] = [*base, *([["HIRE"]] * hire_count)]
        assert len(buys) <= MAX_ORDERS  # otherwise truncation, not the hoist, decides
        orders = _quiet_orders(buys, hire_slot_floor=floor)
        assert sorted(map(repr, orders)) == sorted(map(repr, buys)), (
            f"hire_slot_floor={floor} was not a permutation of {buys}: {orders}"
        )


def test_land_priority_does_not_fire_at_the_default_floor() -> None:
    # The exemption lives behind the same ``<= 0`` early-out as the promotion:
    # at the default the caller's list is emitted untouched, land included,
    # even when a hoist would have reordered it.
    buys: list[list[object]] = [["BUY_ANIMAL", "COW", 1], ["BUY_LAND"], ["HIRE"]]

    assert _quiet_orders(buys) == buys
    assert _quiet_orders(buys, hire_slot_floor=0) == buys
