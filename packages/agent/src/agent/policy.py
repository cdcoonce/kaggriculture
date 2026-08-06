"""Chassis v1 — wheat rush + goose + index-0 price-aware selling.

Composition per turn: parse the obs into a typed view, run the (idempotent)
daily planner, dispatch units, build market orders with sells ahead of buys
and crashables at index 0. A soft watchdog bails to PASS if a turn ever runs
long — the 60 s overage bank is for thinking, never for accidents.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from agent.dispatch import dispatch
from agent.market import build_orders
from agent.plan import FEED_RESERVE, plan_day
from agent.shell import Action, Observation, pass_action
from agent.state import StateTracker
from agent.view import FarmView, parse_obs

SOFT_BUDGET_SECONDS = 0.5  # v1 logic runs in microseconds; this guards regressions


def _goose_owned(view: FarmView) -> bool:
    if view.shed.get("GOOSE", 0) > 0:
        return True
    if any(inv.get("GOOSE", 0) > 0 for inv in view.inventories):
        return True
    return any(isinstance(tile, dict) and "animal" in tile for row in view.tiles for tile in row)


def _wheat_on_hand(view: FarmView) -> int:
    return view.shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in view.inventories)


def _plantable_targets(view: FarmView) -> int:
    from agent.constants import TARGET_TILES

    count = 0
    for x, y in TARGET_TILES:
        tile = view.tiles[y][x]
        if tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED"):
            count += 1
    return count


def make_policy(clock: Callable[[], float] = time.monotonic) -> Any:
    """Build the policy callable with its episode-scoped tracker closed over."""
    tracker = StateTracker()

    def decide(obs: Observation, config: dict[str, Any] | None = None) -> Action:
        start = clock()
        tracker.observe(obs)
        view = parse_obs(obs)

        if clock() - start > SOFT_BUDGET_SECONDS:
            return pass_action()

        goose = _goose_owned(view)
        plan = plan_day(
            day=view.day,
            money=view.money,
            wheat_seeds=view.seeds.get("WHEAT", 0),
            plantable_target_tiles=_plantable_targets(view),
            wheat_on_hand=_wheat_on_hand(view),
            goose_owned=goose,
            hires_today=view.hires_today,
        )
        actions = dispatch(view)

        buys: list[list[object]] = [["HIRE"] for _ in range(plan.hire_count)]
        buys.extend(plan.buys)
        orders = build_orders(
            shed=view.shed,
            prices=view.prices,
            day=view.day,
            wheat_reserve=FEED_RESERVE if goose else 0,
            buys=buys,
        )
        return {"farmer": actions.farmer, "hands": actions.hands, "market": orders}

    return decide
