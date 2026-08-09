"""land-rush-hoarder: rushes all three purchasable land quadrants on cash
availability alone, while running a deliberately under-provisioned wheat
operation (4 tiles, 1 hand/day) that can't fund the last quadrant -- the
"over-expand on land, under-invest in production" archetype (zoo #21).

Queues an unconditional ``BUY_LAND`` market order every turn while any
quadrant remains unbought; the engine's own ``_do_buy_land`` is atomic and
self-gating (it no-ops if unaffordable), so no local price bookkeeping is
needed here. Sells wheat price-blind every turn so cash doesn't sit idle in
shed inventory, but spends on nothing else beyond the land rush and the
4-tile plot's minimal seed/hire upkeep -- all other cash hoards unspent.

Stateless and deterministic: every decision is derived fresh from ``obs``
each call, so a factory-returned closure carries no cross-episode state.
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
HANDS_PER_DAY = 1  # deliberately under-provisioned relative to the 3-quadrant land rush
SEED_COST = 10
TOTAL_QUADRANTS = 4  # NW (starting) + NE + SW + SE


def _compute_target_tiles(n: int = 4, center: Position = SHED_TILE) -> tuple[Position, ...]:
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
WHEAT_SET = frozenset(WHEAT_TILES)


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
    """Return a fresh, stateless land-rush-hoarder agent callable."""

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

        needy_tiles = [pos for pos in WHEAT_TILES if _tile_need(tile_at(*pos), day) is not None]

        # First pass: units already standing on a needy tile claim it outright.
        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            if pos in WHEAT_SET:
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
        if len(farm["unlocked_quadrants"]) < TOTAL_QUADRANTS:
            market.append(["BUY_LAND"])
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

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
