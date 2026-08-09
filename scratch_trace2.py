from kaggle_environments import make
from harness.zoo.public_baseline_approx import make_agent

env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
env.run([make_agent(), "pass"])

TPD = 24

for day in range(6, 12):
    care_count = 0
    feed_count = 0
    pickup_wheat = 0
    for step in range(day * TPD, min((day + 1) * TPD, 720) + 1):
        action = env.steps[step][0].action
        if not isinstance(action, dict):
            continue
        unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
        for a in unit_actions:
            if isinstance(a, list) and a:
                if a[0] == "CARE":
                    care_count += 1
                elif a[0] == "FEED":
                    feed_count += 1
                elif a[0] == "PICKUP" and len(a) > 1 and a[1] == "WHEAT":
                    pickup_wheat += 1
    print(f"day {day}: CARE={care_count} FEED={feed_count} PICKUP_WHEAT={pickup_wheat}")

# Also check animal tile detail near day 7 (SHEEP drops)
for step in [6*24, 6*24+12, 7*24-1, 7*24]:
    obs = env.steps[step][0].observation
    farm = obs["farms"][0]
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict) and "animal" in t:
                print(step, t)
