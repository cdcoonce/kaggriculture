"""Chassis v1 — wheat rush + goose + melon satellite + animal husbandry +
index-0 price-aware selling.

Composition per turn: parse the obs into a typed view, run the (idempotent)
daily planner, dispatch units, build market orders with sells ahead of buys
and crashables at index 0. A soft watchdog bails to PASS if a turn ever runs
long — the 60 s overage bank is for thinking, never for accidents.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from agent.constants import PASTURE_REFERENCE_QUADRANTS, melon_tiles, pasture_tiles, target_tiles
from agent.dispatch import dispatch
from agent.market import build_orders
from agent.plan import FEED_RESERVE, plan_day
from agent.shell import Action, Observation, pass_action
from agent.state import MelonMarketMemory, StateTracker
from agent.view import FarmView, parse_obs

SOFT_BUDGET_SECONDS = 0.5  # v1 logic runs in microseconds; this guards regressions


def _owned_count(view: FarmView, species: str) -> int:
    """Total of one animal species currently owned: placed on a tile, sitting
    in the shed (bought but not yet walked to a pasture/coop), or mid-carry
    in a unit's inventory. Used for purchase-target gating (goose/cow/sheep
    alike), so a bought-but-unplaced animal still counts toward "already
    have enough" and doesn't get rebought."""
    placed = sum(
        1
        for row in view.tiles
        for tile in row
        if isinstance(tile, dict) and tile.get("animal") == species
    )
    shed = view.shed.get(species, 0)
    carried = sum(inv.get(species, 0) for inv in view.inventories)
    return placed + shed + carried


def _animals_placed(view: FarmView) -> int:
    """Count of tiles with any placed animal (goose + cow + sheep) — the
    figure that actually drives daily chore load (FEED/CARE/COLLECT_
    FERTILIZER/HARVEST only apply once an animal is on a tile), used to
    size the feed reserve/top-up and the husbandry hands bonus."""
    return sum(
        1 for row in view.tiles for tile in row if isinstance(tile, dict) and "animal" in tile
    )


def _empty_built_pastures(view: FarmView, pastures: list[tuple[int, int]]) -> int:
    count = 0
    for x, y in pastures:
        tile = view.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile:
            count += 1
    return count


def _wheat_on_hand(view: FarmView) -> int:
    return view.shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in view.inventories)


def _plantable_targets(view: FarmView, tiles: list[tuple[int, int]]) -> int:
    count = 0
    for x, y in tiles:
        tile = view.tiles[y][x]
        if tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED"):
            count += 1
    return count


def _melon_sell_qty(orders: list[list[object]]) -> int:
    """The quantity from this turn's own ``["SELL", "MELON", n]`` order, if
    any -- fed back to ``MelonMarketMemory`` so next turn's opponent-sell
    attribution can net our own sale out of the shared inventory delta."""
    for order in orders:
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "MELON":
            qty = order[2]
            return qty if isinstance(qty, int) else 0
    return 0


def make_policy(clock: Callable[[], float] = time.monotonic) -> Any:
    """Build the policy callable with its episode-scoped trackers closed over."""
    tracker = StateTracker()
    melon_memory = MelonMarketMemory()

    def decide(obs: Observation, config: dict[str, Any] | None = None) -> Action:
        start = clock()
        tracker.observe(obs)
        # Runs here, ahead of the soft-budget check below, so melon-market
        # continuity survives even a turn that later bails to pass_action()
        # (mirrors StateTracker's own placement) -- a bailed turn issues no
        # real market orders, so record_our_melon_sell is correctly never
        # called for it, leaving next turn's "our_sold_last_turn" at 0.
        melon_memory.observe(obs)
        view = parse_obs(obs)

        if clock() - start > SOFT_BUDGET_SECONDS:
            return pass_action()

        tiles = target_tiles(view.unlocked_quadrants)
        melons = melon_tiles(view.unlocked_quadrants)
        # Fixed reference frame, NOT view.unlocked_quadrants -- pastures must
        # never migrate as SW/SE unlock later (constants.PASTURE_REFERENCE_
        # QUADRANTS explains why: a live value orphans built pastures and
        # placed animals the instant the nearest-shed-first ordering shifts).
        pastures = pasture_tiles(PASTURE_REFERENCE_QUADRANTS)
        melon_set = frozenset(melons)
        pasture_set = frozenset(pastures)
        # Set difference, not a positional slice: pasture_set's positions are
        # anchored to the fixed reference frame above and are not guaranteed
        # to occupy any particular prefix of the *live* tiles ordering.
        wheat_tiles = [t for t in tiles if t not in melon_set and t not in pasture_set]
        goose = _owned_count(view, "GOOSE") > 0
        cows_owned = _owned_count(view, "COW")
        sheep_owned = _owned_count(view, "SHEEP")
        animals_placed = _animals_placed(view)
        plan = plan_day(
            day=view.day,
            money=view.money,
            wheat_seeds=view.seeds.get("WHEAT", 0),
            plantable_target_tiles=_plantable_targets(view, wheat_tiles),
            melon_seeds=view.seeds.get("MELON", 0),
            empty_melon_tiles=_plantable_targets(view, melons),
            wheat_on_hand=_wheat_on_hand(view),
            goose_owned=goose,
            hires_today=view.hires_today,
            unlocked_quadrants=view.unlocked_quadrants,
            active_tiles=len(tiles),
            cows_owned=cows_owned,
            sheep_owned=sheep_owned,
            empty_pastures=_empty_built_pastures(view, pastures),
            animals_placed=animals_placed,
        )
        actions = dispatch(view, tiles, melon_set, pasture_set)

        # Buys first, hires last: if the 10-slot cap ever truncates, it drops
        # trailing hires (which self-heal next turn) rather than a purchase.
        buys: list[list[object]] = list(plan.buys)
        buys.extend([["HIRE"]] * plan.hire_count)
        any_animal_owned = goose or cows_owned > 0 or sheep_owned > 0
        wheat_reserve = animals_placed + FEED_RESERVE if any_animal_owned else 0
        orders = build_orders(
            shed=view.shed,
            prices=view.prices,
            day=view.day,
            hour=view.hour,
            wheat_reserve=wheat_reserve,
            buys=buys,
            melon_contested=melon_memory.contested,
            melon_days_since_contested=melon_memory.days_since_contested(view.day),
            melon_rolling_max=melon_memory.rolling_price_max,
        )
        # Clamped to what we actually held, not just what we asked for --
        # build_orders' own _capped_sell already enforces this (an order for
        # more than the shed count never gets emitted), so the clamp here is
        # redundant-but-cheap defensive insurance for next turn's attribution
        # math, matching MelonMarketMemory's own contract.
        melon_sold_this_turn = _melon_sell_qty(orders)
        melon_memory.record_our_melon_sell(min(melon_sold_this_turn, view.shed.get("MELON", 0)))
        return {"farmer": actions.farmer, "hands": actions.hands, "market": orders}

    return decide
