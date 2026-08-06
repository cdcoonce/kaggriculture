"""Daily planner — Plan A opening (wheat rush + goose), land expansion, melon
seed-buying, and hand-count scaling as the farmable universe grows.

Pure and per-turn idempotent: quantities derive only from observable state, so
re-running every turn never double-buys (market orders fill within the turn
they are issued; the next observation already reflects them). Budget is spent
sequentially in priority order: goose, then land, then melon seeds, then
wheat seeds, then feed — melon goes ahead of wheat because it's the
higher-value crop (seed $80 vs $10, and a mature melon sells for far more
than a mature wheat harvest) and should never be starved of budget by
wheat's larger, cheaper seed line.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.constants import LAND_ORDER, LAND_PRICES
from agent.dispatch import MELON_PLANT_CUTOFF_DAY, MELON_PLANT_DAILY_CAP, plant_quota

FEED_RESERVE = 3
SEED_PRICE = 10
MELON_SEED_PRICE = 80
GOOSE_COST = 300
GOOSE_LAST_BUY_DAY = 14  # $300 payback needs ~12 egg days; later purchase never breaks even
PLANT_CUTOFF_DAY = 25  # last profitable wheat planting day (4 growth days + sale)

LAND_RESERVE = 500  # cash floor kept in hand after any land purchase
LAND_LAST_BUY_DAY = {"NE": 24, "SW": 23, "SE": 20}  # later buys don't pay back land's own cost

HANDS_MIN = 3  # the Plan A opening crew, even on the 24-tile NW-only board
HANDS_PER_TILES = 8  # roughly one hand per eight target tiles
MAX_HIRES_PER_TURN = 4  # HIRE is one order slot each; caps the market-list cost of catching up


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
    melon_seeds: int = 0,
    empty_melon_tiles: int = 0,
    wheat_on_hand: int,
    goose_owned: bool,
    hires_today: int,
    unlocked_quadrants: tuple[str, ...],
    active_tiles: int,
) -> DayPlan:
    buys: list[list[object]] = []
    budget = money

    if not goose_owned and day <= GOOSE_LAST_BUY_DAY and budget >= GOOSE_COST:
        buys.append(["BUY_ANIMAL", "GOOSE", 1])
        budget -= GOOSE_COST

    next_quadrant = next((q for q in LAND_ORDER if q not in unlocked_quadrants), None)
    if next_quadrant is not None and day <= LAND_LAST_BUY_DAY[next_quadrant]:
        price = LAND_PRICES[next_quadrant]
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

    feed_gap = FEED_RESERVE - wheat_on_hand
    if goose_owned or any(b[0] == "BUY_ANIMAL" for b in buys):
        if feed_gap > 0 and day <= 27:
            buys.append(["BUY_PRODUCT", "WHEAT", feed_gap])

    hands_target = max(HANDS_MIN, round(active_tiles / HANDS_PER_TILES))
    hire_count = min(max(0, hands_target - hires_today), MAX_HIRES_PER_TURN)

    return DayPlan(hire_count=hire_count, buys=buys)
