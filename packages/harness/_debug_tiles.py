import harness.zoo.public_baseline_approx as pba
from kaggle_environments import make

pba.HERD = ()
inner = pba.make_agent()
env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 240})
env.run([inner, "pass"])

obs = env.steps[24 * 4][0].observation
tiles = obs["farms"][0]["tiles"]
for p in pba.WHEAT_TILES:
    x, y = p
    t = tiles[y][x]
    print(p, t)
