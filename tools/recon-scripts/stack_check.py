"""Registered expression check for the stacked-positives slice.

Registration: eval/prereg/2026-09-12-stack-measured-positives.md. Reads two records over the
same arms, seeds and build:

- an early-cash ledger  (tools/recon-scripts/early_cash_ledger.py --out): standing tiles;
- a settled-flow record (tools/recon-scripts/revenue_breakdown.py --out): revenue by item.

In the ledger the FIRST arm is the shipped reference; the settled-flow tool names its
reference `shipped`.

A stack's check has one job the component checks did not: prove that **both** components
still fire inside the combination. The nullification risk is concrete — slice 0 measured that
strawberry seed spending displaces the early herd the shipped agent would otherwise buy, so
the strawberry component could silently cancel sheep-first. The criteria were committed with
the registration, before any arm data existed:

- C1 strawberry fires: mean standing strawberry tiles at the end of day 12 >= 10, anchored on
  START8_T20's own measured fill of 15.5 in its slice-1 recon.
- C2 herd fires: WOOL settled revenue rises at least 10% against shipped (SHEEP1 alone
  measured +81.3%, so this bar catches nullification rather than grading the effect).
- C3 combined flow: WHEAT + STRAWBERRY + WOOL settled revenue rises at least 10%. The sum is
  the honest form -- a per-item wheat guardrail would veto the strawberry component by
  construction, since a zone displaces wheat.
- C4 degenerate guardrail: the arm still sells at least one unit of every item shipped sells
  at least 10 units of.

Usage:
    uv run python tools/recon-scripts/stack_check.py LEDGER.json --flows BREAKDOWN.json \
        [--out VERDICT.json]
"""

import argparse
import json
import statistics

ENGINE = "1.32.7"
FLOWS_REFERENCE = "shipped"
SEEDS = [857000, 857001, 857002, 857003, 857004, 857005, 857006, 857007]
FILL_DAY = 12
FILL_MIN = 10.0
WOOL_MIN_RISE = 0.10
COMBINED_MIN_RISE = 0.10
COMBINED_ITEMS = ("WHEAT", "STRAWBERRY", "WOOL")
DEGENERATE_UNITS_FLOOR = 10


def end_of_day(rows, day):
    if day >= len(rows) or rows[day]["day"] != day:
        raise ValueError(f"ledger has no end-of-day row for day {day}")
    return rows[day]


