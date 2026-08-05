"""Simulate single-tile crop lifecycles using the ACTUAL engine functions
(_apply_unit_action, _daily_refresh_plants, _decay_plants) as ground truth,
stepping turn-by-turn exactly like the real interpreter does (decay must be
evaluated every step, not once/day -- its 2-step parity window means a
once-daily sample can permanently miss it).
"""
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg

BOARD = 10
TPD = 24


def new_farm_private(crop):
    farm = {"tiles": [[None] * BOARD for _ in range(BOARD)], "farmer": [0, 0]}
    private = {"shed": {}, "seeds": {crop: 1}, "inventories": [{}]}
    return farm, private


def find_optimal_harvest_age(crop, fertilize_ages=frozenset()):
    """Earliest age at which yield_units caps out (no further watering benefit),
    or max_yield_day if the cap is never reached in-window (e.g. wheat/carrot
    unfertilized). Harvesting any later only risks decay for zero extra yield."""
    cd = kagg.CROPS[crop]
    farm, private = new_farm_private(crop)
    step = 0
    kagg._apply_unit_action(farm, private, 0, ["PLANT", crop], BOARD, 0, TPD)
    for day in range(0, cd["max_yield_day"] + 1):
        tile = farm["tiles"][0][0]
        if day in fertilize_ages:
            private["inventories"][0]["FERTILIZER"] = private["inventories"][0].get("FERTILIZER", 0) + 1
            kagg._apply_unit_action(farm, private, 0, ["FERTILIZE"], BOARD, day, TPD)
        kagg._apply_unit_action(farm, private, 0, ["WATER"], BOARD, day, TPD)
        tile = farm["tiles"][0][0]
        if tile["yield_units"] >= cd["max_yield"] and day >= cd["first_yield_day"]:
            return day
        for h in range(TPD):
            kagg._decay_plants(farm, day * TPD + h)
        kagg._daily_refresh_plants(farm, day, TPD)
    return max(cd["max_yield_day"], cd["first_yield_day"])


def run_one_time(crop, harvest_day, fertilize_ages=frozenset(), replant_cycles=1,
                  extra_days_after_last_harvest=0):
    """Plant on day 0; water every day; harvest at `harvest_day` (age, i.e. days
    since planting). If replant_cycles>1, immediately replant same tile and repeat.
    Returns totals: yield, actions, span_days (calendar days from first plant to
    last action, inclusive)."""
    farm, private = new_farm_private(crop)
    cd = kagg.CROPS[crop]
    total_actions = 0
    total_yield_start = 0
    cycles_done = 0
    planted_day = 0
    last_action_day = 0

    def act(action, day):
        nonlocal total_actions, last_action_day
        kagg._apply_unit_action(farm, private, 0, action, BOARD, day, TPD)
        total_actions += 1
        last_action_day = day

    step = 0
    act(["PLANT", crop], 0)
    while True:
        day = step // TPD
        hour = step % TPD
        if hour == 0:
            age = day - planted_day
            tile = farm["tiles"][0][0]
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                if age in fertilize_ages:
                    private["inventories"][0]["FERTILIZER"] = (
                        private["inventories"][0].get("FERTILIZER", 0) + 1)
                    act(["FERTILIZE"], day)
                act(["WATER"], day)
                tile = farm["tiles"][0][0]
                if age == harvest_day and isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    act(["HARVEST"], day)
                    cycles_done += 1
                    if cycles_done < replant_cycles:
                        private["seeds"][crop] = private["seeds"].get(crop, 0) + 1
                        act(["PLANT", crop], day)
                        planted_day = day
                        # New plant must be watered same day too (no grace period:
                        # consecutive_unwatered starts at 1 on planting day).
                        act(["WATER"], day)
                    else:
                        break
        kagg._decay_plants(farm, step)
        if (step + 1) % TPD == 0:
            kagg._daily_refresh_plants(farm, day, TPD)
        step += 1
        if step > 100_000:
            raise RuntimeError("runaway sim")

    total_yield = private["inventories"][0].get(crop, 0)
    span_days = last_action_day + extra_days_after_last_harvest + 1
    return {
        "crop": crop, "cycles": cycles_done, "total_yield": total_yield,
        "total_actions": total_actions, "span_days": span_days,
    }


