"""Chassis v1 — wheat rush + goose + melon satellite + animal husbandry +
index-0 price-aware selling.

Composition per turn: parse the obs into a typed view, run the (idempotent)
daily planner, dispatch units, build market orders with sells ahead of buys
and crashables at index 0. A soft watchdog bails to PASS if a turn ever runs
long — the 60 s overage bank is for thinking, never for accidents.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from agent.constants import (
    BOARD_SIZE,
    COW_TARGET,
    MAX_OWNED_QUADRANTS,
    MELON_TILE_TARGET,
    PASTURE_REFERENCE_QUADRANTS,
    QUADRANTS,
    SHEEP_TARGET,
    STRAWBERRY_REFERENCE_QUADRANTS,
    STRAWBERRY_TILE_TARGET,
    melon_tiles,
    pasture_tiles,
    strawberry_tiles,
    strawberry_tiles_for_frame,
    target_tiles,
)
from agent.dispatch import (
    FEED_BATCH_CAP,
    HAND_MULE_LOAD,
    RESCUE_WATER,
    STRAWBERRY_PLANT_CUTOFF_DAY,
    STRAWBERRY_PLANT_DAILY_CAP,
    STRAWBERRY_PLANT_PRIORITY,
    WHEAT_PLANT_HOUR_CUTOFF,
    WHEAT_PLANT_PRIORITY,
    dispatch,
)
from agent.market import (
    FERT_MIN_PRICE,
    MILK_MIN_PRICE,
    STRAWBERRY_MIN_PRICE,
    VALVE_SOFT_CAP,
    WOOL_MILK_SELL_CAP,
    WOOL_MIN_PRICE,
    build_orders,
)
from agent.plan import (
    ANIMAL_BUY_ORDER,
    FEED_RESERVE,
    GOOSE_MIN_DAY,
    MAX_HIRES_PER_TURN,
    NE_LAND_MIN_DAY,
    STRAWBERRY_SEED_BUDGET_SHARE,
    plan_day,
)
from agent.shell import Action, Observation, pass_action
from agent.state import MelonMarketMemory, ProductCrashLatch, StateTracker
from agent.view import FarmView, clone_pressure_products, parse_obs

SOFT_BUDGET_SECONDS = 0.5  # v1 logic runs in microseconds; this guards regressions

# No cap by default: the full board (BOARD_SIZE**2 tiles, minus COOP_TILE) can
# never yield more wheat tiles than this once melon's and pasture's own zones
# are carved out, so the default preserves today's uncapped remainder for
# every unlock state.
_WHEAT_RUSH_TILES_DEFAULT = (
    BOARD_SIZE * BOARD_SIZE - 1 - MELON_TILE_TARGET - (COW_TARGET + SHEEP_TARGET)
)

# M2c (kaggriculture#59): two-tier shed valve. Absolute-unit thresholds
# against the engine's default 100-unit shed -- policy.decide scales them by
# the real shedCapacity/100 before comparing against shed_total, so a
# non-default capacity still trips the valve at the same *fraction* full.
#
# The soft tier fires EARLIER than M2c shipped it (55 -> 35): tier 1 waives the
# regime floor and substitutes valve_soft_cap for each product's own tighter
# cap, so entering it sooner drains backlog before it can reach the hard tier's
# floor-ignoring full-shed dump. Screened at 0.690 (n=100, band 838000) and
# confirmed 349-151 = 0.698, Wilson ci_lower 0.6564 (n=250, band 839000) against
# frozen:m3c_hml20_96d8b41, the shipped HML20 champion -- so this stacks ON TOP
# of hand_mule_load=20 by construction, not instead of it. Note the screen's own
# opposite arm: valve_soft_threshold=70 scored 0.130, so this knob is steep and
# signed, not a plateau. See eval/prereg/2026-09-07-untested-knob-screen.md.
VALVE_SOFT_THRESHOLD = 35
VALVE_HARD_THRESHOLD = 85

# M2c: WOOL/MILK crash-latch defaults (agent.state.ProductCrashLatch). Tuned
# well under each product's regime floor (wool_floor=150, milk_floor=120) so
# the latch only fires once the price has genuinely crashed, not merely
# dipped below the floor -- see market.py's module docstring, M2c section.
WOOL_CRASH_TRIGGER = 100.0
MILK_CRASH_TRIGGER = 60.0
CRASH_TRIGGER_TICKS = 12

# First day the strawberry mechanic may run AT ALL -- not just its seed-buy
# line. Diagnosis 2026-09-10: an earlier version of this knob lived inside
# plan.py's plan_day and gated ONLY the BUY_SEED STRAWBERRY line. That left
# the zone's own land RESERVATION (the strawberry_set carve-out in decide(),
# below, which removes those tiles from wheat_tiles before plan_day ever
# runs) in place from day 0 regardless of the seed gate -- so wheat's rush
# and the day-0 herd were displaced no matter when the seed line itself was
# allowed to buy. Measured at strawberry_tile_target=31 (8 seeds, band
# 855000, vs public:sokolovsky-v12, engine 1.32.7, turn-by-turn action diff
# against the shipped agent): wheat seed buys fell from 31 to 11-19, ~17 zone
# tiles sat empty from day 0 through day 11, the day-0 BUY_ANIMAL:COW orders
# disappeared, the herd was cut from 6 cows by day 5 to 2-3, and the day-8
# milk/wool cash takeoff never happened.
#
# STRAWBERRY_START_DAY instead gates decide()'s own per-turn effective
# config (see ``cfg`` below), so every strawberry-driven read downstream of
# it -- the zone/reservation, the wheat fall-through, plan_day's seed line,
# dispatch, and the market fertilizer reserve alike -- sees a zero-tile zone
# before this day and the configured zone from it on. There is exactly one
# mechanism, not two. 0 is the shipped default: the mechanic is fully off
# from turn one, so this is a no-op until an eval run raises it.
STRAWBERRY_START_DAY = 0

_KNOWN_QUADRANTS = frozenset(QUADRANTS)

#: Legal values for PolicyConfig.strawberry_fert_reserve (see its field
#: comment). "target" reproduces today's formula; "planted" is the new,
#: occupancy-driven one.
_KNOWN_FERT_RESERVE_MODES = frozenset({"target", "planted"})

#: dispatch()'s own priority-class dict is keyed 0 (most urgent) .. 4
#: (least) -- tasks_by_priority = {p: [] for p in range(5)} in dispatch.py.
#: A strawberry_plant_priority/wheat_plant_priority outside this range would
#: KeyError deep inside a turn the moment a tile of that crop needed
#: planting; PolicyConfig rejects it here instead, at construction, where
#: the error names the field.
_MIN_TASK_PRIORITY = 0
_MAX_TASK_PRIORITY = 4

#: max_hires_per_turn: HIRE is one market-order slot each (market.MAX_ORDERS
#: caps the whole per-turn order list at 10), so a value above 10 could never
#: mean anything beyond "every slot" and a value below 1 would silently
#: disable hiring altogether -- rejected here rather than left to quietly
#: stall crew growth for an entire game.
_MIN_HIRES_PER_TURN = 1
_MAX_HIRES_PER_TURN = 10

#: wheat_plant_hour_cutoff: the valid range of view.hour within one game day.
_MIN_PLANT_HOUR_CUTOFF = 0
_MAX_PLANT_HOUR_CUTOFF = 23

#: extra_hands: the engine itself caps nothing (a rising Fibonacci hire cost
#: within a day, but no ceiling on hands), so 0-5 is a deliberately
#: conservative guard against a runaway CLI override, not a modeled market
#: limit -- the same reasoning market.MAX_ORDERS gives max_hires_per_turn's
#: upper bound, just without a hard mechanical ceiling to derive it from.
_MIN_EXTRA_HANDS = 0
_MAX_EXTRA_HANDS = 5

#: ne_land_min_day: the valid range of view.day across the 30-day game (see
#: plan.LAND_LAST_BUY_DAY["NE"] == 24 for the corresponding *latest* day --
#: a value past that makes the purchase unreachable but is not itself an
#: invalid day, so it is not rejected here).
_MIN_NE_LAND_MIN_DAY = 0
_MAX_NE_LAND_MIN_DAY = 29

#: goose_min_day: the same valid range of view.day as ne_land_min_day above
#: (see plan.GOOSE_LAST_BUY_DAY == 14 for the corresponding *latest* day -- a
#: value past that makes the purchase unreachable but is not itself an
#: invalid day, so it is not rejected here).
_MIN_GOOSE_MIN_DAY = 0
_MAX_GOOSE_MIN_DAY = 29

#: animal_buy_order: must be a permutation of plan.ANIMAL_BUY_ORDER itself --
#: checked by sorted-list equality (not a set) so a duplicate (e.g. ("COW",
#: "COW")) is rejected too, not just an unknown species. Anything else would
#: either KeyError inside plan_day's per-species lookups or silently skip a
#: species' purchase window for the rest of the game.
_SORTED_ANIMAL_BUY_ORDER = sorted(ANIMAL_BUY_ORDER)


@dataclass(frozen=True)
class PolicyConfig:
    """Tuning knobs for the chassis, lifted out of module-level constants so
    an eval run can override them without editing source. Every field's
    default reproduces today's hardcoded behavior exactly."""

    soft_budget_seconds: float = SOFT_BUDGET_SECONDS
    feed_reserve: int = FEED_RESERVE
    melon_tile_target: int = MELON_TILE_TARGET
    cow_target: int = COW_TARGET
    sheep_target: int = SHEEP_TARGET

    # Order the shared per-turn cap/room (plan.ANIMAL_BUY_CAP_PER_TURN,
    # empty-pasture count) is offered to cow vs sheep. Cows-before-sheep was
    # a hardcoded sequence, not a parameter, before this knob existed, so
    # ("COW", "SHEEP") is DEFAULT-NEUTRAL -- every existing game buys in
    # exactly this order already, and every other guard/cap/target in
    # plan_day's animal block is untouched (see plan.py's animal_buy_order
    # loop).
    #
    # Diagnosis (observed strongest public bots, game replays, 2026-09-11):
    # they buy about 4 sheep and 1 cow on day 0 -- sheep-first, not
    # cow-first. An eval run flips this to ("SHEEP", "COW") to measure that
    # ordering. __post_init__ rejects anything that is not a permutation of
    # the default, and coerces a JSON list (no tuple type in JSON) to a
    # tuple the same way strawberry_frame_quadrants does, so an
    # agent_config override stays hashable and reaches plan_day's loop
    # unchanged.
    animal_buy_order: tuple[str, ...] = ANIMAL_BUY_ORDER

    wheat_rush_tiles: int = _WHEAT_RUSH_TILES_DEFAULT
    # Priority tier for a fresh PLANT WHEAT task -- dispatch.py's
    # _field_tasks, threaded through dispatch() the same way
    # strawberry_plant_priority is. Defaults to dispatch.WHEAT_PLANT_PRIORITY,
    # today's hardcoded tier: the same one PLANT MELON, PLANT STRAWBERRY and
    # BUILD_PASTURE already claim, so at the default a wheat planting only
    # wins an idle unit once every nearer same-tier task is already claimed
    # (priority classes are worked in strict order, 0 most urgent through 4
    # least, and a tie within one class goes to distance).
    #
    # Diagnosis (SHIPPED agent, all-default PolicyConfig, seeds
    # 855000-855001 vs public:sokolovsky-v12): PLANT WHEAT tasks are
    # generated ~7,800 times, claimed ~740, executed ~200 of the ~410
    # plant_quota intends. __post_init__ rejects anything outside dispatch's
    # 0-4 priority range, the same bound strawberry_plant_priority uses.
    wheat_plant_priority: int = WHEAT_PLANT_PRIORITY
    # Hour cutoff for a fresh PLANT WHEAT task -- dispatch.py's
    # _field_tasks, threaded the same way. Defaults to dispatch.
    # WHEAT_PLANT_HOUR_CUTOFF (20): a plant issued at hour 21+ cannot
    # reliably get its own same-day water, so PLANT WHEAT stops even with
    # seeds in hand and an empty tile underfoot. Melon's and strawberry's own
    # `hour <= 20` plant gates are separate literals and stay put regardless
    # of this knob. __post_init__ rejects anything outside 0-23, the valid
    # range of view.hour.
    wheat_plant_hour_cutoff: int = WHEAT_PLANT_HOUR_CUTOFF

    # How many quadrants to OWN, counting the always-unlocked NW. The
    # shipped default is 3 of the board's 4 -- this knob is LIVE, not dormant.
    # It binds on every game that reaches three quadrants, refusing the $4,000
    # SE purchase. Set it to 4 to recover pre-cap behavior; that is what the
    # eval arms do, and it is the value a frozen pre-cap baseline needs.
    # Land is not a one-off cost: hands are daily rentals and hands_target
    # scales with active_tiles, so every quadrant carries a standing crew
    # charge on top of its price. See constants.MAX_OWNED_QUADRANTS.
    max_owned_quadrants: int = MAX_OWNED_QUADRANTS

    # Earliest day the NE purchase may fire, mirroring SE's own
    # SE_LAND_MIN_DAY gate (see plan.py) rather than a new mechanism. The NE
    # branch never had an earliest-day gate before this knob existed -- it
    # buys NE the instant it is the next quadrant and cash allows, including
    # turn 0 -- so 0 is DEFAULT-NEUTRAL: day >= 0 is always true and every
    # existing game is bit-for-bit unchanged. SW's and SE's own gates
    # (including SE_LAND_MIN_DAY) are untouched by this knob, and so is the
    # fixed NE -> SW -> SE unlock order (constants.LAND_ORDER).
    #
    # Diagnosis (observed strongest public bots, game replays, 2026-09-11):
    # they own only NW until buying NE around day 6, spending the opening
    # budget on the day-0 herd instead of land. An eval run raises this to
    # hold NE off while that opening plays out. __post_init__ rejects
    # anything outside 0-29, the valid range of view.day across the 30-day
    # game -- see _MAX_NE_LAND_MIN_DAY.
    ne_land_min_day: int = NE_LAND_MIN_DAY

    # Earliest day the goose purchase may fire, the same day >= *_min_day
    # mechanism ne_land_min_day above uses for NE land. The goose branch
    # never had an earliest-day gate before this knob existed -- it buys the
    # instant cash allows, including turn 0 -- so 0 is DEFAULT-NEUTRAL:
    # day >= 0 is always true and every existing game is bit-for-bit
    # unchanged.
    #
    # Diagnosis (observed strongest public bots, game replays, 2026-09-11):
    # the strongest public bots never buy a goose at all and keep the 5 NW
    # pasture slots for 4 sheep + 1 cow before NE is bought -- our goose
    # takes one of those slots, so a sheep-first opening stalls at 3 sheep.
    # An eval run sets this to the NE day (e.g. 6, ne_land_min_day's own eval
    # value) to defer the goose while that opening plays out. __post_init__
    # rejects anything outside 0-29, the valid range of view.day across the
    # 30-day game -- see _MAX_GOOSE_MIN_DAY.
    goose_min_day: int = GOOSE_MIN_DAY

    # Crew size. plan.py's plan_day(), threaded through decide() the same way
    # every other planner knob is. Defaults to plan.MAX_HIRES_PER_TURN (4),
    # today's hardcoded cap on how many HIRE orders one turn's plan may
    # request; see that constant's own comment for the diagnosis (the
    # midnight crew wipe plus this cap means the morning crew rebuilds over 3
    # hours -- units on the farm at hours 0/1/2/3 measured at 1/5/9/11) and
    # for what market.MAX_ORDERS's shared 10-slot cap does to a request this
    # knob raises past what a busy turn's sells/buys leave room for.
    # __post_init__ rejects anything outside 1-10: 0 would silently disable
    # hiring, and above 10 can never fit more HIRE orders than the market
    # list has slots for in one turn regardless.
    max_hires_per_turn: int = MAX_HIRES_PER_TURN

    # Labor SUPPLY, not dispatch priority (kaggriculture diagnosis,
    # 2026-09-11 continuation of the three labor knobs above): even with
    # max_hires_per_turn/wheat_plant_priority/wheat_plant_hour_cutoff tuned,
    # the crew measures saturated (idle share ~4.7%), and pushing labor
    # toward planting via dispatch instead starves watering and raises weeds
    # 1.8-3.2x. extra_hands hires above plan.py's tile-based hands_target,
    # unconditionally -- threaded through plan_day() the same way
    # max_hires_per_turn is, added AFTER that target's own HANDS_MIN floor
    # and husbandry bonus so it never interacts with either. DEFAULT-NEUTRAL:
    # 0 has no prior hardcoded behavior to reproduce (there was never an
    # implicit "extra hands" term before this knob existed), so hands_target
    # and every action are bit-for-bit unchanged at the default.
    # __post_init__ rejects anything outside 0-5 -- see _MAX_EXTRA_HANDS.
    extra_hands: int = 0

    # Feed logistics. Both default to today's behavior. Raising
    # feed_batch_cap measures WORSE (PICKUP +56% for flat FEED); the cause is
    # that the batch drains the shed into unit inventories and doubles the
    # concurrent fetcher count, collapsing the per-unit share -- self
    # inflicted, not a market fact, and not the mule threshold, which binds
    # on well under 1% of normal-day fetches. See dispatch.FEED_BATCH_CAP.
    feed_batch_cap: int = FEED_BATCH_CAP
    hand_mule_load: int = HAND_MULE_LOAD

    # dispatch.py's own crop calendars (wheat/melon/strawberry alike) leave
    # deliberate unwatered gap days on the assumption that the calendar's
    # NEXT scheduled water actually happens -- true only if the crew isn't
    # saturated. A tile whose scheduled water is missed gets no signal at
    # all (dispatch() never reads the engine's own consecutive_unwatered)
    # and weeds overnight: measured at 47 missed-water deaths per 4 games at
    # shipped defaults, 102-113 in strawberry-heavy configs (kaggriculture,
    # 2026-09-11). False is DEFAULT-NEUTRAL: dispatch() ignores
    # consecutive_unwatered entirely at this default, exactly as before the
    # knob existed. See dispatch.RESCUE_WATER for the full mechanism
    # (including the max_lifespan_step skip for a plant that is exhausting
    # regardless of watering) -- this field only carries the value into
    # dispatch() the same way feed_batch_cap/hand_mule_load above do.
    rescue_water: bool = RESCUE_WATER

    # Strawberry satellite. Defaults to a zero-tile zone, which makes every
    # strawberry code path unreachable and the whole mechanic a bit-exact
    # no-op against the pre-strawberry chassis -- the shipped agent is
    # unchanged until a gate says otherwise.
    strawberry_tile_target: int = STRAWBERRY_TILE_TARGET
    strawberry_plant_daily_cap: int = STRAWBERRY_PLANT_DAILY_CAP
    # Priority tier for a fresh PLANT STRAWBERRY task specifically --
    # dispatch.py's _field_tasks, threaded through dispatch() the same way
    # strawberry_plant_daily_cap above is. Defaults to dispatch.
    # STRAWBERRY_PLANT_PRIORITY, today's hardcoded tier: the same one PLANT
    # WHEAT and PLANT MELON already claim, so at the default a
    # strawberry-zone planting only wins an idle unit once every nearer
    # wheat/melon planting in that same tier is already claimed (priority
    # classes are worked in strict order, 0 most urgent through 4 least, and
    # a tie within one class goes to distance).
    #
    # Diagnosis 2026-09-10: this is why an SW-framed zone (bought day 9-10,
    # target 25) plants only ~5 tiles by the day-12 cutoff -- 17-27 nearer
    # NW/NE wheat/melon tasks claim every idle unit first for hours 2-15 of
    # every day, and the few strawberry claims that DO land arrive too late
    # and stop being regenerated once _field_tasks' own hour<=20 planting
    # gate closes for the day. One tier more urgent
    # (dispatch.STRAWBERRY_PLANT_PRIORITY - 1, i.e. 2) instead competes with
    # wheat's/melon's own in-window WATER tasks, the SAME zone's own
    # already-planted strawberry tiles' WATER/FERTILIZE chores
    # (dispatch._strawberry_task's P2), and pasture CARE/
    # COLLECT_FERTILIZER -- real, ongoing competition, not an empty tier.
    # __post_init__ rejects anything outside dispatch's 0-4 priority range.
    strawberry_plant_priority: int = STRAWBERRY_PLANT_PRIORITY
    # Share of the cash still uncommitted when the strawberry seed line runs
    # that the line may take (plan.STRAWBERRY_SEED_BUDGET_SHARE). Swept, not
    # assumed: 1.0 recovers the sizing that shipped before the 2026-08-19
    # prereg, when the line was sized to the zone and could ask for $1,200 a
    # day regardless of what the feed and land lines behind it needed.
    strawberry_seed_budget_share: float = STRAWBERRY_SEED_BUDGET_SHARE
    # First day the strawberry mechanic may run at all (STRAWBERRY_START_DAY
    # above carries the full diagnosis). 0 keeps today's behavior exactly --
    # every turn sees the configured strawberry_tile_target from turn one,
    # same as before this knob existed. An eval run raises it to hold the
    # ENTIRE mechanic off -- the zone's land reservation included, not just
    # the seed buy -- until the herd and the wheat rush have already run.
    strawberry_start_day: int = STRAWBERRY_START_DAY
    strawberry_floor: float = STRAWBERRY_MIN_PRICE
    # How build_orders' fert_reserve is sized (market.py holds back this many
    # FERTILIZER units from sale so a strawberry tile can FERTILIZE at age
    # 9/13 instead of finding an empty shed -- see market.py's fert_reserve
    # comment). "target" (the default) reproduces today's exact formula:
    # reserve = cfg.strawberry_tile_target, reserved from strawberry_start_day
    # on even though no tile exists yet. Diagnosis 2026-09-10: that is what
    # starves day-9 FERTILIZER sales to 0 (shipped: 10-12 units/day) for an
    # SW-framed zone (target 25), delaying the SW purchase a full day past
    # its $2,500 threshold. "planted" instead reserves exactly the number of
    # OUR tiles currently holding a live strawberry plant (kind PLANT, crop
    # STRAWBERRY -- see _strawberry_planted_tiles below), read fresh off the
    # observation every turn: zero before anything is planted, so a zone
    # that has not started yet sells fertilizer exactly like strawberry-off,
    # and it only ever withholds units a real tile can actually spend.
    # __post_init__ rejects any value other than "target"/"planted".
    strawberry_fert_reserve: str = "target"
    # A measuring instrument, not a promotion candidate.
    # STRAWBERRY_REFERENCE_QUADRANTS pins the strawberry zone to a fixed
    # frame, while melon_tiles deliberately tracks the LIVE
    # unlocked_quadrants; nobody has measured whether that difference reaches
    # the agent's behavior at all. It provably cannot before SW is bought --
    # the unlock state IS the reference frame until then -- so the whole
    # question lives in the turns after a third quadrant lands. True swaps in
    # view.unlocked_quadrants so an A/B can answer it empirically. False, the
    # shipped default, is today's call bit-for-bit.
    strawberry_frame_live: bool = False
    # Which quadrants the frame covers when strawberry_frame_live is False
    # (the shipped case). Defaults to STRAWBERRY_REFERENCE_QUADRANTS, so
    # every existing PolicyConfig() keeps today's NW+NE zone exactly. An
    # eval run overrides this (e.g. to ("SW",)) to measure putting the zone
    # somewhere the live agent tends to leave idle instead of carving it out
    # of NW+NE wheat ground: a zone in NW+NE measures at $7-10k/game of
    # displaced wheat revenue, while SW (bought day 9-10) sits with 20-38
    # empty tiles on days 10-16. See constants.strawberry_tiles_for_frame's
    # docstring for why a non-default value here runs a different formula
    # than the default does, and __post_init__ below for the coercion an
    # agent_config override (JSON has no tuple type) needs before this
    # reaches any @cache'd function.
    strawberry_frame_quadrants: tuple[str, ...] = STRAWBERRY_REFERENCE_QUADRANTS

    # M2c (kaggriculture#59): two-tier shed valve + WOOL/MILK crash latches.
    # See the VALVE_*/*_CRASH_TRIGGER module constants above and market.py's
    # module docstring (M2c section) for the full behavior this drives.
    valve_soft_threshold: int = VALVE_SOFT_THRESHOLD
    valve_hard_threshold: int = VALVE_HARD_THRESHOLD
    valve_soft_cap: int = VALVE_SOFT_CAP
    wool_floor: float = WOOL_MIN_PRICE
    milk_floor: float = MILK_MIN_PRICE
    fert_floor: float = FERT_MIN_PRICE
    wool_crash_trigger: float = WOOL_CRASH_TRIGGER
    milk_crash_trigger: float = MILK_CRASH_TRIGGER
    crash_trigger_ticks: int = CRASH_TRIGGER_TICKS
    wool_milk_sell_cap: int = WOOL_MILK_SELL_CAP
    clone_front_run: bool = True

    @property
    def pasture_tile_target(self) -> int:
        """Derived, not independently settable -- an override here would let
        the pasture zone size drift out of sync with the animal targets it's
        supposed to exactly cover (one animal per pasture tile)."""
        return self.cow_target + self.sheep_target

    def __post_init__(self) -> None:
        """Coerce + validate strawberry_frame_quadrants, strawberry_plant_priority
        and strawberry_fert_reserve on EVERY construction (not just the
        agent_config path -- a frozen dataclass has no other post-construction
        hook to hang this on).

        harness.episodes.resolve_agent builds this from a CLI --agent-config
        JSON object (``PolicyConfig(**agent_config)``); JSON has no tuple
        type, so a list must be coerced before it reaches
        constants.strawberry_tiles_for_frame/target_tiles -- both
        ``@cache``'d, so an unhashable list would crash them (and this
        dataclass's own generated ``__hash__`` along with it), and a list
        never equals the tuple default. An unknown quadrant name is rejected
        here too, loudly, rather than silently building a zone that can
        never contain a single real tile.

        strawberry_plant_priority (and wheat_plant_priority, the same check)
        must land inside dispatch()'s own 0-4 priority-class range, or it
        would KeyError deep inside a turn instead of failing here, at
        construction, where the error names the field.
        strawberry_fert_reserve must be one of _KNOWN_FERT_RESERVE_MODES, for
        the same reason strawberry_frame_quadrants' quadrant names are
        checked here rather than left to silently build an empty zone.

        max_hires_per_turn must land inside 1-10 (market.MAX_ORDERS's own
        10-slot cap), and wheat_plant_hour_cutoff inside 0-23 (the valid
        range of view.hour) -- both checked here for the same reason as
        every other field above: loud at construction, not a silent no-op or
        a crash deep inside a turn.

        extra_hands must land inside 0-5 (_MAX_EXTRA_HANDS) -- a deliberately
        conservative guard against a runaway CLI override, checked here for
        the same "loud at construction" reason as every other field above.

        ne_land_min_day must land inside 0-29 (the valid range of view.day),
        checked here for the same "loud at construction" reason as every
        other field above.

        goose_min_day must land inside 0-29 (the valid range of view.day),
        checked here for the same "loud at construction" reason as every
        other field above.

        animal_buy_order gets the same list-to-tuple coercion as
        strawberry_frame_quadrants above (JSON has no tuple type, so a CLI
        --agent-config override arrives as a list -- unhashable, and never
        equal to the tuple default), and is rejected unless it is a
        permutation of plan.ANIMAL_BUY_ORDER: anything else would either
        KeyError inside plan_day's per-species lookups or silently skip a
        species' purchase window for the rest of the game.
        """
        frame = tuple(self.strawberry_frame_quadrants)
        unknown = sorted(set(frame) - _KNOWN_QUADRANTS)
        if unknown:
            raise ValueError(
                f"unknown quadrant name(s) in strawberry_frame_quadrants: {unknown!r}; "
                f"known quadrants: {sorted(_KNOWN_QUADRANTS)}"
            )
        object.__setattr__(self, "strawberry_frame_quadrants", frame)

        if not (_MIN_TASK_PRIORITY <= self.strawberry_plant_priority <= _MAX_TASK_PRIORITY):
            raise ValueError(
                f"strawberry_plant_priority must be within dispatch's "
                f"{_MIN_TASK_PRIORITY} (most urgent) - {_MAX_TASK_PRIORITY} (least urgent) "
                f"priority range, got {self.strawberry_plant_priority!r}"
            )

        if self.strawberry_fert_reserve not in _KNOWN_FERT_RESERVE_MODES:
            raise ValueError(
                f"unknown strawberry_fert_reserve: {self.strawberry_fert_reserve!r}; "
                f"expected one of {sorted(_KNOWN_FERT_RESERVE_MODES)}"
            )

        if not (_MIN_TASK_PRIORITY <= self.wheat_plant_priority <= _MAX_TASK_PRIORITY):
            raise ValueError(
                f"wheat_plant_priority must be within dispatch's "
                f"{_MIN_TASK_PRIORITY} (most urgent) - {_MAX_TASK_PRIORITY} (least urgent) "
                f"priority range, got {self.wheat_plant_priority!r}"
            )

        if not (_MIN_PLANT_HOUR_CUTOFF <= self.wheat_plant_hour_cutoff <= _MAX_PLANT_HOUR_CUTOFF):
            raise ValueError(
                f"wheat_plant_hour_cutoff must be within "
                f"{_MIN_PLANT_HOUR_CUTOFF}-{_MAX_PLANT_HOUR_CUTOFF} (the valid range of "
                f"view.hour), got {self.wheat_plant_hour_cutoff!r}"
            )

        if not (_MIN_HIRES_PER_TURN <= self.max_hires_per_turn <= _MAX_HIRES_PER_TURN):
            raise ValueError(
                f"max_hires_per_turn must be within {_MIN_HIRES_PER_TURN}-"
                f"{_MAX_HIRES_PER_TURN}, got {self.max_hires_per_turn!r}"
            )

        if not (_MIN_EXTRA_HANDS <= self.extra_hands <= _MAX_EXTRA_HANDS):
            raise ValueError(
                f"extra_hands must be within {_MIN_EXTRA_HANDS}-{_MAX_EXTRA_HANDS}, "
                f"got {self.extra_hands!r}"
            )

        if not (_MIN_NE_LAND_MIN_DAY <= self.ne_land_min_day <= _MAX_NE_LAND_MIN_DAY):
            raise ValueError(
                f"ne_land_min_day must be within {_MIN_NE_LAND_MIN_DAY}-"
                f"{_MAX_NE_LAND_MIN_DAY}, got {self.ne_land_min_day!r}"
            )

        if not (_MIN_GOOSE_MIN_DAY <= self.goose_min_day <= _MAX_GOOSE_MIN_DAY):
            raise ValueError(
                f"goose_min_day must be within {_MIN_GOOSE_MIN_DAY}-"
                f"{_MAX_GOOSE_MIN_DAY}, got {self.goose_min_day!r}"
            )

        animal_order = tuple(self.animal_buy_order)
        if sorted(animal_order) != _SORTED_ANIMAL_BUY_ORDER:
            raise ValueError(
                f"animal_buy_order must be a permutation of {ANIMAL_BUY_ORDER!r}, "
                f"got {animal_order!r}"
            )
        object.__setattr__(self, "animal_buy_order", animal_order)


