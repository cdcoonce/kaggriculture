"""Registered expression check for the never-gated knob screen.

Registration: eval/prereg/2026-09-12-never-gated-knob-screen.md. Reads a settled-flow
record (tools/recon-scripts/revenue_breakdown.py --out) and asks whether each arm actually
expresses its own mechanism before any money gate runs.

Each arm names ONE traded item and ONE direction, from the registration's arm table:

    RW      rescue_water                      WHEAT settled revenue rises
    RW_H10  rescue_water + max_hires_per_turn  WHEAT settled revenue rises
    SHEEP1  animal_buy_order sheep-first       WOOL settled revenue rises

The three bars were committed in the registration before any arm data existed:

- C1 positive mechanism: the arm's targeted item's settled revenue moves in its predicted
  direction by at least 10% against shipped.
- C2 collateral guardrail: no OTHER item's settled revenue falls by more than 25% against
  shipped. Items shipped barely trades (mean revenue under $100) are exempt, since a
  percentage on a near-zero base is noise, not damage.
- C3 degenerate guardrail: the arm still sells at least one unit of every item shipped
  sells at least 10 units of. This is the failure mode a floor or a reserve has -- it can
  silently stop an item's sales rather than reprice them.

An arm failing a bar cannot express its mechanism and is dropped before any run.

Usage:
    uv run python tools/recon-scripts/market_knob_check.py RECORD.json [--out VERDICT.json]
"""

import argparse
import json

ENGINE = "1.32.7"
REFERENCE = "shipped"
SEEDS = [855000, 855001, 855002, 855003, 855004, 855005, 855006, 855007]
DIRECTIONAL_MIN = 0.10  # C1: at least a 10% move in the predicted direction
COLLATERAL_MAX_DROP = 0.25  # C2: no other item's revenue falls more than 25%
COLLATERAL_EXEMPT_BELOW = 100.0  # C2: shipped revenue under this is too small to rate
DEGENERATE_UNITS_FLOOR = 10  # C3: applies to items shipped sells at least this many of

#: arm -> (item, direction). Fixed by the registration's arm table; an arm that is not
#: here has no registered mechanism, and the check refuses rather than inventing one.
TARGETS: dict[str, tuple[str, str]] = {
    "RW": ("WHEAT", "up"),
    "RW_H10": ("WHEAT", "up"),
    "SHEEP1": ("WOOL", "up"),
}


def ours(record, arm):
    return record["means_per_arm"][arm]["seat_0_ours"]


