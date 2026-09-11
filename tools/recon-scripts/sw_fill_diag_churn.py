"""Analyze claim churn: for SW-zone PLANT STRAWBERRY claims recorded in
q1_turns.json, trace whether a claiming unit keeps its tile turn-to-turn
(steady walk -> eventual PLANT) or gets reassigned before arriving, and to
what.
"""
import json
import sys
from collections import Counter, defaultdict

d = json.load(open((sys.argv[1] if len(sys.argv) > 1 else "q1_turns.json")))


def trace(game_key, day_lo, day_hi):
    g = d[game_key]
    zone = set(tuple(t) for t in next(r["strawberry_zone"] for r in g.values() if r.get("strawberry_zone")))
    print(f"\n===== {game_key}  zone size {len(zone)} =====")

    lo, hi = day_lo * 24, day_hi * 24 + 23
    steps = sorted((int(s) for s in g.keys() if lo <= int(s) <= hi))

    # Track, per unit index, the tile it was claimed on in the previous turn.
    prev_claims = {}
    churn_reasons = Counter()
    churn_examples = []
    steady_progress = Counter()  # unit -> consecutive turns held on SAME sw tile
    max_steady = defaultdict(int)
    completed = []

    for step in steps:
        rec = g.get(str(step))
        if rec is None or "claims" not in rec:
            continue
        claims = {int(k): tuple(v) for k, v in rec["claims"].items()}
        sw_claims_now = {u: t for u, t in claims.items() if t in zone}

        # who HAD an sw claim last turn but doesn't hold that SAME tile now?
        for u, prev_tile in prev_claims.items():
            if prev_tile not in zone:
                continue
            now_tile = claims.get(u)
            if now_tile == prev_tile:
                steady_progress[u] += 1
                max_steady[u] = max(max_steady[u], steady_progress[u])
                continue
            # churned away from prev_tile
            steady_progress[u] = 0
            if u == 0:
                action = rec.get("farmer_action")
                pos = rec.get("farmer_pos")
            else:
                hi_ = u - 1
                actions = rec.get("hands_actions", [])
                poss = rec.get("hands_pos", [])
                action = actions[hi_] if hi_ < len(actions) else None
                pos = poss[hi_] if hi_ < len(poss) else None
            reason = "no_claim_this_turn" if now_tile is None else f"reclaimed_other_tile:{now_tile in zone}"
            verb = tuple(action) if action else None
            churn_reasons[(reason, verb[0] if verb else None)] += 1
            if len(churn_examples) < 25:
                churn_examples.append(
                    {
                        "step": step,
                        "day": rec["day"],
                        "hour": rec["hour"],
                        "unit": u,
                        "prev_tile": prev_tile,
                        "now_claim": now_tile,
                        "now_action": action,
                        "now_pos": pos,
                    }
                )

        # detect completions: an sw claim whose actual action this turn was PLANT STRAWBERRY
        for u, t in sw_claims_now.items():
            if u == 0:
                action = rec.get("farmer_action")
            else:
                hi_ = u - 1
                actions = rec.get("hands_actions", [])
                action = actions[hi_] if hi_ < len(actions) else None
            if action == ["PLANT", "STRAWBERRY"]:
                completed.append({"step": step, "day": rec["day"], "hour": rec["hour"], "unit": u, "tile": t})

        prev_claims = claims

    print(f"turns examined: {len(steps)}")
    print(f"unique units that ever held an SW claim: {len({u for u in max_steady})}")
    print(f"max consecutive turns any single unit held the SAME sw tile claim: {max(max_steady.values()) if max_steady else 0}")
    print(f"distribution of max-consecutive-hold per unit: {sorted(max_steady.values(), reverse=True)[:20]}")
    print(f"\nchurn reasons (prev sw-claim -> this turn's outcome), top 15:")
    for (reason, verb), n in churn_reasons.most_common(15):
        print(f"  {n:>4}  prev-claim lost, now: {reason:<28} verb_this_turn={verb}")
    print(f"\ncompleted PLANT STRAWBERRY executions in window: {len(completed)}")
    for c in completed[:20]:
        print(f"  step {c['step']} day {c['day']} hr {c['hour']} unit {c['unit']} tile {c['tile']}")

    print("\nsample churn events (up to 25):")
    for ex in churn_examples:
        print(
            f"  step {ex['step']:>4} d{ex['day']:>2} h{ex['hour']:>2} unit {ex['unit']}"
            f"  had_claim={ex['prev_tile']}  now_claim={ex['now_claim']}"
            f"  now_action={ex['now_action']}  now_pos={ex['now_pos']}"
        )


if __name__ == "__main__":
    trace("sw25_855000", 10, 12)
    trace("nwne10_855000", 10, 11)
