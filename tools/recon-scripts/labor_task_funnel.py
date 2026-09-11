"""Task funnel (generated -> claimed -> executed), ALL task types, for the
SHIPPED agent (PolicyConfig() all-defaults -- strawberry off) vs
public:sokolovsky-v12, on kaggriculture main@8f23781.

Adapts kaggriculture's own tools/recon-scripts/sw_fill_diag_q1.py monkeypatch
technique (agent.dispatch._field_tasks + agent.policy.dispatch), generalized
from a single strawberry zone to every task type across the whole board.
Read-only diagnostic: no tracked file is modified; two monkeypatches live
only in this process, applied before env.run() ever calls into the agent.

Task kind is derived from (verb, priority, zone-membership), where zone
membership reuses the SAME melon_tiles/pasture_tiles/strawberry_tiles
frozensets dispatch() itself uses -- not a re-guess from raw tile dicts.

Run from the kaggriculture repo root (main@8f23781):
    uv run python task_funnel.py <seed> <out_dir>

Writes <out_dir>/funnel_<seed>_summary.json (per-kind totals + per-day),
<out_dir>/funnel_<seed>_per_day_hour.json (day x hour x kind funnel), and
<out_dir>/funnel_<seed>_turns.json (compact per-turn log: positions, actions,
claims, shed/seeds/money/hires_today -- reused by other labor/* scripts so
the game is only ever played once per seed).
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time

import kaggle_environments as k

assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"

import agent  # noqa: E402
import agent.dispatch as dispatch_mod  # noqa: E402
import agent.policy as policy_mod  # noqa: E402
from agent.view import parse_obs  # noqa: E402
from harness.episodes import resolve_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

print("agent imported from:", agent.__file__, file=sys.stderr)

SHIPPED_CFG: dict = {}  # PolicyConfig() all-default: strawberry_tile_target=0 always
ALLOWED_SEEDS = range(855000, 855008)


def classify(action, priority, tile, melon_set, pasture_set, strawberry_set):
    """Task kind label from (verb, priority, zone). Zone membership is read
    off the SAME frozensets dispatch()/_field_tasks() use to schedule the
    tile, not re-derived from raw tile state, so this can never disagree
    with the dispatcher's own zone assignment."""
    verb = action[0]
    if tile in pasture_set:
        zone = "PASTURE"
    elif tile in melon_set:
        zone = "MELON"
    elif tile in strawberry_set:
        zone = "STRAWBERRY"
    else:
        zone = "WHEAT"
    if verb == "PLANT":
        crop = action[1] if len(action) > 1 else zone
        return f"PLANT:{crop}"
    if verb == "PLACE":
        species = action[1] if len(action) > 1 else "ANIMAL"
        return f"PLACE:{species}"
    if verb == "BUILD_PASTURE":
        return "BUILD_PASTURE"
    if verb == "DIG":
        return f"DIG:{zone}"
    if verb == "WATER":
        urgency = "urgent" if priority == 0 else "maintenance"
        return f"WATER:{urgency}:{zone}"
    if verb == "HARVEST":
        return f"HARVEST:{zone}"
    if verb == "FEED":
        return "FEED:PASTURE"
    if verb == "CARE":
        return "CARE:PASTURE"
    if verb == "COLLECT_FERTILIZER":
        return "COLLECT_FERTILIZER:PASTURE"
    if verb == "FERTILIZE":
        return f"FERTILIZE:{zone}"
    return f"OTHER:{verb}"


# --- instrumentation state, reset per game --------------------------------
GEN: collections.Counter = collections.Counter()  # (day,hour,kind) -> generated
CLAIMED: collections.Counter = collections.Counter()  # (day,hour,kind) -> claimed
EXECUTED: collections.Counter = collections.Counter()  # (day,hour,kind) -> executed
GOOSE: collections.Counter = collections.Counter()  # (day,hour,goose_status) -> count
TURNS: dict[int, dict] = {}
_LAST_BY_TILE: dict = {}


def reset_state() -> None:
    GEN.clear()
    CLAIMED.clear()
    EXECUTED.clear()
    GOOSE.clear()
    TURNS.clear()
    global _LAST_BY_TILE
    _LAST_BY_TILE = {}


