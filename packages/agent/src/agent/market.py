"""Market-order builder — index-0 price-aware selling (strategy doc).

Orders resolve by queue-slot index across both players: slot 0 fully executes
(moving price) before either player's slot-1 order runs. Crashable goods
therefore always go at the front of the sell block, most price-sensitive
first: melon (quadratic above-curve: base $250, -25% at ~+79 net oversupply,
~$1 floor at ~+158) leads, then milk (linear above-curve, base $160, -25% at
~+19), then wool (quadratic, base $200, -25% at ~+29) -- both currently
under-supplied by the field but crash-prone the moment husbandry lands at
scale -- then fertilizer (linear above-curve, -$0.20/unit oversupply). Wheat/
egg are glut-proof staples: sell every turn, early and often (holding them
only risks shed overflow — cap 100, silent discard).

M2b adds three melon-specific behaviors on top of that base strategy, all
driven by ``agent.state.MelonMarketMemory`` (this module stays pure -- the
policy layer computes ``melon_contested``/``melon_days_since_contested``/
``melon_rolling_max`` and passes them straight in):

1. **Dynamic contested floor.** Replay evidence (2/19 ladder games) showed an
   opponent dump crashing the shared melon price below the static $195 floor
   for the rest of the game, with the floor logic then holding ~64-70 melons
   to day-29 forced liquidation at $84-104 instead of the ~$270 the market
   traded at live. Once ``MelonMarketMemory`` latches CONTESTED, the floor
   decays $8/day from $195 down to a $120 clamp, and a peak gate additionally
   requires selling within $15 of the rolling 24-turn price max -- sell into
   local post-crash peaks instead of the first tick that clears the (now much
   lower) floor.
2. **Liquidation ramp.** The old day-29 cliff let a contested game's backlog
   sit through days 27-28 at a floor the crashed price could no longer clear,
   then dump-all at day 29 into whatever the market happened to be quoting.
   Melon now ramps down explicitly -- day 27 floor $100, day 28 floor $60,
   day >= 29 sells everything uncapped -- so a large backlog has two extra
   days of graduated exits before the unconditional dump. Every other product
   keeps the flat day-29 cliff.
3. **Satellite sell batching.** MELON/MILK/WOOL sell in every hour except a
   blocked mid-morning window, rather than the instant a turn's price clears
   the floor. Exempt from day 27 on: the endgame liquidation window trades
   batching discipline for maximum exit flexibility. WHEAT/EGG/FERTILIZER are
   unaffected.

   Deviation from the original spec (documented per the build brief's own
   "tune and document" clause): the first cut used a narrow 10-hour allowlist
   ({0, 1, 12, 13} + 18-23 -- hour 0 plus the two post-town-tick reveal hours,
   ``state.TOWN_TICK_HOURS``, plus end-of-day). Solo-probed against frozen M2a
   (seeds 41/43, vs "starter") that cost -4.9% to -5.4% money -- over the ~3%
   budget -- with essentially flat SELL MELON/MILK/WOOL cumulative volume, so
   the loss was priced, not missed sales: in this thin, uncontested market
   melon/milk/wool prices only drift slowly (scarcity-driven, no real
   opponent selling to time around), so restricting to 10 checks/day mostly
   just delayed cash into a compounding hire/seed/animal-purchase pipeline
   without ever buying a better price. A swept blocklist of {4-9} (the
   deep-morning stretch, both town-tick-distant and pre-day-end-distant) held
   parity or a small gain across 9 seeds (41/43/44/47/50/60/70/90/123: worst
   case +0.00%, best +2.47%) while still keeping hours 1/13 (post-tick) and
   18-23 (day's end) meaningfully concentrated within the *allowed* set.

M2c (kaggriculture#59) adds a shed-overflow safety valve and replaces WOOL/
MILK's static floors with regime-conditional ones, on top of everything
above:

4. **Two-tier shed valve.** A floor that never yields against a ranch dumper
   with no floors of its own eventually backs the shared 100-unit shed up to
   full -- and the engine SILENTLY DESTROYS anything DROPped (including the
   automatic end-of-day sweep) at a full shed, so healthy wheat/egg income
   evaporates right along with the unsellable backlog. ``policy.decide``
   computes a shed-fill ``valve_tier`` from ``view.shed`` each turn (0 below
   a soft threshold, 1 above it, 2 above a hard threshold -- both thresholds
   scaled to the engine's actual ``shedCapacity``) and threads it straight
   in. Tier 1 ignores every floor below (melon's included) and sells at
   market on a shared soft cap; tier 2 ignores floors AND per-product caps
   and sells the entire shed for MELON/MILK/WOOL/FERTILIZER (WHEAT still
   keeps its feed reserve -- the valve exists to save the farm's OTHER
   income, not to starve the animals it's trying to protect).
5. **Regime-conditional WOOL/MILK floors.** The old static floors held
   forever against a floor-free opponent (the actual shape of the #59
   defect). Once ``agent.state.ProductCrashLatch`` sees enough consecutive
   below-trigger price ticks, that product's floor waives permanently for
   the rest of the episode -- same discipline, and the same never-unlatch
   rationale, as melon's own CONTESTED latch. FERTILIZER's floor also moves
   from $55 to $15 (fertilizer's floor now only gates whether it's worth
   selling versus feeding back in as a wheat-yield input, since the valve --
   not the floor -- is what handles a genuine backlog), and WOOL/MILK's
   per-turn cap goes from 2 to a shared 4.

   M2c also moved WOOL's floor from $150 to $200 -- this was itself a
   regression, caught and reverted back to $150: $200 is exactly WOOL's
   engine ``base`` (its equilibrium quote), so it permitted only ~3 units of
   cumulative oversupply before latching shut, backlogging wool in the
   shared shed instead of selling steadily -- partially undoing this same
   section's own shed-valve fix. See ``WOOL_MIN_PRICE`` below and
   ``test_market.py::test_shipped_floors_permit_meaningful_volume_before_equilibrium``
   for the general guard against any floor landing at/above equilibrium.
"""

