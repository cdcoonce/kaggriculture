"""Labor probe: does an arm express its labor mechanism, and at what cost in weeds?

For each arm (a PolicyConfig override dict; the FIRST arm is the reference, normally the
shipped agent) on each seed, plays one game with our agent in seat 0 against a public leader
and records:

- units on our farm by hour (farmer plus hands, days 1-29);
- executed wheat plantings: tiles that turn into a WHEAT plant between consecutive
  observations, keyed by the DECISION hour (the earlier observation's hour, when the planting
  was ordered);
- weed tile-days: WEED tiles summed over the end-of-day (hour 23) snapshots;
- final money.

With --check it evaluates the expression-check criteria registered in
eval/prereg/2026-09-11-labor-slice1-wheat-planting.md, by arm name. Recon only; requires
engine 1.32.7. Run from the repository (or worktree) root, so the agent under test is the
one `uv run` imports there.

Usage:
    uv run python tools/recon-scripts/labor_probe.py \
        --arms '{"shipped": {}, "H10": {"max_hires_per_turn": 10}}' \
        --seeds 855000-855007 --workers 6 --out probe.json --check
"""

import argparse
import dataclasses
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor

# Registered criteria, by arm name (see the registration's expression check).
RAMP_GAIN_MIN = 1.0  # mean units over hours 1-2 above the reference's
PLANTINGS_RATIO_MIN = 1.15
LATE_PLANTINGS_MIN = 10.0  # plantings ordered at decision hours 21-22, mean per game
WEED_RATIO_MAX = 1.5
CREW_GAIN_PER_HAND_MIN = 0.7  # mean units over hours 4-20 above the reference's, per extra hand
CRITERIA = {
    "H10": ("ramp",),
    "WP2": ("plantings",),
    "CUT22": ("late_plantings",),
    "COMBO": ("ramp", "plantings", "late_plantings"),
    "EH1": ("crew1",),
    "EH2": ("crew2",),
    "EH2_H10": ("crew2", "ramp"),
}


def _is_wheat(t):
    return isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT"


def _is_weed(t):
    return isinstance(t, dict) and t.get("kind") == "WEED"


def play(arm, cfg, seed, opponent):
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])
    units: dict[int, list[int]] = {}
    plantings_by_hour = [0] * 24
    weed_tile_days = 0
    prev = None
    for step in env.steps:
        v = parse_obs(step[0]["observation"])
        if 1 <= v.day <= 29:
            units.setdefault(v.hour, []).append(1 + len(v.hands or []))
        if prev is not None:
            for y, row in enumerate(v.tiles):
                for x, t in enumerate(row):
                    if _is_wheat(t) and not _is_wheat(prev.tiles[y][x]):
                        plantings_by_hour[prev.hour] += 1
        if v.hour == 23:
            weed_tile_days += sum(1 for row in v.tiles for t in row if _is_weed(t))
        prev = v
    return {
        "arm": arm,
        "seed": seed,
        "units_by_hour": {h: sum(c) / len(c) for h, c in sorted(units.items())},
        "wheat_plantings": sum(plantings_by_hour),
        "plantings_by_hour": plantings_by_hour,
        "weed_tile_days": weed_tile_days,
        "final_money": parse_obs(env.steps[-1][0]["observation"]).money,
    }


def _seeds(spec):
    if "-" in spec and "," not in spec:
        lo, hi = (int(x) for x in spec.split("-"))
        return list(range(lo, hi + 1))
    return [int(s) for s in spec.split(",")]


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def summarize(games, arms):
    out = {}
    for arm in arms:
        rows = [g for g in games if g["arm"] == arm]
        out[arm] = {
            "units_by_hour": {
                h: _mean([r["units_by_hour"].get(h, 0.0) for r in rows]) for h in range(5)
            },
            "wheat_plantings": _mean([r["wheat_plantings"] for r in rows]),
            "late_plantings": _mean([sum(r["plantings_by_hour"][21:23]) for r in rows]),
            "crew_4_20": _mean([sum(r["units_by_hour"].get(h, 0.0) for h in range(4, 21)) / 17 for r in rows]),
            "weed_tile_days": _mean([r["weed_tile_days"] for r in rows]),
            "final_money": _mean([r["final_money"] for r in rows]),
        }
    return out


