"""Registered expression check for the strawberry-cohort slice.

Registration: eval/prereg/2026-09-12-strawberry-cohort-price.md. Reads three records over
the same arms, seeds and build:

- an early-cash ledger   (tools/recon-scripts/early_cash_ledger.py --out): standing tiles;
- a weed-provenance scan (tools/recon-scripts/weed_provenance.py --out): missed-water deaths;
- a settled-flow record  (tools/recon-scripts/revenue_breakdown.py --out): revenue by item.

In the ledger and the scan the FIRST arm is the shipped reference; the settled-flow tool
names its reference `shipped`. The three criteria were committed with the registration,
before any of these records existed:

- C1 cohort exists and survives: mean standing strawberry tiles at the end of day 16 >= 20,
  and >= 0.9 x the day-12 mean. The 20 is anchored on the prior GATED arms (15-22 tiles,
  planted late, dying), and the registration discloses in full that it was chosen knowing
  these arms measure 23.5-25.5 on other seeds. It defines the hypothesis; it decides
  nothing. The money rule decides.
- C2 watering guardrail: mean plant deaths from missed watering <= 1.5 x the reference's,
  by the engine's two-consecutive-unwatered-days rule.
- C3 mechanism-matched collateral guardrail: combined WHEAT + STRAWBERRY settled revenue
  rises at least 10% against shipped. A per-item wheat guardrail would veto this slice by
  construction, since trading wheat land for strawberry land IS the mechanism.

Usage:
    uv run python tools/recon-scripts/cohort_check.py LEDGER.json --weeds SCAN.json \
        --flows BREAKDOWN.json [--out VERDICT.json]
"""

import argparse
import json
import statistics

ENGINE = "1.32.7"
FLOWS_REFERENCE = "shipped"
SEEDS = [856000, 856001, 856002, 856003, 856004, 856005, 856006, 856007]
FILL_DAY = 12
SURVIVAL_DAY = 16
COHORT_MIN = 20.0
SURVIVAL_MIN_RATIO = 0.9
DEATHS_RATIO_MAX = 1.5
COMBINED_MIN_RISE = 0.10
COMBINED_ITEMS = ("WHEAT", "STRAWBERRY")
NEGLECT_CATEGORIES = ("established_unwatered", "fresh_planting_unwatered")


def end_of_day(rows, day):
    if day >= len(rows) or rows[day]["day"] != day:
        raise ValueError(f"ledger has no end-of-day row for day {day}")
    return rows[day]


def measure(rows, scan):
    odd = [c for c in scan["births_by_category"] if c.startswith(("UNEXPECTED", "OTHER"))]
    if odd:
        raise ValueError(f"weed scan has unexplained births {odd}: its classification is not validated here")
    return {
        "fill": end_of_day(rows, FILL_DAY)["strawberry"],
        "survival": end_of_day(rows, SURVIVAL_DAY)["strawberry"],
        "neglect_deaths": sum(scan["births_by_category"].get(c, 0) for c in NEGLECT_CATEGORIES),
    }