from __future__ import annotations

from collections.abc import Mapping

SELL_ALL = 99999  # engine validates no upper bound; safe "sell everything" idiom
MAX_ORDERS = 10  # maxMarketOrdersPerTurn — extras silently dropped by the engine
# M2c (kaggriculture#59): lowered from $55 -- the valve, not the floor, now
# handles a genuine fertilizer backlog, so this only gates whether a sale is
# worth it versus feeding fertilizer back in as a +2-yield wheat input.
FERT_MIN_PRICE = 15.0
MELON_MIN_PRICE = 195.0  # ~22% off the $250 base — roughly where the crash starts biting
MILK_MIN_PRICE = 120.0  # 25% off the $160 base — linear crash starts at ~+19 oversupply
# Invariant: a sell floor must sit meaningfully below its product's own
# equilibrium quote (``market_price(item, I0) == base`` always) so it permits
# a real volume of sales before latching shut -- not just the handful of
# units a floor pinned at/above equilibrium allows (see
# test_market.py::test_shipped_floors_permit_meaningful_volume_before_equilibrium,
# which re-derives the permitted-unit count from the real engine for every
# shipped floor).
#
# M2c (kaggriculture#59) briefly raised this to $200 -- exactly WOOL's base,
# i.e. exactly its equilibrium quote -- reasoning that ProductCrashLatch
# (agent.state) would waive it once the price crashed hard enough. But $200
# permits only ~3 cumulative units of oversupply before the quote dips a
# single dollar under the floor and it latches shut, so wool backlogged in
# the shared shed well before any crash ever got the latch to trip --
# partially undoing M2c's own shed-valve fix. $150 (this module's original,
# pre-M2c value) permits ~30 units, restoring steady near-equilibrium selling
# while the crash latch still exists for a genuine floor-free-opponent dump.
WOOL_MIN_PRICE = 150.0
LIQUIDATION_DAY = 29  # unsold inventory is $0 at game end — dump everything

# --- M2b: melon liquidation ramp (replaces the day-29 cliff for MELON only) --
# Graduated exit ahead of the hard liquidation day, so a contested-game
# backlog isn't stuck holding through days 27-28 at a floor the crashed price
# can no longer clear: the floor steps down day by day instead of falling off
# a cliff. day >= LIQUIDATION_DAY (still 29) keeps the existing sell-all,
# no-floor, no-cap behavior via ``final_day``.
MELON_RAMP_DAY_27 = 27
MELON_RAMP_DAY_28 = 28
MELON_RAMP_FLOOR_27 = 100.0
MELON_RAMP_FLOOR_28 = 60.0

