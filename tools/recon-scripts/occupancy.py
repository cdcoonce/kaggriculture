"""Standing-crop occupancy over an episode, for either seat.

Answers the question `strawberry_labor.py` structurally cannot: how much of
the ground is actually carrying a crop, day by day. Its `alive_by_day` counts
STRAWBERRY only, and the shipped champion sets `strawberry_tile_target = 0`,
so on the shipped agent that field is zero on all thirty days.

The measurement logic lives in `harness.occupancy` and is tested
(`packages/harness/tests/test_occupancy.py`) -- including a per-seat teeth
check, because `private` is not broadcast between seats and a census wired to
the wrong one returns a clean, plausible, fictional series.

Read the AGE HISTOGRAM, not just the level. It is the discriminator:
  peaked, peak walking one bin per day -> a synchronized cohort ripening
    together; occupancy MUST oscillate and no dispatch change prevents it
  flat across bins                     -> a true steady state; a falling
    level then means a per-day loss channel, not a cycle

Usage:
    uv run python tools/recon-scripts/occupancy.py --seed 661000
    uv run python tools/recon-scripts/occupancy.py --seed 661000 --both-seats
    uv run python tools/recon-scripts/occupancy.py --candidate zoo:tape-thunder-719
    uv run python tools/recon-scripts/occupancy.py --seed 661000 --json

Not a gate and not a test: prints a report, exits 0 unless the run broke.
Ledger the JSON alongside a gate ledger if a claim leans on it.
"""

import argparse
import json
from dataclasses import asdict


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


def report(days, label, crop):
    print(f"\n=== {label} ===")
    print(f"{'day':>4} {'stand':>6} {'bare':>5} {'seed':>5}  {'by crop':<28} age histogram")
    for day in sorted(days):
        d = days[day]
        crops = " ".join(f"{k}:{v}" for k, v in sorted(d.by_crop.items()))
        ages = " ".join(f"{a}:{c}" for a, c in sorted(d.ages.items()))
        print(f"{day:>4} {d.standing:>6} {d.bare:>5} {d.seeds.get(crop, 0):>5}  {crops:<28} {ages}")

    vals = [days[d].standing for d in sorted(days) if 10 <= d <= 28]
    if vals:
        mean = sum(vals) / len(vals)
        print(
            f"\ndays 10-28: standing min {min(vals)}  max {max(vals)}  "
            f"mean {mean:.1f}  swing {max(vals) - min(vals)}"
        )

    # Peakedness: what share of standing tiles sit in the single largest age
    # bin. A staggered field spreads across ~5 bins (~20% each); a synchronized
    # cohort piles into one.
    shares = []
    for day in sorted(days):
        d = days[day]
        if d.standing >= 10 and d.ages:
            shares.append(max(d.ages.values()) / d.standing)
    if shares:
        print(
            f"largest-age-bin share: mean {100 * sum(shares) / len(shares):.0f}%  "
            f"(a perfectly staggered 5-age field would sit near 20%)"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=661000)
    ap.add_argument("--candidate", default="champion")
    ap.add_argument("--opponent", default="zoo:pass")
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--crop", default="WHEAT", help="which seed pool to show")
    ap.add_argument("--both-seats", action="store_true", help="also census the opponent")
    ap.add_argument(
        "--agent-config",
        default=None,
        help="PolicyConfig overrides as JSON, e.g. '{\"strawberry_tile_target\": 31}'",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    agent_config = json.loads(args.agent_config) if args.agent_config else None

    from harness.occupancy import census

    env = run(args.seed, args.candidate, args.opponent, args.seat, agent_config)
    mine = census(env, seat=args.seat)

    if args.json:
        out = {
            "identity": {
                "seed": args.seed,
                "candidate": args.candidate,
                "opponent": args.opponent,
                "seat": args.seat,
                "agent_config": agent_config or {},
            },
            "candidate": {str(d): asdict(c) for d, c in mine.items()},
        }
        if args.both_seats:
            other = census(env, seat=1 - args.seat)
            out["opponent"] = {str(d): asdict(c) for d, c in other.items()}
        print(json.dumps(out, indent=2, default=str))
        return

    report(
        mine, f"{args.candidate} (seat {args.seat}) vs {args.opponent}, seed {args.seed}", args.crop
    )
    if args.both_seats:
        other = census(env, seat=1 - args.seat)
        report(other, f"{args.opponent} (seat {1 - args.seat})", args.crop)


if __name__ == "__main__":
    main()
