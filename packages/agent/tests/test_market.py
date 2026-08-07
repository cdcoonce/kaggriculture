"""Market-order builder behavior: the index-0 law, sell-often staples, reserves.

Index-0 law (strategy doc, verified edge): market orders resolve by queue-slot
index across both players; an order at slot 0 fully executes (moving price)
before either player's slot-1 order. Crashable goods therefore always sell at
index 0. Wheat/egg are glut-proof (log above-curve) and sell every turn.
"""

from __future__ import annotations

from agent.market import build_orders


def test_crashable_fertilizer_sell_is_index_zero() -> None:
    orders = build_orders(
        shed={"WHEAT": 10, "EGG": 2, "FERTILIZER": 3},
        prices={"FERTILIZER": 100.0, "WHEAT": 25.0, "EGG": 50.0},
        day=6,
        wheat_reserve=3,
        buys=[],
    )
    assert orders[0] == ["SELL", "FERTILIZER", 3]  # below the 4/turn cap: exact shed count
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders
    assert len(orders) <= 10


def test_fertilizer_held_when_price_crashed_but_dumped_at_liquidation() -> None:
    crashed = {"FERTILIZER": 40.0, "WHEAT": 25.0, "EGG": 50.0}
    held = build_orders(shed={"FERTILIZER": 5}, prices=crashed, day=10, wheat_reserve=3, buys=[])
    assert not any(o[1] == "FERTILIZER" for o in held)

    dumped = build_orders(shed={"FERTILIZER": 5}, prices=crashed, day=29, wheat_reserve=3, buys=[])
    assert dumped[0] == ["SELL", "FERTILIZER", 5]  # liquidation ignores both floor and per-turn cap