# --- M2b: contested dynamic floor + peak gate (see module docstring) --------
MELON_CONTESTED_MIN_FLOOR = 120.0  # clamp: the decay never prices melon away for free
MELON_CONTESTED_DECAY_PER_DAY = 8.0  # $195 -> $120 clamp over ~9-10 days of a live crash
MELON_PEAK_GATE_MARGIN = 15.0  # only sell within $15 of the rolling 24-turn high

# --- M2b: satellite sell batching (see module docstring for the tuning note) -
# Expressed as a small BLOCKED set (not an allowlist): empirically tuned down
# from an original 10-hour allowlist after it cost -5% in the uncontested
# solo probe for no offsetting benefit (see module docstring). Hours 4-9 are
# the deep-morning stretch, both town-tick-distant (state.TOWN_TICK_HOURS is
# {1, 13}) and pre-day-end-distant -- blocking just this window held parity
# across 9 probed seeds while still meaningfully concentrating the *allowed*
# hours around the post-tick reveals and the end-of-day stretch.
MELON_MILK_WOOL_BATCH_BLOCKED_HOURS = frozenset({4, 5, 6, 7, 8, 9})
MELON_MILK_WOOL_BATCH_EXEMPT_DAY = 27  # from here on, sell at any hour (endgame flexibility)

# There's no tracked daily-sale counter in this stateless, per-turn design
# (nothing survives between calls), so an intended "at most ~8/day" cap is
# approximated with a flat PER-TURN cap instead: worst case that bounds the
# daily rate at 2*24=48, well above 8, but shed inflow is the real limiter in
# practice (~8 melon tiles, first_yield_day 10 — nothing like 24 harvest
# turns a day is ever on offer). What the cap actually buys is smoothing: it
# keeps one turn's harvest windfall from being dumped in a single order and
# walking the price down the quadratic/linear curve for every unit sold.
MELON_SELL_CAP = 2
# M2c: MILK and WOOL now share one cap (was MILK_SELL_CAP/WOOL_SELL_CAP = 2
# each) -- raised to 4 alongside the regime-conditional floor rework, since
# the valve (not a tight per-turn cap) is now what handles a real backlog.
WOOL_MILK_SELL_CAP = 4
# 15 animals collect ~15 fertilizer/day at full husbandry scale (up from the
# goose-only ~1/day M1 baseline); an uncapped SELL_ALL dump would walk the
# linear-above-curve price down hard every turn the shed fills faster than
# it's worth wheat-input use. Capped, not held-and-floored like melon/milk/
# wool: fertilizer's own floor ($15) already gates *whether* to sell at all.
FERT_SELL_CAP = 4

# Strawberry is the sharpest crashable on the board. Its above-curve is
# LINEAR against T=100 (melon's is quadratic against T=300, wheat's is log
# against T=400), so measured against the engine's own market_price it loses
# 25% of its $120 base after only ~16 units of net oversupply, 50% after ~31,
# and bottoms out at the $1 floor by ~62. Wheat needs thousands of units to
# move at all. A season's town demand is only ~437 units and the market is
# SHARED with the opponent, so the whole crop has to be metered out against
# that drain rather than banked and dumped.
#
# The floor is the real throttle and is set at 75% of base -- the point the
# price curve reaches at ~16 units of oversupply. It self-limits: sell until
# the price has been walked down a quarter, then stop and let the town's
# shops drain the glut back off before selling again. The per-turn cap
# mirrors melon's for the same reason melon has one (never dump one harvest
# windfall down the curve in a single order); with the floor doing the real
# work, the cap only has to stop a single-turn spike.
STRAWBERRY_MIN_PRICE = 90.0
STRAWBERRY_SELL_CAP = 2

# M2c (kaggriculture#59): shared per-turn cap for tier-1 (soft) valve sells,
# applied uniformly across MELON/MILK/WOOL/FERTILIZER in place of each
# product's own (tighter) cap -- see PolicyConfig.valve_soft_cap and the
# module docstring's M2c section.
VALVE_SOFT_CAP = 10


def _capped_sell(item: str, shed: Mapping[str, int], cap: int, liquidating: bool) -> list[object]:
    qty = shed[item] if liquidating else min(shed[item], cap)
    return ["SELL", item, qty]


