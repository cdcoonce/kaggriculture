"""meta-clone: economy core plus animal husbandry, pinned to Kaggle episode
90568437's converged ranch (zoo #21/#23/#27, slice 2 of 2 -- registered in
``harness.zoo.SCRIPTED`` at the bottom of this slice, the freeze point after
which this member is immutable: any behavior change is a new member under a
new name).

Land, hire cadence, planting, feed-stock buying, and sell timing are all
pinned to derived metadata from the observed 151k-money converged ranch: one
``BUY_LAND`` on day 9 unconditionally (the day, not a money threshold -- this
slice's animal spending is capped and predictable enough that a money-gated
trigger would still cross the observed ~$2,100 purchase-time balance well
before day 9 and fire early); a per-day hire ramp; a day-by-day PLANT
schedule (WHEAT/MELON/STRAWBERRY only, never CARROT/TOMATO, nothing after
day 24); WHEAT feed-stock top-ups bought from the market from day 8 on; and
price-blind SELL orders confined to the town-tick windows (hours 0-1 and
19-23).

Animal husbandry (slice 2): four purchase bursts (day 0: 3 SHEEP + 1 COW;
day 6: 5 SHEEP + 4 COW; day 9: 1 COW; day 11: 3 SHEEP) build the herd to its
final 11 SHEEP + 6 COW by day 12, never expanded after -- this corrects
issue #17's "8-cow/5-sheep" guess; the real replay herd carries zero geese.
Each burst is followed by ``BUILD_PASTURE``/``PLACE`` on a fixed 17-tile
pasture zone (one tile per animal) carved out of the NW quadrant (see
``PASTURE_TILES`` below). FEED and CARE run 1:1 with herd size every day, no
every-other-day economizing; COLLECT_FERTILIZER and HARVEST (wool/milk) run
as soon as available, no amortization threshold. FERTILIZER/WOOL/MILK sell
price-blind (no price floor, no volume-order convention) in the same
town-tick windows as crops -- unlike crops, there is no index-0
price-sensitive ordering for animal products.

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

Of those 48 tiles, 17 are permanently reserved for pasture (``PASTURE_
TILES``, below), leaving 31 (``CROP_TILES``) for WHEAT/MELON/STRAWBERRY.
The pasture zone is confined to the NW quadrant only (never NE): the first
animal burst fires day 0, nine days before ``BUY_LAND`` unlocks NE, and a
pasture tile placed in NE would read the engine's ``"LOCKED"`` sentinel and
never actually build. NW alone has 24 non-shed tiles, comfortably more than
the 17 the herd needs.

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
BUY_PRODUCT_CAP = 25  # enough to cover a full 17-animal feed day from the market alone
SELL_HOURS = frozenset({0, 1, 19, 20, 21, 22, 23})  # town-tick windows
# Engine default ``shedCapacity`` (kaggle_environments 1.32.4). The shed is a
# single 100-item pool shared by produce, fertilizer AND bought-but-unplaced
# animals, and ``_commit_unit`` fails a BUY_ANIMAL outright once it is full --
# so unbounded WHEAT stockpiling would silently block the herd build-out.
SHED_CAPACITY = 100

NW_SHED: Position = (4, 4)
NE_SHED: Position = (5, 4)
SHED_ACCESS_TILES: tuple[Position, ...] = (NW_SHED, NE_SHED)

HARVEST_AGE: dict[str, int] = {"WHEAT": 4, "MELON": 12, "STRAWBERRY": 10}
WHEAT_FIRST_YIELD_DAY = 2  # engine's own hard HARVEST gate for WHEAT -- age below this is a no-op
SEED_COST: dict[str, int] = {"WHEAT": 10, "MELON": 80, "STRAWBERRY": 100}

# Animal husbandry (engine-verified, kaggle_environments 1.32.4): cow $400,
# sheep $500. Herd targets sum to exactly the pasture zone size -- one
# animal per pasture tile.
COW_PRICE = 400
SHEEP_PRICE = 500
COW_HERD_TARGET = 6
SHEEP_HERD_TARGET = 11
PASTURE_TILE_TARGET = COW_HERD_TARGET + SHEEP_HERD_TARGET  # 17
ANIMAL_BUY_LAST_DAY = 12  # hard cutoff -- herd "never expanded after" day 12
FEED_RESERVE = 8  # buffer of shed WHEAT kept unsold once any animal is placed
# WHEAT units a unit picks up per shed trip when it is dispatched to FEED.
# The engine puts no cap on inventory (only the shed is capped), and FEED
# consumes exactly 1 WHEAT per animal per day, so one trip can service a
# whole run of adjacent pasture tiles. Picking up 1-per-FEED instead costs a
# full shed round trip per animal, which measurably could not keep 17 animals
# fed inside a 24-turn day and let animals starve out of the herd.
FEED_BATCH = 6
# Units allowed to be *newly* dispatched to a FEED they can't yet perform
# (i.e. sent to the shed to fetch WHEAT) on any one turn. Uncapped, every
# idle unit stampedes to the shed the moment the herd's feeding starts.
FEED_FETCHERS_MAX = 4
# Days of feed the market top-up aims to keep on hand. Above this the shed
# fills with WHEAT nobody will eat, crowding out the shared shed capacity
# BUY_ANIMAL needs (see ``SHED_CAPACITY``).
WHEAT_STOCK_DAYS = 2
# Cash floor kept below ANIMAL/emergency-seed spending: the pinned hire
# cadence (``_hires_for_day``) queues its full day target as market orders
# every turn regardless of affordability, and the engine's 10-order-per-turn
# cap means a money-starved day (nothing affordable, so nothing ever
# succeeds to shrink the queue) can flood every slot with failing HIRE
# orders indefinitely, leaving zero room for a SELL order to ever run again
# -- a permanent zero-money deadlock, observed when this fixture's animal
# spending was allowed to drain money all the way to $0. Never spending the
# last of this reserve on an animal/emergency-seed purchase keeps enough
# cash in play for the hire queue to keep shrinking and SELL orders to keep
# getting a turn.
ANIMAL_CASH_RESERVE = 100
LAND_COST = 1000  # engine-verified: LAND_PRICES[0], the sole BUY_LAND's cost
# Through LAND_DAY, animal spending must also leave the day-9 BUY_LAND
# purchase affordable -- BUY_LAND only ever fires once, at day == LAND_DAY
# hour == 0 (module docstring/``TestLandTiming`` pin this exact one-shot
# timing), with no retry on later turns if that single attempt is
# unaffordable. Left unguarded, the day-0/day-6 animal bursts alone drain
# money well below $1,000 by day 9 (observed: a $24 balance at day 9 hour
# 0), permanently forfeiting NE and its 24 tiles for the rest of the
# episode -- collapsing this fixture's entire crop economy down to NW's 7
# leftover (non-pasture) tiles and cascading into the wheat-feed shortfalls
# this reserve exists to prevent.
PRE_LAND_CASH_RESERVE = LAND_COST + ANIMAL_CASH_RESERVE
# ...but only from this day on. Holding the land reserve back from the day-6
# burst onwards starves that burst of the very cash the replay spends on it
# ("~$1.6-3.5k on hand"), and the burst is what puts the herd -- this
# fixture's actual revenue engine -- on schedule for day 12. Two days of
# fertilizer/wool/milk income is ample to rebuild $1,000 before day 9 hour 0.
PRE_LAND_RESERVE_FIRST_DAY = 8

# Day -> incremental herd purchase, from ep 90568437's observed bursts.
# Cumulative through day 11 already reaches the final 11 SHEEP + 6 COW; the
# ANIMAL_BUY_LAST_DAY cutoff above is a defensive belt-and-suspenders bound,
# not the mechanism that caps herd size (the cumulative-target comparison in
# ``agent()`` does that on its own).
ANIMAL_BURSTS: dict[int, dict[str, int]] = {
    0: {"SHEEP": 3, "COW": 1},
    6: {"SHEEP": 5, "COW": 4},
    9: {"COW": 1},
    11: {"SHEEP": 3},
}


def _cumulative_animal_target(day: int, species: str) -> int:
    """Herd size ``species`` should have reached by the end of ``day``, per
    the observed burst table -- the sum of every burst on or before
    ``day``."""
    return sum(
        counts.get(species, 0) for burst_day, counts in ANIMAL_BURSTS.items() if burst_day <= day
    )


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


def _compute_pasture_zone() -> tuple[Position, ...]:
    """Candidate pasture sites, nearest ``NW_SHED`` first: every non-shed
    tile of the NW quadrant, never NE (module docstring explains why: the
    first animal burst fires day 0, well before NE unlocks on day 9, and a
    pasture tile placed on a still-``"LOCKED"`` tile would never actually
    build).

    Candidates, not a reservation: the herd claims from the front of this
    list only as fast as it actually grows (see ``_pasture_sites``)."""
    candidates = [(x, y) for y in range(5) for x in range(5) if (x, y) != NW_SHED]

    def sort_key(t: Position) -> tuple[int, int, int]:
        return (abs(t[0] - NW_SHED[0]) + abs(t[1] - NW_SHED[1]), t[1], t[0])

    candidates.sort(key=sort_key)
    return tuple(candidates)


PASTURE_ZONE = _compute_pasture_zone()


def _pasture_sites(
    is_pasture: Callable[[Position], bool],
    is_cropped: Callable[[Position], bool],
    wanted: int,
) -> list[Position]:
    """The tiles reserved for the herd this turn: every already-built
    pasture, plus the front of ``PASTURE_ZONE`` out to ``wanted`` sites,
    capped at ``PASTURE_TILE_TARGET``.

    Growing the reservation with the herd rather than staking all 17 up
    front is load-bearing. NW has only 24 non-shed tiles and NE stays
    ``"LOCKED"`` until the day-9 ``BUY_LAND``, so a static 17-tile
    reservation leaves the crop side seven workable tiles for the first nine
    days -- fewer than the pinned ``PLANT_TABLE`` asks for on day 0 alone,
    with most hands idling for want of anywhere to plant.

    A tile already carrying a crop is skipped rather than reserved, and the
    zone extends further down NW instead -- there are 24 candidates for 17
    sites, so there is room to route around. Reserving a cropped tile anyway
    strands the animal it was meant for: a MELON does not come off until age
    12 and a STRAWBERRY is an ongoing crop that never clears the tile at
    all, so the site never becomes buildable. Measured, one day-0 melon
    sitting on a late-reserved site held the 17th animal in the shed from
    day 12 to day 22. Already-built pastures always stay in the list, so the
    zone never churns when an animal is lost."""
    claimed = {pos for pos in PASTURE_ZONE if is_pasture(pos)}
    target = min(wanted, PASTURE_TILE_TARGET)
    for pos in PASTURE_ZONE:
        if len(claimed) >= target:
            break
        if pos in claimed or is_cropped(pos):
            continue
        claimed.add(pos)
    return [pos for pos in PASTURE_ZONE if pos in claimed]


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


# Pasture need-tokens that require the assigned unit to be carrying a
# specific item before the action can fire, and the item each one needs --
# mirrors the champion dispatcher's ``needs_carry``/``_carry_leg`` pattern
# (packages/agent/src/agent/dispatch.py), reused here per the issue's
# explicit authorization to clone the champion's dispatch *mechanics*, never
# its strategy numbers.
CARRY_ITEM: dict[str, str] = {
    "P_FEED": "WHEAT",
    "P_PLACE_COW": "COW",
    "P_PLACE_SHEEP": "SHEEP",
}

# Pasture dispatch order, most urgent first. Every animal exposes exactly one
# need per turn (the elif chain in ``agent()``), so this ordering is what
# decides which chore the whole herd works through first on any given turn:
# an animal still sitting in the shed earns nothing, an unfed animal is on a
# two-day escape clock, and the rest are once-a-day chores that can wait.
PASTURE_PRIORITY: tuple[str, ...] = (
    "P_PLACE_COW",
    "P_PLACE_SHEEP",
    "P_FEED",
    "P_BUILD_PASTURE",
    "P_DIG",
    "P_HARVEST",
    "P_CARE",
    "P_COLLECT_FERTILIZER",
)
PASTURE_NEEDS = frozenset(PASTURE_PRIORITY)

# Crop needs that pre-empt every other crop need while any of them is
# outstanding. WATER is the one irreversible crop chore: the engine turns a
# plant left two days unwatered into a WEED, losing the tile and everything
# already invested in it, and the loss compounds -- fewer live plants the
# next day, then fewer still. A harvest or a replant deferred an hour costs
# nothing (accrued ``yield_units`` sit on the tile indefinitely).
# HARVEST_EMERGENCY joins it because a starving animal is on the same kind
# of clock.
CROP_URGENT = frozenset({"WATER", "HARVEST_EMERGENCY", "DIG"})

# Ranch crew sizing. The pasture sits in NW beside the shed while the crop
# side spreads across NW+NE, so a unit that alternates between them spends
# most of its day walking: measured against the same economy with no herd at
# all, letting all hands serve both sides dropped distinct tiles watered on
# day 26 from 22 to 8, weeding out plants faster than the pinned PLANT_TABLE
# replaces them. Dedicating the first ``ranch`` unit indices to the herd
# (index 0 is the farmer, which always respawns on the NW shed tile) keeps
# each group inside one locality.
#
# Sized off the herd, not off the chores still outstanding this turn: the
# outstanding count falls as the morning's work gets done, so sizing on it
# shrinks the crew back to its floor by mid-afternoon and leaves the day's
# CARE and COLLECT_FERTILIZER rounds unfinished (measured: CARE finishing at
# 7 of 17). One hand comfortably covers three animals' FEED + CARE +
# COLLECT_FERTILIZER within a 24-turn day at pasture-to-shed distances.
RANCH_ANIMALS_PER_UNIT = 3
RANCH_CREW_MIN = 2

# How far ahead of the burst table the pasture reservation runs. A site has
# to be free of crops, then built, before the animal it is for can be
# placed, and a MELON sown on it will not clear until day 12 -- so the
# reservation has to be staked before the crop side sows the tile, not when
# the animal turns up in the shed. Six days is the gap between the day-0 and
# day-6 bursts, i.e. one full burst of warning.
PASTURE_RESERVE_LOOKAHEAD = 6

# Pasture need-tokens that map directly to a fixed action, no carry needed.
DIRECT_ACTION: dict[str, list[str]] = {
    "P_FEED": ["FEED"],
    "P_CARE": ["CARE"],
    "P_HARVEST": ["HARVEST"],
    "P_COLLECT_FERTILIZER": ["COLLECT_FERTILIZER"],
    "P_BUILD_PASTURE": ["BUILD_PASTURE"],
    "P_DIG": ["DIG"],
    "P_PLACE_COW": ["PLACE", "COW"],
    "P_PLACE_SHEEP": ["PLACE", "SHEEP"],
    # Distinct need-token from plain "HARVEST" only so the priority-dispatch
    # pass below can single it out; the engine action is identical.
    "HARVEST_EMERGENCY": ["HARVEST"],
}


def make_agent() -> Callable[[Any], dict[str, Any]]:
    """Return a fresh meta-clone economy-core agent callable with its own
    episode-scoped watering tracker closed over (see module docstring for
    why the day-27+ wind-down cap needs real cross-turn memory: HARVEST
    clears WHEAT/MELON tiles back to empty, so a tile watered earlier today
    then harvested-and-cleared would otherwise silently vanish from a
    board-rescan-based count, letting the cap replenish mid-day)."""
    state: dict[str, Any] = {"day": -1, "watered_today": set(), "assignments": {}}

    def agent(obs: Any) -> dict[str, Any]:
        player = obs["player"]
        farm = obs["farms"][player]
        private = obs["private"]
        seeds = private["seeds"]
        shed = private["shed"]
        inventories = private["inventories"]
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
            state["assignments"] = {}

        # Placed-herd size and feed-emergency detection: BUY_PRODUCT WHEAT
        # (the economy slice's feed-stock top-up) doesn't start until day 8
        # (``BUY_PRODUCT_FIRST_DAY``), but the first animal bursts land days
        # 0-1 -- well before the day-0 WHEAT planting reaches its normal
        # near-max-age harvest window. Without an escape hatch, an animal
        # placed day 1 starves (2 consecutive unfed days) before day 4's
        # first harvest ever lands. ``feed_critical`` gates two narrow,
        # early-game-only overrides below: harvesting WHEAT the instant any
        # yield exists (rather than waiting for ``HARVEST_AGE``), and
        # rushing any carried WHEAT to the shed instead of batching to
        # ``CARRY_THRESHOLD`` -- both inactive once shed+carried WHEAT
        # covers the placed herd (the steady-state case from day 8 on).
        def _is_pasture(pos: Position) -> bool:
            tile = tile_at(*pos)
            return isinstance(tile, dict) and tile.get("kind") == "PASTURE"

        def _has_animal(pos: Position) -> bool:
            tile = tile_at(*pos)
            return isinstance(tile, dict) and "animal" in tile

        carried_species = {
            species: sum(inv.get(species, 0) for inv in inventories if isinstance(inv, dict))
            for species in ("COW", "SHEEP")
        }
        owned_unplaced = sum(
            shed.get(species, 0) + carried_species[species] for species in ("COW", "SHEEP")
        )
        animals_placed = sum(1 for pos in PASTURE_ZONE if _has_animal(pos))
        # Claim one site per animal the burst table says this fixture should
        # own by tonight -- not just per animal already bought. Anything
        # beyond that stays available to the crop side, which needs every NW
        # tile it can get before the day-9 BUY_LAND unlocks NE (see
        # ``_pasture_sites``).
        #
        # Sizing on animals already bought instead makes BUILD_PASTURE
        # strictly trail the purchase, and PLACE trail the build: measured,
        # every burst landed in the shed one day and reached the pasture the
        # next, which walks the herd past its day-12 completion date.
        # Building against the schedule lets a burst be homed the hour it
        # arrives, and costs nothing but a few free BUILD_PASTURE actions.
        scheduled_herd = sum(
            _cumulative_animal_target(day + PASTURE_RESERVE_LOOKAHEAD, species)
            for species in ("COW", "SHEEP")
        )
        pasture_tiles = _pasture_sites(
            _is_pasture,
            lambda pos: _is_plant(tile_at(*pos)),
            max(animals_placed + owned_unplaced, scheduled_herd),
        )
        pasture_set = frozenset(pasture_tiles)
        # Reserved sites are closed to NEW plantings (``empty_tiles`` below
        # draws from this list), but anything already growing on one stays on
        # the crop side's books so it keeps getting watered and harvested.
        crop_tiles = [
            pos for pos in ALL_TILES if pos not in pasture_set or _is_plant(tile_at(*pos))
        ]
        carried_wheat_total = sum(
            inv.get("WHEAT", 0) for inv in inventories if isinstance(inv, dict)
        )
        # A small buffer above the bare per-day minimum (not just
        # ``animals_placed``): a single trickle of emergency-harvested WHEAT
        # exactly matching herd size leaves zero slack for the multi-turn
        # harvest-carry-feed pipeline to keep up with several animals'
        # feeding windows landing close together, which was observed to
        # starve some animals even while the bare-minimum threshold was
        # technically being met turn to turn.
        feed_critical = (
            animals_placed > 0
            and (shed.get("WHEAT", 0) + carried_wheat_total) < animals_placed + FEED_RESERVE
        )

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
        empty_tiles = [pos for pos in crop_tiles if tile_at(*pos) is None]
        plantable_today = set(empty_tiles[:total_plant_remaining])

        # Emergency WHEAT overplanting: while feed_critical, claim additional
        # otherwise-idle empty crop tiles (beyond the pinned PLANT_TABLE's
        # daily quota) for WHEAT specifically. The pinned table's own WHEAT
        # allocation across days ~9-16 is thin (a handful of tiles, sharing
        # the crop pool with a much heavier MELON/STRAWBERRY quota those same
        # days) -- too thin on its own to support a growing herd's daily
        # feed draw once the herd outgrows the day-0/day-4 plantings' yield.
        # Bounded to twice ``animals_placed`` extra tiles (not just 1x) so a
        # single trigger builds a real surplus rather than merely breaking
        # even for one day -- this still can't balloon into silently
        # replacing the pinned economy's own crop mix, since it only ever
        # claims tiles the pinned PLANT_TABLE quota left idle that day.
        #
        # Bounded by ``LAST_PLANT_DAY`` like every other PLANT: the pinned
        # economy stops planting after day 24, and an emergency top-up is
        # not a licence to break that window -- a WHEAT sown on day 25 could
        # not be harvested before the episode ends anyway.
        emergency_wheat_tiles: set[Position] = set()
        if feed_critical and day <= LAST_PLANT_DAY:
            remaining_empty = [pos for pos in empty_tiles if pos not in plantable_today]
            emergency_wheat_tiles = set(remaining_empty[: 2 * animals_placed])

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
        for pos in crop_tiles:
            tile = tile_at(*pos)
            if tile == "LOCKED":
                continue
            if _is_weed(tile):
                need_by_pos[pos] = "DIG"
                continue
            if tile is None:
                if pos in plantable_today:
                    need_by_pos[pos] = "PLANT"
                elif pos in emergency_wheat_tiles:
                    need_by_pos[pos] = "PLANT_EMERGENCY_WHEAT"
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
                yield_units = tile.get("yield_units", 0)
                age = day - tile.get("planted_day", day)
                # Emergency-feed exception: bypass the normal harvest-age
                # gate for WHEAT specifically while an animal is starving
                # for lack of any other feed source (see the
                # ``feed_critical`` note above) -- a partial early harvest
                # yields less WHEAT per tile than waiting for max age, but a
                # starved animal is gone forever, so any WHEAT beats none.
                # Still bounded below by the engine's own hard HARVEST gate
                # (``first_yield_day``) -- attempting HARVEST any earlier is
                # a silent engine no-op, which would otherwise strand a
                # unit's commitment on a tile that can never be resolved.
                emergency = crop == "WHEAT" and feed_critical and age >= WHEAT_FIRST_YIELD_DAY
                if yield_units > 0 and (age >= harvest_age or emergency):
                    need_by_pos[pos] = "HARVEST_EMERGENCY" if emergency else "HARVEST"

        # Pasture chores: FEED (P0, every unfed animal), HARVEST wool/milk as
        # soon as any yield is available (no amortization threshold -- the
        # issue is explicit that this fixture doesn't economize husbandry
        # trips), CARE, then COLLECT_FERTILIZER (feed-independent byproduct,
        # generated daily by the engine's own end-of-day refresh regardless
        # of whether the animal was fed). Built-but-empty pasture tiles PLACE
        # a bought animal (cows before sheep, matching the champion
        # dispatcher's own convention).
        pasture_shed_budget = {
            "COW": shed.get("COW", 0) + carried_species["COW"],
            "SHEEP": shed.get("SHEEP", 0) + carried_species["SHEEP"],
        }
        # Escape risk per unfed animal: the engine removes an animal once
        # ``consecutive_unfed`` reaches 2 at the nightly refresh, so an animal
        # already carrying 1 is one missed day from being gone for good and
        # must be served ahead of a herdmate that ate yesterday.
        unfed_risk: dict[Position, int] = {}
        for pos in pasture_tiles:
            tile = tile_at(*pos)
            if _is_plant(tile):
                # Reserved, but a crop is still standing on it -- leave it to
                # the crop scan above, which waters and harvests it. It turns
                # up here as buildable once that harvest clears the tile.
                continue
            if _is_weed(tile):
                need_by_pos[pos] = "P_DIG"
                continue
            if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile:
                # PLACE (not the BUY_ANIMAL purchase itself) waits for day
                # >= 1: a day-0-placed animal is unfed on both day 0 and
                # day 1 -- the earliest any WHEAT can exist is day 2
                # (``WHEAT_FIRST_YIELD_DAY``) -- so it hits two consecutive
                # unfed days and escapes at the day-1/day-2 boundary with
                # zero chance of ever being fed. A day-1 placement is unfed
                # on day 1 but has a real shot at day 2's first possible
                # harvest before ITS two-unfed-day clock runs out.
                if day >= 1 and pasture_shed_budget["COW"] > 0:
                    pasture_shed_budget["COW"] -= 1
                    need_by_pos[pos] = "P_PLACE_COW"
                elif day >= 1 and pasture_shed_budget["SHEEP"] > 0:
                    pasture_shed_budget["SHEEP"] -= 1
                    need_by_pos[pos] = "P_PLACE_SHEEP"
                continue
            if isinstance(tile, dict) and "animal" in tile:
                if not tile.get("fed_today", False):
                    need_by_pos[pos] = "P_FEED"
                    unfed_risk[pos] = int(tile.get("consecutive_unfed", 0))
                elif int(tile.get("yield_units", 0)) > 0:
                    need_by_pos[pos] = "P_HARVEST"
                elif not tile.get("cared_today", False):
                    need_by_pos[pos] = "P_CARE"
                elif tile.get("fertilizer_available", False):
                    need_by_pos[pos] = "P_COLLECT_FERTILIZER"
                continue
            # Every still-empty claimed site needs building. ``pasture_tiles``
            # is already sized to the herd actually owned, so this is the
            # build-on-demand the small pinned crew can afford -- unlike the
            # champion dispatcher, which eagerly builds its whole zone from
            # turn 0 on a much larger crew.
            if tile is None:
                need_by_pos[pos] = "P_BUILD_PASTURE"

        feed_pending = bool(unfed_risk)
        # Which carried items any outstanding chore is waiting on this turn.
        carry_demand: dict[str, bool] = {}
        for need_kind in need_by_pos.values():
            carry_item = CARRY_ITEM.get(need_kind)
            if carry_item is not None:
                carry_demand[carry_item] = True

        unit_positions: list[Position] = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]

        def _inv_of(idx: int) -> dict[str, Any]:
            inv = inventories[idx] if idx < len(inventories) else {}
            return inv if isinstance(inv, dict) else {}

        def _haul_load(inv: dict[str, Any]) -> int:
            """How much sellable produce this unit is hauling to the shed.

            WHEAT counts only once the whole herd has eaten: while any animal
            is still unfed, carried WHEAT is feed stock in transit and its
            carrier must not be diverted into a shed run -- that round trip
            is exactly what ``FEED_BATCH`` exists to avoid. Nothing is lost
            by holding it, since the engine drops every unit inventory into
            the shed at the nightly refresh anyway."""
            load: int = inv.get("MELON", 0) + inv.get("STRAWBERRY", 0)
            if not feed_pending:
                load += inv.get("WHEAT", 0)
            return load

        # Persistent per-unit task commitment (keyed by unit index, reset on
        # every day-boundary crossing since hands are daily rentals -- same
        # closure pattern as ``state["watered_today"]``). Recomputing the
        # nearest-unclaimed target from scratch every turn (as crop tiles
        # alone could get away with, since the whole universe was
        # homogeneous) livelocks once pasture and crop tiles compete for the
        # same small pool of units: two units a single step apart can keep
        # trading each other's targets turn after turn as their positions
        # shift, each abandoning a half-finished walk (or a fetch-then-carry
        # detour) the instant a marginally closer alternative appears,
        # neither ever arriving. Committing a unit to one target until it's
        # fulfilled (or vanishes) fixes that -- once assigned, distance to
        # that target only ever shrinks, so nothing else can outcompete it.
        assignments: dict[int, Position] = state["assignments"]
        for idx in list(assignments.keys()):
            if idx >= len(unit_positions) or assignments[idx] not in need_by_pos:
                del assignments[idx]
                continue
            # A HARVEST clears its tile back to empty, which the need scan
            # above can immediately re-populate with a fresh PLANT (or
            # PLANT_EMERGENCY_WHEAT) need at that SAME position -- so the
            # "target still in need_by_pos" check above alone doesn't catch
            # a stale assignment here, since the position is still a valid
            # need, just a different one. Left unchecked, the unit that just
            # harvested silently pivots to replanting the same tile instead
            # of carrying its harvest to the shed, stranding a starving
            # animal's only feed for several extra turns. Release the
            # assignment whenever the unit is already carrying enough to
            # warrant a shed run so it falls into the mule-home branch below
            # this turn instead.
            if _haul_load(_inv_of(idx)) >= CARRY_THRESHOLD:
                del assignments[idx]
                continue
            # Carried-item bookkeeping, in ``PASTURE_PRIORITY`` order so a
            # unit holding both an animal and its feed places the animal
            # first. Both rules below exist because a carried item is the
            # ONLY way its chore can ever happen: once the shed is empty,
            # whichever unit happens to hold the last WHEAT (or the last
            # SHEEP) is the herd's sole means of getting that chore done.
            inv_now = _inv_of(idx)
            assigned_need = need_by_pos[assignments[idx]]
            assigned_item = CARRY_ITEM.get(assigned_need)
            # Free a carrier committed to anything other than the chore its
            # cargo unblocks. Left committed it keeps watering, caring,
            # collecting -- with the herd's dinner in its pockets. Measured:
            # 40 WHEAT stranded across idle inventories against an empty
            # shed with only 10 of 12 animals fed, and a hand carrying two
            # SHEEP around all day while two built pastures stood empty.
            #
            # Only a CROP commitment is broken this way. A hand already on a
            # pasture tile is left to finish that animal: the engine exposes
            # one need per animal at a time, so FEED then CARE then
            # COLLECT_FERTILIZER all land on the tile it is already standing
            # on, three chores for zero walking. Yanking it to the next
            # hungry animal after the FEED costs a return trip for each of
            # the other two, and measured, that alone dropped the day's CARE
            # round from 17 of 17 to 9.
            stale_cargo = assigned_need not in PASTURE_NEEDS and any(
                carry_demand.get(item, False) and inv_now.get(item, 0) > 0
                for item in ("COW", "SHEEP", "WHEAT")
            )
            if stale_cargo:
                del assignments[idx]
                continue
            # ...and conversely, drop a commitment the unit cannot possibly
            # discharge: the chore needs an item it does not hold and the
            # shed has none to fetch. ``_carry_leg`` degrades to a step
            # toward the task tile in that case, which for a unit already
            # standing on it is a PASS -- so it camps on a starving animal
            # (or an empty pasture) indefinitely while the item it needs
            # sits in a herdmate's pocket.
            if (
                assigned_item is not None
                and inv_now.get(assigned_item, 0) <= 0
                and shed.get(assigned_item, 0) <= 0
            ):
                del assignments[idx]
        committed = set(assignments.values())

        # Pasture-first dispatch pass (issue #27). The per-unit loop below
        # lets each unit greedily grab whatever need is nearest to ITS OWN
        # position, which is fine while every tile is a crop tile but ranks
        # a routine WATER above a starving animal once the pasture competes
        # for the same units. Here the needs pick the units instead, in
        # ``PASTURE_PRIORITY`` order (most-at-risk animal first within
        # P_FEED), so herd work is placed before crop work gets a look-in --
        # the herd is this fixture's actual revenue engine, and unlike a
        # crop chore an animal chore missed twice running loses the animal
        # outright.
        #
        # Carry-aware, and deliberately rate-limited: a need that requires a
        # carried item prefers a unit already holding it, and only
        # ``FEED_FETCHERS_MAX`` units per turn are newly sent to the shed to
        # fetch it. Without that cap every idle unit stampedes to the shed
        # the moment the herd gets hungry, and the crop side stalls for a
        # whole morning. The budget is per item, not shared: PLACE outranks
        # FEED in ``PASTURE_PRIORITY``, so one pooled counter would let a
        # build-out burst spend the whole turn's fetch allowance and leave
        # the herd's feed couriers undispatched.
        unassigned_idxs = [idx for idx in range(len(unit_positions)) if idx not in assignments]
        fetchers: dict[str, int] = {}
        pasture_queue = [
            pos
            for need_kind in PASTURE_PRIORITY
            for pos in sorted(
                (p for p, n in need_by_pos.items() if n == need_kind),
                key=lambda p: (-unfed_risk.get(p, 0), TILE_INDEX.get(p, 0)),
            )
        ]
        # The ranch crew: the low unit indices, sized off the herd (see
        # ``RANCH_ANIMALS_PER_UNIT``). Only these units get pulled onto
        # pasture work, so the rest never yo-yo between the NW pasture and
        # an NE crop tile.
        herd_to_service = animals_placed + owned_unplaced
        ranch_size = (
            min(
                len(unit_positions),
                max(RANCH_CREW_MIN, -(-herd_to_service // RANCH_ANIMALS_PER_UNIT)),
            )
            if pasture_queue
            else 0
        )
        ranch_idxs = range(ranch_size)
        for pos in pasture_queue:
            if pos in committed or not unassigned_idxs:
                continue
            item = CARRY_ITEM.get(need_by_pos[pos])
            pool = [idx for idx in unassigned_idxs if idx in ranch_idxs]
            if item is not None:
                # Carriers are drawn from the whole crew, not just the ranch:
                # in the early game the only WHEAT in existence is what a
                # crop hand just emergency-harvested out of the field, and
                # that hand is then the herd's sole feed courier.
                carriers = [idx for idx in unassigned_idxs if _inv_of(idx).get(item, 0) > 0]
                if carriers:
                    pool = carriers
                elif not pool:
                    continue
                elif shed.get(item, 0) > 0 and fetchers.get(item, 0) < FEED_FETCHERS_MAX:
                    fetchers[item] = fetchers.get(item, 0) + 1
                else:
                    continue
            if not pool:
                continue
            px, py = pos
            best_idx = min(
                pool,
                key=lambda idx: (
                    abs(unit_positions[idx][0] - px) + abs(unit_positions[idx][1] - py),
                    idx,
                ),
            )
            assignments[best_idx] = pos
            committed.add(pos)
            unassigned_idxs.remove(best_idx)

        # Crop dispatch stays unit-first -- each remaining unit takes the
        # nearest job -- because locality is what makes the crop side
        # affordable at all: running crops through the needs-pick-units pass
        # above instead drags hands clear across the board and back, and was
        # measured to cost four head off the day-12 herd for no watering
        # gain. Priority is expressed by narrowing the candidate set: while
        # any plant is still dry, dry plants are the ONLY crop work on offer
        # (see ``CROP_URGENT``).
        #
        # A ranch hand with no pasture chore this turn is not sent across the
        # board -- it takes crop work in its own quadrant (NW, where the
        # pasture is) or nothing. Sending it to an NE tile commits it for the
        # several turns of walking that get it there and back, which is the
        # cross-map churn the crew split exists to stop; leaving it idle
        # instead wastes a hand every turn a FEED is gated on WHEAT nobody
        # has fetched yet.
        crop_positions = [p for p in need_by_pos if need_by_pos[p] not in PASTURE_NEEDS]
        ranch_reach = [p for p in crop_positions if p[0] <= NW_SHED[0]]
        for idx, pos in enumerate(unit_positions):
            if idx in assignments:
                continue
            # A unit that just finished a task and is now carrying enough to
            # warrant a shed run must not be handed a fresh field
            # assignment -- otherwise it walks straight past the shed toward
            # the next task with a full pack. Mule it home first (the
            # no-assignment branch in the action loop); it frees up next
            # turn.
            if _haul_load(_inv_of(idx)) >= CARRY_THRESHOLD:
                continue
            reachable = ranch_reach if idx in ranch_idxs else crop_positions
            candidates = [p for p in reachable if p not in committed]
            urgent = [p for p in candidates if need_by_pos[p] in CROP_URGENT]
            candidates = urgent if urgent else candidates
            if not candidates:
                continue
            x0, y0 = pos
            target = min(candidates, key=lambda t: (abs(t[0] - x0) + abs(t[1] - y0), TILE_INDEX[t]))
            assignments[idx] = target
            committed.add(target)

        def _pickup_count(item: str) -> int:
            """How many of ``item`` to lift in one shed trip.

            The engine caps the shed but never a unit's inventory, so a
            single trip can stock a whole run of adjacent pasture tiles: one
            WHEAT per unfed animal, or every animal of a species still
            waiting on a home. Lifting one per chore instead costs a full
            shed round trip per animal, which cannot keep a 17-head herd fed
            inside a 24-turn day."""
            if item == "WHEAT":
                # A full batch every trip. Netting off what the crew already
                # carries looks tidier but shrinks later trips to one or two
                # units, and the walk to the shed costs the same either way:
                # measured, it turned ~3 shed runs a day into 13. Stampedes
                # are prevented upstream instead -- the dispatch pass only
                # sends a fetcher when no unit already holds WHEAT.
                return max(1, min(FEED_BATCH, len(unfed_risk)))
            # Animals go one per trip, deliberately unlike WHEAT. A PLACE is
            # one animal per unit per turn no matter how many that unit
            # carries, so a single hand lifting the whole shed serialises the
            # build-out behind its own walking -- and leaves an empty shed, so
            # no second hand can be dispatched to help. One at a time keeps
            # stock in the shed for other hands to draw on, and the last
            # burst lands inside its day instead of trickling into the next.
            return 1

        def _carry_leg(pos: Position, item: str, task_tile: Position) -> list[str]:
            """Fetch ``item`` from the shed before working ``task_tile``:
            walk to the nearer shed-access tile, PICKUP a batch (see
            ``_pickup_count``), then continue toward ``task_tile`` next
            turn. Best-effort when the shed doesn't have it yet -- walk
            toward ``task_tile`` anyway rather than stall (mirrors the
            champion dispatcher's fetch-then-carry ``_carry_leg`` in
            packages/agent/src/agent/dispatch.py, reused here per the
            issue's explicit mechanics-reuse authorization)."""
            px, py = pos
            nearest_shed = min(SHED_ACCESS_TILES, key=lambda s: abs(s[0] - px) + abs(s[1] - py))
            available = shed.get(item, 0)
            if available > 0:
                if pos == nearest_shed:
                    return ["PICKUP", item, min(_pickup_count(item), available)]
                return _step_toward(px, py, *nearest_shed)
            return _step_toward(px, py, *task_tile)

        unit_actions: list[list[str]] = []
        for idx, pos in enumerate(unit_positions):
            x, y = pos
            if tile_at(x, y) == "LOCKED":
                unit_actions.append(_step_toward(x, y, *NW_SHED))
                continue

            inv = inventories[idx] if idx < len(inventories) else {}
            if not isinstance(inv, dict):
                inv = {}

            target = assignments.get(idx)
            if target is not None:
                need = need_by_pos[target]
                if pos != target:
                    if need in CARRY_ITEM and inv.get(CARRY_ITEM[need], 0) <= 0:
                        unit_actions.append(_carry_leg(pos, CARRY_ITEM[need], target))
                    else:
                        unit_actions.append(_step_toward(x, y, *target))
                    continue
                if need == "PLANT":
                    crop = pick_plant_crop()
                    unit_actions.append(["PLANT", crop] if crop is not None else ["PASS"])
                    continue
                if need == "PLANT_EMERGENCY_WHEAT":
                    if remaining_seeds.get("WHEAT", 0) > 0:
                        remaining_seeds["WHEAT"] -= 1
                        unit_actions.append(["PLANT", "WHEAT"])
                    else:
                        unit_actions.append(["PASS"])
                    continue
                if need in CARRY_ITEM:
                    item = CARRY_ITEM[need]
                    if inv.get(item, 0) > 0:
                        unit_actions.append(DIRECT_ACTION[need])
                    else:
                        unit_actions.append(_carry_leg(pos, item, pos))
                    continue
                if need == "WATER":
                    state["watered_today"].add(pos)
                unit_actions.append(DIRECT_ACTION.get(need, [need]))
                continue

            # No unclaimed need left for this unit -- mule carried produce
            # home if loaded, else idle. Carried WHEAT is deliberately not
            # part of the load while the herd is still hungry (see
            # ``_haul_load``): it goes straight into a FEED instead of
            # round-tripping through the shed first.
            if _haul_load(inv) >= CARRY_THRESHOLD:
                nearest_shed = min(SHED_ACCESS_TILES, key=lambda s: abs(s[0] - x) + abs(s[1] - y))
                if pos == nearest_shed:
                    unit_actions.append(["DROP"])
                else:
                    unit_actions.append(_step_toward(x, y, *nearest_shed))
                continue
            unit_actions.append(["PASS"])

        farmer_action = unit_actions[0]
        hands_actions = unit_actions[1:]

        # Order construction is priority-ordered and truncation-aware: the
        # engine caps market orders at ``maxMarketOrdersPerTurn`` (10) and
        # silently drops anything past that index (verified via a real run --
        # a naive single hour-0 burst of BUY_LAND + up to 12 HIRE + several
        # BUY_SEED orders overflows 10 and starves planting for the whole
        # day). SELL goes first, ahead of BUY_LAND/HIRE/BUY_ANIMAL/BUY_SEED:
        # unlike every other order type here, a queued SELL never fails for
        # lack of money (it's the source of money), so it must never be the
        # order truncation drops. Queuing spend orders first was observed to
        # deadlock permanently once money got tight enough that HIRE's own
        # per-turn demand (up to 12 -- see ``_hires_for_day``) alone filled
        # every slot: ``_do_hire`` no-ops silently when unaffordable rather
        # than erroring, so an unaffordable HIRE still consumes its slot and
        # never shrinks ``remaining_hires``, meaning it re-floods every
        # subsequent turn including the very SELL-window turns that would
        # otherwise refill the till -- a permanent zero-money lock with no
        # escape once triggered. HIRE and BUY_SEED demand are each re-derived
        # every turn from the engine's own live counters (``hires_today``,
        # held seeds) rather than tracked locally, and attempted on every
        # turn the need is nonzero (not just hour 0) -- a heavy seed-spend
        # day can leave money too tight to afford the day's full hire ramp at
        # hour 0 (fib-scaled hire cost), so retrying once later revenue lands
        # is what actually closes the gap to the day's target instead of
        # giving up after one or two turns.
        placed_cow = sum(
            1
            for pos in pasture_tiles
            if isinstance(tile_at(*pos), dict) and tile_at(*pos).get("animal") == "COW"
        )
        placed_sheep = sum(
            1
            for pos in pasture_tiles
            if isinstance(tile_at(*pos), dict) and tile_at(*pos).get("animal") == "SHEEP"
        )

        market: list[list[Any]] = []

        if hour in SELL_HOURS:
            # Larger-volume crop first (index 0): the engine processes a
            # market order list by index to completion before the next, so
            # the bigger backlog nets the better pre-crash price. WHEAT is
            # capped below the shed's full count once any animal is placed,
            # holding back a feed reserve -- selling every last WHEAT unit
            # would starve tomorrow's FEED (SELL runs in this same hour-0/1
            # window BUY_PRODUCT's top-up lands in, so an uncapped sell here
            # would net the day's feed stock to zero before FEED ever runs).
            wheat_reserve = animals_placed + FEED_RESERVE if animals_placed > 0 else 0
            wheat_sellable = max(0, shed.get("WHEAT", 0) - wheat_reserve)
            crop_shed = [
                ("WHEAT", wheat_sellable),
                ("MELON", shed.get("MELON", 0)),
                ("STRAWBERRY", shed.get("STRAWBERRY", 0)),
            ]
            crop_shed = [c for c in crop_shed if c[1] > 0]
            crop_shed.sort(key=lambda c: c[1], reverse=True)
            for crop, amount in crop_shed:
                market.append(["SELL", crop, amount if crop == "WHEAT" else 99999])

            # Animal products sell price-blind, immediately, no index-0
            # volume ordering (the economy slice's price-sensitive
            # convention above is for crops only -- see module docstring).
            for product in ("FERTILIZER", "WOOL", "MILK"):
                if shed.get(product, 0) > 0:
                    market.append(["SELL", product, 99999])

        if day == LAND_DAY and hour == 0:
            market.append(["BUY_LAND"])

        # WHEAT feed-stock top-up (issue #27): ahead of HIRE/BUY_ANIMAL/
        # BUY_SEED in priority, so a herd on the edge of starvation is never
        # left unfed because the same turn's cash went to a new hire, a new
        # animal, or a crop seed instead -- feeding the herd already owned
        # takes precedence over growing either the crew or the herd further.
        # No money floor: any affordable amount (even a single unit) is
        # worth buying once feed is tight, since the cited $500 floor was an
        # economy-core convenience threshold, not pinned replay data (the
        # WHEAT-top-up test only pins its hour/day window, never a minimum
        # spend).
        #
        # Sized to a ``WHEAT_STOCK_DAYS`` buffer rather than "as much as the
        # cap allows": the shed is one 100-item pool shared with the
        # bought-but-unplaced animals, and ``_commit_unit`` refuses a
        # BUY_ANIMAL outright once that pool is full -- so an unbounded
        # WHEAT stockpile silently blocks the herd build-out it is meant to
        # sustain.
        if day >= BUY_PRODUCT_FIRST_DAY and hour in BUY_PRODUCT_HOURS:
            price = obs["market"]["prices"].get("WHEAT", 0)
            if price > 0:
                wheat_on_hand = shed.get("WHEAT", 0) + carried_wheat_total
                wanted = max(0, WHEAT_STOCK_DAYS * PASTURE_TILE_TARGET - wheat_on_hand)
                shed_room = max(0, SHED_CAPACITY - sum(shed.values()))
                affordable = int(farm["money"] // price)
                to_buy = min(BUY_PRODUCT_CAP, affordable, wanted, shed_room)
                if to_buy > 0:
                    market.append(["BUY_PRODUCT", "WHEAT", to_buy])

        # Animal purchase bursts (issue #27): buy up to the cumulative
        # target for each species every turn the gap is nonzero and
        # affordable, retried across turns exactly like BUY_SEED/HIRE below
        # -- "day 6: 5 SHEEP + 4 COW... spread across late-day hours as cash
        # allows" describes this same retry-until-filled pattern, not a
        # single-turn burst. ``ANIMAL_BUY_LAST_DAY`` is a defensive cutoff;
        # the cumulative-target comparison against ``*_owned`` already caps
        # the herd at 6 COW + 11 SHEEP on its own once every burst lands.
        #
        # Queued AHEAD of HIRE, and this ordering is load-bearing: the pinned
        # cadence asks for up to 12 hires a day and queues one order each, so
        # on the busiest days HIRE alone overruns the engine's
        # ``maxMarketOrdersPerTurn`` (10) and silently truncates every animal
        # order off the end of the turn that could actually afford one --
        # precisely the hour-0 turns the morning's SELL revenue just funded.
        # Hires lose nothing by yielding: they are fib-priced pocket change,
        # re-derived every turn from the engine's own ``hires_today``, and
        # there are 24 turns a day to land them in.
        placed_by_species = {"COW": placed_cow, "SHEEP": placed_sheep}
        species_prices = {"COW": COW_PRICE, "SHEEP": SHEEP_PRICE}
        if day <= ANIMAL_BUY_LAST_DAY:
            reserve = (
                PRE_LAND_CASH_RESERVE
                if PRE_LAND_RESERVE_FIRST_DAY <= day <= LAND_DAY
                else ANIMAL_CASH_RESERVE
            )
            # The pinned PLANT_TABLE's seed bill for today comes off the top
            # before any animal is bought. Herd spending is the larger draw
            # by an order of magnitude, and BUY_ANIMAL is queued ahead of
            # BUY_SEED, so without this the burst simply eats the day's seed
            # money: measured, the day-11 sheep burst crowded out that day's
            # seven STRAWBERRY seeds, and only three of the nine strawberries
            # the table calls for were ever sown. Strawberries are an ongoing
            # crop -- the tiles that are still standing at the end of the
            # episode -- so losing them quietly hollows out the late-game
            # crop board that the economy slice's watering floor measures.
            seed_bill = sum(
                SEED_COST[crop] * max(0, remaining - seeds.get(crop, 0))
                for crop, remaining in remaining_quota.items()
            )
            spendable = max(0.0, farm["money"] - reserve - seed_bill)
            need_by_species = {
                species: max(
                    0,
                    _cumulative_animal_target(day, species)
                    - placed_by_species[species]
                    - shed.get(species, 0)
                    - carried_species[species],
                )
                for species in ("COW", "SHEEP")
            }
            # Largest shortfall first rather than a fixed species order: the
            # burst table is sheep-heavy (11 v 6), so spending a tight day's
            # cash cows-first every time leaves the sheep half of the herd
            # permanently unbought and the herd short of its day-12 target.
            for species in sorted(need_by_species, key=lambda s: (-need_by_species[s], s)):
                need = need_by_species[species]
                if need <= 0:
                    continue
                price = species_prices[species]
                to_buy = min(need, int(spendable // price))
                if to_buy > 0:
                    market.append(["BUY_ANIMAL", species, to_buy])
                    spendable -= to_buy * price

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

        # Seed stock for the emergency WHEAT overplanting above -- a
        # separate top-up order (independent of the pinned table's own
        # WHEAT seed buy above) sized to whatever's not already on hand.
        if emergency_wheat_tiles:
            needed = max(0, len(emergency_wheat_tiles) - seeds.get("WHEAT", 0))
            if needed > 0:
                affordable = int(farm["money"] // SEED_COST["WHEAT"])
                to_buy = min(needed, affordable)
                if to_buy > 0:
                    market.append(["BUY_SEED", "WHEAT", to_buy])

        return {"farmer": farmer_action, "hands": hands_actions, "market": market}

    return agent
