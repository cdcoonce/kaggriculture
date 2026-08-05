import json
from kaggle_environments import make

def run(seed):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
    env.run(["starter", "starter"])
    final = env.steps[-1]
    return final[0].reward, final[1].reward, env

seed = 42
m0a, m1a, env_a = run(seed)
m0b, m1b, env_b = run(seed)

print(f"Run A: money0={m0a} money1={m1a}")
print(f"Run B: money0={m0b} money1={m1b}")
print(f"Identical final money: {m0a == m0b and m1a == m1b}")

# Compare full step-by-step trajectories for divergence point
steps_a = env_a.steps
steps_b = env_b.steps
divergence_step = None
for i, (sa, sb) in enumerate(zip(steps_a, steps_b)):
    obs_a = sa[0].observation
    obs_b = sb[0].observation
    # Compare farms state as JSON strings (deterministic key order within same run assumed similar)
    da = json.dumps(obs_a.get("farms"), sort_keys=True, default=str)
    db = json.dumps(obs_b.get("farms"), sort_keys=True, default=str)
    if da != db:
        divergence_step = i
        break

print(f"First divergence step (farms state): {divergence_step}")
if divergence_step is not None:
    obs_a = steps_a[divergence_step][0].observation
    obs_b = steps_b[divergence_step][0].observation
    print("day/hour A:", obs_a.get("day"), obs_a.get("hour"))
    print("day/hour B:", obs_b.get("day"), obs_b.get("hour"))
    # print raw diff of farms[0]['tiles'] flattened to find first differing tile
    ta = obs_a["farms"][0]["tiles"]
    tb = obs_b["farms"][0]["tiles"]
    for y in range(len(ta)):
        for x in range(len(ta[y])):
            if json.dumps(ta[y][x], sort_keys=True, default=str) != json.dumps(tb[y][x], sort_keys=True, default=str):
                print(f"tile diff at ({x},{y}): A={ta[y][x]} B={tb[y][x]}")
