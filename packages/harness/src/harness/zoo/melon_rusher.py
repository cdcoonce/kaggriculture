"""melon-rusher: melon monoculture, price-blind flood-sell (zoo #21 batch).

Plants melon on all 24 of the NW quadrant's non-shed tiles -- pure
monoculture, no wheat, no land, no fertilizer. Hires 3 hands a day, waters
and harvests on the same naive per-tile-need loop as ``wheat_spam.py``, and
sells whatever sits in the shed during a fixed 7-hour-of-day window
({0, 1, 19, 20, 21, 22, 23}) with no price check and no floor.

The differentiator from ``melon_dumper.py``: this fixture is fully
stateless, like ``wheat_spam.py``, not a hold-then-latch archetype. It never
withholds a harvest waiting for a trigger -- whatever melon is in the shed
during a window hour gets sold in that same window, from the very first
opportunity onward. Where melon-dumper concentrates cumulative volume into
one engineered burst, melon-rusher's sell volume just tracks its harvest
cadence directly: flood the shared market with volume, indifferent to
price, rather than manufacture one devastating price shock.

Stateless and deterministic: every decision is derived fresh from ``obs``
each call, so a factory-returned closure carries no cross-episode state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Position = tuple[int, int]

SHED_TILE: Position = (4, 4)
CARRY_THRESHOLD = 6  # walk-to-shed-and-DROP once a unit is carrying this much
HARVEST_AGE = 12  # melon max_yield_day; harvesting at this age captures full yield
MELON_LAST_PLANT_DAY = 19  # 10 growth days to first yield; day 19 is the last with any runway
TURNS_PER_DAY = 24
HANDS_PER_DAY = 3
SEED_COST = 80
SELL_WINDOW_HOURS = frozenset({0, 1, 19, 20, 21, 22, 23})


def _compute_target_tiles(n: int = 24, center: Position = SHED_TILE) -> tuple[Position, ...]:
    """The ``n`` NW-quadrant tiles nearest ``center``, excluding it.

    Deterministic: sorted by Manhattan distance, then (y, x) for stable
    tie-breaking. Keeping the shed corner itself out of the set leaves it
    clear for DROP.
    """
    cx, cy = center
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != center]
    candidates.sort(key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
    return tuple(candidates[:n])


TARGET_TILES = _compute_target_tiles()
TARGET_SET = frozenset(TARGET_TILES)


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
        return "PLANT" if day <= MELON_LAST_PLANT_DAY else None
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
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), TARGET_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless melon-rusher agent callable."""

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

        needy_tiles = [pos for pos in TARGET_TILES if _tile_need(tile_at(*pos), day) is not None]

        # First pass: units already standing on a needy tile claim it outright.
        claimed: set[Position] = set()
        on_tile_need: dict[int, str] = {}
        for idx, pos in enumerate(unit_positions):
            if pos in TARGET_SET:
                need = _tile_need(tile_at(*pos), day)
                if need is not None:
                    on_tile_need[idx] = need
                    claimed.add(pos)

        remaining_seeds = seeds.get("MELON", 0)
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
                    unit_actions.append(["PLANT", "MELON"])
                    continue
                # No seeds left for this unit this turn — fall through to idling.
            elif need is not None:
                unit_actions.append([need])
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            carried = inv.get("MELON", 0) if isinstance(inv, dict) else 0
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
        shed_melon = shed.get("MELON", 0)
        if obs["hour"] in SELL_WINDOW_HOURS and shed_melon > 0:
            market.append(["SELL", "MELON", shed_melon])
        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= MELON_LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for pos in TARGET_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                )
                needed = max(0, capacity_needed - seeds.get("MELON", 0))
                if needed > 0:
                    affordable = int(farm["money"] // SEED_COST)
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "MELON", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
