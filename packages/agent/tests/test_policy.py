"""Policy wiring behavior: opening orders, watchdog fallback, process reuse,
and the market-list ordering law (sells, then buys, then hires)."""

from __future__ import annotations

from typing import Any

from agent.policy import make_policy
from agent.shell import pass_action


def _quadrant_of(x: int, y: int) -> str:
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _board(unlocked: tuple[str, ...]) -> list[list[Any]]:
    unlocked_set = set(unlocked)
    return [
        [None if _quadrant_of(x, y) in unlocked_set else "LOCKED" for x in range(10)]
        for y in range(10)
    ]


def raw_obs(
    *, step: int = 0, money: float = 3000.0, unlocked_quadrants: tuple[str, ...] = ("NW",)
) -> dict[str, Any]:
    """A minimal engine-shaped observation for player 0 on a fresh farm."""
    tiles = _board(unlocked_quadrants)
    farm = {
        "money": money,
        "tiles": tiles,
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": list(unlocked_quadrants),
        "hires_today": 0,
    }
    other = {
        "money": money,
        "tiles": [row[:] for row in tiles],
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": list(unlocked_quadrants),
        "hires_today": 0,
    }
    return {
        "step": step,
        "player": 0,
        "farms": [farm, other],
        "private": {"seeds": {"WHEAT": 0}, "shed": {}, "inventories": [{}]},
        "market": {
            "prices": {"WHEAT": 25.0, "EGG": 50.0, "FERTILIZER": 100.0},
            "inventory": {"WHEAT": 10000, "EGG": 10000, "FERTILIZER": 10000},
        },
        "town": {"unlocked_shops": []},
        "day": step // 24,
        "hour": step % 24,
        "remainingOverageTime": 60,
    }


def test_day_zero_opening_orders() -> None:
    # NW-only is 24 target tiles; MELON_TILE_TARGET (8) of those are now the
    # melon zone, so wheat's own plantable count -- and its day-0 seed buy,
    # unthrottled by the quota on the opening day -- is 24 - 8 = 16.
    action = make_policy()(raw_obs(), None)
    market = action["market"]
    assert ["BUY_ANIMAL", "GOOSE", 1] in market
    assert ["BUY_SEED", "MELON", 4] in market
    assert ["BUY_SEED", "WHEAT", 16] in market
    assert market.count(["HIRE"]) == 3
    assert len(market) <= 10


def test_day_zero_flow_emits_exactly_one_buy_land() -> None:
    action = make_policy()(raw_obs(money=3000.0), None)
    assert action["market"].count(["BUY_LAND"]) == 1


def test_watchdog_returns_pass_when_budget_exhausted() -> None:
    ticks = iter([0.0, 100.0])
    policy = make_policy(clock=lambda: next(ticks))
    assert policy(raw_obs(), None) == pass_action()


def test_step_zero_resets_for_process_reuse() -> None:
    policy = make_policy()
    policy(raw_obs(step=500), None)  # a prior episode's late turn
    fresh = policy(raw_obs(step=0), None)  # runner reused the process
    assert ["BUY_ANIMAL", "GOOSE", 1] in fresh["market"]
    assert fresh["market"].count(["HIRE"]) == 3


def test_market_orders_sells_then_buys_then_hires_teeth_check() -> None:
    """Hires sit last in the market list, so the 10-slot cap always drops
    trailing hires (which self-heal next turn) rather than a sell or buy.
    This scenario overflows the cap by two slots (melon's own seed line adds
    a fifth buy ahead of wheat's): if hires were ever placed ahead of buys,
    the feed buy would be one of the ones truncated away instead — this
    exact-list assertion catches that directly, with no monkeypatching of
    plan_day or dispatch.

    NW + NE is 49 target tiles; 8 of those are the melon zone, so wheat's
    plantable count is 41 -- still above the quota-doubled cap of 20 at day
    3 (plant_quota(3, 49) = 10), so the wheat seed buy is quota-bound either
    way. Melon's own target is min(2 * MELON_PLANT_DAILY_CAP, empty melon
    tiles) = min(4, 8) = 4.
    """
    obs = raw_obs(step=3 * 24, money=6000.0, unlocked_quadrants=("NW", "NE"))
    obs["private"]["shed"] = {"FERTILIZER": 3, "EGG": 2, "WHEAT": 2}
    action = make_policy()(obs, None)
    market = action["market"]

    assert market == [
        ["SELL", "FERTILIZER", 99999],
        ["SELL", "EGG", 99999],
        ["SELL", "WHEAT", 2],
        ["BUY_ANIMAL", "GOOSE", 1],
        ["BUY_LAND"],
        ["BUY_SEED", "MELON", 4],
        ["BUY_SEED", "WHEAT", 20],
        ["BUY_PRODUCT", "WHEAT", 1],
        ["HIRE"],
        ["HIRE"],
    ]