# Goose duty is architecturally separate from the priority-tier/claims system
# (dispatch._steward is checked first, pre-empts everything for the farmer --
# see dispatch.py:687-690) -- so it structurally cannot have an "unclaimed"
# backlog the way field/pasture tasks can (the farmer is always immediately
# and exclusively dedicated to it the instant a goose need exists). We still
# log it separately (not folded into the main GEN/CLAIMED/EXECUTED funnel,
# which assumes competition for units that goose duty never has) so its
# share of farmer-turns is visible and its few terminal actions
# (FEED/HARVEST/CARE/COLLECT_FERTILIZER/PLACE/BUILD_COOP/DIG-at-coop) are
# distinguishable from its walk-toward-goose/walk-toward-shed turns.
_orig_steward = dispatch_mod._steward


def _traced_steward(*args, **kwargs):
    action = _orig_steward(*args, **kwargs)
    view = args[0]
    if action is None:
        return action
    verb = action[0]
    status = "walk" if verb in {"NORTH", "SOUTH", "EAST", "WEST"} else f"do:{verb}"
    GOOSE[(view.day, view.hour, status)] += 1
    return action


dispatch_mod._steward = _traced_steward


_orig_field_tasks = dispatch_mod._field_tasks


def _traced_field_tasks(*args, **kwargs):
    global _LAST_BY_TILE
    tasks = _orig_field_tasks(*args, **kwargs)
    view = args[0]
    melon_set = args[2] if len(args) > 2 else kwargs.get("melon_tiles", frozenset())
    pasture_set = args[3] if len(args) > 3 else kwargs.get("pasture_tiles", frozenset())
    strawberry_set = args[4] if len(args) > 4 else kwargs.get("strawberry_tiles", frozenset())
    by_tile: dict = {}
    day, hour = view.day, view.hour
    for t in tasks:
        kind = classify(t.action, t.priority, t.tile, melon_set, pasture_set, strawberry_set)
        by_tile[t.tile] = (tuple(t.action), t.priority, kind)
        GEN[(day, hour, kind)] += 1
    _LAST_BY_TILE = by_tile
    return tasks


dispatch_mod._field_tasks = _traced_field_tasks

_orig_dispatch = policy_mod.dispatch


def _traced_dispatch(*args, **kwargs):
    actions = _orig_dispatch(*args, **kwargs)
    view = args[0]
    day, hour = view.day, view.hour
    by_tile = _LAST_BY_TILE

    for unit_idx, tile in actions.claims.items():
        info = by_tile.get(tuple(tile))
        if info is None:
            continue  # should not happen -- a claim always names a tile _field_tasks offered this turn
        act, pr, kind = info
        CLAIMED[(day, hour, kind)] += 1
        if unit_idx == 0:
            unit_action = actions.farmer
        else:
            hi = unit_idx - 1
            unit_action = actions.hands[hi] if hi < len(actions.hands) else None
        if unit_action == list(act):
            EXECUTED[(day, hour, kind)] += 1

    rec = TURNS.setdefault(view.step, {})
    rec["day"] = day
    rec["hour"] = hour
    rec["money"] = view.money
    rec["shed"] = dict(view.shed)
    rec["seeds"] = dict(view.seeds)
    rec["prices"] = dict(view.prices)
    rec["hires_today"] = view.hires_today
    rec["unlocked"] = list(view.unlocked_quadrants)
    rec["farmer_pos"] = list(view.farmer)
    rec["hands_pos"] = [list(p) for p in view.hands]
    rec["inventories"] = [dict(i) for i in view.inventories]
    rec["farmer_action"] = list(actions.farmer)
    rec["hands_actions"] = [list(a) for a in actions.hands]
    rec["claims"] = {int(kk): list(vv) for kk, vv in actions.claims.items()}
    rec["n_units"] = 1 + len(view.hands)
    rec["n_tasks_generated"] = len(by_tile)
    return actions


policy_mod.dispatch = _traced_dispatch


# ---------------------------------------------------------------------------
def hire_orders_by_turn(env) -> dict[int, int]:
    out = {}
    for t in range(len(env.steps) - 1):
        act = env.steps[t][0].get("action") or {}
        n = sum(1 for o in (act.get("market") or []) if o and o[0] == "HIRE")
        if n:
            out[t] = n
    return out


def play(seed: int, cfg: dict, opponent: str = "public:sokolovsky-v12"):
    reset_state()
    env = make("kaggriculture", configuration={"seed": seed})
    t0 = time.time()
    env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])
    elapsed = time.time() - t0
    return env, elapsed


