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

from agent.market import (
    FERT_MIN_PRICE,
    MELON_MILK_WOOL_BATCH_BLOCKED_HOURS,
    MELON_MILK_WOOL_BATCH_EXEMPT_DAY,
    MELON_MIN_PRICE,
    MILK_MIN_PRICE,
    STRAWBERRY_MIN_PRICE,
    WOOL_MIN_PRICE,
    build_orders,
)
from kaggle_environments.envs.kaggriculture.kaggriculture import MARKET_PARAMS, market_price


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
