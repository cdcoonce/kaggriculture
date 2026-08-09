from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent

env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 240})
env.run([make_agent(), "pass"])

for step in range(144, 192):
    action = env.steps[step][0].action
    obs = env.steps[step][0].observation
    farm = obs["farms"][0]
    private = obs["private"]
    animal_tiles = []
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and "animal" in tile:
                animal_tiles.append((tile["animal"], tile["fed_today"], tile["consecutive_unfed"]))
    print("step", step, "hands", len(farm["hands"]), "shedwheat", private["shed"].get("WHEAT"), "inv", private["inventories"], "animals", animal_tiles, "action", action)

for step in range(0):
    action = env.steps[step][0].action
    obs = env.steps[step][0].observation
    farm = obs["farms"][0]
    private = obs["private"]
    animal_tiles = []
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and "animal" in tile:
                animal_tiles.append((tile["animal"], tile["fed_today"], tile["consecutive_unfed"]))
    print("step", step, "hands", len(farm["hands"]), "inv", private["inventories"], "animals", animal_tiles, "action", action)

for day in range(9):
    step_idx = day * 24
    obs = env.steps[step_idx][0].observation
    farm = obs["farms"][0]
    private = obs["private"]
    counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
    for row in farm["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and "animal" in tile:
                counts[tile["animal"]] += 1
    print("day", day, "money", farm["money"], "shed", private["shed"], "counts", counts, "hands", len(farm["hands"]))