def test_fertilizer_sell_capped_at_four_even_with_more_in_shed() -> None:
    # 15 animals collect ~15 fertilizer/day; an uncapped dump would walk the
    # linear-above-curve price straight down. Cap holds even with 40 on hand.
    orders = build_orders(
        shed={"FERTILIZER": 40}, prices={"FERTILIZER": 100.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "FERTILIZER", 4]

    dumped = build_orders(
        shed={"FERTILIZER": 40}, prices={"FERTILIZER": 100.0}, day=29, wheat_reserve=3, buys=[]
    )
    assert dumped[0] == ["SELL", "FERTILIZER", 40]  # liquidation ignores the cap


def test_wheat_feed_reserve_withheld_until_liquidation() -> None:
    prices = {"WHEAT": 25.0}
    held = build_orders(shed={"WHEAT": 2}, prices=prices, day=10, wheat_reserve=3, buys=[])
    assert held == []

    dumped = build_orders(shed={"WHEAT": 2}, prices=prices, day=29, wheat_reserve=3, buys=[])
    assert ["SELL", "WHEAT", 2] in dumped


def test_sells_survive_the_ten_order_cap() -> None:
    buys: list[list[object]] = [["BUY_SEED", "WHEAT", 1] for _ in range(9)]
    orders = build_orders(
        shed={"WHEAT": 10, "EGG": 1, "FERTILIZER": 1},
        prices={"FERTILIZER": 100.0, "WHEAT": 25.0, "EGG": 50.0},
        day=6,
        wheat_reserve=3,
        buys=buys,
    )
    assert len(orders) == 10
    assert orders[0] == ["SELL", "FERTILIZER", 1]
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders


def test_melon_sell_respects_price_floor() -> None:
    below_floor = build_orders(
        shed={"MELON": 5}, prices={"MELON": 180.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in below_floor)

    above_floor = build_orders(
        shed={"MELON": 5}, prices={"MELON": 200.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "MELON", 2]


def test_melon_sell_capped_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(
        shed={"MELON": 9}, prices={"MELON": 250.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 2]


def test_melon_sell_below_cap_sells_the_exact_shed_count() -> None:
    orders = build_orders(
        shed={"MELON": 1}, prices={"MELON": 250.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert orders[0] == ["SELL", "MELON", 1]


def test_melon_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"MELON": 50.0}
    held = build_orders(shed={"MELON": 9}, prices=crashed, day=10, wheat_reserve=3, buys=[])
    assert not any(o[1] == "MELON" for o in held)

    dumped = build_orders(shed={"MELON": 9}, prices=crashed, day=29, wheat_reserve=3, buys=[])
    assert dumped[0] == ["SELL", "MELON", 9]  # liquidation ignores both floor and per-turn cap


def test_melon_sell_leads_even_fertilizer_at_index_zero() -> None:
    # No MILK/WOOL in the shed this turn, so they don't insert between melon
    # and fertilizer -- confirms melon leads regardless of what else is idle.
    orders = build_orders(
        shed={"MELON": 2, "FERTILIZER": 3},
        prices={"MELON": 250.0, "FERTILIZER": 100.0},
        day=6,
        wheat_reserve=3,
        buys=[],
    )
    assert orders[0] == ["SELL", "MELON", 2]
    assert orders[1] == ["SELL", "FERTILIZER", 3]


def test_no_melon_sell_when_shed_is_empty() -> None:
    orders = build_orders(
        shed={"FERTILIZER": 3}, prices={"MELON": 250.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MELON" for o in orders)


# --- Milk + wool (M2a) ------------------------------------------------------
#
# Same shape as melon's floor+cap: MILK is linear above-curve (base $160,
# -25% at ~+19 net oversupply), WOOL is quadratic (base $200, -25% at ~+29) --
# both currently under-supplied by the field, but crash-prone enough to earn
# their own per-turn cap the moment husbandry starts producing at scale.


def test_milk_sell_respects_price_floor() -> None:
    below_floor = build_orders(
        shed={"MILK": 4}, prices={"MILK": 110.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "MILK" for o in below_floor)

    above_floor = build_orders(
        shed={"MILK": 4}, prices={"MILK": 130.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "MILK", 2]


def test_milk_sell_capped_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(shed={"MILK": 6}, prices={"MILK": 160.0}, day=6, wheat_reserve=3, buys=[])
    assert orders[0] == ["SELL", "MILK", 2]


def test_milk_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"MILK": 50.0}
    held = build_orders(shed={"MILK": 6}, prices=crashed, day=10, wheat_reserve=3, buys=[])
    assert not any(o[1] == "MILK" for o in held)

    dumped = build_orders(shed={"MILK": 6}, prices=crashed, day=29, wheat_reserve=3, buys=[])
    assert dumped[0] == ["SELL", "MILK", 6]


def test_wool_sell_respects_price_floor() -> None:
    below_floor = build_orders(
        shed={"WOOL": 4}, prices={"WOOL": 140.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert not any(o[1] == "WOOL" for o in below_floor)

    above_floor = build_orders(
        shed={"WOOL": 4}, prices={"WOOL": 200.0}, day=6, wheat_reserve=3, buys=[]
    )
    assert above_floor[0] == ["SELL", "WOOL", 2]


def test_wool_sell_capped_per_turn_even_with_more_in_shed() -> None:
    orders = build_orders(shed={"WOOL": 6}, prices={"WOOL": 200.0}, day=6, wheat_reserve=3, buys=[])
    assert orders[0] == ["SELL", "WOOL", 2]


def test_wool_held_below_floor_but_dumped_fully_at_liquidation() -> None:
    crashed = {"WOOL": 60.0}
    held = build_orders(shed={"WOOL": 6}, prices=crashed, day=10, wheat_reserve=3, buys=[])
    assert not any(o[1] == "WOOL" for o in held)

    dumped = build_orders(shed={"WOOL": 6}, prices=crashed, day=29, wheat_reserve=3, buys=[])
    assert dumped[0] == ["SELL", "WOOL", 6]


def test_full_sell_priority_order_is_melon_milk_wool_fertilizer_egg_wheat() -> None:
    orders = build_orders(
        shed={"MELON": 2, "MILK": 2, "WOOL": 2, "FERTILIZER": 2, "EGG": 2, "WHEAT": 10},
        prices={"MELON": 250.0, "MILK": 160.0, "WOOL": 200.0, "FERTILIZER": 100.0, "EGG": 50.0},
        day=6,
        wheat_reserve=3,
        buys=[],
    )
    items_in_order = [o[1] for o in orders]
    assert items_in_order == ["MELON", "MILK", "WOOL", "FERTILIZER", "EGG", "WHEAT"]
