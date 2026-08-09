"""meta-clone: economy core (zoo #21, slice 1/2) — land, hands, planting, feed-
stock buying, and sell timing pinned to derived pacing metadata from Kaggle
episode 90568437 (the observed 151k-money converged ranch; full pacing table
in issue #23's comments).

This slice does NOT register the member in ``harness.zoo.SCRIPTED`` — zoo
members are immutable once registered, so registration is the freeze point
and happens only in slice 2 (the animal-husbandry slice, issue #24, which
depends on this one). The module lands, is importable, and is tested here,
but ``gate_zoo()`` does not change in this slice.

Pinned pacing (all engine-verified from ep 90568437, days 0-indexed, 24
turns/day):

- Exactly one BUY_LAND, on day 9, first turn that day money >= $2,100. This
  unlocks NE; the fixture plays NW+NE only, all game (a fixed reference
  frame, like the champion's ``PASTURE_REFERENCE_QUADRANTS`` convention --
  replicated locally here per issue #23, not imported from packages/agent).
- Daily hire ramp (``HIRE_SCHEDULE``): re-hired every day (hands are daily
  rentals, evicted at every day boundary).
- Planting follows ``PLANT_SCHEDULE``, a day -> {crop: new-plants-that-day}
  table lifted directly from the cited PLANT-event trace. Zero planting
  after day 24. Never carrot/tomato.
- Feed-stock: BUY_PRODUCT WHEAT only, small lots, hour 1-2 each morning from
  day 8 on, only when money >= $500 -- the observed ranch tops up animal
  feed from the market instead of over-planting wheat. This slice has no
  animals to eat it, and the price-blind sell windows below dump the whole
  wheat shed at the next town tick, so end-of-episode shed WHEAT is 0: the
  buy is paced here, but nothing accumulates yet. Slice 2, which adds the
  consumer, is what has to hold a feed floor back from the sell loop.
- Selling clusters at hours 0-1 and 19-23 (town-tick timing); price-blind,
  no fertilizer buyback ever.
- Wind-down: watering is throttled to <= 8 ops/day for days 27-29 (never
  fully stops), versus no cap through day 26. No new planting after day 24
  already stops that half of the ramp-down.

Nearly stateless across episodes: most decisions are derived fresh from
``obs`` each call (day-scoped plant budgets are recovered by scanning tile
state for ``planted_day``, the same technique ``melon_dumper`` uses for its
daily plant cap). The one exception is the wind-down water cap, which needs
a real day-scoped op counter closed over in the returned callable -- see
``make_agent``'s docstring for why a tile-state scan is unsafe there. The
counter resets on every day change, including across episodes, so reusing
one closure never leaks state between runs.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)  # NW shed-access tile
NE_SHED_TILE: Position = (5, 4)  # NE shed-access tile, usable once NE unlocks
TURNS_PER_DAY = 24
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit carries this much

LAND_DAY = 9
LAND_COST = 2100  # observed trigger threshold ("first turn of day 9 where money >= $2,100")

# Daily hire ramp, ep 90568437: day 0: 8; days 1-4: 4; days 5-8: 7; day 9: 9;
# day 10: 7; day 11: 11; days 12-29: 12.
HIRE_SCHEDULE: dict[int, int] = {
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
HIRE_SCHEDULE_DEFAULT = 12  # days 12-29


def _hires_for_day(day: int) -> int:
    return HIRE_SCHEDULE.get(day, HIRE_SCHEDULE_DEFAULT)


# PLANT-event table, day -> {crop: new-plants-that-day}, lifted verbatim from
# the cited trace. Never CARROT/TOMATO.
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
LAST_PLANT_DAY = 24  # zero planting after this day

HARVEST_AGE: dict[str, int] = {"WHEAT": 4, "MELON": 12, "STRAWBERRY": 10}
SEED_COST: dict[str, int] = {"WHEAT": 10, "MELON": 80, "STRAWBERRY": 100}

WHEAT_PRODUCT_BUY_FIRST_DAY = 8
WHEAT_PRODUCT_BUY_HOURS = frozenset({1, 2})
WHEAT_PRODUCT_BUY_MIN_MONEY = 500
WHEAT_PRODUCT_BUY_QTY = 10  # single-digit to low-double-digit lots

SELL_HOURS = frozenset({0, 1, 19, 20, 21, 22, 23})

WATER_WINDDOWN_DAY = 27
WATER_WINDDOWN_CAP = 8  # ops/day for days 27-29 (never fully stops -- cap is > 0)


def _compute_target_tiles() -> tuple[Position, ...]:
    """The 48 NW+NE farmable tiles (both shed-access tiles excluded),
    nearest-to-either-shed-access-tile first, then (y, x) for stable
    tie-breaking. A fixed reference frame for the whole game -- this
    fixture never plays SW/SE -- replicating locally the same fixed-frame
    convention the champion's ``PASTURE_REFERENCE_QUADRANTS`` uses, per
    issue #23 (no import from packages/agent)."""
    access = (SHED_TILE, NE_SHED_TILE)
    candidates = [
        (x, y) for y in range(5) for x in range(10) if (x, y) not in (SHED_TILE, NE_SHED_TILE)
    ]
    candidates.sort(
        key=lambda p: (min(abs(p[0] - ax) + abs(p[1] - ay) for ax, ay in access), p[1], p[0])
    )
    return tuple(candidates)


