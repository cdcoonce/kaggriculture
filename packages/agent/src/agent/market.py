"""Market-order builder — index-0 price-aware selling (strategy doc).

Orders resolve by queue-slot index across both players: slot 0 fully executes
(moving price) before either player's slot-1 order runs. Crashable goods
(fertilizer: linear above-curve, -$0.20/unit oversupply) therefore always go
at index 0. Wheat/egg are glut-proof staples: sell every turn, early and often
(holding them only risks shed overflow — cap 100, silent discard).
"""

from __future__ import annotations

from collections.abc import Mapping

SELL_ALL = 99999  # engine validates no upper bound; safe "sell everything" idiom
MAX_ORDERS = 10  # maxMarketOrdersPerTurn — extras silently dropped by the engine
FERT_MIN_PRICE = 55.0  # below this, fertilizer is worth more as +2-yield wheat input
LIQUIDATION_DAY = 29  # unsold inventory is $0 at game end — dump everything


def build_orders(
    *,
    shed: Mapping[str, int],
    prices: Mapping[str, float],
    day: int,
    wheat_reserve: int,
    buys: list[list[object]],
    final_day: int = LIQUIDATION_DAY,
) -> list[list[object]]:
    """Sells first (crashables at index 0), then the day-plan buys, capped at 10."""
    orders: list[list[object]] = []
    liquidating = day >= final_day

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
