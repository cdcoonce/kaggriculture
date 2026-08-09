"""public-baseline-approx: an approximation of the public notebook "Barnyard
Economist v5" by Roman Rozen (docs/recon/public-meta.md, item 1), the 10th
and final gate-zoo member under the "~10 members" cap.

The source names three concrete, dated structural fixes rather than a full
parameter table: (1) the opening $3,000 bankroll goes into livestock before
land -- "do not spend on land before day 4" moved the notebook's own
benchmark from an ~11k deficit to within ~5k on seat 0; (2) a wheat "filler
crop" (4-day cycle, self-clearing on harvest) keeps the pen from ever being
blocked; (3) tile roles are a pure function of which quadrants are unlocked,
not recomputed from cash/herd size every turn (fixing a tile-flip-flop bug).

This fixture reproduces those three fixes literally and defaults everything
the source doesn't state (see the issue for the full citation trail):
- No melon (a different notebook's strategy, out of scope here).
- A small, modest, symmetric herd: 2 GOOSE + 2 COW + 2 SHEEP, well inside
  the $3,000 opening budget (2x300 + 2x400 + 2x500 = $2,400 flat-priced).
- 8 wheat filler tiles, 3 hands/day.
- Never buys land at all, not even after day 4 -- stricter than the
  source's "not before day 4," chosen because this fixture's fixed NW-only
  reference frame makes "roles as a pure function of unlocked quadrants"
  trivially true for the whole game (only NW is ever unlocked), and
  sidesteps the PASTURE_REFERENCE_QUADRANTS trap documented in
  packages/agent/src/agent/constants.py (a pasture zone pinned to a live,
  reshuffling unlocked-quadrant set can orphan a placed animal with no
  signal at all).
- No fertilizer, ever, and no EGG/MILK/WOOL harvest-and-sell pipeline --
  animals here exist for the day-0 livestock spend and the ongoing
  FEED/CARE loop only.

Stateless and deterministic: every decision is derived fresh from ``obs``
each call, same as wheat-spam (zoo #5) and melon-dumper v1.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
TURNS_PER_DAY = 24
HANDS_PER_DAY = 3

COOP_ZONE_SIZE = 2
PASTURE_ZONE_SIZE = 4
WHEAT_ZONE_SIZE = 8

WHEAT_HARVEST_AGE = 4  # wheat max_yield_day
WHEAT_LAST_PLANT_DAY = 25  # 4 growth days; day 25 is the last that can mature
WHEAT_SEED_COST = 10
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much WHEAT
WHEAT_RESERVE = 6  # never sell shed WHEAT below this -- the herd's flat daily FEED draw
WHEAT_FEED_BUFFER = 6  # top up carried WHEAT to this level when fetching for FEED duty
# The 8-tile zone planted all at once matures all at once (max_yield_day=4)
# and would then get replanted all at once too, producing wheat in one lump
# every 4 days rather than a steady supply -- incompatible with the herd's
# flat 6-WHEAT/day FEED draw. Staggering the zone's planting across 4 days
# spreads harvests across days once the zone reaches steady state instead.
WHEAT_DAILY_PLANT_CAP = 2

GOOSE_TARGET = 2
COW_TARGET = 2
SHEEP_TARGET = 2
ANIMAL_TARGETS: dict[str, int] = {"GOOSE": GOOSE_TARGET, "COW": COW_TARGET, "SHEEP": SHEEP_TARGET}
ANIMAL_COSTS: dict[str, int] = {"GOOSE": 300, "COW": 400, "SHEEP": 500}


def _compute_zones(
    center: Position = SHED_TILE,
) -> tuple[tuple[Position, ...], tuple[Position, ...], tuple[Position, ...]]:
    """(coop_zone, pasture_zone, wheat_zone): the nearest ``COOP_ZONE_SIZE``
    tiles to ``center`` claim COOP (1 per goose), the next
    ``PASTURE_ZONE_SIZE`` claim PASTURE (1 per cow/sheep), the next
    ``WHEAT_ZONE_SIZE`` claim the wheat filler -- 14 of the NW quadrant's 24
    non-shed tiles. A fixed reference frame forever: this fixture never buys
    land, so "unlocked quadrants" never changes. Deterministic: sorted by
    Manhattan distance, then (y, x)."""
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    coop_zone = tuple(candidates[:COOP_ZONE_SIZE])
    pasture_zone = tuple(candidates[COOP_ZONE_SIZE : COOP_ZONE_SIZE + PASTURE_ZONE_SIZE])
    wheat_start = COOP_ZONE_SIZE + PASTURE_ZONE_SIZE
    wheat_zone = tuple(candidates[wheat_start : wheat_start + WHEAT_ZONE_SIZE])
    return coop_zone, pasture_zone, wheat_zone


COOP_TILES, PASTURE_TILES, WHEAT_TILES = _compute_zones()
COOP_SET = frozenset(COOP_TILES)
PASTURE_SET = frozenset(PASTURE_TILES)
WHEAT_SET = frozenset(WHEAT_TILES)
ANIMAL_SET = COOP_SET | PASTURE_SET
ALL_TILES = COOP_TILES + PASTURE_TILES + WHEAT_TILES


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


def _wheat_need(tile: Any, day: int, plantable: bool) -> str | None:
    """What action (if any) a unit standing on a wheat-zone ``tile`` should
    take. Returns one of "DIG", "PLANT", "WATER", "HARVEST", or None.
    ``plantable`` gates PLANT on an empty tile -- the caller staggers which
    empty tiles are plantable this turn (``WHEAT_DAILY_PLANT_CAP``)."""
    if _is_weed(tile):
        return "DIG"
    if tile is None:
        return "PLANT" if day <= WHEAT_LAST_PLANT_DAY and plantable else None
    if _is_plant(tile):
        if not tile.get("watered_today", False):
            return "WATER"
        if tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", day)) >= (
            WHEAT_HARVEST_AGE
        ):
            return "HARVEST"
    return None


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), ALL_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless public-baseline-approx agent callable."""

    def agent(obs: Any) -> dict[str, Any]:
        player = obs["player"]
        farm = obs["farms"][player]
        private = obs["private"]
        seeds = private["seeds"]
        shed = private["shed"]
        step = obs["step"]
        day = step // TURNS_PER_DAY
        tiles = farm["tiles"]
        board_h = len(tiles)
        board_w = len(tiles[0]) if board_h else 0

        def tile_at(x: int, y: int) -> Any:
            if 0 <= x < board_w and 0 <= y < board_h:
                return tiles[y][x]
            return "LOCKED"

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        def carried(idx: int, item: str) -> int:
            inv = inventories[idx] if idx < len(inventories) else {}
            return inv.get(item, 0) if isinstance(inv, dict) else 0

        coop_build_needed = [pos for pos in COOP_TILES if tile_at(*pos) is None]
        pasture_build_needed = [pos for pos in PASTURE_TILES if tile_at(*pos) is None]
        coop_place_needed = [
            pos
            for pos in COOP_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "COOP"
            and "animal" not in tile_at(*pos)
        ]
        pasture_place_needed = [
            pos
            for pos in PASTURE_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "PASTURE"
            and "animal" not in tile_at(*pos)
        ]
        feed_needed = [
            pos
            for pos in ANIMAL_SET
            if isinstance(tile_at(*pos), dict)
            and "animal" in tile_at(*pos)
            and not tile_at(*pos)["fed_today"]
        ]
        care_needed = [
            pos
            for pos in ANIMAL_SET
            if isinstance(tile_at(*pos), dict)
            and "animal" in tile_at(*pos)
            and not tile_at(*pos)["cared_today"]
        ]
        wheat_planted_today = sum(
            1
            for pos in WHEAT_TILES
            if isinstance(tile_at(*pos), dict)
            and tile_at(*pos).get("kind") == "PLANT"
            and tile_at(*pos).get("planted_day") == day
        )
        wheat_plant_budget = max(0, WHEAT_DAILY_PLANT_CAP - wheat_planted_today)
        empty_wheat = [pos for pos in WHEAT_TILES if tile_at(*pos) is None]
        plantable_wheat_today = frozenset(empty_wheat[:wheat_plant_budget])

        def wheat_need_at(pos: Position) -> str | None:
            return _wheat_need(tile_at(*pos), day, pos in plantable_wheat_today)

        wheat_needy = [pos for pos in WHEAT_TILES if wheat_need_at(pos) is not None]

        # Wheat takes until ~day 4 to first mature (max_yield_day=4), so an
        # animal placed on day 0 would starve (2 consecutive unfed days)
        # before any filler-crop harvest could feed it. Hold bought animals
        # in the shed -- money is already committed day 0, satisfying
        # "livestock first" -- until a full day's FEED reserve is actually
        # banked, so placement and sustained feeding start together.
        ready_to_place = shed.get("WHEAT", 0) >= WHEAT_RESERVE

        claimed: set[Position] = set()
        remaining_wheat_seeds = seeds.get("WHEAT", 0)
        unit_actions: list[list[Any]] = []

        for idx, pos in enumerate(unit_positions):
            x, y = pos
            tile = tile_at(x, y)
            if tile == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            action: list[Any] | None = None

            if pos in ANIMAL_SET and isinstance(tile, dict) and "animal" in tile:
                if not tile["fed_today"] and carried(idx, "WHEAT") >= 1:
                    action = ["FEED"]
                elif not tile["cared_today"]:
                    action = ["CARE"]
            elif (
                pos in COOP_SET
                and isinstance(tile, dict)
                and tile.get("kind") == "COOP"
                and "animal" not in tile
            ):
                if carried(idx, "GOOSE") >= 1:
                    action = ["PLACE", "GOOSE"]
            elif (
                pos in PASTURE_SET
                and isinstance(tile, dict)
                and tile.get("kind") == "PASTURE"
                and "animal" not in tile
            ):
                if carried(idx, "COW") >= 1:
                    action = ["PLACE", "COW"]
                elif carried(idx, "SHEEP") >= 1:
                    action = ["PLACE", "SHEEP"]
            elif pos in COOP_SET and tile is None:
                action = ["BUILD_COOP"]
            elif pos in PASTURE_SET and tile is None:
                action = ["BUILD_PASTURE"]
            elif pos in WHEAT_SET:
                need = wheat_need_at(pos)
                if need == "PLANT":
                    if remaining_wheat_seeds > 0:
                        remaining_wheat_seeds -= 1
                        action = ["PLANT", "WHEAT"]
                elif need is not None:
                    action = [need]
            elif pos == SHED_TILE:
                carrying_unplaced_animal = (
                    carried(idx, "GOOSE") >= 1
                    or carried(idx, "COW") >= 1
                    or carried(idx, "SHEEP") >= 1
                )
                carrying_feed_stock = bool(feed_needed) and carried(idx, "WHEAT") >= 1
                if carrying_unplaced_animal or carrying_feed_stock:
                    # Already holding something earmarked for delivery (an
                    # animal to place, or WHEAT fetched to feed a still-unfed
                    # animal) -- don't also grab more or DROP here; DROP would
                    # dump it straight back into the shed the instant WHEAT
                    # hits CARRY_THRESHOLD, undoing the pickup before the unit
                    # ever leaves. Leave action unset so the movement fallback
                    # below walks it to its delivery target instead.
                    pass
                elif carried(idx, "WHEAT") >= CARRY_THRESHOLD:
                    action = ["DROP"]
                else:
                    if ready_to_place:
                        for item in ("GOOSE", "COW", "SHEEP"):
                            if shed.get(item, 0) > 0:
                                action = ["PICKUP", item, shed.get(item, 0)]
                                break
                    if (
                        action is None
                        and feed_needed
                        and carried(idx, "WHEAT") < WHEAT_FEED_BUFFER
                        and shed.get("WHEAT", 0) > 0
                    ):
                        want = WHEAT_FEED_BUFFER - carried(idx, "WHEAT")
                        qty = min(want, shed.get("WHEAT", 0))
                        if qty > 0:
                            action = ["PICKUP", "WHEAT", qty]

            if action is not None:
                unit_actions.append(action)
                continue

            if carried(idx, "GOOSE") >= 1:
                target = _nearest_unclaimed(pos, coop_place_needed, claimed)
                if target is not None:
                    claimed.add(target)
                    unit_actions.append(_step_toward(x, y, *target))
                    continue
            if carried(idx, "COW") >= 1 or carried(idx, "SHEEP") >= 1:
                target = _nearest_unclaimed(pos, pasture_place_needed, claimed)
                if target is not None:
                    claimed.add(target)
                    unit_actions.append(_step_toward(x, y, *target))
                    continue
            if feed_needed and carried(idx, "WHEAT") >= 1:
                target = _nearest_unclaimed(pos, feed_needed, claimed)
                if target is not None:
                    claimed.add(target)
                    unit_actions.append(_step_toward(x, y, *target))
                    continue
            if carried(idx, "WHEAT") >= CARRY_THRESHOLD:
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue
            if feed_needed and carried(idx, "WHEAT") < 1 and shed.get("WHEAT", 0) > 0:
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue
            target = _nearest_unclaimed(pos, care_needed, claimed)
            if target is not None:
                claimed.add(target)
                unit_actions.append(_step_toward(x, y, *target))
                continue
            target = _nearest_unclaimed(pos, coop_build_needed + pasture_build_needed, claimed)
            if target is not None:
                claimed.add(target)
                unit_actions.append(_step_toward(x, y, *target))
                continue
            if ready_to_place and any(shed.get(item, 0) > 0 for item in ("GOOSE", "COW", "SHEEP")):
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue
            target = _nearest_unclaimed(pos, wheat_needy, claimed)
            if target is not None:
                claimed.add(target)
                unit_actions.append(_step_toward(x, y, *target))
                continue
            unit_actions.append(["PASS"])

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        market: list[list[Any]] = []
        shed_wheat = shed.get("WHEAT", 0)
        surplus = shed_wheat - WHEAT_RESERVE
        if surplus > 0:
            market.append(["SELL", "WHEAT", surplus])

        def committed(item: str) -> int:
            board_count = sum(
                1 for row in tiles for t in row if isinstance(t, dict) and t.get("animal") == item
            )
            inv_count = sum(inv.get(item, 0) for inv in inventories if isinstance(inv, dict))
            return board_count + inv_count + shed.get(item, 0)

        available_money = farm["money"]
        for item, cost in ANIMAL_COSTS.items():
            needed = ANIMAL_TARGETS[item] - committed(item)
            if needed <= 0:
                continue
            affordable = int(available_money // cost)
            qty = min(needed, affordable)
            if qty > 0:
                market.append(["BUY_ANIMAL", item, qty])
                available_money -= qty * cost

        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= WHEAT_LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for pos in WHEAT_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                )
                seed_needed = max(0, capacity_needed - seeds.get("WHEAT", 0))
                if seed_needed > 0:
                    seed_affordable = int(available_money // WHEAT_SEED_COST)
                    to_buy = min(seed_needed, seed_affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
