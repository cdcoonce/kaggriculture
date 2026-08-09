from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent, WHEAT_TILES

env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 300})
env.run([make_agent(), "pass"])

for day in range(13):
    start = day * 24
    end = min(start + 24, len(env.steps))
    feed_count = 0
    water_count = 0
    harvest_count = 0
    plant_count = 0
    for step in range(start, end):
        action = env.steps[step][0].action
        if not isinstance(action, dict):
            continue
        unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        for a in unit_actions:
            if not isinstance(a, list) or not a:
                continue
            if a[0] == "FEED":
                feed_count += 1
            elif a[0] == "WATER":
                water_count += 1
            elif a[0] == "HARVEST":
                harvest_count += 1
            elif a[:2] == ["PLANT", "WHEAT"]:
                plant_count += 1

    # end-of-day animal fed_today snapshot (last step of day)
    last_obs = env.steps[end - 1][0].observation
    fed_state = []
    for row in last_obs["farms"][0]["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and "animal" in tile:
                fed_state.append((tile["animal"], tile["fed_today"], tile["consecutive_unfed"]))

    wheat_tile_states = []
    for p in WHEAT_TILES:
        x, y = p
        t = last_obs["farms"][0]["tiles"][y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT":
            wheat_tile_states.append((t.get("planted_day"), t.get("yield_units"), t.get("watered_today")))
        else:
            wheat_tile_states.append(t)

    shed_wheat = last_obs["private"]["shed"].get("WHEAT")
    money = last_obs["farms"][0]["money"]
    print(
        f"day {day}: FEED={feed_count} WATER={water_count} HARVEST={harvest_count} PLANT={plant_count} "
        f"shed_wheat={shed_wheat} money={money} fed_state={fed_state}"
    )
    print(f"   wheat_tiles={wheat_tile_states}")
