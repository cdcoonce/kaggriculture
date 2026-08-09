import harness.zoo.public_baseline_approx as pba
from kaggle_environments import make

pba.HERD = ()
inner = pba.make_agent()
env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 240})
env.run([inner, "pass"])

for step in (104, 105, 110):
    obs = env.steps[step][0].observation
    tiles = obs["farms"][0]["tiles"]
    day = obs["step"] // pba.TURNS_PER_DAY

    def tile_at(x, y):
        return tiles[y][x]

    needy = [p for p in pba.WHEAT_TILES if pba._wheat_need(tile_at(*p), day) is not None]
    print("step", step, "day", day, "needy count", len(needy), "needy", needy[:5])
    for p in pba.WHEAT_TILES:
        t = tile_at(*p)
        print("   ", p, t if not isinstance(t, dict) else {k: t[k] for k in ("kind", "yield_units", "watered_today", "planted_day")})
