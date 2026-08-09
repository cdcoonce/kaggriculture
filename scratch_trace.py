from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent

env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
env.run([make_agent(), "pass"])

for day in range(30):
    idx = day * 24
    obs = env.steps[idx][0].observation
    farm = obs["farms"][0]
    private = obs.get("private")
    counts = {}
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict) and "animal" in t:
                counts[t["animal"]] = counts.get(t["animal"], 0) + 1
    shed = private["shed"] if private else {}
    print("day", day, "money", farm["money"], "counts", counts, "shed", shed, "hands", len(farm["hands"]))

for s in range(1, 10):
    print("action at step", s, ":", env.steps[s][0].action)
