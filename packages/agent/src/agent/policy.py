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
from dataclasses import dataclass
from typing import Any

from agent.constants import (
    BOARD_SIZE,
    COW_TARGET,
    MELON_TILE_TARGET,
    PASTURE_REFERENCE_QUADRANTS,
    SHEEP_TARGET,
    melon_tiles,
    pasture_tiles,
    target_tiles,
)
from agent.dispatch import dispatch
from agent.market import (
    FERT_MIN_PRICE,
    MILK_MIN_PRICE,
    VALVE_SOFT_CAP,
    WOOL_MILK_SELL_CAP,
    WOOL_MIN_PRICE,
    build_orders,
)
from agent.plan import FEED_RESERVE, plan_day
from agent.shell import Action, Observation, pass_action
from agent.state import MelonMarketMemory, ProductCrashLatch, StateTracker
from agent.view import FarmView, parse_obs

SOFT_BUDGET_SECONDS = 0.5  # v1 logic runs in microseconds; this guards regressions

# No cap by default: the full board (BOARD_SIZE**2 tiles, minus COOP_TILE) can
# never yield more wheat tiles than this once melon's and pasture's own zones
# are carved out, so the default preserves today's uncapped remainder for
# every unlock state.
_WHEAT_RUSH_TILES_DEFAULT = (
    BOARD_SIZE * BOARD_SIZE - 1 - MELON_TILE_TARGET - (COW_TARGET + SHEEP_TARGET)
)

# M2c (kaggriculture#59): two-tier shed valve. Absolute-unit thresholds
# against the engine's default 100-unit shed -- policy.decide scales them by
# the real shedCapacity/100 before comparing against shed_total, so a
# non-default capacity still trips the valve at the same *fraction* full.
VALVE_SOFT_THRESHOLD = 55
VALVE_HARD_THRESHOLD = 85

# M2c: WOOL/MILK crash-latch defaults (agent.state.ProductCrashLatch). Tuned
# well under each product's regime floor (wool_floor=200, milk_floor=120) so
# the latch only fires once the price has genuinely crashed, not merely
# dipped below the floor -- see market.py's module docstring, M2c section.
WOOL_CRASH_TRIGGER = 100.0
MILK_CRASH_TRIGGER = 60.0
CRASH_TRIGGER_TICKS = 12


@dataclass(frozen=True)
class PolicyConfig:
    """Tuning knobs for the chassis, lifted out of module-level constants so
    an eval run can override them without editing source. Every field's
    default reproduces today's hardcoded behavior exactly."""

    soft_budget_seconds: float = SOFT_BUDGET_SECONDS
    feed_reserve: int = FEED_RESERVE
    melon_tile_target: int = MELON_TILE_TARGET
    cow_target: int = COW_TARGET
    sheep_target: int = SHEEP_TARGET
    wheat_rush_tiles: int = _WHEAT_RUSH_TILES_DEFAULT

    # M2c (kaggriculture#59): two-tier shed valve + WOOL/MILK crash latches.
    # See the VALVE_*/*_CRASH_TRIGGER module constants above and market.py's
    # module docstring (M2c section) for the full behavior this drives.
    valve_soft_threshold: int = VALVE_SOFT_THRESHOLD
    valve_hard_threshold: int = VALVE_HARD_THRESHOLD
    valve_soft_cap: int = VALVE_SOFT_CAP
    wool_floor: float = WOOL_MIN_PRICE
    milk_floor: float = MILK_MIN_PRICE
    fert_floor: float = FERT_MIN_PRICE
    wool_crash_trigger: float = WOOL_CRASH_TRIGGER
    milk_crash_trigger: float = MILK_CRASH_TRIGGER
    crash_trigger_ticks: int = CRASH_TRIGGER_TICKS
    wool_milk_sell_cap: int = WOOL_MILK_SELL_CAP

    @property
    def pasture_tile_target(self) -> int:
        """Derived, not independently settable -- an override here would let
        the pasture zone size drift out of sync with the animal targets it's
        supposed to exactly cover (one animal per pasture tile)."""
        return self.cow_target + self.sheep_target


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


def _shed_capacity(config: dict[str, Any] | None) -> int:
    """The engine's real per-episode shed capacity, defaulting to 100 (the
    engine's own default) when no config is supplied -- every existing unit
    test calls ``decide`` with ``config=None``, so this must be None-safe."""
    if config is None:
        return 100
    return int(config.get("shedCapacity", 100))


