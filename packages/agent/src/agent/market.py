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
        orders.append(_capped_sell("MELON", shed, MELON_SELL_CAP, liquidating))

    milk = shed.get("MILK", 0)
    if milk > 0 and (liquidating or prices.get("MILK", 0.0) >= MILK_MIN_PRICE):
        orders.append(_capped_sell("MILK", shed, MILK_SELL_CAP, liquidating))

    wool = shed.get("WOOL", 0)
    if wool > 0 and (liquidating or prices.get("WOOL", 0.0) >= WOOL_MIN_PRICE):
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