def _satellite_sell_allowed(day: int, hour: int, valve_tier: int = 0) -> bool:
    """MELON/MILK/WOOL sell in every hour except the blocked mid-morning
    window, except once the endgame liquidation window opens (day >= 27),
    when every hour is fair game -- maximum exit flexibility beats batching
    discipline that late.

    M2c (kaggriculture#59): valve tier 2 (hard) also bypasses the window
    unconditionally, same as the liquidation exemption -- batching is a
    price-timing optimization, and it must never be allowed to delay a
    destruction-prevention sale. Tier 1 (soft) still respects the window
    (it's an optimization trade, not an emergency), matching the existing
    liquidation precedent of "the more severe the exit, the less batching
    discipline applies."""
    if valve_tier >= 2:
        return True
    if day >= MELON_MILK_WOOL_BATCH_EXEMPT_DAY:
        return True
    return hour not in MELON_MILK_WOOL_BATCH_BLOCKED_HOURS


def _melon_dynamic_floor(days_since_contested: int) -> float:
    """$195 decaying $8/day, clamped at $120 -- see module docstring point 1."""
    decayed = MELON_MIN_PRICE - MELON_CONTESTED_DECAY_PER_DAY * days_since_contested
    return max(MELON_CONTESTED_MIN_FLOOR, decayed)


def _valve_sell(
    item: str,
    shed: Mapping[str, int],
    price: float,
    floor: float,
    crashed: bool,
    cap: int,
    liquidating: bool,
    valve_tier: int,
    valve_soft_cap: int,
) -> list[object] | None:
    """Regime-conditional floor sell for MILK/WOOL/FERTILIZER (M2c), overridden
    by the two-tier shed valve (see PolicyConfig / policy.decide and the
    module docstring's M2c section):

    - Liquidation (``day >= final_day``) or valve tier 2 (hard): sell the
      entire shed holding, floor ignored.
    - Valve tier 1 (soft): sell at market, floor ignored, but at the shared
      ``valve_soft_cap`` instead of the product's own (tighter) cap.
    - Valve tier 0: the regime floor applies -- unless ``crashed`` (the
      product's ``agent.state.ProductCrashLatch`` has permanently latched),
      in which case the floor is waived for the rest of the episode too.

    Returns ``None`` when nothing should be sold this turn.
    """
    if shed.get(item, 0) <= 0:
        return None
    if liquidating or valve_tier >= 2:
        return _capped_sell(item, shed, cap, liquidating=True)
    if valve_tier == 1:
        return _capped_sell(item, shed, valve_soft_cap, liquidating=False)
    if crashed or price >= floor:
        return _capped_sell(item, shed, cap, liquidating=False)
    return None