def _valve_tier(shed: dict[str, int], config: dict[str, Any] | None, resolved: PolicyConfig) -> int:
    """M2c (kaggriculture#59): 0/1/2 shed-fill tier from total shed contents.

    Thresholds are absolute units against the engine's default 100-unit
    shed; scaled by the real ``shedCapacity``/100 so a non-default capacity
    still trips the valve at the same *fraction* full, keeping integer
    semantics (floor division, not a float threshold)."""
    capacity = _shed_capacity(config)
    shed_total = sum(shed.values())
    soft_threshold = (resolved.valve_soft_threshold * capacity) // 100
    hard_threshold = (resolved.valve_hard_threshold * capacity) // 100
    if shed_total >= hard_threshold:
        return 2
    if shed_total >= soft_threshold:
        return 1
    return 0


def _melon_sell_qty(orders: list[list[object]]) -> int:
    """The quantity from this turn's own ``["SELL", "MELON", n]`` order, if
    any -- fed back to ``MelonMarketMemory`` so next turn's opponent-sell
    attribution can net our own sale out of the shared inventory delta."""
    for order in orders:
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "MELON":
            qty = order[2]
            return qty if isinstance(qty, int) else 0
    return 0


def make_policy(
    clock: Callable[[], float] = time.monotonic,
    policy_config: PolicyConfig | None = None,
) -> Any:
    """Build the policy callable with its episode-scoped trackers closed over."""
    resolved_config = policy_config if policy_config is not None else PolicyConfig()
    tracker = StateTracker()
    melon_memory = MelonMarketMemory()
    wool_latch = ProductCrashLatch(
        resolved_config.wool_crash_trigger, resolved_config.crash_trigger_ticks
    )
    milk_latch = ProductCrashLatch(
        resolved_config.milk_crash_trigger, resolved_config.crash_trigger_ticks
    )

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
        # Same continuity argument as melon_memory above: a turn that later
        # bails to pass_action() still needs its price tick counted, or a
        # crash spanning a budget-exhausted turn would under-count toward
        # crash_trigger_ticks.
        wool_latch.observe(view.prices.get("WOOL", 0.0), view.step)
        milk_latch.observe(view.prices.get("MILK", 0.0), view.step)

        if clock() - start > resolved_config.soft_budget_seconds:
            return pass_action()

        tiles = target_tiles(view.unlocked_quadrants)
        melons = melon_tiles(view.unlocked_quadrants, target=resolved_config.melon_tile_target)
        # Fixed reference frame, NOT view.unlocked_quadrants -- pastures must
        # never migrate as SW/SE unlock later (constants.PASTURE_REFERENCE_
        # QUADRANTS explains why: a live value orphans built pastures and
        # placed animals the instant the nearest-shed-first ordering shifts).
        pastures = pasture_tiles(
            PASTURE_REFERENCE_QUADRANTS, target=resolved_config.pasture_tile_target
        )
        melon_set = frozenset(melons)
        pasture_set = frozenset(pastures)
        # Set difference, not a positional slice: pasture_set's positions are
        # anchored to the fixed reference frame above and are not guaranteed
        # to occupy any particular prefix of the *live* tiles ordering.
        # Capped at wheat_rush_tiles -- an explicit, config-driven bound on
        # wheat's own zone instead of an unbounded remainder.
        wheat_tiles = [t for t in tiles if t not in melon_set and t not in pasture_set][
            : resolved_config.wheat_rush_tiles
        ]
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
            feed_reserve=resolved_config.feed_reserve,
            cow_target=resolved_config.cow_target,
            sheep_target=resolved_config.sheep_target,
        )
        actions = dispatch(view, tiles, melon_set, pasture_set)

        # Buys first, hires last: if the 10-slot cap ever truncates, it drops
        # trailing hires (which self-heal next turn) rather than a purchase.
        buys: list[list[object]] = list(plan.buys)
        buys.extend([["HIRE"]] * plan.hire_count)
        any_animal_owned = goose or cows_owned > 0 or sheep_owned > 0
        wheat_reserve = animals_placed + resolved_config.feed_reserve if any_animal_owned else 0
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
            valve_tier=_valve_tier(view.shed, config, resolved_config),
            valve_soft_cap=resolved_config.valve_soft_cap,
            wool_floor=resolved_config.wool_floor,
            milk_floor=resolved_config.milk_floor,
            fert_floor=resolved_config.fert_floor,
            wool_crashed=wool_latch.latched,
            milk_crashed=milk_latch.latched,
            wool_milk_sell_cap=resolved_config.wool_milk_sell_cap,
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
