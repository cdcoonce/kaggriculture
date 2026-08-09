import os

os.environ["PBA_DEBUG"] = "1"
import harness.zoo.public_baseline_approx as pba
from kaggle_environments import make

pba.HERD = ()
inner = pba.make_agent()

count = [0]


log = open("_pba_debug.log", "a")


def wrapped(obs):
    step = obs["step"]
    log.write(f"calling with step {step}\n")
    log.flush()
    return inner(obs)


env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 108})
env.run([wrapped, "pass"])