def check(summary, arms, ref):
    base = summary[ref]
    verdict = {}
    for arm in arms:
        if arm == ref:
            continue
        s, crit = summary[arm], {}
        for name in CRITERIA.get(arm, ()):
            if name == "ramp":
                arm_ramp = (s["units_by_hour"][1] + s["units_by_hour"][2]) / 2
                need = (base["units_by_hour"][1] + base["units_by_hour"][2]) / 2 + RAMP_GAIN_MIN
                crit[name] = (arm_ramp, need, arm_ramp >= need)
            elif name == "plantings":
                need = PLANTINGS_RATIO_MIN * base["wheat_plantings"]
                crit[name] = (s["wheat_plantings"], need, s["wheat_plantings"] >= need)
            elif name == "late_plantings":
                crit[name] = (s["late_plantings"], LATE_PLANTINGS_MIN, s["late_plantings"] >= LATE_PLANTINGS_MIN)
            elif name in ("crew1", "crew2"):
                hands = 1 if name == "crew1" else 2
                need = base["crew_4_20"] + CREW_GAIN_PER_HAND_MIN * hands
                crit[name] = (s["crew_4_20"], need, s["crew_4_20"] >= need)
            else:
                raise ValueError(f"unknown criterion {name!r}: a registered criterion must never be skipped")
        cap = WEED_RATIO_MAX * base["weed_tile_days"]
        crit["weed_guardrail"] = (s["weed_tile_days"], cap, s["weed_tile_days"] <= cap)
        verdict[arm] = {"criteria": crit, "pass": all(c[2] for c in crit.values()),
                        "registered_arm": arm in CRITERIA}
    return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="JSON {name: config}; first arm = reference")
    ap.add_argument("--seeds", default="855000-855007")
    ap.add_argument("--opponent", default="public:sokolovsky-v12")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", help="write the JSON record here")
    ap.add_argument("--check", action="store_true", help="evaluate the registered criteria")
    a = ap.parse_args()
    arms = json.loads(a.arms)
    seeds = _seeds(a.seeds)
    ref = next(iter(arms))

    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"
    import agent.policy as pol

    names = {f.name for f in dataclasses.fields(pol.PolicyConfig)}
    for arm, cfg in arms.items():
        missing = [key for key in cfg if key not in names]
        assert not missing, f"{arm}: not PolicyConfig fields: {missing}"

    jobs = [(arm, cfg, seed, a.opponent) for seed in seeds for arm, cfg in arms.items()]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        games = list(ex.map(play, *zip(*jobs, strict=True)))
    summary = summarize(games, arms)

    print(f"{len(seeds)} seeds {seeds[0]}..{seeds[-1]} vs {a.opponent}; reference {ref}")
    print(f"{'arm':<8}{'u@h0':>6}{'u@h1':>6}{'u@h2':>6}{'u@h3':>6}{'u@h4':>6}"
          f"{'crew':>6}{'plant':>8}{'late':>6}{'weeds':>7}{'final$':>9}{'Δ$':>8}")
    for arm in arms:
        s = summary[arm]
        u = s["units_by_hour"]
        print(f"{arm:<8}" + "".join(f"{u[h]:>6.1f}" for h in range(5))
              + f"{s['crew_4_20']:>6.1f}{s['wheat_plantings']:>8.1f}{s['late_plantings']:>6.1f}{s['weed_tile_days']:>7.1f}"
              + f"{s['final_money']:>9,.0f}{s['final_money'] - summary[ref]['final_money']:>+8,.0f}")

    verdict = check(summary, arms, ref) if a.check else None
    if verdict is not None:
        print("\nEXPRESSION CHECK (registered criteria):")
        for arm, v in verdict.items():
            parts = [f"{n} {val:.1f} vs {thr:.1f} {'ok' if ok else 'FAIL'}"
                     for n, (val, thr, ok) in v["criteria"].items()]
            tag = "" if v["registered_arm"] else " [not a registered arm: guardrail only]"
            print(f"  {arm}: {'PASS' if v['pass'] else 'FAIL'}{tag} | " + "; ".join(parts))
        print("OVERALL:", "PASS" if all(v["pass"] for v in verdict.values()) else "FAIL")

    if a.out:
        identity = {
            "script": "tools/recon-scripts/labor_probe.py",
            "git_sha": _git("rev-parse", "HEAD"),
            "packages_dirty": bool(_git("status", "--porcelain", "--", "packages")),
            "engine": k.__version__,
            "opponent": a.opponent,
            "seeds": seeds,
            "arms": arms,
        }
        with open(a.out, "w") as fh:
            json.dump({"identity": identity, "games": games, "summary": summary,
                       "check": verdict}, fh, indent=1, default=str)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
