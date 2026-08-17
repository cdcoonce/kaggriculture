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
from typing import Any

from agent.constants import COOP_TILE, SHED_TILE, nearest_shed_access
from agent.view import FarmView, Tile

UnitAction = list[object]

# Fewer shed round-trips at scale: day-end auto-drop makes carried units
# safe, and 12 units x 9 stays under the 100-cap shed.
HAND_MULE_LOAD = 9

# How many WHEAT a unit may draw in one shed visit to feed animals. 1 is
# today's behavior and measurement says keep it there.
#
# The idea was to amortize a shed round trip across a cluster of animals.
# There is no such trip to amortize: corrected recon puts fetch legs at 2.5%
# of movement at 1.48 steps, the SHORTEST bucket on the board -- a fetch is
# usually a unit already standing at the shed. (The earlier 18.4%-at-4.11-
# steps figure was an instrument artifact; legs were being glued across the
# nightly unit wipe.)
#
# Raising it measures worse anyway: PICKUP +56% for flat FEED, reproducible
# across bands and configs. The cause is endogenous -- a batch drains the
# shed into unit inventories and doubles the concurrent fetcher count, so
# the per-fetcher share collapses. It is NOT the mule threshold, which binds
# on under 1% of normal-day fetches; the regression survives intact with the
# mule effectively disabled at hand_mule_load=20.
FEED_BATCH_CAP = 1

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

# Strawberry lifecycle (engine-verified: tests/test_invariants.py claims 1-8,
# plus a full 720-step planting-window probe). seed $100, first_yield_day 10,
# interval 2, max_yield 4, ongoing True.
#
# Production is credited by the END-OF-DAY refresh, never by WATER (claim 2 --
# the engine's watering bonus sits behind a `not ongoing` guard, so melon's
# "water inside the window for +1" rule does NOT transfer). The refresh on day
# C credits yield for day C+1, and fires when (C+1) - planted_day - 10 is a
# non-negative even number, so yield becomes visible at ages 10/12/14/16 and
# the refresh that produced it ran at ages 9/11/13/15 (claim 3).
#
# max_yield_day (10) is dead code here: both of its readers sit behind
# `not ongoing` guards, so nothing is built on it.
STRAWBERRY_MAX_YIELD = 4
STRAWBERRY_TICK_AGES = (9, 11, 13, 15)  # the refresh ages that credit yield
STRAWBERRY_FINAL_AGE = 16  # last age at which yield appears; sweep whatever is left
# Coverage is `day..day+2` inclusive and is read on the refresh day, so
# fertilizing at age 9 covers the age-9 AND age-11 ticks, and age 13 covers
# 13 and 15 -- two units per tile buys the bonus on all four ticks. Ages
# 9/11/13/15 would buy nothing extra and burn two units, because re-applying
# to an already-covered tile still consumes the item (engine FERTILIZE takes
# the unit before the max() that may not move the coverage day at all).
STRAWBERRY_FERTILIZE_AGES = (9, 13)
# Anti-weed maintenance during the ten-day dead zone before the first tick.
# Watering is mandatory on the planting day itself (engine _new_plant seeds
# consecutive_unwatered=1, so an unwatered fresh planting weeds overnight),
# then every other day is enough to stay under the two-consecutive-misses
# threshold. Age 8 rather than a pure even cadence so it runs straight into
# the age-9 tick with no dry gap.
STRAWBERRY_MAINTENANCE_AGES = (2, 4, 6, 8)
# Ticks land at planted_day + 10/12/14/16 and the last end-of-day refresh of
# the game runs on day 28 (step 719 is never processed), so a tile planted by
# day 12 banks all four ticks through the normal end-of-day shed transfer.
# Day 13 still fires all four but puts the last one on day 29, where it banks
# $0 without a manual DROP; later plantings lose ticks off the tail one at a
# time and day 20 yields nothing at all. 12 is therefore the last *fully*
# productive planting day, and the cutoff is set there rather than at the
# first-yield boundary.
STRAWBERRY_PLANT_CUTOFF_DAY = 12
# Sized to fill a zone of any plausible size well inside the cutoff rather
# than to melon's 2/day stagger. Melon's flat cap is what strands its zone:
# at melon 20+ the zone reserves tiles the cap cannot fill for days, and those
# idle tile-days are what makes melon 22/24 gate worse than melon 16-20. A
# strawberry tile is worth more idle-time than a melon one (it must be planted
# by day 12 or it silently loses ticks), so the daily cap must not be the
# binding constraint -- the seed budget in plan.py is, and it self-throttles.
STRAWBERRY_PLANT_DAILY_CAP = 6

