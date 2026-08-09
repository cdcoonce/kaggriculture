"""fert-market-crasher: a modest wheat economy that funds an accumulate-then-
dump FERTILIZER cycle (zoo #21c, part of #21's four-fixture batch).

Wheat side is a smaller copy of wheat-spam's own dispatch shape (8 tiles
instead of 16, same 2-hands-a-day crew, same never-exceed-seeds-held PLANT
ordering, same price-blind sell-on-sight) -- just enough labor to fund
fertilizer purchases without needing a large crew.

Fertilizer side is the fixture's actual point: FERTILIZER is sellable (the
engine's generic SELL path quotes any item in PRODUCTS) but a round-trip
buy-then-sell-the-same-units nets to zero market impact (BUY_PRODUCT and SELL
move the shared market inventory in opposite directions). The only
mechanically sound way to inject a one-directional supply shock without also
owning livestock (out of scope for this fixture) is to accumulate via
BUY_PRODUCT for a while, then dump the entire backlog via SELL once, later.
This fixture splits the game at a fixed day threshold (``FERT_DUMP_DAY``):
every window-hour turn before it, buy fertilizer (never sell); every
window-hour turn at or after it, sell the whole shed (never buy again). The
split is a pure function of ``obs["step"]`` (``day = step // TURNS_PER_DAY``),
so -- unlike melon-dumper's hold/dump latch, which needs real cross-turn
state to survive its trigger re-evaluating below threshold -- this fixture
stays fully stateless: every decision is derived fresh from ``obs`` each
call, so a factory-returned closure carries no cross-episode state.

Fertilizer orders are further gated to a fixed subset of each day's 24 hours
(``WINDOW_HOURS``) purely for turn-cadence hygiene -- FERTILIZER is excluded
from town consumption entirely, so this gate exploits no documented engine
timing mechanic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much
HARVEST_AGE = 4  # wheat max_yield_day; harvesting at this age captures full yield
LAST_PLANT_DAY = 25  # wheat needs 4 growth days; day 25 is the last that can mature
TURNS_PER_DAY = 24
HANDS_PER_DAY = 2
SEED_COST = 10
WHEAT_ZONE_SIZE = 8  # smaller than wheat-spam's 16: just enough to fund fertilizer buys

WINDOW_HOURS = frozenset({0, 1, 19, 20, 21, 22, 23})  # 7 hours/day fertilizer orders are gated to
FERT_DUMP_DAY = 15  # day < 15: accumulate; day >= 15: dump -- fixed, one-way, no latch needed
FERT_BUY_CAP = 10  # max FERTILIZER units queued per window-hour turn during accumulation


def _compute_target_tiles(
    n: int = WHEAT_ZONE_SIZE, center: Position = SHED_TILE
) -> tuple[Position, ...]:
    """The ``n`` NW-quadrant tiles nearest ``center``, excluding it.

    Deterministic: sorted by Manhattan distance, then (y, x) for stable
    tie-breaking. Keeping the shed corner itself out of the set leaves it
    clear for DROP.
    """
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    return tuple(candidates[:n])


WHEAT_TILES = _compute_target_tiles()
TARGET_SET = frozenset(WHEAT_TILES)


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


def _tile_need(tile: Any, day: int) -> str | None:
    """What action (if any) a unit standing on ``tile`` should take.

    Returns one of "DIG", "PLANT", "WATER", "HARVEST", or None.
    """
    if _is_weed(tile):
        return "DIG"
    if tile is None:
        return "PLANT" if day <= LAST_PLANT_DAY else None
    if _is_plant(tile):
        if not tile.get("watered_today", False):
            return "WATER"
        if tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", day)) >= HARVEST_AGE:
            return "HARVEST"
    return None


def _nearest_unclaimed(
    pos: Position, needy: list[Position], claimed: set[Position]
) -> Position | None:
    candidates = [t for t in needy if t not in claimed]
    if not candidates:
        return None
    x, y = pos
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), WHEAT_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless fert-market-crasher agent callable."""

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

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
        inventories = private["inventories"]

        needy_tiles = [pos for pos in WHEAT_TILES if _tile_need(tile_at(*pos), day) is not None]

        # First pass: units already standing on a needy tile claim it outright.
        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            if pos in TARGET_SET:
                need = _tile_need(tile_at(*pos), day)
                if need is not None:
                    on_tile_need[idx] = need
                    claimed.add(pos)

        remaining_seeds = seeds.get("WHEAT", 0)
        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *SHED_TILE))
                continue

            need = on_tile_need.get(idx)
            if need == "PLANT":
                if remaining_seeds > 0:
                    remaining_seeds -= 1
                    unit_actions.append(["PLANT", "WHEAT"])
                    continue
                # No seeds left for this unit this turn — fall through to idling.
            elif need is not None:
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = inv.get("WHEAT", 0) if isinstance(inv, dict) else 0
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
        if shed.get("WHEAT", 0) > 0:
            market.append(["SELL", "WHEAT", 99999])
        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for pos in WHEAT_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                )
                needed = max(0, capacity_needed - seeds.get("WHEAT", 0))
                if needed > 0:
                    affordable = int(farm["money"] // SEED_COST)
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

        if hour in WINDOW_HOURS:
            if day < FERT_DUMP_DAY:
                price = obs["market"]["prices"]["FERTILIZER"]
                n = min(FERT_BUY_CAP, int(farm["money"] // price))
                if n > 0:
                    market.append(["BUY_PRODUCT", "FERTILIZER", n])
            else:
                fert_shed = shed.get("FERTILIZER", 0)
                if fert_shed > 0:
                    market.append(["SELL", "FERTILIZER", fert_shed])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