def check(fills, arm_side, ref_side):
    """The four registered criteria for one arm, as [(name, passed, detail)]."""
    out = []

    fill = statistics.fmean(fills)
    out.append((
        "C1_strawberry_fires",
        fill >= FILL_MIN,
        f"standing strawberry end of day {FILL_DAY} {fill:.1f} (needs >= {FILL_MIN:g})",
    ))

    got, base = arm_side["revenue"].get("WOOL", 0.0), ref_side["revenue"].get("WOOL", 0.0)
    if base <= 0:
        raise ValueError("shipped earns nothing from WOOL, so a percentage move is undefined")
    rise = (got - base) / base
    out.append((
        "C2_herd_fires",
        rise >= WOOL_MIN_RISE,
        f"WOOL settled revenue ${got:,.0f} vs shipped ${base:,.0f} = {rise:+.1%}"
        f" (needs >= +{WOOL_MIN_RISE:.0%})",
    ))

    got_c = sum(arm_side["revenue"].get(i, 0.0) for i in COMBINED_ITEMS)
    base_c = sum(ref_side["revenue"].get(i, 0.0) for i in COMBINED_ITEMS)
    if base_c <= 0:
        raise ValueError(f"shipped earns nothing from {'+'.join(COMBINED_ITEMS)}")
    rise_c = (got_c - base_c) / base_c
    out.append((
        "C3_combined_flow",
        rise_c >= COMBINED_MIN_RISE,
        f"{'+'.join(COMBINED_ITEMS)} ${got_c:,.0f} vs shipped ${base_c:,.0f} = {rise_c:+.1%}"
        f" (needs >= +{COMBINED_MIN_RISE:.0%})",
    ))

    stopped = [
        item
        for item, base_units in sorted(ref_side["units"].items())
        if base_units >= DEGENERATE_UNITS_FLOOR and arm_side["units"].get(item, 0.0) < 1
    ]
    out.append((
        "C4_degenerate",
        not stopped,
        "no item's sales stopped" if not stopped else f"stopped selling {stopped}",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="stacked-positives expression check")
    ap.add_argument("ledger", help="an early_cash_ledger.py --out record")
    ap.add_argument("--flows", required=True, help="a revenue_breakdown.py --out record, same arms and seeds")
    ap.add_argument("--out", help="write the verdict record here")
    a = ap.parse_args()
    with open(a.ledger) as fh:
        led = json.load(fh)
    with open(a.flows) as fh:
        flo = json.load(fh)

    for name, rec, dirty_key in (("ledger", led, "packages_dirty"), ("flows", flo, "git_dirty_packages")):
        if "identity" not in rec:
            raise SystemExit(f"ABORT: the {name} has no identity block; regenerate it with --out")
        ident = rec["identity"]
        if ident["engine"] != ENGINE:
            raise SystemExit(f"ABORT: the {name} ran on engine {ident['engine']}, not {ENGINE}")
        if ident[dirty_key]:
            raise SystemExit(f"ABORT: the {name} ran on a dirty packages/ tree")
        if sorted(ident["seeds"]) != SEEDS:
            raise SystemExit(f"ABORT: the {name} covers seeds {ident['seeds']}, not the registered {SEEDS}")
    if led["identity"]["git_sha"] != flo["identity"]["git_sha"]:
        raise SystemExit("ABORT: the ledger and the settled-flow record ran on different builds")

    arms = led["identity"]["arms"]
    ref = next(iter(arms))
    if arms[ref] != {}:
        raise SystemExit(f"ABORT: the ledger's first arm ({ref}) must be the shipped reference, config {{}}")
    if FLOWS_REFERENCE not in flo["means_per_arm"]:
        raise SystemExit(f"ABORT: the settled-flow record has no {FLOWS_REFERENCE!r} arm")
    missing = [arm for arm in arms if arm != ref and arm not in flo["means_per_arm"]]
    if missing:
        raise SystemExit(f"ABORT: the settled-flow record is missing arms {missing}")

    seeds = sorted(led["games"])
    fills = {arm: [end_of_day(led["games"][s][arm]["rows"], FILL_DAY)["strawberry"] for s in seeds] for arm in arms}
    ref_side = flo["means_per_arm"][FLOWS_REFERENCE]["seat_0_ours"]

    print(
        f"{len(seeds)} seeds {seeds[0]}..{seeds[-1]} vs {led['identity']['opponent']};"
        f" tree {led['identity']['git_sha'][:7]}; reference {ref}"
    )
    print(f"\n{'arm':<9}{'straw@12':>10}{'WHEAT':>10}{'STRAW':>10}{'WOOL':>10}{'W+S+W':>11}{'recon $':>10}")
    for arm in arms:
        side = ref_side if arm == ref else flo["means_per_arm"][arm]["seat_0_ours"]
        rev = side["revenue"]
        combined = sum(rev.get(i, 0.0) for i in COMBINED_ITEMS)
        print(
            f"{arm:<9}{statistics.fmean(fills[arm]):>10.1f}{rev.get('WHEAT', 0):>10,.0f}"
            f"{rev.get('STRAWBERRY', 0):>10,.0f}{rev.get('WOOL', 0):>10,.0f}"
            f"{combined:>11,.0f}{side['final_money']:>10,.0f}"
        )
    print("(recon $ is one shared baseline against one leader: NOT a result, and not gating)")

    print("\nEXPRESSION CHECK (registered criteria):")
    verdicts = {}
    for arm in arms:
        if arm == ref:
            continue
        results = check(fills[arm], flo["means_per_arm"][arm]["seat_0_ours"], ref_side)
        passed = all(ok for _, ok, _ in results)
        verdicts[arm] = {
            "pass": passed,
            "criteria": {name: {"pass": ok, "detail": detail} for name, ok, detail in results},
        }
        print(f"  {arm}: {'PASS' if passed else 'FAIL'}")
        for name, ok, detail in results:
            print(f"    {name}: {'ok' if ok else 'FAIL'} | {detail}")
    passing = [arm for arm, v in verdicts.items() if v["pass"]]
    print(f"\nARMS CLEARED FOR THE SCREEN: {passing or 'none'}")

    if a.out:
        with open(a.out, "w") as fh:
            json.dump(
                {
                    "identity": {
                        **led["identity"],
                        "checker": "tools/recon-scripts/stack_check.py",
                        "ledger": a.ledger,
                        "settled_flows": a.flows,
                    },
                    "criteria": {
                        "C1_fill_min": FILL_MIN,
                        "C2_wool_min_rise": WOOL_MIN_RISE,
                        "C3_combined_min_rise": COMBINED_MIN_RISE,
                        "C3_items": list(COMBINED_ITEMS),
                        "C4_units_floor": DEGENERATE_UNITS_FLOOR,
                    },
                    "fills": {arm: dict(zip(seeds, fills[arm])) for arm in arms},
                    "verdicts": verdicts,
                    "arms_cleared": passing,
                },
                fh,
                indent=1,
            )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