def check(seeds, ref_seeds, flows_arm, flows_ref):
    """The three registered criteria for one arm, as [(name, passed, detail)]."""

    def mean(key, population=seeds):
        return statistics.fmean(s[key] for s in population)

    out = []
    fill, late = mean("fill"), mean("survival")
    out.append((
        "C1_cohort",
        late >= COHORT_MIN and fill > 0 and late >= SURVIVAL_MIN_RATIO * fill,
        f"standing day {SURVIVAL_DAY} {late:.1f} (needs >= {COHORT_MIN:g})"
        f" and >= {SURVIVAL_MIN_RATIO} x day-{FILL_DAY} {fill:.1f} = {SURVIVAL_MIN_RATIO * fill:.1f}",
    ))

    deaths, ref_deaths = mean("neglect_deaths"), mean("neglect_deaths", ref_seeds)
    out.append((
        "C2_watering",
        deaths <= DEATHS_RATIO_MAX * ref_deaths,
        f"missed-water deaths {deaths:.1f}/game (needs <= {DEATHS_RATIO_MAX} x {ref_deaths:.1f}"
        f" = {DEATHS_RATIO_MAX * ref_deaths:.1f})",
    ))

    got = sum(flows_arm["revenue"].get(i, 0.0) for i in COMBINED_ITEMS)
    base = sum(flows_ref["revenue"].get(i, 0.0) for i in COMBINED_ITEMS)
    if base <= 0:
        raise ValueError("shipped earns nothing from WHEAT+STRAWBERRY, so a percentage move is undefined")
    rise = (got - base) / base
    out.append((
        "C3_combined_flow",
        rise >= COMBINED_MIN_RISE,
        f"{'+'.join(COMBINED_ITEMS)} settled revenue ${got:,.0f} vs shipped ${base:,.0f}"
        f" = {rise:+.1%} (needs >= +{COMBINED_MIN_RISE:.0%})",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="strawberry-cohort expression check")
    ap.add_argument("ledger", help="an early_cash_ledger.py --out record")
    ap.add_argument("--weeds", required=True, help="a weed_provenance.py --out record, same arms and seeds")
    ap.add_argument("--flows", required=True, help="a revenue_breakdown.py --out record, same arms and seeds")
    ap.add_argument("--out", help="write the verdict record here")
    a = ap.parse_args()
    records = {}
    for name, path in (("ledger", a.ledger), ("weeds", a.weeds), ("flows", a.flows)):
        with open(path) as fh:
            records[name] = json.load(fh)

    led, wee, flo = records["ledger"], records["weeds"], records["flows"]
    for name, rec, dirty_key in (("ledger", led, "packages_dirty"), ("weeds", wee, "packages_dirty"),
                                 ("flows", flo, "git_dirty_packages")):
        ident = rec["identity"]
        if ident["engine"] != ENGINE:
            raise SystemExit(f"ABORT: the {name} ran on engine {ident['engine']}, not {ENGINE}")
        if ident[dirty_key]:
            raise SystemExit(f"ABORT: the {name} ran on a dirty packages/ tree")
        if sorted(ident["seeds"]) != SEEDS:
            raise SystemExit(f"ABORT: the {name} covers seeds {ident['seeds']}, not the registered {SEEDS}")
    for field in ("git_sha", "engine", "opponent", "arms", "seeds"):
        if led["identity"][field] != wee["identity"][field]:
            raise SystemExit(f"ABORT: the ledger and the weed scan disagree on {field}")
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
    measures = {arm: [measure(led["games"][s][arm]["rows"], wee["games"][s][arm]) for s in seeds] for arm in arms}
    flows_ref = flo["means_per_arm"][FLOWS_REFERENCE]["seat_0_ours"]

    print(
        f"{len(seeds)} seeds {seeds[0]}..{seeds[-1]} vs {led['identity']['opponent']};"
        f" tree {led['identity']['git_sha'][:7]}; reference {ref}"
    )
    print(f"\n{'arm':<10}{'@12':>7}{'@16':>7}{'deaths':>8}{'WHEAT':>10}{'STRAW':>10}{'W+S':>11}{'recon $':>10}")
    for arm in arms:
        m = measures[arm]
        side = flows_ref if arm == ref else flo["means_per_arm"][arm]["seat_0_ours"]
        wheat, straw = side["revenue"].get("WHEAT", 0.0), side["revenue"].get("STRAWBERRY", 0.0)
        print(
            f"{arm:<10}{statistics.fmean(s['fill'] for s in m):>7.1f}"
            f"{statistics.fmean(s['survival'] for s in m):>7.1f}"
            f"{statistics.fmean(s['neglect_deaths'] for s in m):>8.1f}"
            f"{wheat:>10,.0f}{straw:>10,.0f}{wheat + straw:>11,.0f}{side['final_money']:>10,.0f}"
        )
    print("(recon $ is one shared baseline against one leader: NOT a result, and not gating)")

    print("\nEXPRESSION CHECK (registered criteria):")
    verdicts = {}
    for arm in arms:
        if arm == ref:
            continue
        results = check(measures[arm], measures[ref], flo["means_per_arm"][arm]["seat_0_ours"], flows_ref)
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
                        "checker": "tools/recon-scripts/cohort_check.py",
                        "ledger": a.ledger,
                        "weed_scan": a.weeds,
                        "settled_flows": a.flows,
                    },
                    "criteria": {
                        "C1_cohort_min": COHORT_MIN,
                        "C1_survival_ratio": SURVIVAL_MIN_RATIO,
                        "C2_deaths_ratio_max": DEATHS_RATIO_MAX,
                        "C3_combined_min_rise": COMBINED_MIN_RISE,
                        "C3_items": list(COMBINED_ITEMS),
                    },
                    "measures": {arm: dict(zip(seeds, measures[arm])) for arm in arms},
                    "verdicts": verdicts,
                    "arms_cleared": passing,
                },
                fh,
                indent=1,
            )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
