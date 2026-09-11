"""Where do WEED tiles come from? Births and removals, by the engine's own rules.

For each arm (a PolicyConfig override dict; the FIRST arm is the reference) on each
seed, plays one game against a public leader, then walks every recorded step and diffs
the tile grid against the previous step. Every tile that becomes a WEED is classified by
re-deriving the exact engine condition that must have fired, not by a heuristic, and a
birth that matches none of them is labelled UNEXPECTED_* so it cannot pass unnoticed.

The engine (kaggle_environments 1.32.7, envs/kaggriculture/kaggriculture.py) creates a
WEED in exactly three ways:
  - `_decay_plants`: a plant past its `max_lifespan_step` loses a yield unit every other
    step, and the tile becomes {"kind": "WEED"} when the units hit 0. This is the end of
    a plant's natural life, and it is unavoidable for any crop that is left to finish.
  - the daily refresh: `consecutive_unwatered += 1` on a tile that was not watered that
    day, and `>= 2` replaces the plant with a WEED. A fresh planting starts at 1, so it
    must be watered on its planting day. THIS is the avoidable one -- a plant killed
    because nobody watered it.
  - `_spawn_weeds`: bare ground turns weedy at `weedSpawnChance` (0.005) per tile-day.
DIG is the only way off a WEED tile.

Written for the leader-tape slice (eval/prereg/2026-09-11-leader-tape-slice1.md), whose
C5 criterion is measured from the `established_unwatered` / `fresh_planting_unwatered`
counts below. Recon only; requires engine 1.32.7. Run from the repository (or worktree)
root, so the agent under test is the one `uv run` imports there.

Usage:
    uv run python tools/recon-scripts/weed_provenance.py \
        --arms '{"A_shipped": {}, "LT": {"strawberry_tile_target": 36}}' \
        --seeds 855000,855001 --out scan.json
"""

import argparse
import collections
import json
import subprocess
import time

DAY_BANDS = [(0, 9, "0-9"), (10, 12, "10-12"), (13, 16, "13-16"), (17, 22, "17-22"), (23, 29, "23-29")]
NEGLECT_CATEGORIES = ("established_unwatered", "fresh_planting_unwatered")


def day_band(day):
    for lo, hi, label in DAY_BANDS:
        if lo <= day <= hi:
            return label
    return "30+"


def quadrant_of(x, y, quadrants):
    for name, (xr, yr) in quadrants.items():
        if x in xr and y in yr:
            return name
    return "?"


def compact_label(tile):
    if tile is None:
        return "EMPTY"
    if tile == "LOCKED":
        return "LOCKED"
    if isinstance(tile, dict):
        kind = tile.get("kind")
        if kind == "WEED":
            return "WEED"
        if kind == "PLANT":
            return f"PLANT:{tile.get('crop')}"
        if "animal" in tile:
            return f"STRUCT:{kind}:{tile.get('animal')}"
        if kind in ("COOP", "PASTURE"):
            return f"STRUCT:{kind}:empty"
        return f"DICT_OTHER:{kind}"
    return f"OTHER:{tile!r}"


def decay_would_fire(tile, prev_step):
    """Mirrors the engine's `_decay_plants` condition for turning this exact tile into a
    WEED when the engine processes step ``prev_step``."""
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False
    mls = tile.get("max_lifespan_step", -1)
    if mls is None or mls < 0 or prev_step < mls:
        return False
    if (prev_step - mls) % 2 != 0:
        return False
    return (tile.get("yield_units", 0) - 1) <= 0


def unwater_would_fire(tile):
    """Mirrors the engine's daily-refresh condition for turning this exact tile into a
    WEED at the day boundary it is evaluated on."""
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False
    if tile.get("watered_today", False):
        return False
    return tile.get("consecutive_unwatered", 0) + 1 >= 2