def _owned_count(view: FarmView, species: str) -> int:
    """Total of one animal species currently owned: placed on a tile, sitting
    in the shed (bought but not yet walked to a pasture/coop), or mid-carry
    in a unit's inventory. Used for purchase-target gating (goose/cow/sheep
    alike), so a bought-but-unplaced animal still counts toward "already
    have enough" and doesn't get rebought."""
    placed = sum(
        1
        for row in view.tiles
        for tile in row
        if isinstance(tile, dict) and tile.get("animal") == species
    )
    shed = view.shed.get(species, 0)
    carried = sum(inv.get(species, 0) for inv in view.inventories)
    return placed + shed + carried


def _animals_placed(view: FarmView) -> int:
    """Count of tiles with any placed animal (goose + cow + sheep) — the
    figure that actually drives daily chore load (FEED/CARE/COLLECT_
    FERTILIZER/HARVEST only apply once an animal is on a tile), used to
    size the feed reserve/top-up and the husbandry hands bonus."""
    return sum(
        1 for row in view.tiles for tile in row if isinstance(tile, dict) and "animal" in tile
    )


def _empty_built_pastures(view: FarmView, pastures: list[tuple[int, int]]) -> int:
    count = 0
    for x, y in pastures:
        tile = view.tiles[y][x]
        if isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile:
            count += 1
    return count


