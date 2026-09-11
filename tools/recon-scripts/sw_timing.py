"""On which day does each seat buy its SW quadrant?

docs/recon/strawberry-frame.md found that turning strawberry on pushed our own SW
purchase from day 10-11 to 12-13, past STRAWBERRY_PLANT_CUTOFF_DAY=12. This
re-measures it at the replacement shape (strawberry rebuild Slice 0; cited by
eval/prereg/2026-09-11-strawberry-slice1-start-day.md). Each seat is read through
its OWN observation (per-player fields are not broadcast), via our agent's
parse_obs. Recon only; requires engine 1.32.7. Run from the repository root.

Usage:
    uv run python tools/recon-scripts/sw_timing.py > sw_timing.json
"""

import inspect
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor

ARMS = {
    "A_tiles0": {"strawberry_tile_target": 0},
    "B_s31_w21": {"strawberry_tile_target": 31, "wheat_rush_tiles": 21},
    "C_s24_w21": {"strawberry_tile_target": 24, "wheat_rush_tiles": 21},
}
LEADER = "public:sokolovsky-v12"
SEEDS = range(855000, 855008)


def sw_day(steps, seat, parse_obs, takes_config, tpd=24):
    for t, step in enumerate(steps):
        obs = step[seat]["observation"]
        try:
            view = parse_obs(obs, {}) if takes_config else parse_obs(obs)
        except Exception:
            return "unparseable"
        if "SW" in tuple(view.unlocked_quadrants):
            return t // tpd
    return None


def play(arm, cfg, seed):
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    takes_config = len(inspect.signature(parse_obs).parameters) > 1
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent(LEADER)])
    return (
        arm,
        seed,
        sw_day(env.steps, 0, parse_obs, takes_config),
        sw_day(env.steps, 1, parse_obs, takes_config),
    )


if __name__ == "__main__":
    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"
    jobs = [(a, c, s) for a, c in ARMS.items() for s in SEEDS]
    with ProcessPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(play, *zip(*jobs, strict=True)))
    by_arm: dict = {}
    for arm, seed, ours, theirs in rows:
        by_arm.setdefault(arm, []).append(
            {"seed": seed, "our_sw_day": ours, "leader_sw_day": theirs}
        )
    identity = {
        "script": "tools/recon-scripts/sw_timing.py",
        "git_sha": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "engine": k.__version__,
        "opponent": LEADER,
        "seeds": [SEEDS.start, SEEDS.stop - 1],
        "arms": ARMS,
    }
    print(json.dumps({"identity": identity, "by_arm": by_arm}, indent=1))
