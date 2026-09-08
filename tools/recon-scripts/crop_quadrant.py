"""Which quadrant is each crop actually growing in, day by day?

Answers the question `occupancy.py` structurally cannot. Its census counts
standing crops per day but `harness.occupancy._board` discards the (x, y)
before anything reaches `DayCensus`, so it can say forty wheat tiles were
standing on day 17 and not say where -- and nothing in the tree recorded when
each quadrant was bought either. A prior investigation quoted per-quadrant
figures that could not be reproduced, because no committed instrument computed
them.

The measurement logic lives in `harness.crop_quadrant` and is tested
(`packages/harness/tests/test_crop_quadrant.py`) -- including two teeth checks,
because both ways of getting this wrong are silent. The engine board is
`tiles[y][x]`, and NW/NE differ only in x while NW/SW differ only in y, so a
transposed read SWAPS NE with SW and still sums correctly. And `farms` is
broadcast onto both seats, so a census wired to the wrong index reports the
opponent's board as yours, just as plausibly.

Read the UNLOCK DAYS next to the tile-days. Tile-days are the area under a
quadrant's occupancy curve, so a quadrant bought on day 12 has at most half
the exposure of NW no matter how well it is farmed -- comparing raw
per-quadrant totals without its unlock day compares a full season against a
part of one.

Usage:
    uv run python tools/recon-scripts/crop_quadrant.py --seeds 661000
    uv run python tools/recon-scripts/crop_quadrant.py --seeds 661000,661001 --both-seats
    uv run python tools/recon-scripts/crop_quadrant.py --candidate zoo:melon-rusher
    uv run python tools/recon-scripts/crop_quadrant.py --seeds 661000 --json
    uv run python tools/recon-scripts/crop_quadrant.py --seeds 661000 --out eval/recon/x.json

Not a gate and not a test: prints a report, exits 0 unless the run broke.
Ledger the JSON under eval/recon/ if a claim leans on it.
"""

import argparse
import json
from dataclasses import asdict

#: The candidate always sits in seat 0 here; `--both-seats` adds the opponent.
#: A per-seat sweep is `harness.promotion_gate`'s job, not recon's.
CANDIDATE_SEAT = 0


def run(seed, candidate, opponent, seat, agent_config=None):
    from harness.episodes import resolve_agent
    from harness.gate import is_tunable
    from kaggle_environments import make

    agents = [None, None]
    # Champion and frozen specs accept a PolicyConfig; handing one to a zoo or
    # builtin member raises rather than being silently ignored. The `else`
    # branch used to swallow the override for every non-tunable spec, which is
    # the opposite of what the comment above it claimed: a `--agent-config` on
    # a frozen arm silently produced DEFAULT-config results, so a configured
    # candidate could be compared against a baseline that never saw the knob.
    if agent_config:
        if not is_tunable(candidate):
            raise ValueError(
                f"--agent-config is only supported for champion and 'frozen:' "
                f"specs, got candidate {candidate!r}"
            )
        agents[seat] = resolve_agent(candidate, agent_config)
    else:
        agents[seat] = resolve_agent(candidate)
    agents[1 - seat] = resolve_agent(opponent)
    env = make("kaggriculture", configuration={"seed": seed})
    env.run(agents)
    return env


def report(censuses, label):
    from harness.crop_quadrant import QUADRANT_ORDER, crop_quadrant_tile_days, unlock_days

    print(f"\n=== {label} ===")

    unlocked_on = unlock_days(censuses)
    owned = "  ".join(f"{q} day {d}" for q, d in unlocked_on.items())
    never = [q for q in QUADRANT_ORDER if q not in unlocked_on]
    print(f"unlocked: {owned}" + (f"   (never bought: {', '.join(never)})" if never else ""))

    print(f"\n{'day':>4}  {'owned':<14} {'bare by quadrant':<24} standing crops by quadrant")
    for day in censuses:
        bare = " ".join(f"{q}:{day.bare_by_quadrant[q]}" for q in day.unlocked)
        crops = "   ".join(
            f"{crop} "
            + "/".join(f"{q}:{per[q]}" for q in QUADRANT_ORDER if q in per)
            for crop, per in sorted(day.by_crop_quadrant.items())
        )
        print(f"{day.day:>4}  {','.join(day.unlocked):<14} {bare:<24} {crops}")

    # Tile-days: one tile standing for one day. The area under the curve, which
    # separates "a lot of tiles briefly" from "a few tiles all season" -- a
    # peak or a mean cannot. Same days 10-28 window `occupancy.report` summarizes.
    tile_days = crop_quadrant_tile_days(censuses)
    if tile_days:
        print("\ndays 10-28 tile-days:")
        for crop, per in sorted(tile_days.items()):
            cells = "  ".join(f"{q}:{per[q]:>5}" for q in QUADRANT_ORDER if q in per)
            print(f"  {crop:<12} {cells}   total {sum(per.values()):>6}")
    return {"unlock_days": unlocked_on, "tile_days_10_28": tile_days}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="661000")
    ap.add_argument("--candidate", default="champion")
    ap.add_argument("--opponent", default="zoo:tape-thunder-719")
    ap.add_argument(
        "--agent-config",
        default=None,
        help="PolicyConfig overrides as JSON, e.g. '{\"max_owned_quadrants\": 4}'",
    )
    ap.add_argument("--both-seats", action="store_true", help="also census the opponent")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON ledger to this path")
    args = ap.parse_args()

    agent_config = json.loads(args.agent_config) if args.agent_config else None

    from harness.crop_quadrant import census

    ledger = []
    for seed in (int(s) for s in args.seeds.split(",")):
        env = run(seed, args.candidate, args.opponent, CANDIDATE_SEAT, agent_config)
        mine = census(env.steps, seat=CANDIDATE_SEAT)
        row = {
            "identity": {
                "seed": seed,
                "candidate": args.candidate,
                "opponent": args.opponent,
                "seat": CANDIDATE_SEAT,
                "agent_config": agent_config or {},
            },
            "candidate": [asdict(c) for c in mine],
        }
        summary = report(
            mine,
            f"{args.candidate} (seat {CANDIDATE_SEAT}) vs {args.opponent}, seed {seed}",
        )
        row["candidate_summary"] = summary
        if args.both_seats:
            other_seat = 1 - CANDIDATE_SEAT
            other = census(env.steps, seat=other_seat)
            row["opponent"] = [asdict(c) for c in other]
            row["opponent_summary"] = report(other, f"{args.opponent} (seat {other_seat})")
        ledger.append(row)

    if args.json:
        print(json.dumps(ledger, indent=2, default=str))
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(ledger, fh, indent=2, default=str)
        print(f"\nledger -> {args.out}")


if __name__ == "__main__":
    main()