# The last game day. Harvested or dropped goods can't reach the shed before
# the market closes once it's this late (the market reads shed contents
# pre-drop), so they sell for $0 — stop manufacturing more of them and rush
# whatever's already carried instead.
ENDGAME_DAY = 29
ENDGAME_MULE_THRESHOLD = 1

# Actions in a day, matching view.py's own ``hour = step % 24``.
HOURS_PER_DAY = 24

# Pasture husbandry (M2a, engine-verified): cow $400, first_yield_day 8,
# interval 2, max_held 6, product MILK; sheep $500, first_yield_day 6,
# interval 3, max_held 6, product WOOL. Both use the PASTURE structure, so a
# built-but-empty pasture tile can hold either species. HARVEST amortizes
# trips (wait for >= 2 units) except very late in the game, when whatever's
# sitting on the tile should just be swept up before the day-29 close.
PASTURE_HARVEST_THRESHOLD = 2
PASTURE_HARVEST_LATE_DAY = 27  # from here on, even a single yield unit is worth the trip


_LIVESTOCK = ("GOOSE", "COW", "SHEEP")


def _carry_load(inv: dict[str, int]) -> int:
    """Sellable units carried (live animals in transit to PLACE are pipeline
    cargo, not produce -- counting them here would let the mule-threshold
    check misclassify a unit mid-carry and route it back to the shed)."""
    return sum(n for item, n in inv.items() if item not in _LIVESTOCK)


def _find_goose_tile(view: FarmView) -> tuple[int, int] | None:
    """The placed goose's tile, or None. Scoped to ``animal == "GOOSE"``
    specifically (M2a: with cow/sheep pasture tiles also on the board, a
    bare "any animal" scan would hijack the farmer into stewarding whatever
    animal the row-major board scan finds first -- cow/sheep chores belong
    to the general priority-task system in ``_field_tasks``, not here)."""
    for y, row in enumerate(view.tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict) and tile.get("animal") == "GOOSE":
                return (x, y)
    return None


def _steward(view: FarmView) -> UnitAction | None:
    """The farmer's goose duty for this turn, or None if none is pending."""
    pos = view.farmer
    inv = view.inventories[0] if view.inventories else {}
    goose_pos = _find_goose_tile(view)

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
    # Which tile each unit slot drew this turn, slot 0 being the farmer.
    # Diagnostic only: nothing reads it to decide an action, and a slot is
    # absent when it drew no task (steward, mule, or genuinely idle). Exposed
    # because the dispatcher is stateless by design, which leaves "did this
    # unit's target move between turns, and why" unanswerable from the action
    # stream alone -- a direction reversal is visible, its cause is not.
    claims: dict[int, tuple[int, int]] = field(default_factory=dict)


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


def _day_budget(view: FarmView, slot: int) -> int:
    """Actions ``slot`` still has today, counting this turn.

    The engine's ``_end_of_day`` empties ``farm["hands"]``, so a hand still
    walking when the day rolls over ceases to exist before it arrives and
    every step it took bought nothing. Recon measures 838 such steps an
    episode against a strong competitor plan's 140 -- the largest single line
    in the walking diff.

    Slot 0 is the farmer, which the engine respawns rather than deletes, so
    it keeps its own scheduling and gets an unbounded budget.

    Known limitation, stated rather than half-fixed: a task carrying
    ``needs_carry`` routes the unit via the shed first, so its real journey is
    longer than the straight-line distance this budget is compared against.
    Those legs are under-protected. The guard therefore never blocks work that
    would have fitted; it only fails to block some that would not.
    """
    if slot == 0:
        return 10**9
    return HOURS_PER_DAY - view.hour


@dataclass(frozen=True)
class _Task:
    tile: tuple[int, int]
    action: UnitAction
    priority: int  # 0 = most urgent
    uses_seed: bool = False
    crop: str = ""  # which seed pool uses_seed draws from; set whenever uses_seed is True
    needs_carry: str = ""  # item that must be in the assigned unit's inventory before ``action``


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


