"""Policy wiring behavior: opening orders, watchdog fallback, process reuse."""

from __future__ import annotations

from typing import Any

from agent.policy import make_policy
from agent.shell import pass_action


def raw_obs(*, step: int = 0, money: float = 3000.0) -> dict[str, Any]:
    """A minimal engine-shaped observation for player 0 on a fresh farm."""
    tiles = [[None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)]
    farm = {
        "money": money,
        "tiles": tiles,
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }
    other = {
        "money": money,
        "tiles": [row[:] for row in tiles],
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": ["NW"],
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
    action = make_policy()(raw_obs(), None)
    market = action["market"]
    assert ["BUY_ANIMAL", "GOOSE", 1] in market
    assert ["BUY_SEED", "WHEAT", 24] in market
    assert market.count(["HIRE"]) == 3
    assert len(market) <= 10


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
