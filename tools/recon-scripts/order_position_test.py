"""
Test: does market-order LIST POSITION (index within a turn's market order list)
create a front-running advantage for SELL orders on the same item, independent
of the "who commits first" simultaneity the recon docs describe for MATCHED
index slots?

Setup: give both players a large MELON shed stock. Player 0 queues SELL MELON
as market order index 0. Player 1 queues a harmless filler order at index 0
(that doesn't touch MELON) followed by an identical-size SELL MELON at index 1.
If order-list position matters, player 0 (index 0) should get a materially
better average price per unit than player 1 (index 1), because player 0's
dump fully resolves and calls _refresh_prices() before player 1's index-1
order is even parsed.
"""
import copy
from kaggle_environments import make

env = make("kaggriculture", configuration={"seed": 7}, debug=True)
env.reset()

# Give both players a large melon stock + plenty of money, directly on the
# internal state dicts (bypassing legitimate play so we isolate ONLY the
# market-resolution mechanic under test).
# NOTE: "farms" is a SHARED field (per kaggriculture.json) -- state[0] is the
# canonical copy; state[1]'s observation.farms gets REBUILT from state[0] on
# every step(), so money must be mutated via state[0] for BOTH players, not
# via state[i] per player (that was the bug in the first pass of this test).
for i in range(2):
    env.state[i].observation.private.shed["MELON"] = 200  # private: per-agent, safe to mutate directly
env.state[0].observation.farms[0]["money"] = 100000
env.state[0].observation.farms[1]["money"] = 100000

# Sanity: confirm starting melon inventory/price
print("Pre-trade inventory:", env.state[0].observation.market["inventory"]["MELON"])
print("Pre-trade price:", env.state[0].observation.market["prices"]["MELON"])
pre_money = [env.state[0].observation.farms[i]["money"] for i in range(2)]
print("Pre-trade money:", pre_money)

N = 50  # units each player sells

action0 = {"farmer": ["PASS"], "hands": [], "market": [["SELL", "MELON", N]]}
# Filler for player 1's index 0: a HIRE order (cheap, doesn't touch MELON market at all)
action1 = {"farmer": ["PASS"], "hands": [], "market": [["HIRE"], ["SELL", "MELON", N]]}

env.step([action0, action1])

post_money = [env.state[0].observation.farms[i]["money"] for i in range(2)]
print("Post-trade money:", post_money)
delta = [post_money[i] - pre_money[i] for i in range(2)]
print("Revenue captured — player0 (index0 SELL):", delta[0], " player1 (index1 SELL, after filler):", delta[1])
print("Post-trade melon inventory:", env.state[0].observation.market["inventory"]["MELON"])
print("Post-trade melon price:", env.state[0].observation.market["prices"]["MELON"])
