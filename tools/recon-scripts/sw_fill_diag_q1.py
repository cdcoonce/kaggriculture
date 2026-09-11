"""Q1 diagnostic: why does the SW strawberry zone plant so few tiles on days
10-12? Instruments agent.dispatch._field_tasks (candidate task generation)
and agent.policy.dispatch (final claims + actions) IN THIS SCRIPT ONLY -- no
tracked file is modified. Read-only recon.

Run from the worktree root:
    uv run python /path/to/q1_diag.py
"""
from __future__ import annotations

import collections
import itertools
import json
import sys

import kaggle_environments as k

assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"

import agent  # noqa: E402
import agent.dispatch as dispatch_mod  # noqa: E402
import agent.policy as policy_mod  # noqa: E402
from agent.constants import QUADRANTS  # noqa: E402
from agent.dispatch import STRAWBERRY_PLANT_CUTOFF_DAY, plant_quota  # noqa: E402
from harness.episodes import resolve_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

print("agent imported from:", agent.__file__, file=sys.stderr)

# ---------------------------------------------------------------------------
# Instrumentation: wrap _field_tasks (candidate tasks) and policy.dispatch
# (final claims + actions). Both are monkeypatches local to this process;
# nothing on disk changes.
# ---------------------------------------------------------------------------
TURNS: dict[int, dict] = {}


def _arg(args, kwargs, idx, name, default):
    if idx < len(args):
        return args[idx]
    return kwargs.get(name, default)


_orig_field_tasks = dispatch_mod._field_tasks


def _traced_field_tasks(*args, **kwargs):
    tasks = _orig_field_tasks(*args, **kwargs)
    view = args[0]
    strawberry_tiles = _arg(args, kwargs, 4, "strawberry_tiles", frozenset())
    cap = _arg(args, kwargs, 5, "strawberry_plant_daily_cap", 6)
    rec = TURNS.setdefault(view.step, {})
    rec["day"] = view.day
    rec["hour"] = view.hour
    rec["cap"] = cap
    rec["strawberry_zone"] = sorted(tuple(tt) for tt in strawberry_tiles)
    rec["sw_tasks"] = [
        {"tile": tuple(t.tile), "action": list(t.action), "priority": t.priority, "crop": t.crop}
        for t in tasks
        if tuple(t.tile) in strawberry_tiles
    ]
    # also record total priority-3 (planting-class) task pool size, to gauge
    # how much competition strawberry's PLANT tasks face from wheat/melon.
    rec["all_p3_count"] = sum(1 for t in tasks if t.priority == 3)
    return tasks


dispatch_mod._field_tasks = _traced_field_tasks

_orig_dispatch = policy_mod.dispatch


def _traced_dispatch(*args, **kwargs):
    actions = _orig_dispatch(*args, **kwargs)
    view = args[0]
    strawberry_tiles = _arg(args, kwargs, 4, "strawberry_tiles", frozenset())
    rec = TURNS.setdefault(view.step, {})
    rec["day"] = view.day
    rec["hour"] = view.hour
    rec["money"] = view.money
    rec["seeds"] = dict(view.seeds)
    rec["shed"] = dict(view.shed)
    rec["farmer_pos"] = list(view.farmer)
    rec["hands_pos"] = [list(p) for p in view.hands]
    rec["farmer_action"] = list(actions.farmer)
    rec["hands_actions"] = [list(a) for a in actions.hands]
    rec["claims"] = {int(kk): list(vv) for kk, vv in actions.claims.items()}
    rec["unlocked"] = list(view.unlocked_quadrants)
    rec["active_tiles"] = len(args[1]) if len(args) > 1 else None

    sw_states = {}
    for x, y in strawberry_tiles:
        t = view.tiles[y][x]
        if t is None:
            sw_states[f"{x},{y}"] = {"state": "BARE"}
        elif t == "LOCKED":
            sw_states[f"{x},{y}"] = {"state": "LOCKED"}
        elif isinstance(t, dict) and t.get("kind") == "WEED":
            sw_states[f"{x},{y}"] = {"state": "WEED"}
        elif isinstance(t, dict) and t.get("kind") == "PLANT":
            planted_day = t.get("planted_day", view.day)
            sw_states[f"{x},{y}"] = {
                "state": "PLANT",
                "crop": t.get("crop"),
                "planted_day": planted_day,
                "age": view.day - int(planted_day),
                "yield_units": t.get("yield_units", 0),
                "watered_today": bool(t.get("watered_today", False)),
            }
        else:
            sw_states[f"{x},{y}"] = {"state": f"OTHER:{t!r}"}
    rec["sw_tile_states"] = sw_states
    return actions


