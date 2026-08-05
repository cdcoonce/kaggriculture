"""Animal lifecycle economics using the ACTUAL engine functions, turn-stepped.
Build structure -> place animal -> feed daily -> harvest on production days ->
optionally collect fertilizer daily. Runs for `horizon_days` after placement.
"""
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg

BOARD = 10
TPD = 24


def simulate_animal(animal, horizon_days=30, collect_fertilizer=False, care=False):
    a = kagg.ANIMALS[animal]
    structure_op = "BUILD_COOP" if a["structure"] == "COOP" else "BUILD_PASTURE"
    farm = {"tiles": [[None] * BOARD for _ in range(BOARD)], "farmer": [0, 0]}
    private = {"shed": {}, "seeds": {}, "inventories": [{}]}
    total_actions = 0
    fertilizer_collected = 0

    def act(action, day):
        nonlocal total_actions
        kagg._apply_unit_action(farm, private, 0, action, BOARD, day, TPD)
        total_actions += 1

    # day 0: build structure, then place animal (animal must be in inventory --
    # simulate having already bought it, skip the BUY_ANIMAL market step itself)
    act([structure_op], 0)
    private["inventories"][0][animal] = 1
    act(["PLACE", animal], 0)
    total_actions += 0  # PLACE already counted

    step = 0
    max_step = horizon_days * TPD
    while step < max_step:
        day = step // TPD
        hour = step % TPD
        if hour == 0:
            tile = farm["tiles"][0][0]
            if isinstance(tile, dict) and "animal" in tile:
                private["inventories"][0]["WHEAT"] = private["inventories"][0].get("WHEAT", 0) + 1
                act(["FEED"], day)
                if care:
                    act(["CARE"], day)
                tile = farm["tiles"][0][0]
                if tile.get("yield_units", 0) > 0:
                    act(["HARVEST"], day)
                if collect_fertilizer:
                    tile = farm["tiles"][0][0]
                    if tile.get("fertilizer_available"):
                        act(["COLLECT_FERTILIZER"], day)
                        fertilizer_collected += 1
        kagg._decay_plants(farm, step)  # no-op for animals but harmless
        if (step + 1) % TPD == 0:
            kagg._daily_refresh_animals(farm, day)
        step += 1

    product = a["product"]
    total_product = private["inventories"][0].get(product, 0)
    total_wheat_fed = horizon_days  # one per day, always fed here
    return {
        "animal": animal, "horizon_days": horizon_days, "total_product": total_product,
        "total_actions": total_actions, "wheat_fed": total_wheat_fed,
        "fertilizer_collected": fertilizer_collected,
    }


if __name__ == "__main__":
    print("=== Animal steady-state economics over 30 days, fed daily, harvested daily, no CARE, no fertilizer collection ===")
    for animal in ["GOOSE", "COW", "SHEEP"]:
        r = simulate_animal(animal, horizon_days=30)
        cost = kagg.ANIMALS[animal]["cost"]
        product = kagg.ANIMALS[animal]["product"]
        base_price = kagg.MARKET_PARAMS[product]["base"]
        wheat_price = kagg.MARKET_PARAMS["WHEAT"]["base"]
        revenue = r["total_product"] * base_price
        feed_cost = r["wheat_fed"] * wheat_price
        profit_incl_purchase = revenue - feed_cost - cost
        actions_per_day = r["total_actions"] / r["horizon_days"]
        print(f"{animal:6s} product={r['total_product']:3d} actions={r['total_actions']:3d} "
              f"($/action ex-purchase)={round((revenue-feed_cost)/r['total_actions'],2):>7} "
              f"30d_profit(incl ${cost} purchase, feed@${wheat_price})={profit_incl_purchase:8.0f} "
              f"actions/day={actions_per_day:.2f}")

    print("\n=== Same, WITH daily fertilizer collection (adds 1 action/day) ===")
    for animal in ["GOOSE", "COW", "SHEEP"]:
        r = simulate_animal(animal, horizon_days=30, collect_fertilizer=True)
        print(animal, r)
