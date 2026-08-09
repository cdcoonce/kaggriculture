"""index-front-runner: a minimal wheat economy built to exploit (and
eval-pool-test) the engine's index-0 sell priority (zoo design #21).

Verified engine mechanic (``kaggriculture.py:521-605``): ``_process_market``
processes each player's ``market`` order list by index -- for a given index
``i``, both players' order at that index are quoted using the *current*
market price, then fully committed (including a sell-all ``SELL ITEM 99999``
order, which has no upper bound and drains the entire shed at index ``i`` in
one go) before ``_refresh_prices`` runs and the outer loop advances to index
``i + 1``. So an order at index 0 fully executes -- moving price -- before an
opponent's same-item order at index 1 is even parsed. This is the edge
documented in ``docs/strategy.md:41``: "Index-0 sell priority... Add an
index-front-running opponent to the eval pool to confirm we're not
vulnerable either." This fixture is that opponent.

Just enough wheat production (6 tiles, 2 hands/day) to keep a steady stream
flowing to front-run with -- the point isn't production scale, it's market-
order placement. Every turn (not gated to a town-tick schedule), if the shed
holds wheat and the live price clears a low floor, this fixture places
``["SELL", "WHEAT", 99999]`` as the first element of its market list, ahead
of any HIRE/BUY_SEED orders appended later that turn.

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
HANDS_PER_DAY = 2
SEED_COST = 10
ZONE_SIZE = 6  # minimal wheat plot -- smaller than wheat-spam's 16, plenty to front-run with
WHEAT_SELL_FLOOR = 5  # a fifth of wheat's base=25 -- low enough to always sell, but price-aware


def _compute_target_tiles(n: int = ZONE_SIZE, center: Position = SHED_TILE) -> tuple[Position, ...]:
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
    return min(candidates, key=lambda t: (abs(t[0] - x) + abs(t[1] - y), TARGET_TILES.index(t)))


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh, stateless index-front-runner agent callable."""

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

        # Index-0 front-running: every turn, if the shed holds wheat and the
        # live price clears the floor, sell-all goes in first -- ahead of any
        # HIRE/BUY_SEED orders appended below -- so this order occupies index
        # 0 of the returned market list (module docstring explains why index
        # 0 matters).
        wheat_price = obs["market"]["prices"].get("WHEAT", 0)
        market: list[list[Any]] = []
        if shed.get("WHEAT", 0) > 0 and wheat_price >= WHEAT_SELL_FLOOR:
            market.append(["SELL", "WHEAT", 99999])
        if step % TURNS_PER_DAY == 0:
            for _ in range(HANDS_PER_DAY):
                market.append(["HIRE"])
            if day <= LAST_PLANT_DAY:
                capacity_needed = sum(
                    1 for pos in TARGET_TILES if tile_at(*pos) is None or _is_weed(tile_at(*pos))
                )
                needed = max(0, capacity_needed - seeds.get("WHEAT", 0))
                if needed > 0:
                    affordable = int(farm["money"] // SEED_COST)
                    to_buy = min(needed, affordable)
                    if to_buy > 0:
                        market.append(["BUY_SEED", "WHEAT", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
