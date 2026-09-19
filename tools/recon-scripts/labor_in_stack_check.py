"""Registered expression check for the labor-inside-the-stack slice.

Registration: eval/prereg/2026-09-19-labor-inside-the-stack.md. Reads three records over the
same two arms, seeds and build:

- an early-cash ledger  (tools/recon-scripts/early_cash_ledger.py --out): standing tiles;
- a crew probe          (tools/recon-scripts/labor_probe.py --out): hours worked by hour;
- a settled-flow record (tools/recon-scripts/revenue_breakdown.py --out): revenue by item.

In the ledger and the crew probe the FIRST arm is the reference. For this slice that
reference is **S3** (STACK3 verbatim, re-registered under this slice's name), not `shipped`
-- S3 is a replication reference, not the shipped agent, and is not itself scored. The
settled-flow tool's reference arm for this check is likewise S3 (`FLOWS_REFERENCE = "S3"`),
not the tool's own default `shipped`.

Only S3EH1 is scored. The failure this slice is built to detect is a hand that is hired and
then spends its hours on the same marginal wheat labor slice 2 already priced -- so the check
proves the hand is bought, works, and does not deepen collateral damage, before any money
result is trusted. The four criteria were committed with the registration, before any arm
data existed:

- C1 crew rises: S3EH1 mean crew hours (hours 4-20) >= S3's + 0.7.
- C2 hire spend rises: S3EH1 mean HIRE spend minus S3's >= $1,500.
- C3 strawberry holds: S3EH1 mean standing strawberry tiles at end of day 12 >= 14.0, and
  >= 0.85 x S3's same measure (the prereg's "within 15% of S3's").
- C4 no collateral collapse: S3EH1 WHEAT + WOOL + FERTILIZER settled revenue >= 0.95 x S3's.

An arm clears only if all four pass.

Usage:
    uv run python tools/recon-scripts/labor_in_stack_check.py LEDGER.json --crew CREW.json \
        --flows FLOWS.json [--out VERDICT.json]
"""

import argparse
import json
import statistics

ENGINE = "1.32.7"
FLOWS_REFERENCE = "S3"
SEEDS = list(range(887000, 887008))  # 887000..887007 inclusive, 8 seeds
FILL_DAY = 12
CREW_GAIN_MIN = 0.7
HIRE_RISE_MIN = 1500.0
STRAW_FLOOR = 14.0
STRAW_RATIO_MIN = 0.85
COLLATERAL_ITEMS = ("WHEAT", "WOOL", "FERTILIZER")
COLLATERAL_RATIO_MIN = 0.95


def end_of_day(rows, day):
    if day >= len(rows) or rows[day]["day"] != day:
        raise ValueError(f"ledger has no end-of-day row for day {day}")
    return rows[day]


