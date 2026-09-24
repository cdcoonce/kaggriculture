"""Pool own-bank and margin deltas across leaders for the second-slot screen
(`eval/prereg/2026-09-23-second-slot-screen.md`).

Each arm is measured against three public leaders in independent
`harness.money_gate` ledgers. This script pools those three ledgers per arm
into the two quantities the prereg's decision rule reads:

- **own bank**: `mean_delta`/`stderr` are read straight off each ledger's
  `money_verdict` block (already seat-averaged, one observation per seed).
  Pooled as the simple mean across leaders, pooled se
  `sqrt(sum stderr_i**2) / 3`, one-sided 95% lower bound
  `pooled - 1.645 * pooled_se`, pooled MDE
  `harness.stats.mde_multiplier(n) * pooled_se` (#164).

- **margin**: NOT stored directly. Recomputed per seed from the ledger's
  per-GAME rows. `rows` holds the candidate arm's games (`candidate_money`,
  `opponent_money`); `baseline_rows` holds the baseline arm's games over the
  same seeds, same seat orders. Pairing key is `(seed, candidate_seat)`.
  Per seed and seat: `(cand_own - cand_opp) - (base_own - base_opp)`.
  Averaged over the two seat orders of a seed when both are present (always
  true for a normal `n_games = 2 * n_seeds` run), giving one margin
  observation per seed. Mean/se taken over seeds within a leader, then
  pooled across leaders the same way as own bank, one-sided 95% UPPER bound
  `pooled + 1.645 * pooled_se` (the second-slot screen's CONFIRMED veto reads
  a margin that is confidently *worse*, i.e. an upper bound below $0) AND
  one-sided 95% LOWER bound `pooled - 1.645 * pooled_se` plus MDE
  `harness.stats.mde_multiplier(n) * pooled_margin_se` (added for
  `eval/prereg/2026-09-24-eh1-on-w30-margin.md`, whose rule reads margin's
  LOWER bound instead: CONFIRMED requires it to clear $0). Both bounds are
  computed from the same `pooled_margin`/`pooled_margin_se`; which one a
  given prereg's rule reads is a caller concern, not this script's.

Sanity check (built in, `--check`): the recomputed per-leader own-bank mean
(`mean(cand_own) - mean(base_own)` over the same seed/seat pairing used for
margin) must equal the ledger's `mean_delta`. If it does not, the pairing is
wrong and the margin numbers should not be trusted.

Usage:
    uv run python tools/recon-scripts/second_slot_verdict.py \\
        --group EH1=path/sok.json,path/rayk.json,path/kaito.json \\
        --group RESCUE=... \\
        --check

Recon only, read-only against committed ledgers. Prints a table per group
and, with --out, writes a machine-readable JSON summary.
"""

import argparse
import json
import math
import statistics as stats
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages" / "harness" / "src"))

from harness.stats import mde_multiplier  # noqa: E402

Z_95_ONE_SIDED = 1.645


def _leader_short(opponent: str) -> str:
    # "public:sokolovsky-v12" -> "sokolovsky"
    name = opponent.split(":", 1)[-1]
    return name.split("-")[0]


def _own_bank(ledger: dict) -> dict:
    mv = ledger["money_verdict"]
    return {
        "leader": _leader_short(ledger["identity"]["opponent"]),
        "opponent": ledger["identity"]["opponent"],
        "n_seeds": mv["n_seeds"],
        "mean_delta": mv["mean_delta"],
        "stderr": mv["stderr"],
        "min_delta": mv["min_delta"],
        "vetoes": mv["vetoes"],
        "candidate_degenerate": "candidate_degenerate" in mv["vetoes"],
        "opponent_mean_delta": mv["opponent_mean_delta"],
    }


def _margin_per_seed(ledger: dict) -> dict[int, float]:
    """Paired margin delta per seed, averaged over the two seat orders."""
    by_seed_seat_cand = {}
    for row in ledger["rows"]:
        by_seed_seat_cand[(row["seed"], row["candidate_seat"])] = (
            row["candidate_money"],
            row["opponent_money"],
        )
    by_seed_seat_base = {}
    for row in ledger["baseline_rows"]:
        by_seed_seat_base[(row["seed"], row["candidate_seat"])] = (
            row["candidate_money"],
            row["opponent_money"],
        )

    seeds = sorted({seed for seed, _seat in by_seed_seat_cand})
    per_seed = {}
    per_seed_own = {}
    for seed in seeds:
        seat_margins = []
        seat_owns = []
        for seat in (0, 1):
            key = (seed, seat)
            if key not in by_seed_seat_cand or key not in by_seed_seat_base:
                continue
            cand_own, cand_opp = by_seed_seat_cand[key]
            base_own, base_opp = by_seed_seat_base[key]
            seat_margins.append((cand_own - cand_opp) - (base_own - base_opp))
            seat_owns.append(cand_own - base_own)
        if seat_margins:
            per_seed[seed] = sum(seat_margins) / len(seat_margins)
            per_seed_own[seed] = sum(seat_owns) / len(seat_owns)
    return per_seed, per_seed_own


