"""Where does the owned-quadrant cap's money actually come from?

A money delta cannot tell you whether an arm EARNED more or SPENT less, and
the two have opposite implications for whether a gain is real. This splits
one arm's money delta into its revenue half and its cost half, per item, per
seat, using the engine's own settlement (harness.settlement).

Read the OPPONENT's per-item delta with its unit counts. A tape sells a fixed
schedule, so `units +0` alongside a large revenue delta means the PRICE moved,
not the volume -- and a price move on an item WE never sell cannot have been
caused by us withdrawing supply.

Usage:
    uv run python tools/recon-scripts/land_attribution.py --seeds 663300,663301
    uv run python tools/recon-scripts/land_attribution.py --opponent zoo:tape-thunder-719 --json

Not a gate: prints a report and exits 0 unless the run broke. Ledger the JSON
under eval/recon/ if a claim leans on it.
"""

import argparse
import json
from dataclasses import asdict


def _delta_table(a, b, seat, label):
    """Per-item (arm_b - arm_a) revenue and unit deltas for one seat."""
    items = set(a.revenue.get(seat, {})) | set(b.revenue.get(seat, {}))
    rows = []
    for item in items:
        d_rev = b.revenue.get(seat, {}).get(item, 0.0) - a.revenue.get(seat, {}).get(item, 0.0)
        d_units = b.units.get(seat, {}).get(item, 0) - a.units.get(seat, {}).get(item, 0)
        rows.append((d_rev, item, d_units))
    rows.sort(key=lambda r: -abs(r[0]))
    print(f"  {label}")
    for d_rev, item, d_units in rows:
        if abs(d_rev) >= 1:
            print(f"    {item:<12} {d_rev:+10.0f}   units {d_units:+d}")
    print(f"    {'TOTAL':<12} {sum(r[0] for r in rows):+10.0f}")
    return sum(r[0] for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="663300,663301,663302,663303")
    ap.add_argument("--opponent", default="zoo:tape-barnyard-719")
    ap.add_argument("--candidate", default="champion")
    ap.add_argument("--caps", default="4,3", help="baseline,treatment quadrant caps")
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from harness.settlement import play_with_settlement

    base_cap, treat_cap = (int(c) for c in args.caps.split(","))
    ledger = []

    for seed in (int(s) for s in args.seeds.split(",")):
        runs = {}
        for cap in (base_cap, treat_cap):
            runs[cap] = play_with_settlement(
                seed=seed,
                candidate=args.candidate,
                opponent=args.opponent,
                agent_config={"max_owned_quadrants": cap},
            )
        a, b = runs[base_cap], runs[treat_cap]

        money_delta = b.final_money[0] - a.final_money[0]
        print(f"\n=== seed {seed}  ({args.candidate} vs {args.opponent}) ===")
        for cap in (base_cap, treat_cap):
            r = runs[cap]
            print(
                f"  cap={cap} money={r.final_money} "
                f"settle calls={r.calls} filled={r.filled} rejected={r.rejected}"
            )
            print(
                f"    hire_spend={r.hire_spend(0):.0f} ({r.hires.get(0, 0)} hires)  "
                f"land_spend={r.land_spend(0):.0f}"
            )
            print(f"    shops={r.shops}")
        rev_delta = _delta_table(a, b, 0, f"seat0 ({args.candidate}) revenue delta:")
        opp_delta = _delta_table(a, b, 1, f"seat1 ({args.opponent}) revenue delta:")
        cost_delta = money_delta - rev_delta
        hire_delta = b.hire_spend(0) - a.hire_spend(0)
        land_delta = b.land_spend(0) - a.land_spend(0)
        print(
            f"  SPLIT: money {money_delta:+.0f} = revenue {rev_delta:+.0f} "
            f"+ cost-side {cost_delta:+.0f}"
        )
        print(
            f"    of which MEASURED: hire {-hire_delta:+.0f}  land {-land_delta:+.0f}  "
            f"unattributed {cost_delta + hire_delta + land_delta:+.0f}"
        )
        ledger.append(
            {
                "seed": seed,
                "candidate": args.candidate,
                "opponent": args.opponent,
                "caps": [base_cap, treat_cap],
                "money_delta": money_delta,
                "revenue_delta_seat0": rev_delta,
                "cost_side_delta_seat0": cost_delta,
                "revenue_delta_seat1": opp_delta,
                "hire_spend_delta_seat0": hire_delta,
                "land_spend_delta_seat0": land_delta,
                "hire_spend_by_arm": {
                    str(cap): runs[cap].hire_spend(0) for cap in (base_cap, treat_cap)
                },
                "arms": {str(cap): asdict(runs[cap]) for cap in (base_cap, treat_cap)},
            }
        )

    costs = [row["cost_side_delta_seat0"] for row in ledger]
    revs = [row["revenue_delta_seat0"] for row in ledger]
    if costs:
        print(
            f"\nacross {len(costs)} seeds: cost-side mean {sum(costs) / len(costs):+.0f} "
            f"range [{min(costs):+.0f}, {max(costs):+.0f}] spread {max(costs) - min(costs):.0f}"
        )
        print(
            f"                 revenue mean {sum(revs) / len(revs):+.0f} "
            f"range [{min(revs):+.0f}, {max(revs):+.0f}] spread {max(revs) - min(revs):.0f}"
        )

    if args.json:
        print(json.dumps(ledger, indent=2, default=str))
    if args.out:
        with open(args.out, "w") as fh:
            json.dump(ledger, fh, indent=2, default=str)
        print(f"\nledger -> {args.out}")


if __name__ == "__main__":
    main()