def check(arm, arm_side, ref_side):
    """The three registered bars for one arm, as [(name, passed, detail)]."""
    if arm not in TARGETS:
        raise ValueError(f"{arm} has no registered target item; see the registration's arm table")
    item, direction = TARGETS[arm]
    out = []

    got, base = arm_side["revenue"].get(item, 0.0), ref_side["revenue"].get(item, 0.0)
    if base <= 0:
        raise ValueError(f"{arm}: shipped earns nothing from {item}, so a percentage move is undefined")
    move = (got - base) / base
    ok = move >= DIRECTIONAL_MIN if direction == "up" else move <= -DIRECTIONAL_MIN
    out.append((
        "C1_mechanism",
        ok,
        f"{item} settled revenue ${got:,.0f} vs shipped ${base:,.0f} = {move:+.1%}"
        f" (needs {'+' if direction == 'up' else '-'}{DIRECTIONAL_MIN:.0%} or more {direction})",
    ))

    worst, worst_item = 0.0, None
    for other, base_rev in sorted(ref_side["revenue"].items()):
        if other == item or base_rev < COLLATERAL_EXEMPT_BELOW:
            continue
        drop = (base_rev - arm_side["revenue"].get(other, 0.0)) / base_rev
        if drop > worst:
            worst, worst_item = drop, other
    out.append((
        "C2_collateral",
        worst <= COLLATERAL_MAX_DROP,
        f"worst other-item revenue drop {worst:.1%}"
        + (f" ({worst_item})" if worst_item else " (none)")
        + f" (needs <= {COLLATERAL_MAX_DROP:.0%})",
    ))

    stopped = [
        other
        for other, base_units in sorted(ref_side["units"].items())
        if base_units >= DEGENERATE_UNITS_FLOOR and arm_side["units"].get(other, 0.0) < 1
    ]
    out.append((
        "C3_degenerate",
        not stopped,
        "no item's sales stopped" if not stopped else f"stopped selling {stopped}",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="never-gated knob screen expression check")
    ap.add_argument("record", help="a revenue_breakdown.py --out record")
    ap.add_argument("--out", help="write the verdict record here")
    a = ap.parse_args()
    with open(a.record) as fh:
        record = json.load(fh)

    ident = record["identity"]
    if ident["engine"] != ENGINE:
        raise SystemExit(f"ABORT: engine {ident['engine']}; the check requires {ENGINE}")
    if ident["git_dirty_packages"]:
        raise SystemExit("ABORT: the record ran on a dirty packages/ tree")
    if sorted(ident["seeds"]) != SEEDS:
        raise SystemExit(f"ABORT: the record covers seeds {ident['seeds']}, not the registered {SEEDS}")
    if REFERENCE not in record["means_per_arm"]:
        raise SystemExit(f"ABORT: the record has no {REFERENCE!r} reference arm")
    # The instrument's own reproduction gate: shipped has a recorded mean, and a drift in it
    # means these games are not the games the registration was written against.
    val = record.get("validation", {})
    observed = (val.get("final_money_seat0_means") or {}).get(REFERENCE)
    expected = (val.get("final_money_seat0_expected") or {}).get(REFERENCE)
    if observed is None or expected is None or abs(round(observed) - expected) >= 0.5:
        raise SystemExit(f"ABORT: shipped mean {observed} does not reproduce the recorded {expected}")
    if val.get("conservation_violations"):
        raise SystemExit(f"ABORT: the settlement did not conserve: {val['conservation_violations']}")

    ref_side = ours(record, REFERENCE)
    arms = [a for a in record["means_per_arm"] if a != REFERENCE]
    print(
        f"{len(ident['seeds'])} seeds {min(ident['seeds'])}..{max(ident['seeds'])} vs"
        f" {ident['opponent']}; tree {ident['git_sha'][:7]}; reference {REFERENCE}"
        f" (mean ${ref_side['final_money']:,.0f}, reproduces the recorded {expected:,.0f})"
    )
    print(f"\n{'arm':<9}{'WHEAT':>11}{'WOOL':>10}{'MILK':>10}{'EGG':>9}{'FERT':>10}{'final $':>11}")
    for arm in [REFERENCE, *arms]:
        side = ours(record, arm)
        rev = side["revenue"]
        print(
            f"{arm:<9}{rev.get('WHEAT', 0):>11,.0f}{rev.get('WOOL', 0):>10,.0f}"
            f"{rev.get('MILK', 0):>10,.0f}{rev.get('EGG', 0):>9,.0f}"
            f"{rev.get('FERTILIZER', 0):>10,.0f}{side['final_money']:>11,.0f}"
        )
    print("(final money is recon on one shared baseline: NOT a result, and not gating)")

    print("\nEXPRESSION CHECK (registered criteria):")
    verdicts = {}
    for arm in arms:
        results = check(arm, ours(record, arm), ref_side)
        passed = all(ok for _, ok, _ in results)
        verdicts[arm] = {
            "pass": passed,
            "target": list(TARGETS[arm]),
            "criteria": {name: {"pass": ok, "detail": detail} for name, ok, detail in results},
        }
        print(f"  {arm}: {'PASS' if passed else 'FAIL'}  (target {TARGETS[arm][0]} {TARGETS[arm][1]})")
        for name, ok, detail in results:
            print(f"    {name}: {'ok' if ok else 'FAIL'} | {detail}")
    passing = [a for a, v in verdicts.items() if v["pass"]]
    print(f"\nARMS CLEARED FOR THE SCREEN: {passing or 'none'}")

    if a.out:
        with open(a.out, "w") as fh:
            json.dump(
                {
                    "identity": {**ident, "checker": "tools/recon-scripts/market_knob_check.py", "record": a.record},
                    "criteria": {
                        "C1_directional_min": DIRECTIONAL_MIN,
                        "C2_collateral_max_drop": COLLATERAL_MAX_DROP,
                        "C2_exempt_below": COLLATERAL_EXEMPT_BELOW,
                        "C3_units_floor": DEGENERATE_UNITS_FLOOR,
                        "targets": {k: list(v) for k, v in TARGETS.items()},
                    },
                    "verdicts": verdicts,
                    "arms_cleared": passing,
                },
                fh,
                indent=1,
            )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
