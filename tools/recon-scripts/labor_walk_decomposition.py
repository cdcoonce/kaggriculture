"""Walking decomposition (reassignment churn + morning commute) and labor
supply (hands/hour, idle PASS, hire timing), computed from the per-turn
claims/positions/actions log produced by task_funnel.py.

Churn detection generalizes tools/recon-scripts/sw_fill_diag_churn.py's exact
technique (diff a unit's claim turn-to-turn; a claim that changes while the
unit was still WALKING toward it, not yet arrived, is a churn event) from a
single strawberry zone to the whole board and every task type. Morning-
commute detection is new: for each unit-day, the walk from that unit's first
appearance that day (hour 0 for units that survive the night; the hour they
are re-hired for units spawned intraday) to its first non-walk action.

This is pure post-hoc analysis of already-collected JSON -- it does not run
the game again, so it has no seed/version dependency of its own (the input
files already carry that provenance from task_funnel.py).

Run from anywhere:
    uv run python walk_decomposition.py <turns_json> <summary_json> <out_prefix>
"""
from __future__ import annotations

import collections
import json
import sys

MOVE_VERBS = {"NORTH", "SOUTH", "EAST", "WEST"}
# Field-task verbs that terminate a "morning commute" window -- a unit that
# is still just leaving the shed (walking, or fetching supplies AT a shed
# tile via PICKUP/DROP) has not yet done any field work; the commute ends
# only once it performs an actual task. PASS also ends the window (the unit
# has stopped moving, not because it arrived -- it's idling, a different
# category) but is not counted as a commute step.
FIELD_VERBS = {
    "WATER", "FEED", "HARVEST", "CARE", "COLLECT_FERTILIZER", "PLANT",
    "FERTILIZE", "BUILD_PASTURE", "DIG", "PLACE", "BUILD_COOP",
}
SHED_LOGISTICS_VERBS = {"PICKUP", "DROP"}


def load_turns(path: str) -> list[tuple[int, dict]]:
    with open(path) as fh:
        raw = json.load(fh)
    turns = [(int(step), rec) for step, rec in raw.items()]
    turns.sort(key=lambda kv: kv[0])
    return turns


def unit_count(rec: dict) -> int:
    return 1 + len(rec.get("hands_pos", []))


def unit_pos(rec: dict, unit: int):
    if unit == 0:
        return tuple(rec["farmer_pos"])
    hp = rec.get("hands_pos", [])
    idx = unit - 1
    return tuple(hp[idx]) if idx < len(hp) else None


def unit_action(rec: dict, unit: int):
    if unit == 0:
        return rec.get("farmer_action")
    ha = rec.get("hands_actions", [])
    idx = unit - 1
    return ha[idx] if idx < len(ha) else None


def unit_claim(rec: dict, unit: int):
    claims = rec.get("claims", {})
    # JSON round-trip turns int keys into strings.
    v = claims.get(unit) if unit in claims else claims.get(str(unit))
    return tuple(v) if v is not None else None


def is_walk(action) -> bool:
    return bool(action) and action[0] in MOVE_VERBS


def is_pass(action) -> bool:
    return bool(action) and action[0] == "PASS"


