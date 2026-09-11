"""Daily planner — Plan A opening (wheat rush + goose), land expansion, melon
seed-buying, animal husbandry, and hand-count scaling as the farmable
universe (and the chore load) grows.

Pure and per-turn idempotent: quantities derive only from observable state, so
re-running every turn never double-buys (market orders fill within the turn
they are issued; the next observation already reflects them). Budget is spent
sequentially in priority order: goose, then NE land, then melon seeds, then
animals (cows before sheep), then wheat seeds, then strawberry seeds, then
feed, then SW land, then SE land -- though the SE rung is unreachable at the shipped default, see
``MAX_OWNED_QUADRANTS``.

Melon goes ahead of wheat because it's the higher-value crop (seed $80 vs
$10, and a mature melon sells for far more than a mature wheat harvest) and
should never be starved of budget by wheat's larger, cheaper seed line.
Animals go ahead of wheat/SW/SE for the same reason, one rung up: replay
evidence shows the two strongest observed opponents draw 40-69% of revenue
from cow/sheep products, so the husbandry pipeline (bounded by each
species' own breakeven purchase window) gets first claim on budget right
after the melon satellite. SW is deliberately moved *after* animals (and
SE after SW, further demoted behind an extra cash-reserve gate) so land
expansion never crowds out the higher-return animal purchases while their
windows are still open.

The SE rung is dead code at the shipped default. ``MAX_OWNED_QUADRANTS`` is 3,
so ``_next_quadrant`` returns None once NW/NE/SW are held and the SE branch
never fires. It is kept reachable only through an explicit
``PolicyConfig(max_owned_quadrants=4)``, which is what the eval arms use to
recover pre-cap behavior. A replay or settlement ledger showing $3,000 of land
spend (NE+SW) rather than $7,000 is the cap working, not a planner bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.constants import (
    COW_TARGET,
    LAND_ORDER,
    LAND_PRICES,
    MAX_OWNED_QUADRANTS,
    SHEEP_TARGET,
)
from agent.dispatch import (
    MELON_PLANT_CUTOFF_DAY,
    MELON_PLANT_DAILY_CAP,
    STRAWBERRY_PLANT_CUTOFF_DAY,
    STRAWBERRY_PLANT_DAILY_CAP,
    plant_quota,
)

FEED_RESERVE = 3
SEED_PRICE = 10
MELON_SEED_PRICE = 80
STRAWBERRY_SEED_PRICE = 100
# Share of the cash still uncommitted when the strawberry seed line runs
# that the line may take. 1.0 is the pre-2026-08-19-prereg sizing.
STRAWBERRY_SEED_BUDGET_SHARE = 0.5
GOOSE_COST = 300
GOOSE_LAST_BUY_DAY = 14  # $300 payback needs ~12 egg days; later purchase never breaks even
# GOOSE_MIN_DAY (PolicyConfig.goose_min_day): earliest day the goose purchase
# may fire, the same day >= *_min_day mechanism NE_LAND_MIN_DAY below uses for
# NE land. The goose branch never had an earliest-day gate before this knob
# existed -- it buys the instant cash allows, including turn 0 -- so 0 is
# DEFAULT-NEUTRAL: day >= 0 is always true, and every existing game is
# bit-for-bit unchanged. Single source of truth for PolicyConfig.
# goose_min_day's own default (threaded policy.py -> plan_day(), the same
# pattern NE_LAND_MIN_DAY and MAX_HIRES_PER_TURN below use), so the knob's
# default can never drift out of sync with what this module does when the
# knob is left alone.
#
# Diagnosis (observed strongest public bots, game replays, 2026-09-11): the
# strongest public bots never buy a goose at all and keep the 5 NW pasture
# slots for 4 sheep + 1 cow before NE is bought -- our goose takes one of
# those slots, so a sheep-first opening stalls at 3 sheep. An eval run sets
# this to the NE day (e.g. 6, ne_land_min_day's own eval value) to defer the
# goose while that opening plays out.
GOOSE_MIN_DAY = 0
PLANT_CUTOFF_DAY = 25  # last profitable wheat planting day (4 growth days + sale)

LAND_RESERVE = 500  # cash floor kept in hand after any land purchase
LAND_LAST_BUY_DAY = {"NE": 24, "SW": 23, "SE": 20}  # later buys don't pay back land's own cost
# NE_LAND_MIN_DAY (PolicyConfig.ne_land_min_day): earliest day the NE
# purchase may fire, the same mechanism SE_LAND_MIN_DAY below already gates
# SE with. The NE branch never had an earliest-day gate before this knob
# existed -- it buys NE the instant it is the next quadrant and cash allows,
# including turn 0 -- so 0 is DEFAULT-NEUTRAL: day >= 0 is always true, and
# every existing game is bit-for-bit unchanged. Single source of truth for
# PolicyConfig.ne_land_min_day's own default (threaded policy.py ->
# plan_day(), the same pattern MAX_HIRES_PER_TURN below uses), so the knob's
# default can never drift out of sync with what this module does when the
# knob is left alone.
#
# Diagnosis (observed strongest public bots, game replays, 2026-09-11): they
# own only NW until buying NE around day 6, spending the opening budget on
# the day-0 herd instead. An eval run raises this to hold NE off while that
# opening plays out; SW's and SE's own gates (including SE_LAND_MIN_DAY) and
# the fixed NE -> SW -> SE unlock order (constants.LAND_ORDER) are untouched.
NE_LAND_MIN_DAY = 0
SE_LAND_MIN_DAY = 12  # demoted: SE never pays back if the animal pipeline is still ramping
SE_LAND_RESERVE = 2000  # demoted further: a bigger cash cushion than NE/SW's flat LAND_RESERVE

HANDS_MIN = 3  # the Plan A opening crew, even on the 24-tile NW-only board
HANDS_PER_TILES = 8  # roughly one hand per eight target tiles
# extra_hands (PolicyConfig field, default 0): a flat add-on to hands_target,
# applied AFTER the HANDS_MIN floor and the husbandry bonus below rather than
# inside the max(...), so it never interacts with either -- it is pure
# additional labor SUPPLY. Unlike every other knob in this module, there is
# no prior hardcoded constant it reproduces (there was never an implicit
# "extra hands" term before this knob existed), so its own default lives as
# a bare 0 on PolicyConfig rather than a named constant here.
#
# Diagnosis (kaggriculture, 2026-09-11, continuation of the MAX_HIRES_PER_
# TURN/WHEAT_PLANT_PRIORITY/WHEAT_PLANT_HOUR_CUTOFF diagnosis above): even
# with those three knobs tuned, the crew measures saturated -- idle share
# ~4.7% -- so only ~200 of the ~410 wheat plantings plant_quota intends
# execute per game. Moving labor toward planting via a higher DISPATCH tier
# or a later wheat_plant_hour_cutoff instead starves WATER tasks and raises
# weeds 1.8-3.2x, because the existing crew is already fully committed. The
# next lever is labor SUPPLY rather than dispatch priority: more hands on
# the farm, not a different claim order for the hands already there.
# HIRE is one order slot each; caps the market-list cost of catching up. Single
# source of truth for PolicyConfig.max_hires_per_turn (threaded policy.py ->
# plan_day(), the same pattern as dispatch.STRAWBERRY_PLANT_PRIORITY), so the
# knob's default can never drift out of sync with what this module does when
# the knob is left alone.
#
# Diagnosis (SHIPPED agent, all-default PolicyConfig, seeds 855000-855001 vs
# public:sokolovsky-v12): the engine evicts every hand at midnight, so the
# morning crew is rebuilt from scratch over 3 hours every day at this default
# -- units on the farm (farmer + hands) at hours 0/1/2/3 measured at 1/5/9/11.
# Tier-3 field work (PLANT WHEAT among it) has few or no idle units to claim
# it for that whole stretch. Raising this knob does not by itself guarantee a
# faster ramp reaches the market: market.MAX_ORDERS caps the WHOLE per-turn
# order list at 10, HIRE orders are appended LAST (see policy.decide's "Buys
# first, hires last" comment), and any hires past that shared cap are
# silently DROPPED by the truncation, not deferred to a later slot in the
# same turn -- though the shortfall persists and is asked for again next turn
# since plan_day recomputes hands_target - hires_today fresh every time.
#
# The hour-0 OBSERVATION itself never shows more than the bare farmer, for
# ANY value of this knob: hires_today resets to 0 at the start of every day,
# and that first observation necessarily precedes the day's first action
# batch, so no hire this knob requests can have taken effect yet (recon,
# seeds 777400-777401: units@hour0 == 1.00 identically at max_hires_per_turn
# 4 and 10). The knob's effect first becomes visible at hour 1 -- and even
# then, whether all of a raised request actually reaches the market on that
# first turn depends on how many sell/buy lines are already competing for
# the same 10 slots: uncontested (nothing else to buy or sell that turn) all
# of it lands, but on a busy turn it does not -- measured directly at both
# ends in test_policy.py's test_max_hires_per_turn_threads_from_policy_
# config_to_the_market_list (10 requested, 10 land) and test_hires_beyond_
# the_market_order_cap_are_dropped_not_deferred (10 requested, 3 land).
MAX_HIRES_PER_TURN = 4
HUSBANDRY_HAND_THRESHOLD = 8  # placed animals at which chore load earns a dedicated extra hand

# Animal breakeven purchase windows (engine-verified): cow $400, first yield
# day 8 after PLACE, every 2 days; sheep $500, first yield day 6, every 3
# days. Buying past these windows can't recoup the purchase price before the
# day-29 liquidation, so both cutoffs sit well before game end.
COW_PRICE = 400
SHEEP_PRICE = 500
COW_LAST_BUY_DAY = 9
SHEEP_LAST_BUY_DAY = 11
ANIMAL_BUY_CAP_PER_TURN = 2  # shared across cow+sheep: paces the shed->pasture placement pipeline

# Per-species purchase parameters, keyed for the animal_buy_order loop in
# plan_day() below -- single source of truth, so the loop can never drift out
# of sync with the species constants just above.
_ANIMAL_PRICE: dict[str, int] = {"COW": COW_PRICE, "SHEEP": SHEEP_PRICE}
_ANIMAL_LAST_BUY_DAY: dict[str, int] = {"COW": COW_LAST_BUY_DAY, "SHEEP": SHEEP_LAST_BUY_DAY}

# ANIMAL_BUY_ORDER (PolicyConfig.animal_buy_order): the order the shared
# per-turn cap/room is offered to cow vs sheep. Cows-before-sheep was a
# hardcoded sequence, not a parameter, before this knob existed, so
# ("COW", "SHEEP") is DEFAULT-NEUTRAL -- every existing game buys in exactly
# this order already. Single source of truth for PolicyConfig.
# animal_buy_order's own default, the same pattern NE_LAND_MIN_DAY above and
# MAX_HIRES_PER_TURN below use.
#
# Diagnosis (observed strongest public bots, game replays, 2026-09-11): they
# buy about 4 sheep and 1 cow on day 0 -- sheep-first, not cow-first -- so an
# eval run flips this to measure that ordering.
ANIMAL_BUY_ORDER: tuple[str, ...] = ("COW", "SHEEP")


@dataclass(frozen=True)
class DayPlan:
    hire_count: int = 0
    buys: list[list[object]] = field(default_factory=list)


def _next_quadrant(
    unlocked_quadrants: tuple[str, ...],
    max_owned_quadrants: int = MAX_OWNED_QUADRANTS,
) -> str | None:
    """The next quadrant to buy, or None when we already hold enough.

    The cap counts OWNED quadrants including the always-unlocked NW. The
    shipped default is ``MAX_OWNED_QUADRANTS = 3``, so this guard DOES fire on
    the shipped path: once NW/NE/SW are held it returns None and the $4,000 SE
    quadrant is never bought. The guard is load-bearing, not scaffolding --
    deleting it re-enables SE and silently reverts a result gated at n=64
    across four tapes (see ``constants.MAX_OWNED_QUADRANTS``).

    Pass ``max_owned_quadrants=4`` to recover the uncapped, pre-cap behavior;
    at 4 the guard cannot bind on a four-quadrant board because the
    ``next(...)`` below already returns None once every quadrant is held.
    """
    if len(unlocked_quadrants) >= max_owned_quadrants:
        return None
    return next((q for q in LAND_ORDER if q not in unlocked_quadrants), None)


def plan_day(
    *,
    day: int,
    money: float,
    wheat_seeds: int,
    plantable_target_tiles: int,
    melon_seeds: int = 0,
    empty_melon_tiles: int = 0,
    strawberry_seeds: int = 0,
    empty_strawberry_tiles: int = 0,
    strawberry_plant_daily_cap: int = STRAWBERRY_PLANT_DAILY_CAP,
    strawberry_seed_budget_share: float = STRAWBERRY_SEED_BUDGET_SHARE,
    wheat_on_hand: int,
    goose_owned: bool,
    goose_min_day: int = GOOSE_MIN_DAY,
    hires_today: int,
    unlocked_quadrants: tuple[str, ...],
    active_tiles: int,
    max_owned_quadrants: int = MAX_OWNED_QUADRANTS,
    ne_land_min_day: int = NE_LAND_MIN_DAY,
    cows_owned: int = 0,
    sheep_owned: int = 0,
    empty_pastures: int = 0,
    animals_placed: int = 0,
    feed_reserve: int = FEED_RESERVE,
    cow_target: int = COW_TARGET,
    sheep_target: int = SHEEP_TARGET,
    animal_buy_order: tuple[str, ...] = ANIMAL_BUY_ORDER,
    max_hires_per_turn: int = MAX_HIRES_PER_TURN,
    extra_hands: int = 0,
) -> DayPlan:
    buys: list[list[object]] = []
    budget = money

    if (
        not goose_owned
        and day >= goose_min_day
        and day <= GOOSE_LAST_BUY_DAY
        and budget >= GOOSE_COST
    ):
        buys.append(["BUY_ANIMAL", "GOOSE", 1])
        budget -= GOOSE_COST

    if (
        _next_quadrant(unlocked_quadrants, max_owned_quadrants) == "NE"
        and day >= ne_land_min_day
        and day <= LAND_LAST_BUY_DAY["NE"]
    ):
        price = LAND_PRICES["NE"]
        if budget >= price + LAND_RESERVE:
            buys.append(["BUY_LAND"])
            budget -= price

    if day <= MELON_PLANT_CUTOFF_DAY:
        # Hold at most two days of melon's own 2/day planting stagger — the
        # same "two days of headroom" reasoning as the wheat seed line below,
        # just sized to melon's flat daily cap instead of wheat's tile-scaled
        # plant_quota.
        melon_seed_target = min(2 * MELON_PLANT_DAILY_CAP, empty_melon_tiles)
        need = melon_seed_target - melon_seeds
        affordable = int(budget // MELON_SEED_PRICE)
        n = min(need, affordable)
        if n > 0:
            buys.append(["BUY_SEED", "MELON", n])
            budget -= n * MELON_SEED_PRICE

    # Animals: bought in animal_buy_order (cows before sheep by default), at
    # most ANIMAL_BUY_CAP_PER_TURN total, never more than the empty-built-
    # pasture count observed this turn (trap: a bought animal that can't be
    # placed is dead capital sitting in the shed — it can never be sold), and
    # only inside each species' own breakeven purchase window. Looped rather
    # than duplicated per species so animal_buy_order can reorder the two
    # blocks without touching either one's guard, cap, or target math.
    animal_room = empty_pastures
    turn_cap_left = ANIMAL_BUY_CAP_PER_TURN
    animal_target: dict[str, int] = {"COW": cow_target, "SHEEP": sheep_target}
    animal_owned: dict[str, int] = {"COW": cows_owned, "SHEEP": sheep_owned}

    for species in animal_buy_order:
        if day <= _ANIMAL_LAST_BUY_DAY[species]:
            need = max(0, animal_target[species] - animal_owned[species])
            n = min(need, animal_room, turn_cap_left, int(budget // _ANIMAL_PRICE[species]))
            if n > 0:
                buys.append(["BUY_ANIMAL", species, n])
                budget -= n * _ANIMAL_PRICE[species]
                animal_room -= n
                turn_cap_left -= n

    if day <= PLANT_CUTOFF_DAY:
        # Hold at most two days of the dispatcher's plant quota: seeds beyond
        # that are dead cash that delays land purchases (day 0 exempt — the
        # opening rush plants the whole board).
        quota = plant_quota(day, active_tiles)
        seed_target = min(plantable_target_tiles, 2 * quota)
        need = seed_target - wheat_seeds
        affordable = int(budget // SEED_PRICE)
        n = min(need, affordable)
        if n > 0:
            buys.append(["BUY_SEED", "WHEAT", n])
            budget -= n * SEED_PRICE

    # Strawberry sits AFTER the animal pipeline AND after wheat. It is the
    # highest-value crop the board can grow (4 of the 8 shop types buy it,
    # against melon's 0, and a fertilized tile yields 8 units a cycle), which
    # argues for putting it earlier -- and it was in fact placed ahead of
    # wheat until the 2026-08-19 prereg measured what that cost. A $100 seed
    # line running before a $10 one consumed the whole early budget: the days
    # 0-13 wheat seed pool sat at exactly 0 and WHEAT did not reach the board
    # until day 14, while the zone reserved 31 tiles and filled 15-17 and the
    # rest sat bare because the wheat rush could not start. Wheat is the early
    # cash engine and the cheapest ground-holder per dollar, so it is funded
    # first and strawberry draws on what it leaves -- the same relationship
    # strawberry already has with the animal pipeline one rung up.
    #
    # There is room for it to do that: production ticks at planted_day +
    # 10/12/14/16 against a last-refresh day of 28 mean a tile planted by day
    # 12 still banks a full four ticks, so the seed line has a thirteen-day
    # runway funded out of ongoing revenue rather than needing the whole
    # commitment out of the opening bankroll.
    if day <= STRAWBERRY_PLANT_CUTOFF_DAY:
        # Three bounds, all of which must hold: two days of the dispatcher's
        # own strawberry stagger (same reasoning as the melon and wheat seed
        # lines above), the tiles that actually exist to plant into, and a
        # share of the cash still uncommitted when this line runs.
        #
        # The share is what re-ordering alone cannot buy. Two lines still run
        # after this one -- the animal feed top-up and the SW land buy -- and
        # a zone sized at 31 tiles asks for 12 x $100 = $1,200 every day
        # regardless of what those need. Sizing the ask to cash rather than to
        # the zone is what lets a large zone be swept at all, since otherwise
        # the zone size itself decides how much of the farm's budget the crop
        # commandeers. A share of 1.0 recovers the pre-prereg sizing exactly,
        # so the sweep can argue the cap back off on its own evidence.
        strawberry_seed_target = min(2 * strawberry_plant_daily_cap, empty_strawberry_tiles)
        need = strawberry_seed_target - strawberry_seeds
        affordable = int((budget * strawberry_seed_budget_share) // STRAWBERRY_SEED_PRICE)
        n = min(need, affordable)
        if n > 0:
            buys.append(["BUY_SEED", "STRAWBERRY", n])
            budget -= n * STRAWBERRY_SEED_PRICE

    # Feed reserve/top-up sizes to *placed* animals only — a bought-but-not-
    # yet-placed animal (still walking the shed->pasture pipeline) doesn't
    # need feeding today. The trigger still fires as soon as any animal is
    # owned in any state (matches the legacy goose-only trigger) so the shed
    # stocks up ahead of that animal's eventual placement.
    feed_gap = (animals_placed + feed_reserve) - wheat_on_hand
    any_animal_owned = (
        goose_owned or cows_owned > 0 or sheep_owned > 0 or any(b[0] == "BUY_ANIMAL" for b in buys)
    )
    if any_animal_owned and feed_gap > 0 and day <= 27:
        buys.append(["BUY_PRODUCT", "WHEAT", feed_gap])

    # SW moves after animals: only once each species' target is met or its
    # window has closed, so land expansion never crowds out a still-open,
    # higher-return animal purchase.
    animals_done = (cows_owned >= cow_target or day > COW_LAST_BUY_DAY) and (
        sheep_owned >= sheep_target or day > SHEEP_LAST_BUY_DAY
    )
    sw_next = _next_quadrant(unlocked_quadrants, max_owned_quadrants) == "SW"
    if animals_done and sw_next and day <= LAND_LAST_BUY_DAY["SW"]:
        price = LAND_PRICES["SW"]
        if budget >= price + LAND_RESERVE:
            buys.append(["BUY_LAND"])
            budget -= price

    # SE is demoted further still: a strong observed opponent (~151k) never
    # bought it at all, so it needs both a later earliest-day and a much
    # bigger cash cushion than NE/SW's flat reserve before it's worth it.
    if (
        _next_quadrant(unlocked_quadrants, max_owned_quadrants) == "SE"
        and day >= SE_LAND_MIN_DAY
        and day <= LAND_LAST_BUY_DAY["SE"]
    ):
        price = LAND_PRICES["SE"]
        if budget >= price + SE_LAND_RESERVE:
            buys.append(["BUY_LAND"])
            budget -= price

    husbandry_hand = 1 if animals_placed >= HUSBANDRY_HAND_THRESHOLD else 0
    hands_target = (
        max(HANDS_MIN, round(active_tiles / HANDS_PER_TILES) + husbandry_hand) + extra_hands
    )
    hire_count = min(max(0, hands_target - hires_today), max_hires_per_turn)

    return DayPlan(hire_count=hire_count, buys=buys)