def run_ongoing(crop, fertilize_ages=frozenset(), harvest_every_age=1, horizon_days=60):
    """Ongoing crop (tomato/strawberry): plant once, water+harvest daily (or every
    N ages) until the tile weeds out from decay. Returns totals over the full life."""
    farm, private = new_farm_private(crop)
    cd = kagg.CROPS[crop]
    total_actions = 0

    def act(action, day):
        nonlocal total_actions
        kagg._apply_unit_action(farm, private, 0, action, BOARD, day, TPD)
        total_actions += 1

    step = 0
    act(["PLANT", crop], 0)
    life_days = None
    for day_probe in range(horizon_days):
        pass  # placeholder, real loop below
    max_step = horizon_days * TPD
    while step < max_step:
        day = step // TPD
        hour = step % TPD
        if hour == 0:
            tile = farm["tiles"][0][0]
            if not (isinstance(tile, dict) and tile.get("kind") == "PLANT"):
                life_days = day
                break
            age = day  # planted_day == 0
            if age in fertilize_ages:
                private["inventories"][0]["FERTILIZER"] = (
                    private["inventories"][0].get("FERTILIZER", 0) + 1)
                act(["FERTILIZE"], day)
            act(["WATER"], day)
            tile = farm["tiles"][0][0]
            if (isinstance(tile, dict) and tile.get("kind") == "PLANT"
                    and tile.get("yield_units", 0) > 0
                    and day - tile["planted_day"] >= cd["first_yield_day"]
                    and age % harvest_every_age == 0):
                act(["HARVEST"], day)
        kagg._decay_plants(farm, step)
        if (step + 1) % TPD == 0:
            kagg._daily_refresh_plants(farm, day, TPD)
        step += 1
    if life_days is None:
        life_days = horizon_days

    total_yield = private["inventories"][0].get(crop, 0)
    return {"crop": crop, "total_yield": total_yield, "total_actions": total_actions,
            "life_days": life_days}


if __name__ == "__main__":
    print("=== Optimal harvest age (unfertilized) ===")
    for crop in ["WHEAT", "CARROT", "MELON"]:
        print(crop, find_optimal_harvest_age(crop))

    print("\n=== ONE-TIME CROPS: single cycle, OPTIMAL harvest age, UNFERTILIZED ===")
    opt_age = {}
    for crop in ["WHEAT", "CARROT", "MELON"]:
        cd = kagg.CROPS[crop]
        h = find_optimal_harvest_age(crop)
        opt_age[crop] = h
        r = run_one_time(crop, harvest_day=h)
        print(crop, "harvest_age=", h, r, "yield/day=", round(r["total_yield"] / r["span_days"], 3))

    print("\n=== ONE-TIME CROPS: single cycle, OPTIMAL harvest age, FERTILIZED (bonus window) ===")
    opt_age_fert = {}
    for crop in ["WHEAT", "CARROT", "MELON"]:
        cd = kagg.CROPS[crop]
        window_start = (cd["max_yield_day"] + 1) // 2
        fert_ages = set(range(window_start, cd["max_yield_day"] + 1))
        h = find_optimal_harvest_age(crop, fertilize_ages=frozenset(fert_ages))
        opt_age_fert[crop] = h
        r = run_one_time(crop, harvest_day=h, fertilize_ages=frozenset(fert_ages))
        print(crop, "fert_ages=", sorted(fert_ages), "harvest_age=", h, r,
              "yield/day=", round(r["total_yield"] / r["span_days"], 3))

    print("\n=== ONE-TIME CROPS: 4 continuous replant cycles (steady state), UNFERTILIZED, optimal harvest age ===")
    for crop in ["WHEAT", "CARROT", "MELON"]:
        h = opt_age[crop]
        r = run_one_time(crop, harvest_day=h, replant_cycles=4)
        print(crop, r, "yield/day=", round(r["total_yield"] / r["span_days"], 4),
              "actions/day=", round(r["total_actions"] / r["span_days"], 4))

    print("\n=== ONGOING CROPS: full lifecycle to decay-weed, UNFERTILIZED, harvest daily ===")
    for crop in ["TOMATO", "STRAWBERRY"]:
        r = run_ongoing(crop, harvest_every_age=1, horizon_days=60)
        print(crop, r, "yield/day=", round(r["total_yield"] / r["life_days"], 4),
              "actions/day=", round(r["total_actions"] / r["life_days"], 4))

    print("\n=== ONGOING CROPS: full lifecycle, FERTILIZED every scheduled-production age ===")
    # Tomato scheduled prod ages: first_yield_day..+3*interval = 8,9,10,11
    # Strawberry: 10,12,14,16
    fert_schedule = {
        "TOMATO": {8, 9, 10, 11},
        "STRAWBERRY": {10, 12, 14, 16},
    }
    for crop in ["TOMATO", "STRAWBERRY"]:
        r = run_ongoing(crop, fertilize_ages=frozenset(fert_schedule[crop]), harvest_every_age=1, horizon_days=60)
        print(crop, r, "yield/day=", round(r["total_yield"] / r["life_days"], 4),
              "actions/day=", round(r["total_actions"] / r["life_days"], 4))
