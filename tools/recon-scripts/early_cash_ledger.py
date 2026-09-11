"""Early-cash ledger: where does the opening's cash go, and does an arm reproduce it?

For each arm (a PolicyConfig override dict; the FIRST arm is the reference) on each
seed, plays one game against a public leader and records, per day: end-of-day money,
tiles by crop, animals, unlocked quadrants, hands, and submitted non-SELL market orders
(submissions, not fills -- read them alongside the money trajectory). It then diffs
every arm's submitted actions against the reference arm, turn by turn, and records the
first divergence. The game is deterministic in the seed plus both seats' actions, so an
arm whose actions match the reference through day N-1 provably leaves that stretch of
the game untouched -- the check a start-day gate at day N has to pass.

Written for the strawberry rebuild (eval/prereg/2026-09-11-strawberry-slice1-start-day.md):
with strawberry on, day-0 seed buys displaced the herd and, with it, the day-8 cash
takeoff. Recon only; requires engine 1.32.7. Run from the repository (or worktree) root,
so the agent under test is the one `uv run` imports there.

Usage:
    uv run python tools/recon-scripts/early_cash_ledger.py \
        --arms '{"A_shipped": {}, "B": {"strawberry_tile_target": 31}}' \
        --seeds 855000,855001 --out ledger.json
"""

import argparse
import collections
import dataclasses
import json
import subprocess


def flat(tiles):
    for row in tiles:
        yield from (row if isinstance(row, (list, tuple)) else [row])


def board(v):
    c = collections.Counter()
    for t in flat(v.tiles):
        if t is None:
            c["empty"] += 1
        elif t == "LOCKED":
            pass
        elif isinstance(t, dict):
            if t.get("kind") == "WEED":
                c["weed"] += 1
            elif t.get("crop"):
                c[str(t["crop"]).lower()] += 1
            a = t.get("animal") or (
                t.get("kind") if t.get("kind") in ("COW", "SHEEP", "GOOSE") else None
            )
            if a:
                kind = a.get("kind", "?") if isinstance(a, dict) else a
                c["a_" + str(kind).lower()] += 1
    return c


def orders(action):
    out = collections.Counter()
    mk = (action or {}).get("market", []) if isinstance(action, dict) else []
    for o in mk or []:
        if not o or o[0] == "SELL":
            continue
        item = o[1] if len(o) > 1 else ""
        qty = o[2] if len(o) > 2 and isinstance(o[2], (int, float)) else 1
        out[f"{o[0]}:{item}" if item else o[0]] += min(qty, 999)
    return out


