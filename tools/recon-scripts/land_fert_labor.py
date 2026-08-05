"""Land payback, fertilizer EV, animal breakeven day, labor saturation."""
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg

TILES_PER_QUADRANT = 25

print("=== Land quadrant payback, using WHEAT steady-state per-tile profit (base price, no travel) ===")
# From crop_sim.py steady-state: WHEAT 4 cycles -> yield=16, actions=28, span=17 days
wheat_yield_per_day = 16 / 17
wheat_actions_per_day = 28 / 17
wheat_seed_cost_per_day = (4 * kagg.CROPS["WHEAT"]["seed"]) / 17
wheat_revenue_per_day = wheat_yield_per_day * kagg.MARKET_PARAMS["WHEAT"]["base"]
wheat_profit_per_tile_day = wheat_revenue_per_day - wheat_seed_cost_per_day
print(f"wheat: yield/day/tile={wheat_yield_per_day:.3f} revenue/day/tile=${wheat_revenue_per_day:.2f} "
      f"seed_cost/day/tile=${wheat_seed_cost_per_day:.2f} profit/day/tile=${wheat_profit_per_tile_day:.2f} "
      f"actions/day/tile={wheat_actions_per_day:.3f}")

for name, price in [("NE", 1000), ("SW", 2000), ("SE", 4000)]:
    quadrant_profit_day = wheat_profit_per_tile_day * TILES_PER_QUADRANT
    quadrant_actions_day = wheat_actions_per_day * TILES_PER_QUADRANT
    payback_days_notravel = price / quadrant_profit_day
    payback_days_2xtravel = price / (quadrant_profit_day)  # profit unaffected by travel, only action needs double
    print(f"{name} (${price}): quadrant_profit/day=${quadrant_profit_day:.0f} "
          f"quadrant_actions_needed/day={quadrant_actions_day:.0f} "
          f"(~{quadrant_actions_day*2:.0f} with 1 move/tile/day travel overhead) "
          f"payback={payback_days_notravel:.1f} days")

print("\n=== Fertilizer EV per one-time crop (single cycle) ===")
# hand-computed from crop_sim.py verified yields
cases = [
    ("WHEAT", 4, 25, 10, 3, kagg.CROPS["WHEAT"]["seed"]),
    ("CARROT", 3, 35, 20, 2, kagg.CROPS["CARROT"]["seed"]),
]
for crop, unfert_yield, price, unfert_profit_placeholder, fert_units, seed in [
    ("WHEAT", 4, 25, None, 3, 10),
    ("CARROT", 3, 35, None, 2, 20),
]:
    fert_yield = {"WHEAT": 6, "CARROT": 4}[crop]
    unfert_profit = unfert_yield * price - seed
    fert_profit_market = fert_yield * price - seed - fert_units * 100
    fert_profit_free = fert_yield * price - seed
    print(f"{crop}: unfert_profit=${unfert_profit} fert_profit_at_market_$100/u=${fert_profit_market} "
          f"fert_profit_if_free=${fert_profit_free} delta_if_free=${fert_profit_free-unfert_profit} "
          f"delta_if_market=${fert_profit_market-unfert_profit}")

print("MELON: fertilizer adds ZERO yield (cap already hit by first_yield_day=10 gate "
      "regardless of fertilizer) -- always -EV to fertilize melon.")

print("\n=== Animal purchase breakeven day (within 30-day season) ===")
for animal in ["GOOSE", "COW", "SHEEP"]:
    a = kagg.ANIMALS[animal]
    product = a["product"]
    price = kagg.MARKET_PARAMS[product]["base"]
    feed_price = kagg.MARKET_PARAMS["WHEAT"]["base"]
    interval = a["interval"]
    net_per_production = price - feed_price * interval  # feed cost accrues every day regardless, but production every `interval` days
    # Simpler: daily net = (price/interval) - feed_price (feed happens daily)
    daily_net = price / interval - feed_price
    cost = a["cost"]
    fyd = a["first_yield_day"]
    # profit(D) = daily_net * max(0, 29 - (D+fyd) + 1) - cost   [rough, ignores interval granularity]
    # solve for D where profit=0
    days_needed = cost / daily_net
    last_day = 29 - fyd - days_needed + 1
    print(f"{animal}: daily_net(post-first-egg)=${daily_net:.2f} days_of_production_to_breakeven="
          f"{days_needed:.1f} last_profitable_purchase_day(full breakeven)={last_day:.1f} "
          f"(any marginal-positive purchase day <= {29-fyd})")

print("\n=== Labor saturation: hire cost vs tile ceiling ===")
print("Hire cost (fib) is trivial (<=$55 for 10th hire/day) vs any crop's $/action (wheat ~$13-30, "
      "melon ~$100+, animals ~$10-25). Binding constraint is NOT hire price, it's:")
print("  (a) tile count -- 100 tiles max (full board), and")
print("  (b) market absorption -- see town_demand.py sustainable sell rates.")
max_tiles = 100
print(f"Full board = {max_tiles} tiles. At wheat's ~{wheat_actions_per_day:.2f} actions/tile/day "
      f"(no travel), working all {max_tiles} tiles needs {max_tiles*wheat_actions_per_day:.0f} actions/day "
      f"-> {max_tiles*wheat_actions_per_day/24:.1f} farmer-equivalents (no travel) or "
      f"~{max_tiles*wheat_actions_per_day*2/24:.1f} with 1-move-per-tile travel overhead.")
