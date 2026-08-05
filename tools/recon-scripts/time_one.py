import time, sys
from kaggle_environments import make

t0 = time.time()
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1}, debug=True)
env.run(["starter", "random"])
t1 = time.time()

final = env.steps[-1]
for i, s in enumerate(final):
    print(f"Player {i}: reward={s.reward}, status={s.status}")
print(f"wall_clock_seconds={t1-t0:.3f}")
print(f"num_steps={len(env.steps)}")