def _wheat_on_hand(view: FarmView) -> int:
    return view.shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in view.inventories)


def _strawberry_planted_tiles(view: FarmView) -> int:
    """Count of OUR tiles currently holding a live strawberry plant (kind
    PLANT, crop STRAWBERRY) -- read fresh off the observation every turn for
    PolicyConfig.strawberry_fert_reserve == "planted". Zero before anything
    has been planted, same as a strawberry-off agent, regardless of what
    strawberry_tile_target is configured to."""
    return sum(
        1
        for row in view.tiles
        for tile in row
        if isinstance(tile, dict)
        and tile.get("kind") == "PLANT"
        and tile.get("crop") == "STRAWBERRY"
    )


def _plantable_targets(view: FarmView, tiles: list[tuple[int, int]]) -> int:
    count = 0
    for x, y in tiles:
        tile = view.tiles[y][x]
        if tile is None or (isinstance(tile, dict) and tile.get("kind") == "WEED"):
            count += 1
    return count


def _zone_fallthrough_tiles(
    view: FarmView, config: PolicyConfig, strawberry_set: frozenset[tuple[int, int]]
) -> int:
    """Empty strawberry-zone ground that the DISPATCHER will plant with wheat.

    ``dispatch.py``'s strawberry branch already falls an empty zone tile
    through to a WHEAT plant once the daily strawberry cap is spent or the
    planting window has shut -- see its "reservation trap, fixed rather than
    inherited" comment. The planner did not know that: ``wheat_tiles``
    subtracts ``strawberry_set`` outright, so the seed line never bought for
    that ground and the fall-through could not fire against an empty shed.
    Measured at ``strawberry_tile_target = 31`` (prereg 2026-08-28), wheat's
    plantable target sat at exactly 0 for thirteen days while 21 zone tiles
    were empty and the farm ran on $0-165 because nothing was producing.

    The horizon here is strawberry's own, not the dispatcher's single-turn
    budget: ``plan.py`` sizes the strawberry seed line to TWO days of the
    planting stagger, so anything past ``2 * cap`` is ground strawberry's own
    seed line is not asking for either. Counting from that boundary makes the
    two lines disjoint by construction -- no tile is ever counted by both --
    which is what keeps this from double-buying seed for the same square. It
    is deliberately the conservative side of the dispatcher's real behaviour:
    the dispatcher would hand wheat more than this on any turn where the daily
    cap is already partly spent.

    Reservation itself is untouched. ``strawberry_tiles`` keeps its fixed
    reference frame and its size, and nothing is planted here that the
    dispatcher would not already have planted -- so the seventeen-day-plant
    invariant ``STRAWBERRY_REFERENCE_QUADRANTS`` exists to protect is not in
    play.
    """
    empty_zone = _plantable_targets(view, sorted(strawberry_set))
    if view.day > STRAWBERRY_PLANT_CUTOFF_DAY:
        # Window shut: the dispatcher hands wheat the whole empty zone, and
        # plan.py's own strawberry seed line has stopped buying, so there is
        # nothing left to stay disjoint from.
        return empty_zone
    return max(0, empty_zone - 2 * config.strawberry_plant_daily_cap)