def _pasture_task(
    x: int, y: int, tile: dict[str, Any], day: int, shed: dict[str, int]
) -> _Task | None:
    """The single most urgent chore for a placed animal, or a PLACE task for
    an empty built pasture (drawn from the caller's own running shed-budget
    dict, mutated in place exactly like ``plant_budget``/``melon_budget``).

    P0 FEED an unfed animal — two consecutive unfed days makes it escape
    (the structure survives, the animal doesn't), and skipping FEED on a
    production day also zeroes that day's banked CARE bonus.
    P1 HARVEST once yield_units >= PASTURE_HARVEST_THRESHOLD (amortize
    trips — walking a shed round trip for a single MILK/WOOL unit is a
    worse use of a turn than waiting one more production cycle), or for any
    yield_units >= 1 from PASTURE_HARVEST_LATE_DAY on (the game is ending;
    sweep up whatever's there). P1 also covers PLACE-ing a bought animal
    from the shed onto an empty pasture — same tier as HARVEST: getting an
    animal into production a day sooner is worth about as much as amortizing
    a harvest trip, but neither is as urgent as an active escape risk.
    P2 CARE if not cared today, else COLLECT_FERTILIZER if available.
    """
    if "animal" in tile:
        if not tile.get("fed_today", False):
            return _Task((x, y), ["FEED"], priority=0, needs_carry="WHEAT")
        yield_units = int(tile.get("yield_units", 0))
        if yield_units >= PASTURE_HARVEST_THRESHOLD or (
            yield_units >= 1 and day >= PASTURE_HARVEST_LATE_DAY
        ):
            return _Task((x, y), ["HARVEST"], priority=1)
        if not tile.get("cared_today", False):
            return _Task((x, y), ["CARE"], priority=2)
        if tile.get("fertilizer_available", False):
            return _Task((x, y), ["COLLECT_FERTILIZER"], priority=2)
        return None

    # Built but empty: place a bought animal, cows before sheep.
    if shed.get("COW", 0) > 0:
        shed["COW"] -= 1
        return _Task((x, y), ["PLACE", "COW"], priority=1, needs_carry="COW")
    if shed.get("SHEEP", 0) > 0:
        shed["SHEEP"] -= 1
        return _Task((x, y), ["PLACE", "SHEEP"], priority=1, needs_carry="SHEEP")
    return None


def _strawberry_task(x: int, y: int, tile: dict[str, Any], age: int, day: int) -> _Task | None:
    """The single most urgent chore on an occupied strawberry tile, or None.

    First-match-wins, like every other crop branch, and that ordering carries
    the design:

    P0 the planting day, unwatered. Not optional -- the engine seeds a fresh
       plant with ``consecutive_unwatered = 1``, so skipping this one water
       weeds the tile overnight and burns the $100 seed.
    P1 ``yield_units`` at ``STRAWBERRY_MAX_YIELD``. The engine clamps with
       ``min(max_yield, yield + bonus)``, so a fertilized tile fills to 4 in
       two ticks and every later tick adds nothing until it is drained.
       Harvesting on the cap (ages 12 and 16) is what makes the fertilizer
       bonus worth 8 units a cycle instead of 4 -- lazy harvest silently
       halves it, with no error and no signal.
    P1 anything still on the tile at the final age, fertilized or not: the
       unfertilized path only ever reaches 4 on the last tick, so without
       this sweep it would never be harvested at all.
    P2 water on a tick age. Ordered ahead of FERTILIZE deliberately: the
       engine computes ``fertilized = was_watered and covered``, so an
       unwatered tick day pays no bonus however well fertilized it is, which
       makes water strictly the more valuable of the two. Both still land the
       same day -- tasks regenerate every turn, so the tile takes water on one
       turn and fertilizer on the next.
    P2 anti-weed maintenance water in the dead zone before the first tick.
    P2 fertilize at age 9 or 13 when coverage has lapsed. The comparison is
       against ``day``, matching the engine's own ``fertilized_until_day >=
       current_day`` read, so an already-covered tile is never re-fertilized
       into a wasted unit.
    """
    watered_today = bool(tile.get("watered_today", False))
    yield_units = int(tile.get("yield_units", 0))

    if age == 0 and not watered_today:
        return _Task((x, y), ["WATER"], priority=0)
    if yield_units >= STRAWBERRY_MAX_YIELD:
        return _Task((x, y), ["HARVEST"], priority=1)
    if yield_units > 0 and age >= STRAWBERRY_FINAL_AGE:
        return _Task((x, y), ["HARVEST"], priority=1)
    if age in STRAWBERRY_TICK_AGES and not watered_today:
        return _Task((x, y), ["WATER"], priority=2)
    if age in STRAWBERRY_MAINTENANCE_AGES and not watered_today:
        return _Task((x, y), ["WATER"], priority=2)
    if age in STRAWBERRY_FERTILIZE_AGES and int(tile.get("fertilized_until_day", -1)) < day:
        return _Task((x, y), ["FERTILIZE"], priority=2, needs_carry="FERTILIZER")
    return None