def check(m_arm, m_ref):
    """The four registered criteria for S3EH1 against S3, as [(name, passed, detail)]."""
    out = []

    need1 = m_ref["crew_4_20"] + CREW_GAIN_MIN
    out.append((
        "C1_crew_rise",
        m_arm["crew_4_20"] >= need1,
        f"S3EH1 crew_4_20 {m_arm['crew_4_20']:.2f} vs S3 {m_ref['crew_4_20']:.2f} + "
        f"{CREW_GAIN_MIN:g} = {need1:.2f} (needs >=)",
    ))

    hire_rise = m_arm["hire_spend"] - m_ref["hire_spend"]
    out.append((
        "C2_hire_spend_rise",
        hire_rise >= HIRE_RISE_MIN,
        f"HIRE spend ${m_arm['hire_spend']:,.0f} vs S3 ${m_ref['hire_spend']:,.0f} = "
        f"{hire_rise:+,.0f} (needs >= +${HIRE_RISE_MIN:,.0f})",
    ))

    floor_ok = m_arm["strawberry_d12"] >= STRAW_FLOOR
    ratio_need = STRAW_RATIO_MIN * m_ref["strawberry_d12"]
    ratio_ok = m_arm["strawberry_d12"] >= ratio_need
    out.append((
        "C3_strawberry_holds",
        floor_ok and ratio_ok,
        f"standing strawberry end of day {FILL_DAY} {m_arm['strawberry_d12']:.1f} "
        f"(needs >= {STRAW_FLOOR:g}) and >= {STRAW_RATIO_MIN:g} x S3's "
        f"{m_ref['strawberry_d12']:.1f} = {ratio_need:.2f}",
    ))

    collateral_need = COLLATERAL_RATIO_MIN * m_ref["collateral_total"]
    out.append((
        "C4_no_collateral_collapse",
        m_arm["collateral_total"] >= collateral_need,
        f"{'+'.join(COLLATERAL_ITEMS)} ${m_arm['collateral_total']:,.0f} vs "
        f"{COLLATERAL_RATIO_MIN:g} x S3's ${m_ref['collateral_total']:,.0f} = "
        f"${collateral_need:,.0f} (needs >=)",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="labor-inside-the-stack expression check")
    ap.add_argument("ledger", help="an early_cash_ledger.py --out record")
    ap.add_argument("--crew", required=True, help="a labor_probe.py --out record, same arms and seeds")
    ap.add_argument("--flows", required=True, help="a revenue_breakdown.py --out record, same arms and seeds")
    ap.add_argument("--out", help="write the verdict record here")
    a = ap.parse_args()
    records = {}
    for name, path in (("ledger", a.ledger), ("crew", a.crew), ("flows", a.flows)):
        with open(path) as fh:
            records[name] = json.load(fh)

    led, crw, flo = records["ledger"], records["crew"], records["flows"]
    for name, rec, dirty_key in (("ledger", led, "packages_dirty"), ("crew", crw, "packages_dirty"),
                                 ("flows", flo, "git_dirty_packages")):
        if "identity" not in rec:
            raise SystemExit(f"ABORT: the {name} has no identity block; regenerate it with --out")
        ident = rec["identity"]
        if ident["engine"] != ENGINE:
            raise SystemExit(f"ABORT: the {name} ran on engine {ident['engine']}, not {ENGINE}")
        if ident[dirty_key]:
            raise SystemExit(f"ABORT: the {name} ran on a dirty packages/ tree")
        if sorted(ident["seeds"]) != SEEDS:
            raise SystemExit(f"ABORT: the {name} covers seeds {ident['seeds']}, not the registered {SEEDS}")
    for field in ("git_sha", "engine", "opponent", "arms", "seeds"):
        if led["identity"][field] != crw["identity"][field]:
            raise SystemExit(f"ABORT: the ledger and the crew probe disagree on {field}")
    if led["identity"]["git_sha"] != flo["identity"]["git_sha"]:
        raise SystemExit("ABORT: the ledger and the settled-flow record ran on different builds")

    arms = led["identity"]["arms"]
    ref = next(iter(arms))
    if ref != "S3":
        raise SystemExit(f"ABORT: the ledger's first arm ({ref}) must be S3, the registered reference")
    if "S3EH1" not in arms:
        raise SystemExit("ABORT: the ledger is missing S3EH1")
    if FLOWS_REFERENCE not in flo["means_per_arm"]:
        raise SystemExit(f"ABORT: the settled-flow record has no {FLOWS_REFERENCE!r} arm")
    missing_flows = [arm for arm in arms if arm != ref and arm not in flo["means_per_arm"]]
    if missing_flows:
        raise SystemExit(f"ABORT: the settled-flow record is missing arms {missing_flows}")
    missing_crew = [arm for arm in arms if arm not in crw["summary"]]
    if missing_crew:
        raise SystemExit(f"ABORT: the crew probe is missing arms {missing_crew}")

    seeds = sorted(led["games"])
    fills = {arm: [end_of_day(led["games"][s][arm]["rows"], FILL_DAY)["strawberry"] for s in seeds] for arm in arms}
    flows_side = {arm: flo["means_per_arm"][arm]["seat_0_ours"] for arm in arms}

    measures = {}
    for arm in arms:
        rev = flows_side[arm]["revenue"]
        measures[arm] = {
            "crew_4_20": crw["summary"][arm]["crew_4_20"],
            "hire_spend": flows_side[arm]["fixed_spend"].get("HIRE", 0.0),
            "strawberry_d12": statistics.fmean(fills[arm]),
            "wheat": rev.get("WHEAT", 0.0),
            "wool": rev.get("WOOL", 0.0),
            "fertilizer": rev.get("FERTILIZER", 0.0),
            "collateral_total": sum(rev.get(i, 0.0) for i in COLLATERAL_ITEMS),
        }

    print(
        f"{len(seeds)} seeds {seeds[0]}..{seeds[-1]} vs {led['identity']['opponent']};"
        f" tree {led['identity']['git_sha'][:7]}; reference {ref}"
    )
    print(f"\n{'arm':<9}{'crew':>7}{'HIRE':>10}{'straw@12':>10}{'WHEAT':>10}{'WOOL':>10}"
          f"{'FERT':>10}{'collat':>11}")
    for arm in arms:
        m = measures[arm]
        print(
            f"{arm:<9}{m['crew_4_20']:>7.2f}{m['hire_spend']:>10,.0f}{m['strawberry_d12']:>10.1f}"
            f"{m['wheat']:>10,.0f}{m['wool']:>10,.0f}{m['fertilizer']:>10,.0f}"
            f"{m['collateral_total']:>11,.0f}"
        )

    print("\nEXPRESSION CHECK (registered criteria):")
    verdicts = {}
    for arm in arms:
        if arm == ref:
            continue
        results = check(measures[arm], measures[ref])
        passed = all(ok for _, ok, _ in results)
        verdicts[arm] = {
            "pass": passed,
            "criteria": {name: {"pass": ok, "detail": detail} for name, ok, detail in results},
        }
        print(f"  {arm}: {'PASS' if passed else 'FAIL'}")
        for name, ok, detail in results:
            print(f"    {name}: {'ok' if ok else 'FAIL'} | {detail}")
    passing = [arm for arm, v in verdicts.items() if v["pass"]]
    print(f"\nARMS CLEARED: {passing or 'none'}")

    if a.out:
        with open(a.out, "w") as fh:
            json.dump(
                {
                    "identity": {
                        **led["identity"],
                        "checker": "tools/recon-scripts/labor_in_stack_check.py",
                        "ledger": a.ledger,
                        "crew": a.crew,
                        "flows": a.flows,
                    },
                    "criteria": {
                        "C1_crew_gain_min": CREW_GAIN_MIN,
                        "C2_hire_rise_min": HIRE_RISE_MIN,
                        "C3_strawberry_floor": STRAW_FLOOR,
                        "C3_strawberry_ratio_min": STRAW_RATIO_MIN,
                        "C4_collateral_ratio_min": COLLATERAL_RATIO_MIN,
                        "C4_items": list(COLLATERAL_ITEMS),
                    },
                    "measures": measures,
                    "verdicts": verdicts,
                    "arms_cleared": passing,
                },
                fh,
                indent=1,
            )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