def _shed_capacity(config: dict[str, Any] | None) -> int:
    """The engine's real per-episode shed capacity, defaulting to 100 (the
    engine's own default) when no config is supplied -- every existing unit
    test calls ``decide`` with ``config=None``, so this must be None-safe."""
    if config is None:
        return 100
    return int(config.get("shedCapacity", 100))


def _valve_tier(shed: dict[str, int], config: dict[str, Any] | None, resolved: PolicyConfig) -> int:
    """M2c (kaggriculture#59): 0/1/2 shed-fill tier from total shed contents.

    Thresholds are absolute units against the engine's default 100-unit
    shed; scaled by the real ``shedCapacity``/100 so a non-default capacity
    still trips the valve at the same *fraction* full, keeping integer
    semantics (floor division, not a float threshold)."""
    capacity = _shed_capacity(config)
    shed_total = sum(shed.values())
    soft_threshold = (resolved.valve_soft_threshold * capacity) // 100
    hard_threshold = (resolved.valve_hard_threshold * capacity) // 100
    if shed_total >= hard_threshold:
        return 2
    if shed_total >= soft_threshold:
        return 1
    return 0


def _melon_sell_qty(orders: list[list[object]]) -> int:
    """The quantity from this turn's own ``["SELL", "MELON", n]`` order, if
    any -- fed back to ``MelonMarketMemory`` so next turn's opponent-sell
    attribution can net our own sale out of the shared inventory delta."""
    for order in orders:
        if len(order) >= 3 and order[0] == "SELL" and order[1] == "MELON":
            qty = order[2]
            return qty if isinstance(qty, int) else 0
    return 0


