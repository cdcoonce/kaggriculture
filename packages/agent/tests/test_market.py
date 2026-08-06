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
    assert orders[0] == ["SELL", "FERTILIZER", 99999]
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders
    assert len(orders) <= 10


def test_fertilizer_held_when_price_crashed_but_dumped_at_liquidation() -> None:
    crashed = {"FERTILIZER": 40.0, "WHEAT": 25.0, "EGG": 50.0}
    held = build_orders(shed={"FERTILIZER": 5}, prices=crashed, day=10, wheat_reserve=3, buys=[])
    assert not any(o[1] == "FERTILIZER" for o in held)

    dumped = build_orders(shed={"FERTILIZER": 5}, prices=crashed, day=29, wheat_reserve=3, buys=[])
    assert dumped[0] == ["SELL", "FERTILIZER", 99999]


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
    assert orders[0] == ["SELL", "FERTILIZER", 99999]
    assert ["SELL", "EGG", 99999] in orders
    assert ["SELL", "WHEAT", 7] in orders
