"""Decompose a money-gate ledger's opponent delta into mechanism buckets.

kaggriculture#82 / the 2026-09-05 hand-mule-load successor registration
(eval/prereg/2026-09-05-hand-mule-load-successor-registration.md): a
redirection criterion that bounds the WHOLE opponent money delta cannot tell
genuine market suppression apart from shop-roster mediator noise
(kaggriculture#82) or a fixed-price affordability cascade. This script drives
``harness.opponent_split.split_ledger`` over one or more committed money-gate
ledgers and prints the per-ledger, per-mechanism decomposition: traded_market
(the only channel the champion's own market behavior prices), untraded_market
(mediator noise), and fixed_price (BUY_SEED/BUY_ANIMAL/HIRE/BUY_LAND
affordability).

The instrument's exactness contract (see harness.opponent_split's module
docstring) means a ledger this script cannot faithfully reproduce -- a
conservation residual, a row that doesn't match, or an aggregate that
disagrees with the ledger's own opponent_mean_delta -- is reported as FAILED
rather than papered over.

Usage:
    uv run python tools/recon-scripts/opponent_revenue_split.py \\
        --ledger eval/gates/2026-...-money.json
    uv run python tools/recon-scripts/opponent_revenue_split.py \\
        --ledger a-money.json --ledger b-money.json --out eval/recon/ --workers 8

Not a gate: prints a report and exits 0 unless the run itself broke. Ledger
the JSON under eval/recon/ if a claim leans on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _digest_mismatch(ledger_path: Path, payload: dict[str, Any]) -> str | None:
    """Copy of ``rerun_ledger``'s opponent-digest precondition.

    A tape or kernel plan is machine-local and uncommitted (harness.gate.
    opponent_digest's docstring): a different file with the same name on this
    machine would replay different money under an identical identity,
    silently, unless this is checked before a single game is played. Returns
    an error line, or ``None`` when the recorded digest is absent (a
    non-tape/kernel opponent) or matches.
    """
    from harness.gate import opponent_digest

    identity = payload["identity"]
    recorded_digest = identity.get("opponent_digest")
    if not recorded_digest:
        return None
    fresh_digest = opponent_digest(identity["opponent"])
    if fresh_digest != recorded_digest:
        return f"{ledger_path}: recorded={recorded_digest!r} fresh={fresh_digest!r}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="opponent-revenue-split",
        description="Decompose a money-gate ledger's opponent delta into mechanism buckets.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        action="append",
        required=True,
        dest="ledgers",
        help="money-gate ledger JSON to decompose (repeatable)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write a JSON report here; a DIRECTORY when --ledger is repeated",
    )
    parser.add_argument("--workers", type=int, default=8, help="per-seed replay parallelism")
    args = parser.parse_args(argv)

    payloads: list[tuple[Path, dict[str, Any]]] = [
        (path, json.loads(path.read_text(encoding="utf-8"))) for path in args.ledgers
    ]

    # Before ANY replay, across every ledger given: a digest mismatch on the
    # third ledger must not be discovered after the first two already burned
    # wall-clock replaying games.
    mismatches = [
        line
        for path, payload in payloads
        for line in (_digest_mismatch(path, payload),)
        if line is not None
    ]
    if mismatches:
        for line in mismatches:
            print(f"OPPONENT DIGEST MISMATCH: {line}")
        return 2

    from harness.opponent_split import split_ledger

    multiple = len(payloads) > 1
    if args.out is not None and multiple:
        args.out.mkdir(parents=True, exist_ok=True)

    failed = False
    for path, payload in payloads:
        print(f"\n=== {path} ===")

        def _progress(index: int, n_seeds: int, _path: Path = path) -> None:
            print(f"  {_path.name}: seed {index + 1}/{n_seeds}", file=sys.stderr)

        try:
            result = split_ledger(payload, progress=_progress, workers=args.workers)
        except (ValueError, NotImplementedError) as exc:
            print(f"  FAILED: {exc}")
            failed = True
            continue

        print(f"  traded_items:         {result.traded_items}")
        print(f"  mean traded_market:   {result.mean_traded_market:14.2f}")
        print(f"  mean untraded_market: {result.mean_untraded_market:14.2f}")
        print(f"  mean fixed_price:     {result.mean_fixed_price:14.2f}")
        print(f"  mean total:           {result.mean_total:14.2f}")
        print(f"  max residual:         {result.max_residual!r}")

        if args.out is not None:
            out_path = (args.out / f"{path.stem}-opponent-split.json") if multiple else args.out
            report = {
                "identity": payload["identity"],
                "ledger_path": str(path),
                "traded_items": result.traded_items,
                "means": {
                    "traded_market": result.mean_traded_market,
                    "untraded_market": result.mean_untraded_market,
                    "fixed_price": result.mean_fixed_price,
                    "total": result.mean_total,
                },
                "max_residual": result.max_residual,
                "per_seed": [
                    {
                        "seed": seed.seed,
                        "traded_market": seed.traded_market,
                        "untraded_market": seed.untraded_market,
                        "fixed_price": seed.fixed_price,
                        "total": seed.total,
                    }
                    for seed in result.seeds
                ],
            }
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"  -> {out_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