def _field_tasks(
    view: FarmView,
    tiles: list[tuple[int, int]],
    melon_tiles: frozenset[tuple[int, int]] = frozenset(),
    pasture_tiles: frozenset[tuple[int, int]] = frozenset(),
    strawberry_tiles: frozenset[tuple[int, int]] = frozenset(),
    strawberry_plant_daily_cap: int = STRAWBERRY_PLANT_DAILY_CAP,
) -> list[_Task]:
    """Work needed on the target tiles, tagged with an urgency class.

    Priority 0 (most urgent) through 4 (least), first-match-wins per tile.
    Wheat tiles keep the original rules. A standing crop is scheduled off the
    crop it actually is, not off the zone it stands in, so "wheat tile" here
    means a tile holding WHEAT (or empty ground outside
    ``melon_tiles``/``strawberry_tiles``/``pasture_tiles``), whichever zone
    the current land purchases happen to have drawn around it:
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

    Pasture tiles (positions in ``pasture_tiles``) see ``_pasture_task``'s
    FEED/HARVEST/PLACE/CARE/COLLECT_FERTILIZER rules for P0-P2, BUILD_PASTURE
    at P3 while the zone's built count stays under ``len(pasture_tiles)`` --
    the size of the zone actually passed in, not a module-level constant, so
    a ``PolicyConfig`` override of cow_target/sheep_target (which resizes the
    zone the caller passes) is honored without any extra plumbing (mirrors
    wheat/melon's own P3 planting gate) -- and the shared P4 DIG below for a
    weed that spawned on a still-empty designated tile.

    Endgame: on the last day, after hour 20, no P1 (harvest) task is ever
    emitted for any crop or animal — the market reads shed contents
    pre-drop, so anything harvested this late can't reach the shed before
    the game ends and sells for $0 (``dispatch`` makes the matching change
    on the mule side: any carried load at all becomes worth rushing home).
    """
    wheat_planted_today = 0
    melon_planted_today = 0
    strawberry_planted_today = 0
    for x, y in tiles:
        cell: Tile = view.tiles[y][x]
        if (
            isinstance(cell, dict)
            and cell.get("kind") == "PLANT"
            and int(cell.get("planted_day", -1)) == view.day
        ):
            # Keyed off the tile's OWN crop, not zone membership, because a
            # strawberry-zone tile can legitimately hold wheat once the
            # strawberry planting window has closed (see the zone's own
            # fall-through below). Zone membership would then charge that
            # wheat planting to strawberry's stagger and stall the wheat line.
            if cell.get("crop") == "STRAWBERRY":
                strawberry_planted_today += 1
            elif (x, y) in melon_tiles:
                melon_planted_today += 1
            else:
                wheat_planted_today += 1
    plant_budget = max(0, plant_quota(view.day, len(tiles)) - wheat_planted_today)
    melon_budget = max(0, MELON_PLANT_DAILY_CAP - melon_planted_today)
    strawberry_budget = max(0, strawberry_plant_daily_cap - strawberry_planted_today)
    # Shed count PLUS whatever any unit is already carrying: once a unit
    # PICKUPs the last shed animal, the shed's own count drops to 0, but the
    # PLACE task for its target tile must keep being generated (by this same
    # total staying put) or the carrying unit loses its assignment next turn,
    # gets misclassified as idle, and mules the animal straight back into the
    # shed instead of finishing the walk (regression -- see
    # test_carrying_unit_keeps_place_task_after_shed_count_drops_to_zero).
    animal_shed_budget = {
        "COW": view.shed.get("COW", 0) + sum(inv.get("COW", 0) for inv in view.inventories),
        "SHEEP": view.shed.get("SHEEP", 0) + sum(inv.get("SHEEP", 0) for inv in view.inventories),
    }
    tasks: list[_Task] = []
    for x, y in tiles:
        tile: Tile = view.tiles[y][x]
        is_melon = (x, y) in melon_tiles
        is_pasture = (x, y) in pasture_tiles
        is_strawberry = (x, y) in strawberry_tiles and not is_pasture and not is_melon
        if tile is None:
            if is_pasture:
                # Every empty tile in the zone gets built, full stop. This used
                # to carry a `built_count < PASTURE_TILE_TARGET` ceiling, which
                # was BOTH stale and redundant: stale because a PolicyConfig
                # override of cow_target/sheep_target resizes the zone the
                # caller passes without touching that module constant (so a
                # zone larger than the constant had its tail silently stranded
                # -- an animal bought for such a tile can never be PLACEd and
                # sits in the shed all game, the M2a failure mode); redundant
                # because the zone is its own bound. Reaching this line means
                # this zone tile is empty, so with b built and u unbuilt the
                # k-th emission checks b+k < b+u, i.e. k < u -- true for every
                # k it can ever see. A ceiling that cannot fire is not a guard,
                # so it is gone rather than left to read like one.
                tasks.append(_Task((x, y), ["BUILD_PASTURE"], priority=3))
            elif is_melon:
                if view.day <= MELON_PLANT_CUTOFF_DAY and view.hour <= 20 and melon_budget > 0:
                    crop_task = _Task(
                        (x, y), ["PLANT", "MELON"], priority=3, uses_seed=True, crop="MELON"
                    )
                    tasks.append(crop_task)
                    melon_budget -= 1
            elif is_strawberry:
                if (
                    view.day <= STRAWBERRY_PLANT_CUTOFF_DAY
                    and view.hour <= 20
                    and strawberry_budget > 0
                ):
                    tasks.append(
                        _Task(
                            (x, y),
                            ["PLANT", "STRAWBERRY"],
                            priority=3,
                            uses_seed=True,
                            crop="STRAWBERRY",
                        )
                    )
                    strawberry_budget -= 1
                elif view.hour <= 20 and plant_budget > 0:
                    # The reservation trap, fixed rather than inherited. A zone
                    # that keeps claiming tiles it can no longer plant is just
                    # idle ground: melon reserves its whole zone all game
                    # against a flat 2/day cap, which is what strands ~110
                    # tile-days at melon 20 and makes 22/24 gate worse than
                    # 16-20. Strawberry's window CLOSES (day 12, after which a
                    # planting cannot bank a full four ticks), and a tile that
                    # finished its cycle and was dug re-enters as empty ground
                    # well after that -- so once the window is shut, or the
                    # daily cap is spent, an empty zone tile falls through to
                    # wheat instead of being held for a crop that can no
                    # longer profitably go in it.
                    tasks.append(
                        _Task((x, y), ["PLANT", "WHEAT"], priority=3, uses_seed=True, crop="WHEAT")
                    )
                    plant_budget -= 1
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
            # Keyed off the tile's own crop rather than zone membership: a
            # strawberry-zone tile legitimately holds WHEAT once the planting
            # window has closed, and it must then be worked on wheat's much
            # shorter timeline, not strawberry's.
            #
            # Melon needs the same key for a different reason. Its zone is a
            # proximity-ordered PREFIX of target_tiles, and a BUY_LAND
            # re-orders target_tiles -- constants.py pins the pasture zone to
            # a fixed frame precisely because it does. So the melon zone both
            # sheds tiles that already hold a melon and admits tiles that
            # already hold wheat. Under the old `is_melon` key an evicted
            # melon was worked on wheat's rules and HARVESTed from age 5,
            # which the engine rejects until first_yield_day 10 (27.1% of ALL
            # HARVEST fires, measured; 100% melon, 100% out-of-zone), and an
            # admitted wheat matched no melon branch at all so it was never
            # harvested. The zone still decides what gets PLANTED; only the
            # standing crop's own schedule is read off the crop.
            if tile.get("crop") == "STRAWBERRY":
                strawberry_task = _strawberry_task(x, y, tile, age, view.day)
                if strawberry_task is not None:
                    tasks.append(strawberry_task)
            elif tile.get("crop") == "MELON":
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
        elif is_pasture and isinstance(tile, dict) and tile.get("kind") == "PASTURE":
            animal_task = _pasture_task(x, y, tile, view.day, animal_shed_budget)
            if animal_task is not None:
                tasks.append(animal_task)

    if view.day >= ENDGAME_DAY and view.hour > 20:
        tasks = [t for t in tasks if t.priority != 1]
    return tasks


