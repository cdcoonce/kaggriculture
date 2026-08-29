"""How many shop draws can an arm actually disturb? (kaggriculture#82)

#82 records that ``_spawn_weeds`` advances the day's rng only for bare tiles
and the shop is drawn from that same stream, then generalises to "every gate
in ``eval/gates/`` is affected." That generalisation is too strong, and this
prices the real bound per arm.

The draw fires only while the roster is under ``MAX_SHOP_INSTANCES``, so a
default 30-day game has EXACTLY 8 coupled draws (end-of-day 2/5/8/11/14/17/
20/23, none after 23), and the rng is rebuilt daily -- so coupling is
within-day, never cumulative. An arm therefore disturbs only the draws from
the first draw-day on which its COMBINED bare-tile count differs. An arm that
moves occupancy only after end-of-day 23 disturbs none and is genuinely
paired.

Read `coupled/total`. That is the precision penalty on this arm, as a count
rather than a blanket warning. It is a BOUND on disturbed draws, not a count
of changed shops: 8 shop types drawn with replacement means a desynced draw
still lands on the same shop about 1 time in 8.

DO NOT use `roster_identical` to filter seeds into a "truly paired" subset.
The roster is a MEDIATOR -- caused by the treatment -- so conditioning on it
selects the seeds where the arm happened not to express its occupancy effect.
It is printed for description only. The effect can only be averaged over.

The measurement logic lives in ``harness.shop_roster`` and is tested
(``packages/harness/tests/test_shop_roster.py``), including a teeth check on
the end-of-day sampling hour -- an hour-0 read measures a board a full day of
churn away from the one ``_spawn_weeds`` saw.

Usage:
    uv run python tools/recon-scripts/shop_roster_coupling.py --seeds 663302,663303
    uv run python tools/recon-scripts/shop_roster_coupling.py --knob strawberry_tile_target --arms 0,31
    uv run python tools/recon-scripts/shop_roster_coupling.py --seeds 663300 --schedule-only
    uv run python tools/recon-scripts/shop_roster_coupling.py --seeds 663302 --json

Not a gate: prints a report and exits 0 unless the run broke. Ledger the JSON
under eval/recon/ if a claim leans on it.
"""

import argparse
import json


def _run(seed, candidate, opponent, knob, value):
    from kaggle_environments import make

    from harness.episodes import resolve_agent

    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent(candidate, {knob: value}), resolve_agent(opponent)])
    return env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="663302,663303")
    ap.add_argument("--candidate", default="champion")
    ap.add_argument("--opponent", default="builtin:pass")
    ap.add_argument("--knob", default="max_owned_quadrants")
    ap.add_argument("--arms", default="4,3", help="baseline,treatment knob values")
    ap.add_argument(
        "--schedule-only",
        action="store_true",
        help="print the draw schedule for one arm and exit; no comparison",
    )
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from harness.shop_roster import compare_profiles, draw_days, profile

    base, treat = (int(v) for v in args.arms.split(","))
    seeds = [int(s) for s in args.seeds.split(",")]
    ledger = []

    print(f"draw schedule (end-of-day): {draw_days()}  -- {len(draw_days())} draws, none after 23")

    for seed in seeds:
        env_a = _run(seed, args.candidate, args.opponent, args.knob, base)
        prof_a = profile(env_a)

        if args.schedule_only:
            print(f"\n=== seed {seed}  {args.knob}={base} ===")
            for day, bare in sorted(prof_a.bare_by_day.items()):
                print(f"  end-of-day {day:2d}: combined bare {bare:4d}")
            print(f"  final roster: {sorted(prof_a.roster)}")
            ledger.append({"seed": seed, "arm": base, "bare_by_day": prof_a.bare_by_day})
            continue

        prof_b = profile(_run(seed, args.candidate, args.opponent, args.knob, treat))
        result = compare_profiles(prof_a, prof_b)

        print(f"\n=== seed {seed}  ({args.knob} {base} vs {treat}, vs {args.opponent}) ===")
        for day in sorted(prof_a.bare_by_day):
            a_bare, b_bare = prof_a.bare_by_day[day], prof_b.bare_by_day[day]
            flag = "  <-- DIVERGES" if a_bare != b_bare else ""
            print(f"  end-of-day {day:2d}: {a_bare:4d} vs {b_bare:4d}{flag}")
        print(f"  first divergent draw-day: {result.first_divergent_day}")
        print(f"  COUPLED DRAWS: {result.coupled_draws}/{result.total_draws}")
        print(f"  roster {base}: {sorted(prof_a.roster)}")
        print(f"  roster {treat}: {sorted(prof_b.roster)}")
        print(f"  roster identical: {result.roster_identical}  (descriptive only, never a filter)")

        ledger.append(
            {
                "seed": seed,
                "knob": args.knob,
                "arms": [base, treat],
                "opponent": args.opponent,
                "first_divergent_day": result.first_divergent_day,
                "coupled_draws": result.coupled_draws,
                "total_draws": result.total_draws,
                "roster_identical": result.roster_identical,
                "bare_by_day": {str(base): prof_a.bare_by_day, str(treat): prof_b.bare_by_day},
                "roster": {str(base): prof_a.roster, str(treat): prof_b.roster},
            }
        )

    coupled = [row["coupled_draws"] for row in ledger if "coupled_draws" in row]
    if coupled:
        print(
            f"\nacross {len(coupled)} seeds: coupled draws mean "
            f"{sum(coupled) / len(coupled):.1f}/{ledger[0]['total_draws']} "
            f"range [{min(coupled)}, {max(coupled)}]"
        )

    if args.json:
        print(json.dumps(ledger, indent=2, default=str))
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(ledger, fh, indent=2, default=str)
        print(f"\nledger -> {args.out}")


if __name__ == "__main__":
    main()
