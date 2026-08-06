"""Daily planner — Plan A opening (wheat rush + goose) and its phase cutoffs.

Pure and per-turn idempotent: quantities derive only from observable state, so
re-running every turn never double-buys (market orders fill within the turn
they are issued; the next observation already reflects them).
"""

from __future__ import annotations

from dataclasses import dataclass, field

HANDS_TARGET = 3
FEED_RESERVE = 3
SEED_PRICE = 10
GOOSE_COST = 300
GOOSE_LAST_BUY_DAY = 14  # $300 payback needs ~12 egg days; later purchase never breaks even
PLANT_CUTOFF_DAY = 25  # last profitable wheat planting day (4 growth days + sale)


@dataclass(frozen=True)
class DayPlan:
    hire_count: int = 0
    buys: list[list[object]] = field(default_factory=list)


def plan_day(
    *,
    day: int,
    money: float,
    wheat_seeds: int,
    plantable_target_tiles: int,
    wheat_on_hand: int,
    goose_owned: bool,
    hires_today: int,
) -> DayPlan:
    buys: list[list[object]] = []
    budget = money

    if not goose_owned and day <= GOOSE_LAST_BUY_DAY and budget >= GOOSE_COST:
        buys.append(["BUY_ANIMAL", "GOOSE", 1])
        budget -= GOOSE_COST

    if day <= PLANT_CUTOFF_DAY:
        need = plantable_target_tiles - wheat_seeds
        affordable = int(budget // SEED_PRICE)
        n = min(need, affordable)
        if n > 0:
            buys.append(["BUY_SEED", "WHEAT", n])
            budget -= n * SEED_PRICE

    feed_gap = FEED_RESERVE - wheat_on_hand
    if goose_owned or any(b[0] == "BUY_ANIMAL" for b in buys):
        if feed_gap > 0 and day <= 27:
            buys.append(["BUY_PRODUCT", "WHEAT", feed_gap])

    return DayPlan(hire_count=max(0, HANDS_TARGET - hires_today), buys=buys)