def funnel_summary():
    totals: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for (day, hour, kind), n in GEN.items():
        totals[kind]["gen"] += n
    for (day, hour, kind), n in CLAIMED.items():
        totals[kind]["claimed"] += n
    for (day, hour, kind), n in EXECUTED.items():
        totals[kind]["executed"] += n
    per_kind_total = [
        {
            "kind": kind,
            "generated": c["gen"],
            "claimed": c["claimed"],
            "executed": c["executed"],
            "claim_rate": (c["claimed"] / c["gen"] if c["gen"] else None),
            "exec_rate_of_claimed": (c["executed"] / c["claimed"] if c["claimed"] else None),
        }
        for kind, c in sorted(totals.items())
    ]

    by_day: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for (day, hour, kind), n in GEN.items():
        by_day[(day, kind)]["gen"] += n
    for (day, hour, kind), n in CLAIMED.items():
        by_day[(day, kind)]["claimed"] += n
    for (day, hour, kind), n in EXECUTED.items():
        by_day[(day, kind)]["executed"] += n
    per_day = [
        {"day": day, "kind": kind, "generated": c["gen"], "claimed": c["claimed"], "executed": c["executed"]}
        for (day, kind), c in sorted(by_day.items())
    ]

    all_keys = sorted(set(GEN) | set(CLAIMED) | set(EXECUTED))
    per_day_hour = [
        {
            "day": day,
            "hour": hour,
            "kind": kind,
            "generated": GEN.get((day, hour, kind), 0),
            "claimed": CLAIMED.get((day, hour, kind), 0),
            "executed": EXECUTED.get((day, hour, kind), 0),
        }
        for (day, hour, kind) in all_keys
    ]
    return per_kind_total, per_day, per_day_hour


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 855000
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "."
    assert seed in ALLOWED_SEEDS, f"seed {seed} out of allowed range 855000-855007"
    os.makedirs(out_dir, exist_ok=True)

    env, elapsed = play(seed, SHIPPED_CFG)
    final_view = parse_obs(env.steps[-1][0]["observation"])
    opp_view = None
    try:
        final_view_opp_money = float(env.steps[-1][1]["observation"]["farms"][1]["money"])
    except Exception:
        final_view_opp_money = None

    per_kind_total, per_day, per_day_hour = funnel_summary()
    hires = hire_orders_by_turn(env)
    goose_totals = collections.Counter()
    for (day, hour, status), n in GOOSE.items():
        goose_totals[status] += n

    out = {
        "seed": seed,
        "config": "SHIPPED (PolicyConfig defaults, no overrides)",
        "opponent": "public:sokolovsky-v12",
        "elapsed_sec": elapsed,
        "final_money_ours": final_view.money,
        "final_money_opponent": final_view_opp_money,
        "per_kind_total": per_kind_total,
        "per_day": per_day,
        "goose_totals": dict(goose_totals),
        "hire_orders_by_turn": hires,
        "n_turns_logged": len(TURNS),
    }
    summary_path = os.path.join(out_dir, f"funnel_{seed}_summary.json")
    per_day_hour_path = os.path.join(out_dir, f"funnel_{seed}_per_day_hour.json")
    turns_path = os.path.join(out_dir, f"funnel_{seed}_turns.json")
    with open(summary_path, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    with open(per_day_hour_path, "w") as fh:
        json.dump(per_day_hour, fh, default=str)
    with open(turns_path, "w") as fh:
        json.dump(TURNS, fh, default=str)

    print(f"seed={seed} elapsed={elapsed:.1f}s turns_logged={len(TURNS)} "
          f"final_money_ours={final_view.money:,.0f} final_money_opp={final_view_opp_money}")
    print(f"{'kind':<30} {'gen':>6} {'claimed':>8} {'executed':>9} {'claim%':>7} {'exec%claimed':>13}")
    for row in per_kind_total:
        cr = f"{row['claim_rate']*100:.1f}" if row["claim_rate"] is not None else "  -  "
        er = f"{row['exec_rate_of_claimed']*100:.1f}" if row["exec_rate_of_claimed"] is not None else "  -  "
        print(f"{row['kind']:<30} {row['generated']:>6} {row['claimed']:>8} {row['executed']:>9} {cr:>7} {er:>13}")
    print(f"\nwrote {summary_path}\nwrote {per_day_hour_path}\nwrote {turns_path}")


if __name__ == "__main__":
    main()
