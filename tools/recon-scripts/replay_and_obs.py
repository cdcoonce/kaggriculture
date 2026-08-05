import json, pprint
from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 7}, debug=True)
env.run(["starter", "starter"])

# Save full replay JSON
with open("replay-starter-mirror.json", "w") as f:
    json.dump(env.toJSON(), f)

steps = env.steps
print(f"total steps recorded: {len(steps)}")

# Money curve every 24 steps (once per day)
print("\n=== MONEY CURVE (every 24 steps) ===")
print("step,day,money0,money1")
for i in range(0, len(steps), 24):
    obs = steps[i][0].observation
    farms = obs["farms"]
    print(f"{i},{obs.get('day')},{farms[0]['money']},{farms[1]['money']}")
# last step too
i = len(steps) - 1
obs = steps[i][0].observation
farms = obs["farms"]
print(f"{i},{obs.get('day')},{farms[0]['money']},{farms[1]['money']}")

# Observation at step 0
print("\n=== OBS AT STEP 0 (player 0) ===")
obs0 = steps[0][0].observation
pp = pprint.PrettyPrinter(width=120)
d0 = json.loads(json.dumps(obs0, default=str))
# truncate tiles grids for readability
def truncate_tiles(o):
    for farm in o.get("farms", []):
        tiles = farm.get("tiles")
        if tiles:
            farm["tiles_truncated_sample_row0"] = tiles[0]
            farm["tiles_shape"] = f"{len(tiles)}x{len(tiles[0])}"
            del farm["tiles"]
    return o
pp.pprint(truncate_tiles(d0))

# Observation at a mid-game step (step 360 ~ day 15)
mid = 360
print(f"\n=== OBS AT STEP {mid} (player 0) ===")
obsm = steps[mid][0].observation
dm = json.loads(json.dumps(obsm, default=str))
pp.pprint(truncate_tiles(dm))