def classify_birth(prev_tile, prev_step, birth_day, birth_hour):
    """(category, extra fields) for a tile that is WEED now and was not at ``prev_step``.
    ``prev_step`` is the engine step that was being processed when it happened."""
    if prev_tile is None:
        if birth_hour == 0:
            return "bare_ground_spawn", {}
        return "UNEXPECTED_none_to_weed_offhour", {}
    if prev_tile == "LOCKED":
        return "UNEXPECTED_locked_to_weed", {}
    if isinstance(prev_tile, dict) and prev_tile.get("kind") == "PLANT":
        crop = prev_tile.get("crop")
        planted_day = prev_tile.get("planted_day")
        age = birth_day - planted_day if planted_day is not None else None
        if decay_would_fire(prev_tile, prev_step):
            return "exhausted_crop", {"crop": crop, "planted_day": planted_day, "age": age}
        if birth_hour == 0 and unwater_would_fire(prev_tile):
            sub = "fresh_planting_unwatered" if (age is not None and age <= 0) else "established_unwatered"
            return sub, {"crop": crop, "planted_day": planted_day, "age": age}
        return "UNEXPECTED_plant_to_weed", {"crop": crop, "planted_day": planted_day, "age": age}
    if isinstance(prev_tile, dict) and ("animal" in prev_tile or prev_tile.get("kind") in ("COOP", "PASTURE")):
        return "UNEXPECTED_structure_to_weed", {}
    return "OTHER_unclassified", {}