def make_policy(
    clock: Callable[[], float] = time.monotonic,
    policy_config: PolicyConfig | None = None,
) -> Any:
    """Build the policy callable with its episode-scoped trackers closed over."""
    resolved_config = policy_config if policy_config is not None else PolicyConfig()
    tracker = StateTracker()
    melon_memory = MelonMarketMemory()
    wool_latch = ProductCrashLatch(
        resolved_config.wool_crash_trigger, resolved_config.crash_trigger_ticks
    )
    milk_latch = ProductCrashLatch(
        resolved_config.milk_crash_trigger, resolved_config.crash_trigger_ticks
    )
    # Last turn's task assignment, so a unit already walking toward a tile is
    # not made to re-win it from scratch every turn. Held here rather than in
    # the dispatcher because the dispatcher is deliberately stateless; this is
    # the same episode-scoped-closure pattern as the trackers above. A turn
    # that bails to pass_action() simply leaves it untouched, which is right:
    # nothing moved, so last turn's claims are still the current ones.
    unit_claims: dict[int, tuple[int, int]] = {}

    def decide(obs: Observation, config: dict[str, Any] | None = None) -> Action:
        start = clock()
        tracker.observe(obs)
        # Runs here, ahead of the soft-budget check below, so melon-market
        # continuity survives even a turn that later bails to pass_action()
        # (mirrors StateTracker's own placement) -- a bailed turn issues no
        # real market orders, so record_our_melon_sell is correctly never
        # called for it, leaving next turn's "our_sold_last_turn" at 0.
        melon_memory.observe(obs)
        view = parse_obs(obs)
        # Same continuity argument as melon_memory above: a turn that later
        # bails to pass_action() still needs its price tick counted, or a
        # crash spanning a budget-exhausted turn would under-count toward
        # crash_trigger_ticks.
        wool_latch.observe(view.prices.get("WOOL", 0.0), view.step)
        milk_latch.observe(view.prices.get("MILK", 0.0), view.step)

        if clock() - start > resolved_config.soft_budget_seconds:
            return pass_action()

        # Effective per-turn config. Before strawberry_start_day, every read
        # below runs as though strawberry_tile_target were 0 -- not just the
        # seed-buy line (see STRAWBERRY_START_DAY above for the full
        # diagnosis of why gating only the seed line was not enough). cfg is
        # identical to resolved_config in every OTHER field always, so any
        # code path that never touches strawberry_tile_target is provably
        # unaffected by this line; the point is that no downstream read below
        # needs its own, separate gate to get that guarantee.
        cfg = (
            replace(resolved_config, strawberry_tile_target=0)
            if view.day < resolved_config.strawberry_start_day
            else resolved_config
        )

        tiles = target_tiles(view.unlocked_quadrants)
        melons = melon_tiles(view.unlocked_quadrants, target=cfg.melon_tile_target)
        # Fixed reference frame, NOT view.unlocked_quadrants -- pastures must
        # never migrate as SW/SE unlock later (constants.PASTURE_REFERENCE_
        # QUADRANTS explains why: a live value orphans built pastures and
        # placed animals the instant the nearest-shed-first ordering shifts).
        pastures = pasture_tiles(PASTURE_REFERENCE_QUADRANTS, target=cfg.pasture_tile_target)
        melon_set = frozenset(melons)
        pasture_set = frozenset(pastures)
        # Fixed by default (cfg.strawberry_frame_quadrants) for the same
        # reason pastures use a fixed frame, and more urgently: a strawberry
        # tile is occupied for seventeen days, so a zone that drifted on a
        # BUY_LAND would orphan a live plant mid-cycle and it would weed two
        # days later. See STRAWBERRY_REFERENCE_QUADRANTS.
        #
        # strawberry_frame_live lifts that pin, for measurement only. What
        # makes a live frame survivable for a CROP and not for an ANIMAL is an
        # asymmetry in dispatch: standing-crop scheduling keys on the tile's
        # own tile["crop"] (dispatch.py, commit 01a5123), so a strawberry the
        # zone sheds is still worked on strawberry's seventeen-day timeline
        # rather than wheat's five-day one -- pinned by
        # test_strawberry_evicted_from_the_zone_keeps_strawberry_timing. Animal
        # chores have no such fallback: dispatch gates them on `is_pasture`
        # zone membership with nothing animal-generic behind it, so a drifting
        # PASTURE_REFERENCE_QUADRANTS silently starves and loses placed
        # animals. Do NOT mirror this flag onto pastures.
        strawberry_frame = (
            view.unlocked_quadrants if cfg.strawberry_frame_live else cfg.strawberry_frame_quadrants
        )
        # STRAWBERRY_REFERENCE_QUADRANTS keeps the OLD fixed-offset formula
        # (strawberry_tiles): it assumes melon+pasture fill exactly the
        # frame's first 18 tiles, which only holds for this one frame, and
        # even then only intermittently -- constants.strawberry_tiles_for_
        # frame's docstring has the full mechanism, and test_constants.py's
        # test_the_general_formula_disagrees_with_the_default_frame_formula_
        # once_sw_unlocks proves the two formulas actually disagree for this
        # frame across most of a real game. Any OTHER frame routes through
        # the general, melon/pasture-aware formula instead -- there is no
        # shipped-behavior default to preserve for those.
        # strawberry_frame_live predates strawberry_frame_quadrants and keeps
        # today's fixed-offset formula over the live quadrants; only a non-default
        # FIXED frame takes the melon/pasture-aware one.
        if cfg.strawberry_frame_live or strawberry_frame == STRAWBERRY_REFERENCE_QUADRANTS:
            strawberries = strawberry_tiles(strawberry_frame, target=cfg.strawberry_tile_target)
        else:
            strawberries = strawberry_tiles_for_frame(
                strawberry_frame, cfg.strawberry_tile_target, melon_set, pasture_set
            )
        strawberry_set = frozenset(strawberries) - melon_set - pasture_set
        # Set difference, not a positional slice: pasture_set's positions are
        # anchored to the fixed reference frame above and are not guaranteed
        # to occupy any particular prefix of the *live* tiles ordering.
        # Capped at wheat_rush_tiles -- an explicit, config-driven bound on
        # wheat's own zone instead of an unbounded remainder.
        wheat_tiles = [
            t
            for t in tiles
            if t not in melon_set and t not in pasture_set and t not in strawberry_set
        ][: cfg.wheat_rush_tiles]
        goose = _owned_count(view, "GOOSE") > 0
        cows_owned = _owned_count(view, "COW")
        sheep_owned = _owned_count(view, "SHEEP")
        animals_placed = _animals_placed(view)
        plan = plan_day(
            day=view.day,
            money=view.money,
            wheat_seeds=view.seeds.get("WHEAT", 0),
            plantable_target_tiles=(
                _plantable_targets(view, wheat_tiles)
                + _zone_fallthrough_tiles(view, cfg, strawberry_set)
            ),
            melon_seeds=view.seeds.get("MELON", 0),
            empty_melon_tiles=_plantable_targets(view, melons),
            strawberry_seeds=view.seeds.get("STRAWBERRY", 0),
            empty_strawberry_tiles=_plantable_targets(view, sorted(strawberry_set)),
            strawberry_plant_daily_cap=cfg.strawberry_plant_daily_cap,
            strawberry_seed_budget_share=cfg.strawberry_seed_budget_share,
            wheat_on_hand=_wheat_on_hand(view),
            goose_owned=goose,
            goose_min_day=cfg.goose_min_day,
            hires_today=view.hires_today,
            unlocked_quadrants=view.unlocked_quadrants,
            active_tiles=len(tiles),
            max_owned_quadrants=cfg.max_owned_quadrants,
            ne_land_min_day=cfg.ne_land_min_day,
            cows_owned=cows_owned,
            sheep_owned=sheep_owned,
            empty_pastures=_empty_built_pastures(view, pastures),
            animals_placed=animals_placed,
            feed_reserve=cfg.feed_reserve,
            cow_target=cfg.cow_target,
            sheep_target=cfg.sheep_target,
            animal_buy_order=cfg.animal_buy_order,
            max_hires_per_turn=cfg.max_hires_per_turn,
            extra_hands=cfg.extra_hands,
        )
        actions = dispatch(
            view,
            tiles,
            melon_set,
            pasture_set,
            strawberry_set,
            prior_claims=unit_claims,
            strawberry_plant_daily_cap=cfg.strawberry_plant_daily_cap,
            strawberry_plant_priority=cfg.strawberry_plant_priority,
            wheat_plant_priority=cfg.wheat_plant_priority,
            wheat_plant_hour_cutoff=cfg.wheat_plant_hour_cutoff,
            feed_batch_cap=cfg.feed_batch_cap,
            hand_mule_load=cfg.hand_mule_load,
            rescue_water=cfg.rescue_water,
        )
        unit_claims.clear()
        unit_claims.update(actions.claims)

        # Buys first, hires last: if the 10-slot cap ever truncates, it drops
        # trailing hires (which self-heal next turn) rather than a purchase.
        buys: list[list[object]] = list(plan.buys)
        buys.extend([["HIRE"]] * plan.hire_count)
        any_animal_owned = goose or cows_owned > 0 or sheep_owned > 0
        wheat_reserve = animals_placed + cfg.feed_reserve if any_animal_owned else 0
        fert_reserve = (
            cfg.strawberry_tile_target
            if cfg.strawberry_fert_reserve == "target"
            else _strawberry_planted_tiles(view)
        )
        orders = build_orders(
            shed=view.shed,
            prices=view.prices,
            day=view.day,
            hour=view.hour,
            wheat_reserve=wheat_reserve,
            buys=buys,
            melon_contested=melon_memory.contested,
            melon_days_since_contested=melon_memory.days_since_contested(view.day),
            melon_rolling_max=melon_memory.rolling_price_max,
            valve_tier=_valve_tier(view.shed, config, cfg),
            valve_soft_cap=cfg.valve_soft_cap,
            wool_floor=cfg.wool_floor,
            milk_floor=cfg.milk_floor,
            fert_floor=cfg.fert_floor,
            strawberry_floor=cfg.strawberry_floor,
            # cfg.strawberry_fert_reserve selects the formula (see
            # PolicyConfig). "target" (the default) reproduces today's exact
            # derivation -- reserve = cfg.strawberry_tile_target -- so it is
            # exactly 0 (and the sell path exactly unchanged) whenever
            # strawberry is off, including before strawberry_start_day
            # (cfg.strawberry_tile_target is 0 there, same as every other
            # zone read this turn). "planted" instead reserves only what is
            # actually standing (_strawberry_planted_tiles), so a zone that
            # has not started planting yet withholds nothing.
            fert_reserve=fert_reserve,
            wool_crashed=wool_latch.latched,
            milk_crashed=milk_latch.latched,
            wool_milk_sell_cap=cfg.wool_milk_sell_cap,
            front_run_products=(
                clone_pressure_products(view) if cfg.clone_front_run else frozenset()
            ),
        )
        # Clamped to what we actually held, not just what we asked for --
        # build_orders' own _capped_sell already enforces this (an order for
        # more than the shed count never gets emitted), so the clamp here is
        # redundant-but-cheap defensive insurance for next turn's attribution
        # math, matching MelonMarketMemory's own contract.
        melon_sold_this_turn = _melon_sell_qty(orders)
        melon_memory.record_our_melon_sell(min(melon_sold_this_turn, view.shed.get("MELON", 0)))
        return {"farmer": actions.farmer, "hands": actions.hands, "market": orders}

    return decide
