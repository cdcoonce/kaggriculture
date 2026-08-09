from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent

for seed in (7, 41, 43, 100, 202):
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
    env.run([make_agent(), "starter"])
    bad_days = []
    for day in range(30):
        step_idx = day * 24
        if step_idx >= len(env.steps):
            break
        obs = env.steps[step_idx][0].observation
        counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
        for row in obs["farms"][0]["tiles"]:
            for tile in row:
                if isinstance(tile, dict) and "animal" in tile:
                    counts[tile["animal"]] = counts.get(tile["animal"], 0) + 1
        if day >= 5 and counts != {"GOOSE": 2, "COW": 2, "SHEEP": 2}:
            bad_days.append((day, dict(counts)))
    statuses = [s.status for s in env.steps[-1]]
    money = env.steps[-1][0].observation["farms"][0]["money"]
    print("seed", seed, "statuses", statuses, "money", money, "bad_days", bad_days)
