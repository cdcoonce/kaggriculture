"""Local validation for the M0a probe agent.

Mirrors Kaggle's validation episode (self-play) plus a sanity game vs the
built-in starter. Exits nonzero on any non-DONE status.
"""

import sys
from pathlib import Path

from kaggle_environments import make

PROBE = str(Path(__file__).resolve().parent / "main.py")


def run(agents, label):
    env = make("kaggriculture", debug=True)
    env.run(agents)
    final = env.steps[-1]
    ok = True
    for i, state in enumerate(final):
        print(f"{label} player {i}: status={state.status} reward={state.reward}")
        ok = ok and state.status == "DONE"
    return ok


def main():
    ok = run([PROBE, PROBE], "self-play")
    ok = run([PROBE, "starter"], "vs-starter") and ok
    if not ok:
        print("FAIL: non-DONE status observed")
        sys.exit(1)
    print("OK: all agents finished DONE")


if __name__ == "__main__":
    main()
