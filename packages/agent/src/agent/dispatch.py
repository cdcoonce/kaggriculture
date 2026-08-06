"""Per-turn unit dispatcher — farmer as goose steward and shed mule, hands as
field crew over the target wheat tiles.

Everything is recomputed from the view each turn (hands are daily rentals, the
farmer respawns at the shed corner nightly), so the dispatcher carries no
cross-turn state at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.constants import COOP_TILE, SHED_TILE, TARGET_TILES
from agent.view import FarmView, Tile

UnitAction = list[object]

HAND_MULE_LOAD = 6  # a hand this loaded walks its harvest home for same-day sale


def _carry_load(inv: dict[str, int]) -> int:
    """Sellable units carried (the goose is pipeline cargo, not produce)."""
    return sum(n for item, n in inv.items() if item != "GOOSE")


def _find_animal(view: FarmView) -> tuple[int, int] | None:
    for y, row in enumerate(view.tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and "animal" in tile:
                return (x, y)
    return None


def _steward(view: FarmView) -> UnitAction | None:
    """The farmer's goose duty for this turn, or None if none is pending."""
    pos = view.farmer
    inv = view.inventories[0] if view.inventories else {}
    goose_pos = _find_animal(view)

    if goose_pos is None:
        if inv.get("GOOSE", 0) > 0:
            if pos == COOP_TILE:
                site: Tile = view.tiles[COOP_TILE[1]][COOP_TILE[0]]
                if site is None:
                    return ["BUILD_COOP"]
                if isinstance(site, dict):
                    if site.get("kind") == "COOP" and "animal" not in site:
                        return ["PLACE", "GOOSE"]
                    if site.get("kind") == "WEED":
                        return ["DIG"]
                return None
            return _step_toward(pos, COOP_TILE)
        if view.shed.get("GOOSE", 0) > 0:
            if pos == SHED_TILE:
                return ["PICKUP", "GOOSE", 1]
            return _step_toward(pos, SHED_TILE)
        return None

    tile = view.tiles[goose_pos[1]][goose_pos[0]]
    if not isinstance(tile, dict):  # unreachable; defensive for the never-crash law
        return None
    unfed = not tile.get("fed_today", False)
    chores_pending = (
        int(tile.get("yield_units", 0)) > 0
        or not tile.get("cared_today", False)
        or bool(tile.get("fertilizer_available", False))
    )

    if pos == goose_pos:
        if unfed and inv.get("WHEAT", 0) > 0:
            return ["FEED"]
        if int(tile.get("yield_units", 0)) > 0:
            return ["HARVEST"]
        if not tile.get("cared_today", False):
            return ["CARE"]
        if tile.get("fertilizer_available", False):
            return ["COLLECT_FERTILIZER"]
        return None

    if unfed:
        if inv.get("WHEAT", 0) > 0:
            return _step_toward(pos, goose_pos)
        if view.shed.get("WHEAT", 0) > 0:
            if pos == SHED_TILE:
                return ["PICKUP", "WHEAT", 1]
            return _step_toward(pos, SHED_TILE)
    if chores_pending:
        return _step_toward(pos, goose_pos)
    return None


def _mule(pos: tuple[int, int]) -> UnitAction:
    step = _step_toward(pos, SHED_TILE)
    return step if step is not None else ["DROP"]


@dataclass
class Actions:
    farmer: UnitAction = field(default_factory=lambda: ["PASS"])
    hands: list[UnitAction] = field(default_factory=list)


def _step_toward(pos: tuple[int, int], target: tuple[int, int]) -> UnitAction | None:
    x, y = pos
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return None


@dataclass(frozen=True)
class _Task:
    tile: tuple[int, int]
    action: UnitAction
    uses_seed: bool = False


def _field_tasks(view: FarmView) -> list[_Task]:
    """Work needed on the target tiles, in deterministic priority order."""
    tasks: list[_Task] = []
    for x, y in TARGET_TILES:
        tile: Tile = view.tiles[y][x]
        if tile is None:
            tasks.append(_Task((x, y), ["PLANT", "WHEAT"], uses_seed=True))
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            tasks.append(_Task((x, y), ["DIG"]))
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            age = view.day - int(tile.get("planted_day", view.day))
            ripe = int(tile.get("yield_units", 0)) > 0 and age >= 4
            if not tile.get("watered_today", False):
                tasks.append(_Task((x, y), ["WATER"]))
            elif ripe:
                tasks.append(_Task((x, y), ["HARVEST"]))
    return tasks


def dispatch(view: FarmView) -> Actions:
    units: list[tuple[int, int]] = [view.farmer, *view.hands]
    chosen: list[UnitAction] = [["PASS"] for _ in units]
    fielded = set(range(len(units)))

    steward_action = _steward(view)
    if steward_action is not None:
        chosen[0] = steward_action
        fielded.discard(0)
    elif _carry_load(view.inventories[0] if view.inventories else {}) > 0:
        chosen[0] = _mule(view.farmer)
        fielded.discard(0)

    # Heavily-loaded hands walk their harvest home before taking new work.
    for i in range(1, len(units)):
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if _carry_load(inv) >= HAND_MULE_LOAD:
            chosen[i] = _mule(units[i])
            fielded.discard(i)

    tasks = _field_tasks(view)
    seed_budget = view.seeds.get("WHEAT", 0)
    claimed: set[tuple[int, int]] = set()
    assigned: dict[int, _Task] = {}

    def claim(i: int, task: _Task) -> None:
        nonlocal seed_budget
        claimed.add(task.tile)
        if task.uses_seed:
            seed_budget -= 1
        assigned[i] = task

    # Pass 1: a unit already standing on a task tile keeps it — never walk a
    # closer unit past work another unit is on top of.
    by_tile = {t.tile: t for t in tasks}
    for i, pos in enumerate(units):
        if i not in fielded:
            continue
        task = by_tile.get(pos)
        if task is not None and pos not in claimed:
            if task.uses_seed and seed_budget <= 0:
                continue
            claim(i, task)

    # Pass 2: everyone else takes the nearest unclaimed task.
    for i, pos in enumerate(units):
        if i not in fielded or i in assigned:
            continue
        best: _Task | None = None
        best_dist = 10**9
        for task in tasks:
            if task.tile in claimed:
                continue
            if task.uses_seed and seed_budget <= 0:
                continue
            dist = abs(pos[0] - task.tile[0]) + abs(pos[1] - task.tile[1])
            if dist < best_dist:
                best, best_dist = task, dist
        if best is not None:
            claim(i, best)

    for i, pos in enumerate(units):
        task = assigned.get(i)
        if task is None:
            continue
        move = _step_toward(pos, task.tile)
        chosen[i] = move if move is not None else task.action

    # Nobody idles: leftover carry walks home; a unit parked on LOCKED ground
    # (hand spawns) walks toward the shed corner so tomorrow's tile-ops can run.
    for i, pos in enumerate(units):
        if chosen[i] != ["PASS"]:
            continue
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if _carry_load(inv) > 0:
            chosen[i] = _mule(pos)
        elif view.tiles[pos[1]][pos[0]] == "LOCKED":
            step = _step_toward(pos, SHED_TILE)
            if step is not None:
                chosen[i] = step

    return Actions(farmer=chosen[0], hands=chosen[1:])
