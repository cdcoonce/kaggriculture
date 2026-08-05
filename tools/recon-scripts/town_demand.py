"""Town demand schedule (shops + town center) per product, day 0-29, using the
real SHOPS / TOWN_CENTER_DEMAND_SCHEDULE / interval constants from the engine.
Shop unlock order is randomized per-episode (rng.choice among remaining shops
every townShopUnlockInterval=3 days); we model the EXPECTED number of a
product's supporting shops unlocked by day d via the hypergeometric mean
(shops unlock uniformly at random from the remaining pool), which is exact in
expectation over the random seed.
"""
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg
from market_curves import delta_for_price

SHOPS = kagg.SHOPS
TOTAL_SHOPS = len(SHOPS)  # 8
UNLOCK_INTERVAL = 3
SHOP_TICK_INTERVAL = 4     # turns
CENTER_TICK_INTERVAL = 12  # turns
TPD = 24

# shops supporting each product, with per-tick pull (2x if that shop is single-product)
product_shops = {}
for shop, products in SHOPS.items():
    mult = 2 if len(products) == 1 else 1
    for p in products:
        product_shops.setdefault(p, []).append((shop, mult))

SEASON_DAYS = 30


def expected_shops_unlocked_by_day(day):
    """Number of shops unlocked by end of `day` (deterministic: floor(day/3), capped at 8)."""
    return min(TOTAL_SHOPS, day // UNLOCK_INTERVAL)


def expected_daily_shop_demand(product, day):
    n_p = len(product_shops.get(product, []))
    if n_p == 0:
        return 0.0
    k = expected_shops_unlocked_by_day(day)
    frac_unlocked = k / TOTAL_SHOPS  # expected fraction of this product's shops unlocked
    ticks_per_day = TPD / SHOP_TICK_INTERVAL  # 6
    # expected per-tick pull = frac_unlocked * sum(mult for this product's shops) -- since
    # each candidate shop is unlocked independently-in-expectation with prob frac_unlocked
    per_tick = frac_unlocked * sum(m for _, m in product_shops.get(product, []))
    return per_tick * ticks_per_day


def center_mult(day):
    for threshold, m in kagg.TOWN_CENTER_DEMAND_SCHEDULE:
        if day >= threshold:
            return m
    return 1


def daily_center_demand(product):
    # constant across products (all TOWN_CENTER_PRODUCTS get 1*mult per tick)
    ticks_per_day = TPD / CENTER_TICK_INTERVAL  # 2
    def f(day):
        if product == "FERTILIZER":
            return 0.0
        return center_mult(day) * ticks_per_day
    return f


print("=== Expected shops unlocked by day (deterministic count) ===")
for d in [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 29]:
    print(d, expected_shops_unlocked_by_day(d))

print("\n=== Per-product: shop count, full post-unlock daily shop demand, town-center daily demand, "
      "combined day-29 demand, 30-day cumulative expected demand ===")
for product in kagg.PRODUCTS:
    shops_for = product_shops.get(product, [])
    full_shop_demand = sum(m for _, m in shops_for) * (TPD / SHOP_TICK_INTERVAL)
    center_fn = daily_center_demand(product)
    cum = 0.0
    for day in range(SEASON_DAYS):
        cum += expected_daily_shop_demand(product, day) + center_fn(day)
    day29_total = expected_daily_shop_demand(product, 29) + center_fn(29)
    print(f"{product:12s} shops={len(shops_for)} full_shop_demand/day={full_shop_demand:6.1f} "
          f"center@d29={center_fn(29):4.1f} total@d29={day29_total:6.1f} "
          f"cum_30day_expected={cum:8.1f}")

print("\n=== Sustainable combined (both players) daily SELL rate to stay within -25% price band "
      "by day 30, given town demand offsets some of the inventory add ===")
for product in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]:
    d25 = delta_for_price(product, kagg.MARKET_PARAMS[product]["base"] * 0.75, "above")
    center_fn = daily_center_demand(product)
    cum_town = sum(expected_daily_shop_demand(product, day) + center_fn(day) for day in range(SEASON_DAYS))
    # solve S * 30 - cum_town = d25  =>  S = (d25 + cum_town) / 30
    S = (d25 + cum_town) / SEASON_DAYS
    print(f"{product:12s} d25_threshold={d25:9.1f} cum_town_30d={cum_town:8.1f} "
          f"sustainable_combined_sell/day={S:7.2f}  (i.e. ~{S/2:6.2f} each if split evenly)")