def dig_ops(action):
    if not isinstance(action, dict):
        return 0
    n = 0
    units = [action.get("farmer")] + list(action.get("hands") or [])
    for u in units:
        if isinstance(u, list) and u and u[0] == "DIG":
            n += 1
    return n


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def play_and_scan(cfg, seed, opponent, quadrants):
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])
    n_steps = len(env.steps)
    views = [parse_obs(env.steps[t][0]["observation"]) for t in range(n_steps)]

    births, removals = [], []
    dig_actions_per_day = collections.Counter()
    weed_removals_per_day = collections.Counter()
    weed_births_per_day = collections.Counter()
    eod_weed_count = {}

    board_size = len(views[0].tiles)
    history = {(x, y): [] for x in range(board_size) for y in range(board_size)}
    last_label = {}
    for x in range(board_size):
        for y in range(board_size):
            lbl = compact_label(views[0].tiles[y][x])
            history[(x, y)].append({"step": 0, "day": views[0].day, "hour": views[0].hour, "label": lbl})
            last_label[(x, y)] = lbl

    for t in range(1, n_steps):
        v_prev, v_cur = views[t - 1], views[t]
        prev_step = t - 1
        for y in range(board_size):
            row_prev, row_cur = v_prev.tiles[y], v_cur.tiles[y]
            for x in range(board_size):
                pt, ct = row_prev[x], row_cur[x]
                lbl = compact_label(ct)
                if lbl != last_label[(x, y)]:
                    history[(x, y)].append({"step": t, "day": v_cur.day, "hour": v_cur.hour, "label": lbl})
                    last_label[(x, y)] = lbl
                pt_is_weed = isinstance(pt, dict) and pt.get("kind") == "WEED"
                ct_is_weed = isinstance(ct, dict) and ct.get("kind") == "WEED"
                if ct_is_weed and not pt_is_weed:
                    cat, extra = classify_birth(pt, prev_step, v_cur.day, v_cur.hour)
                    rec = {
                        "step": t, "day": v_cur.day, "hour": v_cur.hour, "x": x, "y": y,
                        "quadrant": quadrant_of(x, y, quadrants), "category": cat,
                        "prev_tile": pt if not isinstance(pt, dict) else dict(pt),
                    }
                    rec.update(extra)
                    births.append(rec)
                    weed_births_per_day[v_cur.day] += 1
                elif pt_is_weed and not ct_is_weed:
                    removals.append({
                        "step": t, "day": v_cur.day, "hour": v_cur.hour, "x": x, "y": y,
                        "quadrant": quadrant_of(x, y, quadrants), "becomes": lbl,
                    })
                    weed_removals_per_day[v_cur.day] += 1
        dig_actions_per_day[v_prev.day] += dig_ops(env.steps[t - 1][0].get("action"))

    # End-of-day snapshot at t_end = day*24+23, the same convention early_cash_ledger.py
    # uses, so the two records' weed counts are comparable. Read directly rather than off
    # the transition loop, so day 29 isn't dropped for want of a following step.
    for day in range(30):
        t_end = day * 24 + 23
        if t_end < n_steps:
            eod_weed_count[day] = sum(
                1 for row in views[t_end].tiles for tl in row if isinstance(tl, dict) and tl.get("kind") == "WEED"
            )

    strawberry_end_events = []
    for (x, y), hist in history.items():
        for i in range(1, len(hist)):
            prev_h, cur_h = hist[i - 1], hist[i]
            if prev_h["label"] == "PLANT:STRAWBERRY" and cur_h["label"] != "PLANT:STRAWBERRY":
                raw_prev = views[cur_h["step"] - 1].tiles[y][x]
                planted_day = raw_prev.get("planted_day") if isinstance(raw_prev, dict) else None
                strawberry_end_events.append({
                    "x": x, "y": y, "quadrant": quadrant_of(x, y, quadrants),
                    "planted_day": planted_day, "end_day": cur_h["day"], "end_hour": cur_h["hour"],
                    "becomes": cur_h["label"],
                    "age_at_end": (cur_h["day"] - planted_day) if planted_day is not None else None,
                })

    by_category = collections.Counter(b["category"] for b in births)
    by_band = collections.Counter((b["category"], day_band(b["day"])) for b in births)
    return {
        "n_steps": n_steps,
        "births": births,
        "removals": removals,
        "dig_actions_per_day": dict(sorted(dig_actions_per_day.items())),
        "weed_removals_per_day": dict(sorted(weed_removals_per_day.items())),
        "weed_births_per_day": dict(sorted(weed_births_per_day.items())),
        "eod_weed_count": dict(sorted(eod_weed_count.items())),
        "eod_weed_tiledays_sum_0_29": sum(eod_weed_count.values()),
        "births_by_category": dict(sorted(by_category.items())),
        "births_by_category_and_band": {f"{c}|{b}": n for (c, b), n in sorted(by_band.items())},
        "neglect_deaths": sum(by_category[c] for c in NEGLECT_CATEGORIES),
        "strawberry_end_events": strawberry_end_events,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="JSON {name: config}; first arm = reference")
    ap.add_argument("--seeds", default="855000")
    ap.add_argument("--opponent", default="public:sokolovsky-v12")
    ap.add_argument("--out", required=True, help="write the JSON record here")
    a = ap.parse_args()
    arms = json.loads(a.arms)
    seeds = [int(s) for s in a.seeds.split(",")]

    import dataclasses

    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"
    import agent
    import agent.policy as pol
    from agent.constants import QUADRANTS

    defaults = {f.name: f.default for f in dataclasses.fields(pol.PolicyConfig)}
    for arm, cfg in arms.items():
        missing = [key for key in cfg if key not in defaults]
        assert not missing, f"{arm}: not PolicyConfig fields: {missing}"

    identity = {
        "script": "tools/recon-scripts/weed_provenance.py",
        "git_sha": git("rev-parse", "HEAD"),
        "packages_dirty": bool(git("status", "--porcelain", "--", "packages")),
        "agent_imported_from": agent.__file__,
        "engine": k.__version__,
        "opponent": a.opponent,
        "seeds": seeds,
        "arms": arms,
    }
    print("identity:", json.dumps(identity))

    games: dict = {}
    t0 = time.time()
    for arm, cfg in arms.items():
        for seed in seeds:
            gt0 = time.time()
            res = play_and_scan(cfg, seed, a.opponent, QUADRANTS)
            games.setdefault(str(seed), {})[arm] = res
            print(
                f"{arm} seed={seed}: births={len(res['births'])} neglect={res['neglect_deaths']} "
                f"weed_tiledays={res['eod_weed_tiledays_sum_0_29']} ({time.time() - gt0:.1f}s)"
            )
    print(f"total scan time: {time.time() - t0:.1f}s")

    print(f"\n{'arm':<14}{'neglect/game':>13}{'exhausted':>11}{'bare':>7}{'weed tile-days':>16}{'unexplained':>13}")
    for arm in arms:
        per_seed = [games[str(s)][arm] for s in seeds]
        cats = collections.Counter()
        for g in per_seed:
            cats.update(g["births_by_category"])
        odd = sum(n for c, n in cats.items() if c.startswith(("UNEXPECTED", "OTHER")))
        print(
            f"{arm:<14}{sum(g['neglect_deaths'] for g in per_seed) / len(per_seed):>13.1f}"
            f"{cats['exhausted_crop'] / len(per_seed):>11.1f}{cats['bare_ground_spawn'] / len(per_seed):>7.1f}"
            f"{sum(g['eod_weed_tiledays_sum_0_29'] for g in per_seed) / len(per_seed):>16.1f}{odd:>13d}"
        )

    with open(a.out, "w") as fh:
        json.dump({"identity": identity, "games": games}, fh, default=str)
    print("\nwrote", a.out)


if __name__ == "__main__":
    main()
