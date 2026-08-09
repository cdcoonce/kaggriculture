from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent, WHEAT_TILES, TURNS_PER_DAY

inner = make_agent()
total_harvested = [0]
per_day_harvested = {}


def wrapped(obs):
    action = inner(obs)
    day = obs["step"] // TURNS_PER_DAY
    tiles = obs["farms"][obs["player"]]["tiles"]
    unit_positions = [tuple(obs["farms"][obs["player"]]["farmer"])] + [
        tuple(h) for h in obs["farms"][obs["player"]]["hands"]
    ]
    unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
    for pos, a in zip(unit_positions, unit_actions):
        if isinstance(a, list) and a and a[0] == "HARVEST":
            x, y = pos
            t = tiles[y][x]
            if isinstance(t, dict):
                yu = t.get("yield_units", 0)
                total_harvested[0] += yu
                per_day_harvested[day] = per_day_harvested.get(day, 0) + yu
    return action


env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
env.run([wrapped, "pass"])

print("total harvested (wheat units)", total_harvested[0])
print("per day:", per_day_harvested)
print("days simulated", len(env.steps) // 24)
print("avg/day", total_harvested[0] / (len(env.steps) / 24))