def canon(x):
    return json.dumps(x, sort_keys=True, default=str)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="JSON {name: config}; first arm = reference")
    ap.add_argument("--seeds", default="855000")
    ap.add_argument("--opponent", default="public:sokolovsky-v12")
    ap.add_argument("--out", help="write the JSON record here")
    a = ap.parse_args()
    arms = json.loads(a.arms)
    seeds = [int(s) for s in a.seeds.split(",")]

    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"
    import agent
    import agent.policy as pol
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    try:
        defaults = {f.name: f.default for f in dataclasses.fields(pol.PolicyConfig)}
    except TypeError:
        defaults = dict(vars(pol.PolicyConfig()))
    for arm, cfg in arms.items():
        missing = [key for key in cfg if key not in defaults]
        assert not missing, f"{arm}: not PolicyConfig fields: {missing}"
        loaded = ", ".join(f"{key}={cfg[key]} (default {defaults[key]})" for key in cfg)
        print(f"{arm}: {loaded or 'shipped defaults'}")

    identity = {
        "script": "tools/recon-scripts/early_cash_ledger.py",
        "git_sha": git("rev-parse", "HEAD"),
        "packages_dirty": bool(git("status", "--porcelain", "--", "packages")),
        "agent_imported_from": agent.__file__,
        "engine": k.__version__,
        "opponent": a.opponent,
        "seeds": seeds,
        "arms": arms,
    }
    print("identity:", json.dumps(identity))
    ref_name = next(iter(arms))
    games: dict = {}
    for seed in seeds:
        envs = {}
        for arm, cfg in arms.items():
            env = make("kaggriculture", configuration={"seed": seed})
            env.run([resolve_agent("champion", cfg), resolve_agent(a.opponent)])
            envs[arm] = env
            rows = []
            for day in range(30):
                t_end = day * 24 + 23
                if t_end >= len(env.steps):
                    break
                v = parse_obs(env.steps[t_end][0]["observation"])
                b = board(v)
                day_orders = collections.Counter()
                for t in range(day * 24, t_end + 1):
                    day_orders += orders(env.steps[t][0].get("action"))
                rows.append(
                    {
                        "day": day,
                        "obs_day": v.day,
                        "money": v.money,
                        "wheat": b["wheat"],
                        "strawberry": b["strawberry"],
                        "melon": b["melon"],
                        "empty": b["empty"],
                        "cow": b["a_cow"],
                        "sheep": b["a_sheep"],
                        "goose": b["a_goose"],
                        "quads": "".join(v.unlocked_quadrants),
                        "hands": len(v.hands or []),
                        "orders": dict(sorted(day_orders.items())),
                    }
                )
            final = {s: parse_obs(env.steps[-1][s]["observation"]).money for s in (0, 1)}
            game = {
                "rows": rows,
                "final_money": final[0],
                "opp_final_money": final[1],
                "sw_day": next((r["day"] for r in rows if "SW" in r["quads"]), None),
                "peak_strawberry": max(r["strawberry"] for r in rows),
            }
            if arm != ref_name:
                ref, div = envs[ref_name], None
                for t in range(min(len(ref.steps), len(env.steps))):
                    for s in (0, 1):
                        ra = canon(ref.steps[t][s].get("action"))
                        ca = canon(env.steps[t][s].get("action"))
                        if ra != ca:
                            ov = parse_obs(env.steps[max(t - 1, 0)][0]["observation"])
                            div = {
                                "step": t,
                                "day": ov.day,
                                "hour": ov.hour,
                                "seat": s,
                                "ref_action": ra[:400],
                                "arm_action": ca[:400],
                            }
                            break
                    if div:
                        break
                game["first_divergence_vs_ref"] = div
            games.setdefault(str(seed), {})[arm] = game

            print(
                f"\n===== {arm} (seed {seed}) final ${final[0]:,.0f} vs opp ${final[1]:,.0f}"
                f" | SW day {game['sw_day']} | peak strawberry {game['peak_strawberry']} ====="
            )
            if arm != ref_name:
                d = game["first_divergence_vs_ref"]
                if d is None:
                    print(f"  first action divergence vs {ref_name}: NONE (identical all game)")
                else:
                    print(
                        f"  first action divergence vs {ref_name}: step {d['step']}"
                        f" (day {d['day']} hour {d['hour']}) seat {d['seat']}"
                        f"\n    ref: {d['ref_action'][:200]}\n    arm: {d['arm_action'][:200]}"
                    )
            print(
                f"{'d':>2} {'money':>7} {'wht':>3} {'strw':>4} {'mel':>3} {'emp':>3} {'cow':>3}"
                f" {'shp':>3} {'gse':>3} {'quad':>6} {'hnd':>3} | orders submitted (non-SELL)"
            )
            for r in rows[:13]:
                od = " ".join(f"{kk}={vv}" for kk, vv in r["orders"].items())
                flag = "" if r["obs_day"] == r["day"] else f" [obs_day {r['obs_day']}]"
                print(
                    f"{r['day']:>2} {r['money']:>7,.0f} {r['wheat']:>3} {r['strawberry']:>4}"
                    f" {r['melon']:>3} {r['empty']:>3} {r['cow']:>3} {r['sheep']:>3}"
                    f" {r['goose']:>3} {r['quads']:>6} {r['hands']:>3} | {od[:140]}{flag}"
                )
    if a.out:
        with open(a.out, "w") as fh:
            json.dump({"identity": identity, "games": games}, fh, indent=1, default=str)
        print("\nwrote", a.out)


if __name__ == "__main__":
    main()