ALL_TILES = _compute_target_tiles()
TARGET_SET = frozenset(ALL_TILES)

# The 48 tiles are ONE shared pool, not three fixed per-crop zones: peak
# concurrent occupancy per crop (melon 26 around day 11, wheat 27 around day
# 24, strawberry 9 for the rest of the game once planted) sums well past 48,
# but the peaks do not coincide -- melon's last planting is day 15 and its
# tiles free up as it is harvested, exactly as the wheat table's day-19..24
# surge asks for them. A fixed partition cannot express the pinned PLANT
# table; a shared pool with per-crop *preference orders* can, while keeping
# each crop clustered and the whole assignment deterministic.
#
# Melon (premium, most walked-to) prefers the tiles nearest the shed-access
# pair; wheat (highest churn, replanted over its 4-day maturity) works in
# from the far end; strawberry -- ``ongoing``, planted once and holding its
# tile for the rest of the game -- takes the middle band so it never strands
# either of the other two.
MELON_PLANT_ORDER = ALL_TILES
WHEAT_PLANT_ORDER = tuple(reversed(ALL_TILES))
_MIDDLE = len(ALL_TILES) // 2
STRAWBERRY_PLANT_ORDER = tuple(
    sorted(ALL_TILES, key=lambda p: (abs(ALL_TILES.index(p) - _MIDDLE), ALL_TILES.index(p)))
)
PLANT_ORDERS: dict[str, tuple[Position, ...]] = {
    "MELON": MELON_PLANT_ORDER,
    "STRAWBERRY": STRAWBERRY_PLANT_ORDER,
    "WHEAT": WHEAT_PLANT_ORDER,
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


def _nearest_shed_access(pos: Position, unlocked_quadrants: list[str]) -> Position:
    access = [SHED_TILE]
    if "NE" in unlocked_quadrants:
        access.append(NE_SHED_TILE)
    x, y = pos
    return min(access, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), t[1], t[0]))


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), ALL_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh meta-clone economy-core agent callable.

    Nearly stateless -- every decision is re-derived fresh from ``obs`` each
    call -- except the wind-down water cap (days >= WATER_WINDDOWN_DAY),
    which closes over a small mutable day-scoped op counter. A tile-state
    scan (counting ``watered_today`` flags, the technique used for the
    per-day plant budgets above) is NOT a safe proxy for "ops already spent
    today" here: a same-day harvest removes a watered tile from the live
    pool, silently freeing up counted "budget" again and letting more than
    the cap's worth of WATER orders through. The counter only ever
    increments within a day and resets on a day change (including on reuse
    across episodes, since a fresh episode's day 0 always differs from
    whatever day the closure last saw).
    """
    water_ops_state: dict[str, int] = {"day": -1, "water_ops_today": 0}

    def agent(obs: Any) -> dict[str, Any]:
        player = obs["player"]
        farm = obs["farms"][player]
        private = obs["private"]
        seeds = private["seeds"]
        shed = private["shed"]
        step = obs["step"]
        day = step // TURNS_PER_DAY
        hour = step % TURNS_PER_DAY
        money = farm["money"]
        unlocked_quadrants = farm.get("unlocked_quadrants", ["NW"])
        tiles = farm["tiles"]
        board_h = len(tiles)
        board_w = len(tiles[0]) if board_h else 0

        def tile_at(x: int, y: int) -> Any:
            if 0 <= x < board_w and 0 <= y < board_h:
                return tiles[y][x]
            return "LOCKED"

        if day != water_ops_state["day"]:
            water_ops_state["day"] = day
            water_ops_state["water_ops_today"] = 0

        # Per-day planting budgets: how many NEW plants of each crop remain
        # for today, recovered by scanning for tiles already planted today
        # (same technique melon_dumper uses for its daily plant cap).
        today_target = PLANT_SCHEDULE.get(day, {})
        remaining_budget: dict[str, int] = {}
        for crop in ("MELON", "STRAWBERRY", "WHEAT"):
            target = today_target.get(crop, 0)
            planted_today = sum(
                1
                for pos in ALL_TILES
                if isinstance(tile_at(*pos), dict)
                and tile_at(*pos).get("kind") == "PLANT"
                and tile_at(*pos).get("crop") == crop
                and tile_at(*pos).get("planted_day") == day
            )
            remaining_budget[crop] = max(0, target - planted_today) if day <= LAST_PLANT_DAY else 0

        # Today's tile assignment, drawn from the shared pool in each crop's
        # preference order. Assigning here (rather than partitioning the
        # board once at import) is what lets the day-19..24 wheat surge reuse
        # tiles the melon cohort has already vacated.
        plant_plan: dict[Position, str] = {}
        for crop in ("MELON", "STRAWBERRY", "WHEAT"):
            budget = remaining_budget[crop]
            if budget <= 0:
                continue
            for pos in PLANT_ORDERS[crop]:
                if budget <= 0:
                    break
                if pos in plant_plan or tile_at(*pos) is not None:
                    continue
                plant_plan[pos] = crop
                budget -= 1

        # Wind-down water budget: uncapped through day 26, throttled to
        # WATER_WINDDOWN_CAP ops/day for days 27-29 (never fully stops).
        # Gated on ``water_ops_state``'s monotonic counter, not a tile-state
        # scan -- see the make_agent docstring for why a scan is unsafe here.
        needing_water = [
            pos
            for pos in ALL_TILES
            if _is_plant(tile_at(*pos)) and not tile_at(*pos).get("watered_today", False)
        ]
        if day >= WATER_WINDDOWN_DAY:
            water_budget = max(0, WATER_WINDDOWN_CAP - water_ops_state["water_ops_today"])
            approved_water = set(needing_water[:water_budget])
        else:
            approved_water = set(needing_water)

        def need_at(pos: Position) -> str | None:
            tile = tile_at(*pos)
            if tile == "LOCKED":
                return None
            if tile is None:
                return "PLANT" if pos in plant_plan else None
            if _is_weed(tile):
                return "DIG"
            if _is_plant(tile):
                if not tile.get("watered_today", False):
                    return "WATER" if pos in approved_water else None
                crop = tile.get("crop", "WHEAT")
                age = day - tile.get("planted_day", day)
                if tile.get("yield_units", 0) > 0 and age >= HARVEST_AGE.get(crop, 0):
                    return "HARVEST"
            return None

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        needy_tiles = [pos for pos in ALL_TILES if need_at(pos) is not None]

        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            # ``claimed`` gates units STANDING on a tile as well as units
            # targeting one: two co-located units would otherwise both read
            # the same need and both emit the action, spending two ops of a
            # computed budget (the wind-down water cap, a day's plant budget)
            # for one tile's worth of work.
            if pos in TARGET_SET and pos not in claimed:
                need = need_at(pos)
                if need is not None:
                    on_tile_need[idx] = need
                    claimed.add(pos)

        remaining_seeds = {crop: seeds.get(crop, 0) for crop in ("WHEAT", "MELON", "STRAWBERRY")}
        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            shed_target = _nearest_shed_access(pos, unlocked_quadrants)
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *shed_target))
                continue

            need = on_tile_need.get(idx)
            if need == "PLANT":
                crop = plant_plan[pos]
                if remaining_seeds[crop] > 0:
                    remaining_seeds[crop] -= 1
                    unit_actions.append(["PLANT", crop])
                    continue
                # No seed left for this unit's crop this turn -- fall through to idling.
            elif need is not None:
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = (
                sum(inv.get(c, 0) for c in ("WHEAT", "MELON", "STRAWBERRY"))
                if isinstance(inv, dict)
                else 0
            )
            if carried >= CARRY_THRESHOLD:
                if pos == shed_target:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *shed_target))
                continue

            target = _nearest_unclaimed(pos, needy_tiles, claimed)
            if target is None:
                unit_actions.append(["PASS"])
                continue
            claimed.add(target)
            unit_actions.append(_step_toward(x, y, *target))

        water_ops_state["water_ops_today"] += sum(1 for a in unit_actions if a == ["WATER"])

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []

        # BUY_LAND: exactly once, on day 9, first turn money clears the
        # observed threshold.
        if day == LAND_DAY and len(unlocked_quadrants) < 2 and money >= LAND_COST:
            market.append(["BUY_LAND"])

        # HIRE: daily rentals, re-hired every day per HIRE_SCHEDULE, spread
        # across turns as needed (the engine truncates a turn's market list
        # at 10 orders).
        hires_needed = _hires_for_day(day) - farm.get("hires_today", 0)
        for _ in range(max(0, hires_needed)):
            market.append(["HIRE"])

        # SELL: price-blind, clustered at hours 0-1 / 19-23 (town-tick
        # timing), never fertilizer.
        if hour in SELL_HOURS:
            for crop in ("WHEAT", "MELON", "STRAWBERRY"):
                if shed.get(crop, 0) > 0:
                    market.append(["SELL", crop, 99999])

        # Feed-stock top-up: BUY_PRODUCT WHEAT only, small lots, hour 1-2,
        # from day 8 on, only when money clears the observed floor.
        if (
            day >= WHEAT_PRODUCT_BUY_FIRST_DAY
            and hour in WHEAT_PRODUCT_BUY_HOURS
            and money >= WHEAT_PRODUCT_BUY_MIN_MONEY
        ):
            market.append(["BUY_PRODUCT", "WHEAT", WHEAT_PRODUCT_BUY_QTY])

        # BUY_SEED: top up toward today's PLANT_SCHEDULE target, opportunistically
        # (not hour-gated, so it can slot into whatever room a turn has left).
        if day <= LAST_PLANT_DAY:
            for crop in ("MELON", "STRAWBERRY", "WHEAT"):
                # Against what the day still OWES, not the day's full target
                # -- topping up to the target after the tiles are already in
                # the ground buys a second batch that cannot be planted
                # (melon_dumper.py's plant-cap top-up nets out the same way).
                needed = max(0, remaining_budget[crop] - seeds.get(crop, 0))
                if needed > 0:
                    affordable = int(money // SEED_COST[crop])
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", crop, to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
