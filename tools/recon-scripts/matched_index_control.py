"""Control: both players' SELL MELON at the SAME index (0) -> should be
symmetric/identical revenue, confirming the asymmetry above is specifically
an index-mismatch effect, not some other bias (player-order, etc.)."""
from kaggle_environments import make

env = make("kaggriculture", configuration={"seed": 7}, debug=True)
env.reset()

for i in range(2):
    env.state[i].observation.private.shed["MELON"] = 200
env.state[0].observation.farms[0]["money"] = 100000
env.state[0].observation.farms[1]["money"] = 100000

N = 50
action0 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", N]]}
action1 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", N]]}  # SAME index (0) this time

pre_money = [env.state[0].observation.farms[i]["money"] for i in range(2)]
env.step([action0, action1])
post_money = [env.state[0].observation.farms[i]["money"] for i in range(2)]
delta = [post_money[i] - pre_money[i] for i in range(2)]
print("Matched-index (both SELL MELON at index 0) revenue:", delta)