def analyze(turns: list[tuple[int, dict]]):
    # --- churn: diff each unit's claim turn-to-turn -----------------------
    prev_claim: dict[int, tuple | None] = {}
    prev_was_walk: dict[int, bool] = {}
    episode_start: dict[int, int] = {}  # unit -> step its current claim episode began
    churn_events = []
    churn_steps_total = 0
    churn_steps_reassigned = 0  # abandoned claim, but new_claim is a different tile
    churn_steps_stranded = 0  # abandoned claim, new_claim is None this turn
    completed_episodes = 0
    completed_episode_lengths = []

    # --- morning commute: first appearance of each (unit, day) -----------
    seen_unit_day: set[tuple[int, int]] = set()
    commute_done_unit_day: set[tuple[int, int]] = set()
    commute_steps_total = 0
    commute_events = 0

    # --- labor supply -------------------------------------------------
    hands_by_hour: dict[tuple[int, int], list[int]] = collections.defaultdict(list)
    idle_pass_turns = 0
    total_unit_turns = 0
    move_turns = 0

    max_units_seen = 0

    for step, rec in turns:
        day, hour = rec["day"], rec["hour"]
        n = unit_count(rec)
        max_units_seen = max(max_units_seen, n)
        hands_by_hour[(day, hour)].append(n)

        for u in range(n):
            action = unit_action(rec, u)
            if action is None:
                continue
            total_unit_turns += 1
            walk = is_walk(action)
            if walk:
                move_turns += 1
            if is_pass(action):
                idle_pass_turns += 1

            cur_claim = unit_claim(rec, u)

            # churn: last turn had a claim AND was walking (not yet arrived),
            # and this turn's claim differs (including disappearing).
            pc = prev_claim.get(u)
            pw = prev_was_walk.get(u, False)
            if pc is not None and pw and cur_claim != pc:
                ep_start = episode_start.get(u, step)
                length = step - ep_start
                churn_steps_total += length
                if cur_claim is None:
                    churn_steps_stranded += length
                else:
                    churn_steps_reassigned += length
                churn_events.append(
                    {
                        "step": step, "day": day, "hour": hour, "unit": u,
                        "abandoned_claim": pc, "episode_len_turns": length,
                        "new_claim": cur_claim, "new_action": action,
                    }
                )

            # episode bookkeeping: a new episode starts whenever the claim
            # changes to a new non-None tile (including from None).
            if cur_claim != pc:
                episode_start[u] = step
            elif cur_claim is not None and pc is not None and cur_claim == pc and not walk:
                # claim held and this turn's action is NOT a walk -> the unit
                # arrived and is executing (or fetching) -- if the action
                # equals... we don't have the task action here, but any
                # non-walk terminal action while holding the same claim we
                # count as the episode "landing" this turn (it may still
                # continue -- e.g. multi-unit fetch -- next episode-start
                # logic simply won't retrigger since cur_claim==pc keeps the
                # same episode_start).
                pass

            # morning commute: first time we see this (unit, day) this game.
            key = (u, day)
            if key not in seen_unit_day:
                seen_unit_day.add(key)
                # walk forward from here (inclusive) until first non-walk,
                # using a lookahead scan over the remaining turns of THIS
                # unit -- done lazily below via a second pass for simplicity
                # and to avoid mutating the main loop's control flow.

            prev_claim[u] = cur_claim
            prev_was_walk[u] = walk

    # Second pass, per unit per day, to measure morning-commute length
    # (first appearance -> first non-walk action that day), and to measure
    # completed-claim-episode lengths (claim held across N turns, closing in
    # a non-walk action -- i.e. NOT a churn) for the "long legs" question.
    by_unit: dict[int, list[tuple[int, dict]]] = collections.defaultdict(list)
    for step, rec in turns:
        n = unit_count(rec)
        for u in range(n):
            by_unit[u].append((step, rec))

    for u, seq in by_unit.items():
        seq.sort(key=lambda kv: kv[0])
        cur_day = None
        commute_active = False
        for step, rec in seq:
            day = rec["day"]
            action = unit_action(rec, u)
            if action is None:
                continue
            if day != cur_day:
                cur_day = day
                commute_active = True
                commute_events += 1
            if commute_active:
                verb = action[0]
                if is_walk(action):
                    commute_steps_total += 1
                elif verb in SHED_LOGISTICS_VERBS:
                    pass  # fetching supplies at the shed is still "leaving the shed", not yet field work
                else:
                    # FIELD_VERBS (arrived, working) or PASS (stopped, idling)
                    # both end the commute window; only FIELD_VERBS count as
                    # a "completed" commute (PASS means it never got a task).
                    commute_active = False
                    commute_done_unit_day.add((u, day))

        # completed (non-churned) claim episodes: reconstruct by scanning
        # claims again for this unit, measuring runs of a constant claim
        # that end in a non-walk action (i.e. executed, not abandoned).
        prev_c = None
        ep_len = 0
        for step, rec in seq:
            action = unit_action(rec, u)
            if action is None:
                continue
            c = unit_claim(rec, u)
            if c is not None and c == prev_c:
                ep_len += 1
                if not is_walk(action):
                    completed_episodes += 1
                    completed_episode_lengths.append(ep_len + 1)
                    ep_len = 0
                    prev_c = None
                    continue
            elif c is not None and c != prev_c:
                ep_len = 0
            prev_c = c

    hands_series = {
        f"{day}:{hour}": (min(v), max(v), sum(v) / len(v))
        for (day, hour), v in sorted(hands_by_hour.items())
    }

    return {
        "total_unit_turns": total_unit_turns,
        "move_turns": move_turns,
        "idle_pass_turns": idle_pass_turns,
        "max_units_seen": max_units_seen,
        "churn": {
            "events": len(churn_events),
            "steps_total": churn_steps_total,
            "steps_reassigned_to_other_tile": churn_steps_reassigned,
            "steps_stranded_no_new_claim": churn_steps_stranded,
            "examples": churn_events[:30],
        },
        "morning_commute": {
            "unit_day_count": commute_events,
            "steps_total": commute_steps_total,
            "mean_steps_per_unit_day": (
                commute_steps_total / commute_events if commute_events else None
            ),
        },
        "completed_episodes": {
            "count": completed_episodes,
            "mean_length_turns": (
                sum(completed_episode_lengths) / len(completed_episode_lengths)
                if completed_episode_lengths else None
            ),
            "max_length_turns": max(completed_episode_lengths) if completed_episode_lengths else None,
            "length_histogram": dict(collections.Counter(completed_episode_lengths)),
        },
        "hands_by_hour": hands_series,
    }


