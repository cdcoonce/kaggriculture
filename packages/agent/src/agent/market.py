"""Market-order builder — index-0 price-aware selling (strategy doc).

Orders resolve by queue-slot index across both players: slot 0 fully executes
(moving price) before either player's slot-1 order runs. Crashable goods
therefore always go at the front of the sell block, most price-sensitive
first: melon (quadratic above-curve: base $250, -25% at ~+79 net oversupply,
~$1 floor at ~+158) leads even fertilizer (linear above-curve, -$0.20/unit
oversupply). Wheat/egg are glut-proof staples: sell every turn, early and
often (holding them only risks shed overflow — cap 100, silent discard).
"""

from __future__ import annotations

from collections.abc import Mapping

SELL_ALL = 99999  # engine validates no upper bound; safe "sell everything" idiom
MAX_ORDERS = 10  # maxMarketOrdersPerTurn — extras silently dropped by the engine
FERT_MIN_PRICE = 55.0  # below this, fertilizer is worth more as +2-yield wheat input
MELON_MIN_PRICE = 195.0  # ~22% off the $250 base — roughly where the crash starts biting
LIQUIDATION_DAY = 29  # unsold inventory is $0 at game end — dump everything

# There's no tracked daily-sale counter in this stateless, per-turn design
# (nothing survives between calls), so an intended "at most ~8/day" cap is
# approximated with a flat PER-TURN cap instead: worst case that bounds the
# daily rate at 2*24=48, well above 8, but shed inflow is the real limiter in
# practice (~8 melon tiles, first_yield_day 10 — nothing like 24 harvest
# turns a day is ever on offer). What the cap actually buys is smoothing: it
# keeps one turn's harvest windfall from being dumped in a single order and
# walking the price down the quadratic curve for every melon sold that turn.
MELON_SELL_CAP = 2


def build_orders(
    *,
    shed: Mapping[str, int],
    prices: Mapping[str, float],
    day: int,
    wheat_reserve: int,
    buys: list[list[object]],
    final_day: int = LIQUIDATION_DAY,
) -> list[list[object]]:
    """Sells first (crashables at index 0, melon leading), then buys, capped at 10."""
    orders: list[list[object]] = []
    liquidating = day >= final_day

    melon = shed.get("MELON", 0)
    if melon > 0 and (liquidating or prices.get("MELON", 0.0) >= MELON_MIN_PRICE):
        qty = melon if liquidating else min(melon, MELON_SELL_CAP)
        orders.append(["SELL", "MELON", qty])

    fert = shed.get("FERTILIZER", 0)
    if fert > 0 and (liquidating or prices.get("FERTILIZER", 0.0) >= FERT_MIN_PRICE):
        orders.append(["SELL", "FERTILIZER", SELL_ALL])
    if shed.get("EGG", 0) > 0:
        orders.append(["SELL", "EGG", SELL_ALL])
    reserve = 0 if liquidating else wheat_reserve
    wheat_for_sale = shed.get("WHEAT", 0) - reserve
    if wheat_for_sale > 0:
        orders.append(["SELL", "WHEAT", wheat_for_sale])

    orders.extend(buys)
    return orders[:MAX_ORDERS]
