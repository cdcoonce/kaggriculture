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
    SHEEP_TARGET,
    STRAWBERRY_REFERENCE_QUADRANTS,
    STRAWBERRY_TILE_TARGET,
    melon_tiles,
    pasture_tiles,
    strawberry_tiles,
    target_tiles,
)
from agent.dispatch import (
    FEED_BATCH_CAP,
    HAND_MULE_LOAD,
    STRAWBERRY_PLANT_CUTOFF_DAY,
    STRAWBERRY_PLANT_DAILY_CAP,
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
from agent.plan import FEED_RESERVE, STRAWBERRY_SEED_BUDGET_SHARE, plan_day
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
    wheat_rush_tiles: int = _WHEAT_RUSH_TILES_DEFAULT

    # How many quadrants to OWN, counting the always-unlocked NW. The
    # shipped default is 3 of the board's 4 -- this knob is LIVE, not dormant.
    # It binds on every game that reaches three quadrants, refusing the $4,000
    # SE purchase. Set it to 4 to recover pre-cap behavior; that is what the
    # eval arms do, and it is the value a frozen pre-cap baseline needs.
    # Land is not a one-off cost: hands are daily rentals and hands_target
    # scales with active_tiles, so every quadrant carries a standing crew
    # charge on top of its price. See constants.MAX_OWNED_QUADRANTS.
    max_owned_quadrants: int = MAX_OWNED_QUADRANTS

    # Feed logistics. Both default to today's behavior. Raising
    # feed_batch_cap measures WORSE (PICKUP +56% for flat FEED); the cause is
    # that the batch drains the shed into unit inventories and doubles the
    # concurrent fetcher count, collapsing the per-unit share -- self
    # inflicted, not a market fact, and not the mule threshold, which binds
    # on well under 1% of normal-day fetches. See dispatch.FEED_BATCH_CAP.
    feed_batch_cap: int = FEED_BATCH_CAP
    hand_mule_load: int = HAND_MULE_LOAD

    # Strawberry satellite. Defaults to a zero-tile zone, which makes every
    # strawberry code path unreachable and the whole mechanic a bit-exact
    # no-op against the pre-strawberry chassis -- the shipped agent is
    # unchanged until a gate says otherwise.
    strawberry_tile_target: int = STRAWBERRY_TILE_TARGET
    strawberry_plant_daily_cap: int = STRAWBERRY_PLANT_DAILY_CAP
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
        # Fixed reference frame for the same reason pastures use one, and more
        # urgently: a strawberry tile is occupied for seventeen days, so a zone
        # that drifted on a BUY_LAND would orphan a live plant mid-cycle and it
        # would weed two days later. See STRAWBERRY_REFERENCE_QUADRANTS.
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
            view.unlocked_quadrants if cfg.strawberry_frame_live else STRAWBERRY_REFERENCE_QUADRANTS
        )
        strawberries = strawberry_tiles(strawberry_frame, target=cfg.strawberry_tile_target)
        melon_set = frozenset(melons)
        pasture_set = frozenset(pastures)
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
            hires_today=view.hires_today,
            unlocked_quadrants=view.unlocked_quadrants,
            active_tiles=len(tiles),
            max_owned_quadrants=cfg.max_owned_quadrants,
            cows_owned=cows_owned,
            sheep_owned=sheep_owned,
            empty_pastures=_empty_built_pastures(view, pastures),
            animals_placed=animals_placed,
            feed_reserve=cfg.feed_reserve,
            cow_target=cfg.cow_target,
            sheep_target=cfg.sheep_target,
        )
        actions = dispatch(
            view,
            tiles,
            melon_set,
            pasture_set,
            strawberry_set,
            prior_claims=unit_claims,
            strawberry_plant_daily_cap=cfg.strawberry_plant_daily_cap,
            feed_batch_cap=cfg.feed_batch_cap,
            hand_mule_load=cfg.hand_mule_load,
        )
        unit_claims.clear()
        unit_claims.update(actions.claims)

        # Buys first, hires last: if the 10-slot cap ever truncates, it drops
        # trailing hires (which self-heal next turn) rather than a purchase.
        buys: list[list[object]] = list(plan.buys)
        buys.extend([["HIRE"]] * plan.hire_count)
        any_animal_owned = goose or cows_owned > 0 or sheep_owned > 0
        wheat_reserve = animals_placed + cfg.feed_reserve if any_animal_owned else 0
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
            # Derived, not a separate knob, so it can never drift out of sync
            # with the zone it exists to serve -- and so it is exactly 0 (and
            # the sell path exactly unchanged) whenever strawberry is off,
            # including before strawberry_start_day (cfg.strawberry_tile_target
            # is 0 there, same as every other zone read this turn).
            fert_reserve=cfg.strawberry_tile_target,
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
