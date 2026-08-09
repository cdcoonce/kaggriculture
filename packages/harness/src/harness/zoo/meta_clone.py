"""meta-clone: economy core, slice 1/2 (issue #23) -- land, hands, planting,
feed-stock buying, and sell timing pinned to derived metadata from Kaggle
episode 90568437 (the observed 151k-money converged ranch).

This slice does NOT register the member in ``harness.zoo.SCRIPTED`` --
zoo members are immutable once registered, so registration is deferred to
slice 2 (the animal-husbandry slice, which builds on this economy core and
freezes the combined behavior under the ``meta-clone`` name).

Numbers pinned directly from the issue's derived-metadata spec:

- Land: a single unconditional ``BUY_LAND`` at day 9 hour 0 (``day == 9`` is
  the sole trigger, not a money threshold -- see issue for why a money gate
  would fire early absent this slice's animal spending).
- Hires/day: a fixed day->count table (``HIRES_PER_DAY``), re-hired daily
  since hands are engine-evicted at every day boundary. Spread across
  ``HIRE_HOURS`` (not all queued in a single turn) because the engine caps
  ``maxMarketOrdersPerTurn`` at 10 and the day-12+ rate (12 hires) plus
  same-turn SELL/BUY_SEED orders would otherwise silently truncate.
- Planting: a fixed day->{crop: count} table (``PLANT_SCHEDULE``) taken
  directly from the issue's cited PLANT-event table. Zero planting after
  day 24; never CARROT/TOMATO. Tile targets use a fixed NW+NE frame (the
  same convention as the champion's ``PASTURE_REFERENCE_QUADRANTS``,
  replicated locally here rather than imported).
- Feed-stock: small ``BUY_PRODUCT`` WHEAT lots at hour 1-2, day >= 8, only
  when money >= $500.
- Selling: price-blind full-shed ``SELL`` orders clustered at hours 0-1 and
  19-23 (town-tick timing), silent mid-day.
- Watering wind-down: days 27-29 cap at <=8 distinct live tiles watered per
  day (never fully stops). This is a deliberate policy cap, not incidental:
  the issue's own PLANT table plants WHEAT as late as days 23-24 (4-day
  maturity => still growing/needing water on days 27-28), so an uncapped
  "water everything live" policy cannot satisfy the <=8 ceiling on its own.
  HARVEST is checked (and fires) independently of same-day watering (the
  engine's HARVEST handler has no ``watered_today`` gate), so capped-out
  tiles still get harvested when ripe -- only the WATER action itself is
  rationed once the day's cap is spent. The cap is computed fresh from
  ``obs`` each turn (count of live tiles already showing
  ``watered_today=True`` in the target zones), so no cross-turn state is
  needed to enforce it.

Stateless and deterministic like ``wheat_spam``/``melon_dumper``: every
decision is derived fresh from ``obs`` each call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much of any crop
TURNS_PER_DAY = 24

# -- Land -------------------------------------------------------------------
LAND_DAY = 9  # sole trigger: day == LAND_DAY, unconditional (not money-gated)

# -- Hires --------------------------------------------------------------------
# Fixed day -> hands-to-hire-today table (issue spec). Hands are daily
# rentals (engine evicts farm["hands"] at every day boundary), so this fires
# fresh every day rather than accumulating.
HIRES_PER_DAY: dict[int, int] = {
    0: 8,
    1: 4,
    2: 4,
    3: 4,
    4: 4,
    5: 7,
    6: 7,
    7: 7,
    8: 7,
    9: 9,
    10: 7,
    11: 11,
}
DEFAULT_HIRES_PER_DAY = 12  # days 12-29

# Spread across 4 hours so a single turn never approaches the engine's
# maxMarketOrdersPerTurn=10 cap alongside same-turn SELL/BUY_SEED orders.
HIRE_HOURS: tuple[int, ...] = (3, 4, 5, 6)


def _hires_for_day(day: int) -> int:
    return HIRES_PER_DAY.get(day, DEFAULT_HIRES_PER_DAY)


def _hire_count_for_hour(day: int, hour: int) -> int:
    if hour not in HIRE_HOURS:
        return 0
    total = _hires_for_day(day)
    base, remainder = divmod(total, len(HIRE_HOURS))
    slot = HIRE_HOURS.index(hour)
    return base + 1 if slot < remainder else base


# -- Planting -----------------------------------------------------------------
# Fixed day -> {crop: count} table, taken directly from the issue's cited
# PLANT-event table. No entry beyond day 24 (LAST_PLANT_DAY), and never
# CARROT/TOMATO.
PLANT_SCHEDULE: dict[int, dict[str, int]] = {
    0: {"WHEAT": 8, "MELON": 5},
    1: {"MELON": 3},
    3: {"MELON": 1},
    4: {"WHEAT": 8, "MELON": 2},
    5: {"MELON": 1},
    8: {"WHEAT": 4},
    9: {"WHEAT": 3, "MELON": 5},
    10: {"STRAWBERRY": 1, "MELON": 3},
    11: {"MELON": 6, "STRAWBERRY": 7},
    12: {"WHEAT": 4},
    13: {"WHEAT": 3},
    14: {"STRAWBERRY": 1, "MELON": 1},
    15: {"MELON": 1},
    16: {"WHEAT": 4},
    17: {"WHEAT": 3},
    19: {"WHEAT": 5},
    20: {"WHEAT": 6},
    21: {"WHEAT": 10},
    23: {"WHEAT": 5},
    24: {"WHEAT": 6},
}
LAST_PLANT_DAY = 24

# Engine CROPS table (max_yield_day / seed cost), for harvest-age and
# BUY_SEED pricing.
HARVEST_AGE: dict[str, int] = {"WHEAT": 4, "MELON": 12, "STRAWBERRY": 10}
SEED_COST: dict[str, int] = {"WHEAT": 10, "MELON": 80, "STRAWBERRY": 100}
CROPS_PLANTED: tuple[str, ...] = ("WHEAT", "MELON", "STRAWBERRY")
BUY_SEED_HOUR = 7  # arbitrary fixed hour, clear of HIRE/SELL/BUY_PRODUCT windows

# -- Feed-stock buying ----------------------------------------------------------
FEED_BUY_HOURS: frozenset[int] = frozenset({1, 2})
FEED_BUY_FIRST_DAY = 8
FEED_BUY_MONEY_FLOOR = 500
FEED_BUY_LOT = 8  # single-digit to low-double-digit units, per issue spec

# -- Selling ------------------------------------------------------------------
SELL_HOURS: frozenset[int] = frozenset({0, 1, 19, 20, 21, 22, 23})
SELLABLE_CROPS: tuple[str, ...] = ("WHEAT", "MELON", "STRAWBERRY")

# -- Watering wind-down ---------------------------------------------------------
WATER_WIND_DOWN_DAY = 27  # days >= this: watering capped
WATER_CAP_LATE = 8  # <=8 distinct live tiles watered/day for days 27-29


def _compute_zones() -> tuple[tuple[Position, ...], tuple[Position, ...], tuple[Position, ...]]:
    """(wheat_zone, melon_zone, strawberry_zone): a fixed NW+NE frame (the
    same convention as the champion's PASTURE_REFERENCE_QUADRANTS, always
    ("NW", "NE") regardless of live unlocked_quadrants -- replicated locally
    here rather than imported per issue scope). NW is x,y in [0,5); NE is x
    in [5,10), y in [0,5) -- 50 candidate tiles minus the shed corner = 49,
    sorted by Manhattan distance to SHED_TILE then (y, x) for a stable,
    deterministic ordering. NE tiles remain "LOCKED" (a string, not a dict)
    until the day-9 BUY_LAND fires; the existing tile-need dispatch already
    treats LOCKED tiles as needing nothing, so no explicit unlock gating is
    required here.
    """
    cx, cy = SHED_TILE
    candidates = [(x, y) for y in range(5) for x in range(10) if (x, y) != SHED_TILE]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    wheat_zone = tuple(candidates[:20])
    melon_zone = tuple(candidates[20:40])
    strawberry_zone = tuple(candidates[40:49])
    return wheat_zone, melon_zone, strawberry_zone


WHEAT_TILES, MELON_TILES, STRAWBERRY_TILES = _compute_zones()
ZONE_BY_CROP: dict[str, tuple[Position, ...]] = {
    "WHEAT": WHEAT_TILES,
    "MELON": MELON_TILES,
    "STRAWBERRY": STRAWBERRY_TILES,
}
ALL_TILES = WHEAT_TILES + MELON_TILES + STRAWBERRY_TILES
TARGET_SET = frozenset(ALL_TILES)
CROP_BY_TILE: dict[Position, str] = {
    pos: crop for crop in CROPS_PLANTED for pos in ZONE_BY_CROP[crop]
}


def _step_toward(x: int, y: int, tx: int, ty: int) -> list[str]:
    """One cardinal step toward (tx, ty); resolves x before y."""
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _is_weed(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def _is_plant(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), ALL_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless meta-clone economy-core agent callable."""

    def agent(obs: Any) -> dict[str, Any]:
        player = obs["player"]
        farm = obs["farms"][player]
        private = obs["private"]
        seeds = private["seeds"]
        shed = private["shed"]
        step = obs["step"]
        day = step // TURNS_PER_DAY
        hour = step % TURNS_PER_DAY
        tiles = farm["tiles"]
        board_h = len(tiles)
        board_w = len(tiles[0]) if board_h else 0

        def tile_at(x: int, y: int) -> Any:
            if 0 <= x < board_w and 0 <= y < board_h:
                return tiles[y][x]
            return "LOCKED"

        # Today's per-crop planting budget and how much of it is already
        # planted (tiles in that crop's zone whose planted_day == today).
        day_budget = PLANT_SCHEDULE.get(day, {})
        planted_today: dict[str, int] = dict.fromkeys(CROPS_PLANTED, 0)
        for crop in CROPS_PLANTED:
            for pos in ZONE_BY_CROP[crop]:
                t = tile_at(*pos)
                if _is_plant(t) and t.get("crop") == crop and t.get("planted_day") == day:
                    planted_today[crop] += 1
        plant_room: dict[str, int] = {
            crop: max(0, day_budget.get(crop, 0) - planted_today[crop]) for crop in CROPS_PLANTED
        }
        plantable_now: dict[str, int] = dict(plant_room)

        # Watering wind-down: on days >= WATER_WIND_DOWN_DAY, only the first
        # WATER_CAP_LATE distinct live tiles (in ALL_TILES order) that still
        # need water this turn get a WATER need; the rest are skipped (they
        # may weed out over subsequent days -- expected wind-down, not a
        # bug). Uncapped on earlier days. already-watered tiles (engine
        # flag) count against the cap even before this turn's assignment.
        water_budget: int | None = None
        if day >= WATER_WIND_DOWN_DAY:
            already_watered = sum(
                1
                for pos in ALL_TILES
                if _is_plant(tile_at(*pos)) and tile_at(*pos).get("watered_today")
            )
            water_budget = max(0, WATER_CAP_LATE - already_watered)

        def need_at(pos: Position) -> str | None:
            nonlocal water_budget
            crop = CROP_BY_TILE[pos]
            tile = tile_at(*pos)
            if _is_weed(tile):
                return "DIG"
            if tile is None:
                if day <= LAST_PLANT_DAY and plantable_now[crop] > 0:
                    return "PLANT"
                return None
            if not _is_plant(tile):
                return None
            harvest_age = HARVEST_AGE[crop]
            planted_day = tile.get("planted_day", day)
            if tile.get("yield_units", 0) > 0 and (day - planted_day) >= harvest_age:
                return "HARVEST"
            if not tile.get("watered_today", False):
                if water_budget is None:
                    return "WATER"
                if water_budget > 0:
                    water_budget -= 1
                    return "WATER"
                return None
            return None

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        # need_at() has a stateful side effect (rationing water_budget), so
        # it must be evaluated exactly once per tile this turn -- cache the
        # results rather than calling it again for the on-tile claim pass.
        need_by_tile: dict[Position, str] = {}
        for pos in ALL_TILES:
            need = need_at(pos)
            if need is not None:
                need_by_tile[pos] = need
        needy_tiles = list(need_by_tile.keys())

        # First pass: units already standing on a needy tile claim it outright.
        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            if pos in TARGET_SET:
                need = need_by_tile.get(pos)
                if need is not None:
                    on_tile_need[idx] = need
                    claimed.add(pos)

        remaining_seeds: dict[str, int] = {crop: seeds.get(crop, 0) for crop in CROPS_PLANTED}
        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            need = on_tile_need.get(idx)
            if need == "PLANT":
                crop = CROP_BY_TILE[pos]
                if remaining_seeds[crop] > 0 and plantable_now[crop] > 0:
                    remaining_seeds[crop] -= 1
                    plantable_now[crop] -= 1
                    unit_actions.append(["PLANT", crop])
                    continue
                # No seeds or budget left for this tile's crop this turn.
            elif need is not None:
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = sum(inv.get(c, 0) for c in CROPS_PLANTED) if isinstance(inv, dict) else 0
            if carried >= CARRY_THRESHOLD:
                if pos == SHED_TILE:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            target = _nearest_unclaimed(pos, needy_tiles, claimed)
            if target is None:
                unit_actions.append(["PASS"])
                continue
            claimed.add(target)
            unit_actions.append(_step_toward(x, y, *target))

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []

        if day == LAND_DAY and hour == 0:
            market.append(["BUY_LAND"])

        hire_n = _hire_count_for_hour(day, hour)
        for _ in range(hire_n):
            market.append(["HIRE"])

        if hour == BUY_SEED_HOUR:
            for crop, budget in day_budget.items():
                needed = max(0, budget - seeds.get(crop, 0))
                if needed > 0:
                    price = SEED_COST[crop]
                    affordable = int(farm["money"] // price)
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", crop, to_buy])

        feed_buy_window = hour in FEED_BUY_HOURS and day >= FEED_BUY_FIRST_DAY
        if feed_buy_window and farm["money"] >= FEED_BUY_MONEY_FLOOR:
            price = obs["market"]["prices"].get("WHEAT", 0)
            if price > 0:
                affordable = int(farm["money"] // price)
                lot = min(FEED_BUY_LOT, affordable)
                if lot > 0:
                    market.append(["BUY_PRODUCT", "WHEAT", lot])

        if hour in SELL_HOURS:
            ready = [c for c in SELLABLE_CROPS if shed.get(c, 0) > 0]
            ready.sort(key=lambda c: shed.get(c, 0), reverse=True)
            for crop in ready:
                market.append(["SELL", crop, 99999])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
