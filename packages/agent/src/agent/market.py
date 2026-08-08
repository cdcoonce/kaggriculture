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
"""

from __future__ import annotations

from collections.abc import Mapping

SELL_ALL = 99999  # engine validates no upper bound; safe "sell everything" idiom
MAX_ORDERS = 10  # maxMarketOrdersPerTurn — extras silently dropped by the engine
FERT_MIN_PRICE = 55.0  # below this, fertilizer is worth more as +2-yield wheat input
MELON_MIN_PRICE = 195.0  # ~22% off the $250 base — roughly where the crash starts biting
MILK_MIN_PRICE = 120.0  # 25% off the $160 base — linear crash starts at ~+19 oversupply
WOOL_MIN_PRICE = 150.0  # 25% off the $200 base — quadratic crash starts at ~+29 oversupply
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
MILK_SELL_CAP = 2
WOOL_SELL_CAP = 2
# 15 animals collect ~15 fertilizer/day at full husbandry scale (up from the
# goose-only ~1/day M1 baseline); an uncapped SELL_ALL dump would walk the
# linear-above-curve price down hard every turn the shed fills faster than
# it's worth wheat-input use. Capped, not held-and-floored like melon/milk/
# wool: fertilizer's own floor ($55) already gates *whether* to sell at all.
FERT_SELL_CAP = 4


def _capped_sell(item: str, shed: Mapping[str, int], cap: int, liquidating: bool) -> list[object]:
    qty = shed[item] if liquidating else min(shed[item], cap)
    return ["SELL", item, qty]


def _satellite_sell_allowed(day: int, hour: int) -> bool:
    """MELON/MILK/WOOL sell in every hour except the blocked mid-morning
    window, except once the endgame liquidation window opens (day >= 27),
    when every hour is fair game -- maximum exit flexibility beats batching
    discipline that late."""
    if day >= MELON_MILK_WOOL_BATCH_EXEMPT_DAY:
        return True
    return hour not in MELON_MILK_WOOL_BATCH_BLOCKED_HOURS


def _melon_dynamic_floor(days_since_contested: int) -> float:
    """$195 decaying $8/day, clamped at $120 -- see module docstring point 1."""
    decayed = MELON_MIN_PRICE - MELON_CONTESTED_DECAY_PER_DAY * days_since_contested
    return max(MELON_CONTESTED_MIN_FLOOR, decayed)


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
) -> list[list[object]]:
    """Sells first (crashables at index 0, melon leading), then buys, capped at 10.

    ``melon_contested``/``melon_days_since_contested``/``melon_rolling_max``
    come straight from a caller-owned ``agent.state.MelonMarketMemory`` (this
    function stays a pure computation over the values it's handed -- see the
    module docstring for the three M2b behaviors they drive).
    """
    orders: list[list[object]] = []
    liquidating = day >= final_day

    melon = shed.get("MELON", 0)
    if melon > 0 and _satellite_sell_allowed(day, hour):
        melon_price = prices.get("MELON", 0.0)
        if day >= final_day:
            orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating=True))
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

    milk = shed.get("MILK", 0)
    if (
        milk > 0
        and _satellite_sell_allowed(day, hour)
        and (liquidating or prices.get("MILK", 0.0) >= MILK_MIN_PRICE)
    ):
        orders.append(_capped_sell("MILK", shed, MILK_SELL_CAP, liquidating))

    wool = shed.get("WOOL", 0)
    if (
        wool > 0
        and _satellite_sell_allowed(day, hour)
        and (liquidating or prices.get("WOOL", 0.0) >= WOOL_MIN_PRICE)
    ):
        orders.append(_capped_sell("WOOL", shed, WOOL_SELL_CAP, liquidating))

    fert = shed.get("FERTILIZER", 0)
    if fert > 0 and (liquidating or prices.get("FERTILIZER", 0.0) >= FERT_MIN_PRICE):
        orders.append(_capped_sell("FERTILIZER", shed, FERT_SELL_CAP, liquidating))

    if shed.get("EGG", 0) > 0:
        orders.append(["SELL", "EGG", SELL_ALL])
    reserve = 0 if liquidating else wheat_reserve
    wheat_for_sale = shed.get("WHEAT", 0) - reserve
    if wheat_for_sale > 0:
        orders.append(["SELL", "WHEAT", wheat_for_sale])

    orders.extend(buys)
    return orders[:MAX_ORDERS]
