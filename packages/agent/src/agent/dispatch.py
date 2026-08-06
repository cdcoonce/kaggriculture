"""Per-turn unit dispatcher — farmer as goose steward and shed mule, hands as
field crew over the target wheat and melon tiles.

Everything is recomputed from the view each turn (hands are daily rentals, the
farmer respawns at the shed corner nightly), so the dispatcher carries no
cross-turn state at all. The target-tile universe is owned by the caller
(``constants.target_tiles``, sized to whatever land is unlocked) and threaded
in once per turn rather than recomputed per unit; the melon subset of that
universe (``constants.melon_tiles``) is threaded in separately so the field
loop can apply melon's own task rules to those positions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.constants import COOP_TILE, SHED_TILE, nearest_shed_access
from agent.view import FarmView, Tile

UnitAction = list[object]

# Fewer shed round-trips at scale: day-end auto-drop makes carried units
# safe, and 12 units x 9 stays under the 100-cap shed.
HAND_MULE_LOAD = 9

# Melon lifecycle (engine-verified against kaggle_environments 1.32.4): seed
# $80, first_yield_day 10, max_yield_day 12, max_yield 6; WATER gives +1
# yield only at age in [window_start, max_yield_day], where
# window_start = (max_yield_day + 1) // 2 = 6.
MELON_PLANT_CUTOFF_DAY = 19  # 10-day runway to first yield; the game ends day 29
MELON_PLANT_DAILY_CAP = 2  # melon's own stagger quota; plant_quota (below) is wheat-only
MELON_WINDOW_START = 6
MELON_RIPE_AGE = 12  # max_yield_day
MELON_STALE_AGE = 13  # one past max_yield_day: harvest regardless of watered_today
MELON_MAX_YIELD = 6

# The last game day. Harvested or dropped goods can't reach the shed before
# the market closes once it's this late (the market reads shed contents
# pre-drop), so they sell for $0 — stop manufacturing more of them and rush
# whatever's already carried instead.
ENDGAME_DAY = 29
ENDGAME_MULE_THRESHOLD = 1


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


def _mule(pos: tuple[int, int], unlocked_quadrants: tuple[str, ...]) -> UnitAction:
    target = nearest_shed_access(pos, unlocked_quadrants)
    step = _step_toward(pos, target)
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
    priority: int  # 0 = most urgent
    uses_seed: bool = False
    crop: str = ""  # which seed pool uses_seed draws from; set whenever uses_seed is True


def plant_quota(day: int, active_tiles: int) -> int:
    """Daily cap on NEW plantings — the field's desynchronizer.

    Wheat's ~5-day cycle means a steady state keeps ~1/5 of the field in each
    age; planting more than that in one day builds a synchronized cohort that
    ripens together, swamps the crew with same-day harvests, and collapses
    into plant/harvest oscillation (observed: planted swinging 99->31->93 with
    weed spikes on every burst). Day 0 is exempt — the whole board is empty,
    there is no competing work, and the opening rush is the proven Plan A;
    the quota starts desynchronizing at the first replant wave.
    """
    if day == 0:
        return active_tiles
    return max(1, -(-active_tiles // 5))


def _field_tasks(
    view: FarmView,
    tiles: list[tuple[int, int]],
    melon_tiles: frozenset[tuple[int, int]] = frozenset(),
) -> list[_Task]:
    """Work needed on the target tiles, tagged with an urgency class.

    Priority 0 (most urgent) through 4 (least), first-match-wins per tile.
    Wheat tiles (any tile not in ``melon_tiles``) keep the original rules:
      0 a same-day planting, unwatered — skipping it turns it into a WEED
        overnight, so it must be watered today no matter what else is near.
      1 a ripe tile: watered and age >= 4, or age >= 5 regardless of
        watered_today (a missed final water still converts to harvest
        rather than leaving the tile stuck).
      2 an in-window water (age 2..4, unwatered) — still earns +1 yield.
      3 an empty tile to plant, but only through hour 20 (a later planting
        can't reliably get its own same-day water) and only within what
        remains of today's ``plant_quota``.
      4 a weed to dig.
    Age-1 tiles get no task at all: one unwatered day is safe (the weed
    trap needs two consecutive misses) and age 1 is outside the yield
    window, so watering it would be wasted labor.

    Melon tiles (positions in ``melon_tiles``) use the same priority numbers
    but melon's own crop timeline (first_yield_day 10, max_yield_day 12,
    yield window [6, 12]) and its own flat 2/day planting stagger
    (``MELON_PLANT_DAILY_CAP``) instead of wheat's tile-count-scaled
    ``plant_quota`` — the two staggers are independent, so a slow wheat day
    never starves melon planting or vice versa:
      0 same-day planting, unwatered (identical reasoning to wheat).
      1 ripe: yield_units already maxed, or watered and age >= 12, or
        age >= 13 regardless of watered_today (the missed-final-water case).
      2 an in-window water (age 6..12, unwatered), or one of two anti-weed
        maintenance waters at age 2 or 4 during the 5-day dead zone between
        planting and the yield window — every other day is enough to stay
        under the 2-consecutive-unwatered weed threshold, so ages 1, 3 and
        5 get no task.
      3 an empty melon tile to plant, gated on
        ``day <= MELON_PLANT_CUTOFF_DAY`` as well as hour <= 20 and melon's
        own daily cap.
      4 a weed to dig (shared with wheat — a weed is a weed either way).

    Endgame: on the last day, after hour 20, no P1 (harvest) task is ever
    emitted for either crop — the market reads shed contents pre-drop, so
    anything harvested this late can't reach the shed before the game ends
    and sells for $0 (``dispatch`` makes the matching change on the mule
    side: any carried load at all becomes worth rushing home).
    """
    wheat_planted_today = 0
    melon_planted_today = 0
    for x, y in tiles:
        cell: Tile = view.tiles[y][x]
        if (
            isinstance(cell, dict)
            and cell.get("kind") == "PLANT"
            and int(cell.get("planted_day", -1)) == view.day
        ):
            if (x, y) in melon_tiles:
                melon_planted_today += 1
            else:
                wheat_planted_today += 1
    plant_budget = max(0, plant_quota(view.day, len(tiles)) - wheat_planted_today)
    melon_budget = max(0, MELON_PLANT_DAILY_CAP - melon_planted_today)

    tasks: list[_Task] = []
    for x, y in tiles:
        tile: Tile = view.tiles[y][x]
        is_melon = (x, y) in melon_tiles
        if tile is None:
            if is_melon:
                if view.day <= MELON_PLANT_CUTOFF_DAY and view.hour <= 20 and melon_budget > 0:
                    crop_task = _Task(
                        (x, y), ["PLANT", "MELON"], priority=3, uses_seed=True, crop="MELON"
                    )
                    tasks.append(crop_task)
                    melon_budget -= 1
            elif view.hour <= 20 and plant_budget > 0:
                tasks.append(
                    _Task((x, y), ["PLANT", "WHEAT"], priority=3, uses_seed=True, crop="WHEAT")
                )
                plant_budget -= 1
        elif isinstance(tile, dict) and tile.get("kind") == "WEED":
            tasks.append(_Task((x, y), ["DIG"], priority=4))
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            age = view.day - int(tile.get("planted_day", view.day))
            watered_today = bool(tile.get("watered_today", False))
            yield_units = int(tile.get("yield_units", 0))
            if is_melon:
                if age == 0 and not watered_today:
                    tasks.append(_Task((x, y), ["WATER"], priority=0))
                elif yield_units >= MELON_MAX_YIELD:
                    tasks.append(_Task((x, y), ["HARVEST"], priority=1))
                elif yield_units > 0 and age >= MELON_RIPE_AGE and watered_today:
                    tasks.append(_Task((x, y), ["HARVEST"], priority=1))
                elif yield_units > 0 and age >= MELON_STALE_AGE:
                    tasks.append(_Task((x, y), ["HARVEST"], priority=1))
                elif MELON_WINDOW_START <= age <= MELON_RIPE_AGE and not watered_today:
                    tasks.append(_Task((x, y), ["WATER"], priority=2))
                elif age in (2, 4) and not watered_today:
                    tasks.append(_Task((x, y), ["WATER"], priority=2))
            else:
                if age == 0 and not watered_today:
                    tasks.append(_Task((x, y), ["WATER"], priority=0))
                elif yield_units > 0 and age >= 4 and watered_today:
                    tasks.append(_Task((x, y), ["HARVEST"], priority=1))
                elif yield_units > 0 and age >= 5:
                    tasks.append(_Task((x, y), ["HARVEST"], priority=1))
                elif 2 <= age <= 4 and not watered_today:
                    tasks.append(_Task((x, y), ["WATER"], priority=2))

    if view.day >= ENDGAME_DAY and view.hour > 20:
        tasks = [t for t in tasks if t.priority != 1]
    return tasks


def dispatch(
    view: FarmView,
    tiles: list[tuple[int, int]],
    melon_tiles: frozenset[tuple[int, int]] = frozenset(),
) -> Actions:
    units: list[tuple[int, int]] = [view.farmer, *view.hands]
    chosen: list[UnitAction] = [["PASS"] for _ in units]
    fielded = set(range(len(units)))

    steward_action = _steward(view)
    if steward_action is not None:
        chosen[0] = steward_action
        fielded.discard(0)
    elif _carry_load(view.inventories[0] if view.inventories else {}) > 0:
        chosen[0] = _mule(view.farmer, view.unlocked_quadrants)
        fielded.discard(0)

    # Heavily-loaded hands walk their harvest home before taking new work.
    # On the last day, any carried load at all is mule-worthy: a hand that
    # keeps farming past hour 20 only grows a pile that can't reach the shed
    # before the game ends (see _field_tasks' matching P1 suppression).
    mule_threshold = ENDGAME_MULE_THRESHOLD if view.day >= ENDGAME_DAY else HAND_MULE_LOAD
    for i in range(1, len(units)):
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if _carry_load(inv) >= mule_threshold:
            chosen[i] = _mule(units[i], view.unlocked_quadrants)
            fielded.discard(i)

    tasks = _field_tasks(view, tiles, melon_tiles)
    # Wheat and melon draw from separate seed pools; keyed by the task's own
    # crop so exhausting one never blocks the other's PLANT tasks.
    seed_budgets = {"WHEAT": view.seeds.get("WHEAT", 0), "MELON": view.seeds.get("MELON", 0)}
    claimed: set[tuple[int, int]] = set()
    assigned: dict[int, _Task] = {}

    def claim(i: int, task: _Task) -> None:
        claimed.add(task.tile)
        if task.uses_seed:
            seed_budgets[task.crop] -= 1
        assigned[i] = task

    # Urgency classes are worked strictly in order (0 = most urgent .. 4 =
    # least): a unit claimed in an earlier class is unavailable to every
    # later one, however close it stands to that class's work.
    tasks_by_priority: dict[int, list[_Task]] = {p: [] for p in range(5)}
    for t in tasks:
        tasks_by_priority[t.priority].append(t)

    for priority in range(5):
        class_tasks = tasks_by_priority[priority]
        if not class_tasks:
            continue

        # Pass 1: a unit already standing on one of this class's task tiles
        # keeps it — never walk a closer unit past work another unit is on.
        by_tile = {t.tile: t for t in class_tasks}
        for i, pos in enumerate(units):
            if i not in fielded or i in assigned:
                continue
            task = by_tile.get(pos)
            if task is not None and pos not in claimed:
                if task.uses_seed and seed_budgets[task.crop] <= 0:
                    continue
                claim(i, task)

        # Pass 2: everyone else still available takes the nearest unclaimed
        # task in this class.
        for i, pos in enumerate(units):
            if i not in fielded or i in assigned:
                continue
            best: _Task | None = None
            best_dist = 10**9
            for candidate in class_tasks:
                if candidate.tile in claimed:
                    continue
                if candidate.uses_seed and seed_budgets[candidate.crop] <= 0:
                    continue
                dist = abs(pos[0] - candidate.tile[0]) + abs(pos[1] - candidate.tile[1])
                if dist < best_dist:
                    best, best_dist = candidate, dist
            if best is not None:
                claim(i, best)

    for i, pos in enumerate(units):
        task = assigned.get(i)
        if task is None:
            continue
        move = _step_toward(pos, task.tile)
        chosen[i] = move if move is not None else task.action

    # Nobody idles: leftover carry walks home; a unit parked on LOCKED ground
    # (hand spawns can land on any shed corner, even one behind still-locked
    # land) walks toward the nearest OPEN corner so tomorrow's tile-ops can run.
    for i, pos in enumerate(units):
        if chosen[i] != ["PASS"]:
            continue
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if _carry_load(inv) > 0:
            chosen[i] = _mule(pos, view.unlocked_quadrants)
        elif view.tiles[pos[1]][pos[0]] == "LOCKED":
            step = _step_toward(pos, nearest_shed_access(pos, view.unlocked_quadrants))
            if step is not None:
                chosen[i] = step

    return Actions(farmer=chosen[0], hands=chosen[1:])