def _carry_leg(
    pos: tuple[int, int],
    item: str,
    task_tile: tuple[int, int],
    view: FarmView,
    quantity: int = 1,
) -> UnitAction:
    """Fetch ``item`` from the shed before working ``task_tile``, mirroring
    the goose steward's fetch-then-carry pattern: walk to shed access, then
    PICKUP, for any task whose action needs something the unit isn't
    already carrying (FEED needs WHEAT; PLACE needs the animal itself).

    Best-effort when the shed is also empty (the feed-reserve top-up or an
    animal purchase hasn't landed yet this turn): walk toward the task tile
    anyway rather than stall — the eventual FEED/PLACE is a harmless no-op
    at the engine level until the carry requirement is actually met.

    ``quantity`` is sized by the caller, not here: the bounds that make a
    batch safe (this turn's mule threshold, the unit's existing load, and how
    many other units are drawing on the same shed) are only visible once
    every task has been assigned. See the batch bounds in ``dispatch``. It is
    1 by default and measurement says leave it there -- see FEED_BATCH_CAP.
    """
    shed_access = nearest_shed_access(pos, view.unlocked_quadrants)
    if view.shed.get(item, 0) > 0:
        if pos == shed_access:
            return ["PICKUP", item, quantity]
        step = _step_toward(pos, shed_access)
        if step is not None:
            return step
        return ["PICKUP", item, quantity]
    step = _step_toward(pos, task_tile)
    return step if step is not None else ["PASS"]