policy_mod.dispatch = _traced_dispatch


# ---------------------------------------------------------------------------
def play(seed: int, cfg: dict, opponent="public:sokolovsky-v12"):
    TURNS.clear()
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])
    return env, dict(TURNS)


def tile_state_histogram(turns_by_step, step, zone):
    rec = turns_by_step.get(step)
    if rec is None or "sw_tile_states" not in rec:
        return None
    hist = collections.Counter()
    for x, y in zone:
        s = rec["sw_tile_states"].get(f"{x},{y}", {}).get("state", "MISSING")
        hist[s] += 1
    return dict(hist)


def summarize(seed: int, cfg: dict, label: str, day_lo=9, day_hi=13):
    env, turns = play(seed, cfg)
    zone = sorted(tuple(t) for t in turns[max(turns)]["strawberry_zone"]) if turns else []
    # zone can change turn to turn only in theory; use the LAST turn's zone as
    # reference (should be constant once cfg.strawberry_tile_target is fixed).
    any_zone_rec = next((r["strawberry_zone"] for r in turns.values() if r.get("strawberry_zone")), [])
    zone = sorted(tuple(t) for t in any_zone_rec)

    print(f"\n{'=' * 90}\n{label}  seed={seed}  zone_size={len(zone)}\n{'=' * 90}")
    print(f"cfg: {cfg}")
    print(f"zone tiles: {zone}")

    lo, hi = day_lo * 24, day_hi * 24 + 23

    # ---- per-day end-of-day snapshot -------------------------------------
    print(f"\n-- end-of-day snapshots (day {day_lo}-{day_hi}) --")
    print(
        f"{'day':>3} {'money':>8} {'straw_seed':>10} {'wheat_seed':>10} "
        f"{'BARE':>4} {'WEED':>4} {'STRAW':>5} {'WHEAT':>5} {'LOCKED':>6} {'unlocked':>10}"
    )
    for day in range(day_lo, day_hi + 1):
        step = day * 24 + 23
        rec = turns.get(step)
        if rec is None:
            continue
        hist = tile_state_histogram(turns, step, zone)
        straw_ct = sum(
            1
            for v in rec["sw_tile_states"].values()
            if v.get("state") == "PLANT" and v.get("crop") == "STRAWBERRY"
        )
        wheat_ct = sum(
            1
            for v in rec["sw_tile_states"].values()
            if v.get("state") == "PLANT" and v.get("crop") == "WHEAT"
        )
        print(
            f"{day:>3} {rec['money']:>8,.0f} {rec['seeds'].get('STRAWBERRY', 0):>10} "
            f"{rec['seeds'].get('WHEAT', 0):>10} "
            f"{hist.get('BARE', 0):>4} {hist.get('WEED', 0):>4} {straw_ct:>5} {wheat_ct:>5} "
            f"{hist.get('LOCKED', 0):>6} {''.join(rec['unlocked']):>10}"
        )

    # ---- task generation -> claim -> execution funnel ----------------------
    gen = collections.Counter()  # (day, action_tuple) -> count of tile-turns generated
    claimed = collections.Counter()
    executed = collections.Counter()
    claim_examples = []
    for step in range(lo, min(hi, max(turns)) + 1):
        rec = turns.get(step)
        if rec is None or "sw_tasks" not in rec:
            continue
        day = rec["day"]
        claims_this_turn = {tuple(v): kk for kk, v in rec.get("claims", {}).items()}
        for task in rec["sw_tasks"]:
            act = tuple(task["action"])
            gen[(day, act)] += 1
            tile = task["tile"]
            if tile in claims_this_turn:
                claimed[(day, act)] += 1
                unit_idx = claims_this_turn[tile]
                if unit_idx == 0:
                    unit_action = rec.get("farmer_action")
                    unit_pos = rec.get("farmer_pos")
                else:
                    hidx = unit_idx - 1
                    hands_actions = rec.get("hands_actions", [])
                    hands_pos = rec.get("hands_pos", [])
                    unit_action = hands_actions[hidx] if hidx < len(hands_actions) else None
                    unit_pos = hands_pos[hidx] if hidx < len(hands_pos) else None
                if unit_action == list(act):
                    executed[(day, act)] += 1
                    if len(claim_examples) < 12 and act[:2] == ["PLANT", "STRAWBERRY"]:
                        claim_examples.append(
                            {
                                "step": step,
                                "day": day,
                                "hour": rec["hour"],
                                "tile": tile,
                                "unit": unit_idx,
                                "unit_pos": unit_pos,
                                "action": unit_action,
                            }
                        )

    print(f"\n-- SW-zone task funnel: GENERATED -> CLAIMED -> EXECUTED (day {day_lo}-{day_hi}) --")
    all_actions = sorted(set(a for (_, a) in gen), key=lambda a: (a[0], a[1] if len(a) > 1 else ""))
    for day in range(day_lo, day_hi + 1):
        for act in all_actions:
            g = gen.get((day, act), 0)
            if g == 0:
                continue
            c = claimed.get((day, act), 0)
            e = executed.get((day, act), 0)
            print(f"  day {day:>2}  {str(act):<28} generated={g:>3}  claimed={c:>3}  executed={e:>3}")

    print("\n-- sample executed PLANT STRAWBERRY events (up to 12) --")
    for ex in claim_examples:
        print(f"  step {ex['step']:>4} day {ex['day']:>2} hr {ex['hour']:>2}  "
              f"unit {ex['unit']} at {ex['unit_pos']} -> planted {ex['tile']}")

    # ---- unit distance-to-zone trace (how close do units GET to SW?) ------
    print(f"\n-- min unit distance to SW zone bbox, sampled every 4 hours (day {day_lo}-{day_hi}) --")

    def bbox_dist(pos, zone):
        xs = [t[0] for t in zone]
        ys = [t[1] for t in zone]
        x, y = pos
        dx = 0 if xs[0] <= x <= xs[-1] else min(abs(x - xx) for xx in (min(xs), max(xs)))
        dy = 0 if ys[0] <= y <= ys[-1] else min(abs(y - yy) for yy in (min(ys), max(ys)))
        return dx + dy

    if zone:
        for day in range(day_lo, day_hi + 1):
            row = []
            for hour in range(0, 24, 4):
                step = day * 24 + hour
                rec = turns.get(step)
                if rec is None:
                    row.append("  . ")
                    continue
                positions = [rec["farmer_pos"]] + rec.get("hands_pos", [])
                dmin = min(bbox_dist(p, zone) for p in positions)
                units_inside = sum(1 for p in positions if tuple(p) in set(zone))
                row.append(f"{dmin:>2}{'*' if units_inside else ' '}")
            print(f"  day {day:>2} hr[0,4..20]: " + " ".join(row) + "   (* = >=1 unit standing inside zone)")

    # ---- BUY_SEED / BUY_LAND orders touching strawberry/SW --------------
    print(f"\n-- BUY orders each day (from raw action log, day {day_lo}-{day_hi}) --")
    for day in range(day_lo, day_hi + 1):
        day_orders = collections.Counter()
        for t in range(day * 24, min(day * 24 + 23, len(env.steps) - 1) + 1):
            act = env.steps[t][0].get("action") or {}
            for o in act.get("market", []) or []:
                if not o or o[0] == "SELL":
                    continue
                item = o[1] if len(o) > 1 else ""
                qty = o[2] if len(o) > 2 and isinstance(o[2], (int, float)) else 1
                day_orders[f"{o[0]}:{item}" if item else o[0]] += qty
        print(f"  day {day:>2}: {dict(sorted(day_orders.items()))}")

    n_calls = len(turns)
    print(f"\n[sanity] _field_tasks/dispatch call count across whole game: {n_calls} (expect 720 for a full game)")

    return env, turns, zone


if __name__ == "__main__":
    SW25 = {
        "strawberry_frame_quadrants": ["SW"],
        "strawberry_tile_target": 25,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 9,
    }
    NWNE10 = {
        "strawberry_tile_target": 31,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 10,
    }

    results = {}
    for seed in (855000, 855001):
        env, turns, zone = summarize(seed, SW25, f"SW25 (seed {seed})")
        results[f"sw25_{seed}"] = turns

    env, turns, zone = summarize(855000, NWNE10, "NWNE10 (seed 855000, contrast)")
    results["nwne10_855000"] = turns

    out_path = (sys.argv[1] if len(sys.argv) > 1 else "q1_turns.json")
    with open(out_path, "w") as fh:
        json.dump(results, fh, default=str)
    print(f"\nwrote {out_path}")