def build_orders(
    *,
    shed: Mapping[str, int],
    prices: Mapping[str, float],
    day: int,
    hour: int,
    wheat_reserve: int,
    buys: list[list[object]],
    final_day: int = LIQUIDATION_DAY,
    melon_contested: bool = False,
    melon_days_since_contested: int = 0,
    melon_rolling_max: float = 0.0,
    valve_tier: int = 0,
    valve_soft_cap: int = VALVE_SOFT_CAP,
    wool_floor: float = WOOL_MIN_PRICE,
    milk_floor: float = MILK_MIN_PRICE,
    fert_floor: float = FERT_MIN_PRICE,
    strawberry_floor: float = STRAWBERRY_MIN_PRICE,
    fert_reserve: int = 0,
    wool_crashed: bool = False,
    milk_crashed: bool = False,
    wool_milk_sell_cap: int = WOOL_MILK_SELL_CAP,
) -> list[list[object]]:
    """Sells first (crashables at index 0, melon leading), then buys, capped at 10.

    ``melon_contested``/``melon_days_since_contested``/``melon_rolling_max``
    come straight from a caller-owned ``agent.state.MelonMarketMemory`` (this
    function stays a pure computation over the values it's handed -- see the
    module docstring for the three M2b behaviors they drive).

    ``valve_tier``/``valve_soft_cap``/``wool_floor``/``milk_floor``/
    ``fert_floor``/``wool_crashed``/``milk_crashed``/``wool_milk_sell_cap``
    are the M2c additions (kaggriculture#59): ``valve_tier`` comes from
    ``policy.decide``'s shed-fill computation, ``wool_crashed``/
    ``milk_crashed`` from a caller-owned pair of ``agent.state.
    ProductCrashLatch`` instances -- see the module docstring's M2c section.
    """
    orders: list[list[object]] = []
    liquidating = day >= final_day

    melon = shed.get("MELON", 0)
    if melon > 0 and _satellite_sell_allowed(day, hour, valve_tier):
        melon_price = prices.get("MELON", 0.0)
        if day >= final_day:
            orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=True))
        elif valve_tier >= 2:
            orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=True))
        elif valve_tier == 1:
            orders.append(_capped_sell("MELON", shed, valve_soft_cap, liquidating=False))
        elif day >= MELON_RAMP_DAY_28:
            if melon_price >= MELON_RAMP_FLOOR_28:
                orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=False))
        elif day >= MELON_RAMP_DAY_27:
            if melon_price >= MELON_RAMP_FLOOR_27:
                orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=False))
        elif melon_contested:
            floor = _melon_dynamic_floor(melon_days_since_contested)
            if melon_price >= floor and melon_price >= melon_rolling_max - MELON_PEAK_GATE_MARGIN:
                orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=False))
        elif melon_price >= MELON_MIN_PRICE:
            orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=False))

    # Straight after melon, ahead of milk/wool. The index-0 law is about
    # CONTESTED goods -- an order at an earlier slot fully executes, moving
    # the price, before either player's later order -- and strawberry is the
    # one crop here with real shared demand: 4 of the 8 shop types buy it,
    # against melon's 0, so the opponent is plausibly selling into the same
    # book. Ordering among our own different products is otherwise neutral
    # (each item walks its own inventory curve independently), so the only
    # thing this position buys is a better slot in the one race that exists.
    if shed.get("STRAWBERRY", 0) > 0 and _satellite_sell_allowed(day, hour, valve_tier):
        strawberry_order = _valve_sell(
            "STRAWBERRY",
            shed,
            prices.get("STRAWBERRY", 0.0),
            strawberry_floor,
            False,  # no crash latch: the floor is already the self-limiting throttle
            STRAWBERRY_SELL_CAP,
            liquidating,
            valve_tier,
            valve_soft_cap,
        )
        if strawberry_order is not None:
            orders.append(strawberry_order)

    if shed.get("MILK", 0) > 0 and _satellite_sell_allowed(day, hour, valve_tier):
        milk_order = _valve_sell(
            "MILK",
            shed,
            prices.get("MILK", 0.0),
            milk_floor,
            milk_crashed,
            wool_milk_sell_cap,
            liquidating,
            valve_tier,
            valve_soft_cap,
        )
        if milk_order is not None:
            orders.append(milk_order)

    if shed.get("WOOL", 0) > 0 and _satellite_sell_allowed(day, hour, valve_tier):
        wool_order = _valve_sell(
            "WOOL",
            shed,
            prices.get("WOOL", 0.0),
            wool_floor,
            wool_crashed,
            wool_milk_sell_cap,
            liquidating,
            valve_tier,
            valve_soft_cap,
        )
        if wool_order is not None:
            orders.append(wool_order)

    # Fertilizer is the one product that is also an INPUT. Every unit held
    # back here is a unit a strawberry tile can spend at age 9 or 13, and the
    # engine pays a doubled tick only when the tile is covered -- so an
    # unreserved sell path drains the shed to zero between animal collections
    # and the FERTILIZE task silently no-ops (the engine's handler bails when
    # _inv_take fails, with no error). Zeroed while liquidating, exactly like
    # wheat_reserve below: on the last days there is no future tick left to
    # fertilize for, so the units are worth more sold.
    fert_held_back = 0 if liquidating else fert_reserve
    fert_sellable = max(0, shed.get("FERTILIZER", 0) - fert_held_back)
    if fert_sellable > 0:
        fert_order = _valve_sell(
            "FERTILIZER",
            {**shed, "FERTILIZER": fert_sellable},
            prices.get("FERTILIZER", 0.0),
            fert_floor,
            False,  # fertilizer has no crash latch -- the valve covers its backlog
            FERT_SELL_CAP,
            liquidating,
            valve_tier,
            valve_soft_cap,
        )
        if fert_order is not None:
            orders.append(fert_order)

    if shed.get("EGG", 0) > 0:
        orders.append(["SELL", "EGG", SELL_ALL])
    reserve = 0 if liquidating else wheat_reserve
    wheat_for_sale = shed.get("WHEAT", 0) - reserve
    if wheat_for_sale > 0:
        orders.append(["SELL", "WHEAT", wheat_for_sale])

    orders.extend(buys)
    return orders[:MAX_ORDERS]