def hire_timing(summary: dict) -> dict:
    hires = summary.get("hire_orders_by_turn", {})
    by_day_hour: dict[str, int] = collections.defaultdict(int)
    by_day: dict[int, int] = collections.defaultdict(int)
    for step_str, n in hires.items():
        step = int(step_str)
        day, hour = step // 24, step % 24
        by_day_hour[f"{day}:{hour}"] += n
        by_day[day] += n
    return {
        "total_hire_orders": sum(hires.values()),
        "by_day": dict(sorted(by_day.items())),
        "by_day_hour": dict(sorted(by_day_hour.items())),
    }


def main():
    turns_path = sys.argv[1]
    summary_path = sys.argv[2]
    out_prefix = sys.argv[3] if len(sys.argv) > 3 else "walk_decomp"

    turns = load_turns(turns_path)
    with open(summary_path) as fh:
        summary = json.load(fh)

    result = analyze(turns)
    result["hire_timing"] = hire_timing(summary)
    result["seed"] = summary.get("seed")

    out_path = f"{out_prefix}.json"
    with open(out_path, "w") as fh:
        json.dump(result, fh, indent=2, default=str)

    c = result["churn"]
    mc = result["morning_commute"]
    ce = result["completed_episodes"]
    ht = result["hire_timing"]
    print(f"seed={result['seed']}")
    print(f"total_unit_turns={result['total_unit_turns']} move_turns={result['move_turns']} "
          f"idle_pass_turns={result['idle_pass_turns']} max_units_seen={result['max_units_seen']}")
    print(f"\nCHURN: {c['events']} events, {c['steps_total']} walk-turns invested-then-abandoned "
          f"({c['steps_total']/result['move_turns']*100:.2f}% of all move-turns); "
          f"of which reassigned-to-another-tile={c['steps_reassigned_to_other_tile']}, "
          f"stranded-with-no-new-claim={c['steps_stranded_no_new_claim']}")
    print(f"MORNING COMMUTE: {mc['unit_day_count']} unit-days, {mc['steps_total']} total commute steps "
          f"(mean {mc['mean_steps_per_unit_day']:.2f} steps/unit-day) "
          f"({mc['steps_total']/result['move_turns']*100:.2f}% of all move-turns)")
    print(f"COMPLETED (non-churned) EPISODES: {ce['count']}, mean length {ce['mean_length_turns']:.2f} turns, "
          f"max {ce['max_length_turns']} turns")
    print(f"\nHIRE ORDERS: {ht['total_hire_orders']} total, by day: {ht['by_day']}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
