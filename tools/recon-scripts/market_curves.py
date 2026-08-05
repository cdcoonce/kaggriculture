"""Price-impact analysis using the ACTUAL market_price()/MARKET_PARAMS from the
engine. Computes: (1) sanity check against README's P(I0-T)/P(I0+T)/P(I0+2T)
table, (2) inventory delta (units sold above I0) at which price falls 25%/50%/
to floor, (3) inventory delta (units bought/consumed below I0) at which price
rises 25%/50%/100%, (4) marginal revenue curves for selling N units in one
shot starting from I0.
"""
import math
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg

MP = kagg.MARKET_PARAMS
I0 = kagg.MARKET_I0


def invert(func, value):
    value = max(0.0, value)
    if func == "linear":
        return value
    if func == "sq":
        return math.sqrt(value)
    if func == "sqrt":
        return value ** 2
    if func == "log":
        return math.exp(value) - 1.0
    if func == "log10":
        return 10 ** value - 1.0
    raise ValueError(func)


def delta_for_price(item, target_price, side):
    p = MP[item]
    base = p["base"]
    if side == "above":
        func, target, T = p["above_func"], p["above_target"], p["T"]
        amp = target * base / kagg._shape(func, T)
        val = (base - target_price) / amp
    else:
        func, target, T = p["below_func"], p["below_target"], p["T"]
        amp = target * base / kagg._shape(func, T)
        val = (target_price - base) / amp
    return invert(func, val)


print("=== Sanity check vs README table: P(I0-T), P(I0+T), P(I0+2T) ===")
print(f"{'item':12s} {'base':>5s} {'T':>5s} {'P(I0-T)':>9s} {'P(I0+T)':>9s} {'P(I0+2T)':>9s}")
for item in kagg.PRODUCTS:
    p = MP[item]
    T = p["T"]
    pm = kagg.market_price(item, I0 - T)
    pp = kagg.market_price(item, I0 + T)
    pp2 = kagg.market_price(item, I0 + 2 * T)
    print(f"{item:12s} {p['base']:5d} {T:5d} {pm:9d} {pp:9d} {pp2:9d}")

print("\n=== GLUT side (player selling): units ABOVE I0 to hit -25% / -50% / floor($1) ===")
print(f"{'item':12s} {'base':>5s} {'T':>5s} {'-25%@':>10s} {'-50%@':>10s} {'floor@':>10s} "
      f"{'floor/T':>8s}")
for item in kagg.PRODUCTS:
    if item == "FERTILIZER":
        continue
    p = MP[item]
    base = p["base"]
    T = p["T"]
    d25 = delta_for_price(item, base * 0.75, "above")
    d50 = delta_for_price(item, base * 0.50, "above")
    dfloor = delta_for_price(item, 1.0, "above")
    print(f"{item:12s} {base:5d} {T:5d} {d25:10.1f} {d50:10.1f} {dfloor:10.1f} {dfloor/T:8.2f}")

print("\n=== SCARCITY side (town/buyer draining inventory): units BELOW I0 for +25% / +50% / +100% ===")
print(f"{'item':12s} {'base':>5s} {'T':>5s} {'+25%@':>10s} {'+50%@':>10s} {'+100%@':>10s}")
for item in kagg.PRODUCTS:
    p = MP[item]
    base = p["base"]
    T = p["T"]
    d25 = delta_for_price(item, base * 1.25, "below")
    d50 = delta_for_price(item, base * 1.50, "below")
    d100 = delta_for_price(item, base * 2.00, "below")
    print(f"{item:12s} {base:5d} {T:5d} {d25:10.1f} {d50:10.1f} {d100:10.1f}")

print("\n=== Marginal revenue of the Nth unit sold today (solo player dumping into a fresh I0 market) ===")
for item in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]:
    prices = []
    inv = I0
    for n in range(1, 51):
        pr = kagg.market_price(item, inv)
        prices.append(pr)
        if pr > 1:
            inv += 1
    print(item, "1st:", prices[0], "10th:", prices[9], "25th:", prices[24], "50th:", prices[49],
          "revenue@50=", sum(prices))

print("\n=== Same, but TWO players both selling the same volume simultaneously (each unit alternates) ===")
for item in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]:
    inv = I0
    my_prices = []
    for n in range(1, 51):
        pr = kagg.market_price(item, inv)
        my_prices.append(pr)
        if pr > 1:
            inv += 1
        # opponent sells one too (same price this round per engine's lockstep unit processing)
        pr2 = kagg.market_price(item, inv)
        if pr2 > 1:
            inv += 1
    print(item, "my 1st:", my_prices[0], "my 10th:", my_prices[9], "my 25th:", my_prices[24],
          "my 50th:", my_prices[49], "my revenue@50=", sum(my_prices))