def dispatch(
    view: FarmView,
    tiles: list[tuple[int, int]],
    melon_tiles: frozenset[tuple[int, int]] = frozenset(),
    pasture_tiles: frozenset[tuple[int, int]] = frozenset(),
    strawberry_tiles: frozenset[tuple[int, int]] = frozenset(),
    prior_claims: dict[int, tuple[int, int]] | None = None,
    strawberry_plant_daily_cap: int = STRAWBERRY_PLANT_DAILY_CAP,
    feed_batch_cap: int = FEED_BATCH_CAP,
    hand_mule_load: int = HAND_MULE_LOAD,
) -> Actions:
    """Choose an action for every unit, and report what each one claimed.

    ``prior_claims`` is last turn's ``Actions.claims``. It is the dispatcher's
    only concession to cross-turn state, and it buys exactly one thing: a unit
    already walking toward a tile keeps it instead of re-competing for it from
    scratch. Measured stateless, ~45% of walking turns ended in a retarget,
    and ~95% of those had the old tile still sitting there available -- the
    unit simply lost a fresh greedy comparison it had already won. Every step
    back down a corridor it just walked up is pure waste.

    A claim is deliberately weak. It is honoured only inside the priority
    class that currently holds that tile's task, and only after the
    stand-on-it pass, so it can never outrank a more urgent class nor walk a
    unit past work another unit is already standing on. It evaporates the
    moment its tile stops offering a task.
    """
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
    mule_threshold = ENDGAME_MULE_THRESHOLD if view.day >= ENDGAME_DAY else hand_mule_load
    for i in range(1, len(units)):
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if _carry_load(inv) >= mule_threshold:
            chosen[i] = _mule(units[i], view.unlocked_quadrants)
            fielded.discard(i)

    tasks = _field_tasks(
        view, tiles, melon_tiles, pasture_tiles, strawberry_tiles, strawberry_plant_daily_cap
    )
    # Wheat, melon and strawberry draw from separate seed pools; keyed by the
    # task's own crop so exhausting one never blocks the others' PLANT tasks.
    seed_budgets = {
        "WHEAT": view.seeds.get("WHEAT", 0),
        "MELON": view.seeds.get("MELON", 0),
        "STRAWBERRY": view.seeds.get("STRAWBERRY", 0),
    }
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

        # Pass 1b: a unit that claimed one of this class's tiles last turn
        # keeps it. Ordered after the stand-on-it pass so a unit already
        # standing on the work still wins it, and inside the class loop so a
        # stale claim can never hold a unit back from more urgent work.
        held = prior_claims or {}
        for i in range(len(units)):
            if i not in fielded or i in assigned:
                continue
            tile = held.get(i)
            if tile is None or tile in claimed:
                continue
            task = by_tile.get(tile)
            if task is None:
                continue
            if task.uses_seed and seed_budgets[task.crop] <= 0:
                continue
            claim(i, task)

        # Pass 2: everyone else still available takes the nearest unclaimed
        # task in this class that it can still finish today.
        for i, pos in enumerate(units):
            if i not in fielded or i in assigned:
                continue
            budget = _day_budget(view, i)
            best: _Task | None = None
            best_dist = 10**9
            for candidate in class_tasks:
                if candidate.tile in claimed:
                    continue
                if candidate.uses_seed and seed_budgets[candidate.crop] <= 0:
                    continue
                dist = abs(pos[0] - candidate.tile[0]) + abs(pos[1] - candidate.tile[1])
                # Walk the distance, then spend one action on the work. A hand
                # that cannot do both before the wipe is better left for a
                # nearer task in this class than sent on a walk that is thrown
                # away at midnight -- which is the whole point of the filter
                # living here, in front of the claim, rather than rejecting
                # afterwards: the unit falls through to the next candidate
                # instead of idling.
                if dist + 1 > budget:
                    continue
                if dist < best_dist:
                    best, best_dist = candidate, dist
            if best is not None:
                claim(i, best)

    # Bounds on a batched feed fetch. The batch is off by default (see
    # FEED_BATCH_CAP for why it measures worse); these keep the knob safe to
    # sweep rather than making it a good idea.
    #
    # None of the three is visible from inside _carry_leg:
    #   - the mule threshold, checked against LAST turn's inventory before any
    #     task is assigned, so a batch landing the unit at or above it routes
    #     the unit back to the shed to DROP. Measured to bind on under 1% of
    #     normal-day fetches, so this is a guard, not the reason batching
    #     fails. From ENDGAME_DAY the threshold is 1, which collapses the
    #     batch to a single unit -- that path is most of what this clamp does;
    #   - the wheat this turn's SELL order is already sized against. The engine
    #     applies unit actions before market orders and SELL self-clamps to the
    #     live shed one unit at a time, so an overdraw shrinks the sale with no
    #     signal anywhere. Staying within the unfed-animal count keeps the draw
    #     inside market.py's own `animals_placed + feed_reserve` sell floor;
    #   - the other units fetching this turn, which would each size against the
    #     same stock and collectively overdraw it. This is the term that
    #     actually binds, and batching makes it bind harder by pulling more
    #     units into fetching at once.
    feed_fetchers = [
        i
        for i, t in assigned.items()
        if t.needs_carry == "WHEAT"
        and (view.inventories[i] if i < len(view.inventories) else {}).get("WHEAT", 0) <= 0
    ]
    unfed = sum(1 for t in tasks if t.needs_carry == "WHEAT")
    shed_share = view.shed.get("WHEAT", 0) // max(1, len(feed_fetchers))

    for i, pos in enumerate(units):
        task = assigned.get(i)
        if task is None:
            continue
        inv = view.inventories[i] if i < len(view.inventories) else {}
        if task.needs_carry and inv.get(task.needs_carry, 0) <= 0:
            quantity = 1
            if task.needs_carry == "WHEAT":
                headroom = mule_threshold - 1 - _carry_load(inv)
                quantity = max(1, min(unfed, headroom, shed_share, feed_batch_cap))
            chosen[i] = _carry_leg(pos, task.needs_carry, task.tile, view, quantity)
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

    return Actions(
        farmer=chosen[0],
        hands=chosen[1:],
        claims={i: task.tile for i, task in assigned.items()},
    )
