"""meta-clone: economy core pinned to Kaggle episode 90568437's converged
ranch (zoo #23, slice 1 of 2 -- rig prerequisite for the tuning rig's search
pool).

Land, hire cadence, planting, feed-stock buying, and sell timing are all
pinned to derived metadata from the observed 151k-money converged ranch: one
``BUY_LAND`` on day 9 unconditionally (the day, not a money threshold -- this
slice has none of the real ranch's animal spending, so a money-gated trigger
would cross the observed ~$2,100 purchase-time balance well before day 9 and
fire early); a per-day hire ramp; a day-by-day PLANT schedule (WHEAT/MELON/
STRAWBERRY only, never CARROT/TOMATO, nothing after day 24); WHEAT feed-stock
top-ups bought from the market from day 8 on; and price-blind SELL orders
confined to the town-tick windows (hours 0-1 and 19-23).

This slice builds the economy only -- no animal actions, no pasture, and no
registration in ``harness.zoo.SCRIPTED`` (see that module's docstring: zoo
members are immutable once registered, so registration is deferred to slice
2, the animal-husbandry slice that depends on this module).

Tile universe: the fixed NW+NE frame, replicated locally rather than
imported -- same convention as the champion's ``PASTURE_REFERENCE_QUADRANTS``
in ``packages/agent/src/agent/constants.py`` (a static ``("NW", "NE")``
tuple, never the live ``unlocked_quadrants``): 48 tiles (2 rows of 5x5
quadrants minus the two shed-access corners), sorted nearest-shed-access
first. NE tiles read as the engine sentinel ``"LOCKED"`` until the day-9
purchase unlocks them; the generic need-scan below only recognizes ``None``
(empty) or a weed/plant dict, so ``"LOCKED"`` tiles are silently skipped with
no special-casing needed once ``BUY_LAND`` fires. This fixture never buys
SW/SE, so NW+NE is the tile universe for the whole game.

Deterministic, but not fully stateless like wheat-spam or melon-dumper v1:
most decisions (including the once-only day-9 land purchase) are pure
functions of ``obs`` each call, but the day-27+ watering wind-down needs real
cross-turn memory -- HARVEST clears a harvested WHEAT/MELON tile back to
empty, so a live board rescan for "how many distinct tiles were watered
today" would undercount once some of today's watered tiles get harvested and
cleared later the same day, letting the cap silently replenish mid-day.
``make_agent()`` therefore closes over a small mutable dict (the same
pattern ``melon_dumper``'s hold/dump latch uses) tracking the set of tiles
watered so far today, reset on every day-boundary crossing (including a
fresh episode reusing the same closure, since day rolling back to 0 is
itself a boundary crossing).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

TURNS_PER_DAY = 24
LAND_DAY = 9  # sole BUY_LAND trigger: day == 9, hour 0 -- not a money threshold
LAST_PLANT_DAY = 24  # no PLANT-event after this day, per the cited table
WATER_WINDDOWN_DAY = 27  # days 27-29: watering budget drops to WATER_WINDDOWN_CAP/day
WATER_WINDDOWN_CAP = 8
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much
BUY_PRODUCT_HOURS = frozenset({1, 2})
BUY_PRODUCT_FIRST_DAY = 8
BUY_PRODUCT_MONEY_FLOOR = 500
BUY_PRODUCT_CAP = 10  # single-digit to low-double-digit lots
SELL_HOURS = frozenset({0, 1, 19, 20, 21, 22, 23})  # town-tick windows

NW_SHED: Position = (4, 4)
NE_SHED: Position = (5, 4)
SHED_ACCESS_TILES: tuple[Position, ...] = (NW_SHED, NE_SHED)

HARVEST_AGE: dict[str, int] = {"WHEAT": 4, "MELON": 12, "STRAWBERRY": 10}
SEED_COST: dict[str, int] = {"WHEAT": 10, "MELON": 80, "STRAWBERRY": 100}

# Day -> {crop: count}, from the cited PLANT-event table (ep 90568437).
PLANT_TABLE: dict[int, dict[str, int]] = {
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


def _hires_for_day(day: int) -> int:
    """Hire cadence from the cited hires/day table."""
    if day == 0:
        return 8
    if 1 <= day <= 4:
        return 4
    if 5 <= day <= 8:
        return 7
    if day == 9:
        return 9
    if day == 10:
        return 7
    if day == 11:
        return 11
    return 12  # days 12-29


def _compute_target_tiles() -> tuple[Position, ...]:
    """The 48 non-shed-access tiles of the fixed NW+NE frame, nearest the
    nearer shed-access corner first -- the same fixed-frame convention as the
    champion's ``PASTURE_REFERENCE_QUADRANTS`` (a static ("NW", "NE") tuple,
    never the live ``unlocked_quadrants``), replicated locally rather than
    imported."""
    tiles = [(x, y) for y in range(5) for x in range(10) if (x, y) not in SHED_ACCESS_TILES]

    def sort_key(t: Position) -> tuple[int, int, int]:
        dist = min(abs(t[0] - ax) + abs(t[1] - ay) for ax, ay in SHED_ACCESS_TILES)
        return (dist, t[1], t[0])

    tiles.sort(key=sort_key)
    return tuple(tiles)


ALL_TILES = _compute_target_tiles()
TILE_INDEX: dict[Position, int] = {pos: i for i, pos in enumerate(ALL_TILES)}


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
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), TILE_INDEX[t]))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh meta-clone economy-core agent callable with its own
    episode-scoped watering tracker closed over (see module docstring for
    why the day-27+ wind-down cap needs real cross-turn memory: HARVEST
    clears WHEAT/MELON tiles back to empty, so a tile watered earlier today
    then harvested-and-cleared would otherwise silently vanish from a
    board-rescan-based count, letting the cap replenish mid-day)."""
    state: dict[str, Any] = {"day": -1, "watered_today": set()}

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

        if day != state["day"]:
            state["day"] = day
            state["watered_today"] = set()

        # This day's remaining PLANT quota per crop, recomputed fresh from a
        # tile scan each turn (stateless, matching melon_dumper's planted-
        # today count) -- no cross-turn planting tracker needed.
        today_quota = PLANT_TABLE.get(day, {}) if day <= LAST_PLANT_DAY else {}
        planted_today: dict[str, int] = dict.fromkeys(today_quota, 0)
        for pos in ALL_TILES:
            tile = tile_at(*pos)
            if _is_plant(tile) and tile.get("planted_day") == day:
                crop = tile.get("crop")
                if crop in planted_today:
                    planted_today[crop] += 1
        remaining_quota = {
            crop: max(0, quota - planted_today[crop]) for crop, quota in today_quota.items()
        }
        total_plant_remaining = sum(remaining_quota.values())
        empty_tiles = [pos for pos in ALL_TILES if tile_at(*pos) is None]
        plantable_today = set(empty_tiles[:total_plant_remaining])

        remaining_seeds = {
            "WHEAT": seeds.get("WHEAT", 0),
            "MELON": seeds.get("MELON", 0),
            "STRAWBERRY": seeds.get("STRAWBERRY", 0),
        }

        def pick_plant_crop() -> str | None:
            for crop in today_quota:
                if remaining_quota.get(crop, 0) > 0 and remaining_seeds.get(crop, 0) > 0:
                    remaining_quota[crop] -= 1
                    remaining_seeds[crop] -= 1
                    return crop
            return None

        # Watering wind-down (days 27-29): cap distinct-tile WATER orders at
        # WATER_WINDDOWN_CAP/day. Counted from ``state["watered_today"]``
        # (updated below, after dispatch decides this turn's actions) rather
        # than a live board rescan -- a rescan undercounts once HARVEST
        # clears a watered WHEAT/MELON tile back to empty, which would let
        # the budget silently replenish mid-day.
        water_budget: int | None = None
        if day >= WATER_WINDDOWN_DAY:
            water_budget = max(0, WATER_WINDDOWN_CAP - len(state["watered_today"]))

        need_by_pos: dict[Position, str] = {}
        water_used = 0
        for pos in ALL_TILES:
            tile = tile_at(*pos)
            if tile == "LOCKED":
                continue
            if _is_weed(tile):
                need_by_pos[pos] = "DIG"
                continue
            if tile is None:
                if pos in plantable_today:
                    need_by_pos[pos] = "PLANT"
                continue
            if _is_plant(tile):
                if not tile.get("watered_today", False):
                    if water_budget is not None and water_used >= water_budget:
                        continue
                    water_used += 1
                    need_by_pos[pos] = "WATER"
                    continue
                crop = tile.get("crop")
                harvest_age = HARVEST_AGE.get(crop, 999)
                if (
                    tile.get("yield_units", 0) > 0
                    and (day - tile.get("planted_day", day)) >= harvest_age
                ):
                    need_by_pos[pos] = "HARVEST"

        needy_tiles = list(need_by_pos.keys())

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            need = need_by_pos.get(pos)
            if need is not None:
                on_tile_need[idx] = need
                claimed.add(pos)

        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *NW_SHED))
                continue

            need = on_tile_need.get(idx)
            if need == "PLANT":
                crop = pick_plant_crop()
                if crop is not None:
                    unit_actions.append(["PLANT", crop])
                    continue
                # No seeds/quota left for this unit this turn -- fall
                # through to idling.
            elif need is not None:
                if need == "WATER":
                    state["watered_today"].add(pos)
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = (
                inv.get("WHEAT", 0) + inv.get("MELON", 0) + inv.get("STRAWBERRY", 0)
                if isinstance(inv, dict)
                else 0
            )
            if carried >= CARRY_THRESHOLD:
                nearest_shed = min(SHED_ACCESS_TILES, key=lambda s: abs(s[0] - x) + abs(s[1] - y))
                if pos == nearest_shed:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *nearest_shed))
                continue

            target = _nearest_unclaimed(pos, needy_tiles, claimed)
            if target is None:
                unit_actions.append(["PASS"])
                continue
            claimed.add(target)
            unit_actions.append(_step_toward(x, y, *target))

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        # Order construction is priority-ordered and truncation-aware: the
        # engine caps market orders at ``maxMarketOrdersPerTurn`` (10) and
        # silently drops anything past that index (verified via a real run --
        # a naive single hour-0 burst of BUY_LAND + up to 12 HIRE + several
        # BUY_SEED orders overflows 10 and starves planting for the whole
        # day). BUY_LAND and HIRE go first (highest priority). HIRE and
        # BUY_SEED demand are each re-derived every turn from the engine's
        # own live counters (``hires_today``, held seeds) rather than
        # tracked locally, and attempted on every turn the need is nonzero
        # (not just hour 0) -- a heavy seed-spend day can leave money too
        # tight to afford the day's full hire ramp at hour 0 (fib-scaled
        # hire cost), so retrying once later revenue lands is what actually
        # closes the gap to the day's target instead of giving up after one
        # or two turns.
        market: list[list[Any]] = []
        if day == LAND_DAY and hour == 0:
            market.append(["BUY_LAND"])

        hires_today = farm.get("hires_today", 0)
        remaining_hires = max(0, _hires_for_day(day) - hires_today)
        for _ in range(remaining_hires):
            market.append(["HIRE"])

        for crop, remaining in remaining_quota.items():
            if remaining <= 0:
                continue
            have = seeds.get(crop, 0)
            needed = max(0, remaining - have)
            if needed <= 0:
                continue
            cost = SEED_COST[crop]
            affordable = int(farm["money"] // cost)
            to_buy = min(needed, affordable)
            if to_buy > 0:
                market.append(["BUY_SEED", crop, to_buy])

        if hour in SELL_HOURS:
            # Larger-volume crop first (index 0): the engine processes a
            # market order list by index to completion before the next, so
            # the bigger backlog nets the better pre-crash price.
            crop_shed = [(crop, shed.get(crop, 0)) for crop in ("WHEAT", "MELON", "STRAWBERRY")]
            crop_shed = [c for c in crop_shed if c[1] > 0]
            crop_shed.sort(key=lambda c: c[1], reverse=True)
            for crop, _amount in crop_shed:
                market.append(["SELL", crop, 99999])

        if (
            day >= BUY_PRODUCT_FIRST_DAY
            and hour in BUY_PRODUCT_HOURS
            and farm["money"] >= BUY_PRODUCT_MONEY_FLOOR
        ):
            price = obs["market"]["prices"].get("WHEAT", 0)
            if price > 0:
                affordable = int(farm["money"] // price)
                to_buy = min(BUY_PRODUCT_CAP, affordable)
                if to_buy > 0:
                    market.append(["BUY_PRODUCT", "WHEAT", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