def _mean_se(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, math.inf
    sd = stats.stdev(values)
    return mean, sd / math.sqrt(n)


def analyze_group(name: str, paths: list[str], check: bool) -> dict:
    ledgers = [json.load(open(p)) for p in paths]
    own_rows = [_own_bank(l) for l in ledgers]

    own_means = [r["mean_delta"] for r in own_rows]
    own_ses = [r["stderr"] for r in own_rows]
    pooled_own = sum(own_means) / len(own_means)
    pooled_own_se = math.sqrt(sum(se**2 for se in own_ses)) / len(own_ses)
    pooled_own_lb = pooled_own - Z_95_ONE_SIDED * pooled_own_se
    n_per_leader = {r["n_seeds"] for r in own_rows}
    assert len(n_per_leader) == 1, f"{name}: leaders at different n_seeds: {n_per_leader}"
    n = n_per_leader.pop()
    pooled_mde = mde_multiplier(n) * pooled_own_se

    margin_rows = []
    for ledger, own_row in zip(ledgers, own_rows):
        per_seed_margin, per_seed_own = _margin_per_seed(ledger)
        margin_mean, margin_se = _mean_se(list(per_seed_margin.values()))
        recomputed_own_mean = sum(per_seed_own.values()) / len(per_seed_own)
        check_ok = math.isclose(recomputed_own_mean, own_row["mean_delta"], rel_tol=1e-6, abs_tol=0.5)
        margin_rows.append(
            {
                "leader": own_row["leader"],
                "margin_mean": margin_mean,
                "margin_se": margin_se,
                "n_seeds_paired": len(per_seed_margin),
                "own_bank_check_recomputed": recomputed_own_mean,
                "own_bank_check_ledger": own_row["mean_delta"],
                "own_bank_check_ok": check_ok,
            }
        )
        if check and not check_ok:
            raise SystemExit(
                f"{name}/{own_row['leader']}: recomputed own-bank mean {recomputed_own_mean} "
                f"!= ledger mean_delta {own_row['mean_delta']} -- pairing is wrong"
            )

    margin_means = [r["margin_mean"] for r in margin_rows]
    margin_ses = [r["margin_se"] for r in margin_rows]
    pooled_margin = sum(margin_means) / len(margin_means)
    pooled_margin_se = math.sqrt(sum(se**2 for se in margin_ses)) / len(margin_ses)
    pooled_margin_ub = pooled_margin + Z_95_ONE_SIDED * pooled_margin_se
    pooled_margin_lb = pooled_margin - Z_95_ONE_SIDED * pooled_margin_se
    pooled_margin_mde = mde_multiplier(n) * pooled_margin_se

    any_vetoes = [v for r in own_rows for v in r["vetoes"]]
    any_candidate_degenerate = any(r["candidate_degenerate"] for r in own_rows)
    min_leader_delta = min(own_means)

    result = {
        "arm": name,
        "n_seeds": n,
        "own_bank": own_rows,
        "pooled_own_delta": pooled_own,
        "pooled_own_se": pooled_own_se,
        "pooled_own_lb95": pooled_own_lb,
        "pooled_mde_80": pooled_mde,
        "min_leader_own_delta": min_leader_delta,
        "margin": margin_rows,
        "pooled_margin_delta": pooled_margin,
        "pooled_margin_se": pooled_margin_se,
        "pooled_margin_ub95": pooled_margin_ub,
        "pooled_margin_lb95": pooled_margin_lb,
        "pooled_margin_mde_80": pooled_margin_mde,
        "any_vetoes": any_vetoes,
        "any_candidate_degenerate": any_candidate_degenerate,
    }
    return result


def print_table(result: dict) -> None:
    name = result["arm"]
    print(f"\n=== {name}  (n={result['n_seeds']}/leader) ===")
    print(f"{'leader':<12}{'own Δ':>12}{'se':>10}{'margin Δ':>12}{'se':>10}")
    margin_by_leader = {m["leader"]: m for m in result["margin"]}
    for r in result["own_bank"]:
        m = margin_by_leader[r["leader"]]
        print(
            f"{r['leader']:<12}{r['mean_delta']:>12,.0f}{r['stderr']:>10,.0f}"
            f"{m['margin_mean']:>12,.0f}{m['margin_se']:>10,.0f}"
        )
    print(
        f"{'pooled':<12}{result['pooled_own_delta']:>12,.0f}{result['pooled_own_se']:>10,.0f}"
        f"{result['pooled_margin_delta']:>12,.0f}{result['pooled_margin_se']:>10,.0f}"
    )
    print(f"  own-bank one-sided 95% LB: {result['pooled_own_lb95']:,.0f}")
    print(f"  own-bank pooled mde_80:    {result['pooled_mde_80']:,.0f}")
    print(f"  margin one-sided 95% UB:   {result['pooled_margin_ub95']:,.0f}")
    print(f"  margin one-sided 95% LB:   {result['pooled_margin_lb95']:,.0f}")
    print(f"  margin pooled mde_80:      {result['pooled_margin_mde_80']:,.0f}")
    print(f"  min leader own Δ:          {result['min_leader_own_delta']:,.0f}")
    print(f"  vetoes across leaders:     {result['any_vetoes']}")
    print(f"  candidate_degenerate:      {result['any_candidate_degenerate']}")
    for m in result["margin"]:
        flag = "" if m["own_bank_check_ok"] else "  <-- MISMATCH"
        print(
            f"    [{m['leader']}] pairing check: recomputed {m['own_bank_check_recomputed']:,.1f} "
            f"vs ledger {m['own_bank_check_ledger']:,.1f} ({m['n_seeds_paired']} seeds paired){flag}"
        )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--group",
        action="append",
        default=[],
        required=True,
        help="NAME=path1.json,path2.json,path3.json (one money-gate ledger per leader)",
    )
    ap.add_argument("--check", action="store_true", help="raise if the pairing sanity check fails")
    ap.add_argument("--out", default=None, help="write machine-readable JSON summary here")
    args = ap.parse_args()

    results = []
    for spec in args.group:
        name, _, rest = spec.partition("=")
        paths = rest.split(",")
        result = analyze_group(name, paths, args.check)
        print_table(result)
        results.append(result)

    if args.out:
        with open(args.out, "w") as fh:
            json.dump(results, fh, indent=2, default=str)
        print(f"\nledger -> {args.out}")


if __name__ == "__main__":
    main()
