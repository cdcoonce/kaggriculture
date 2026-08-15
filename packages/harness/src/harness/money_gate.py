"""Money-based promotion gate: a paired, two-arm, absolute-money criterion.

Win rate has no gradient at this distance from the frontier. Against the
top-ladder tape opponents the champion goes 0-40 or 0-100 every time, so a
change that moves banked money from $37k to $55k -- most of the way to where
ladder games become winnable -- still reads ``0-40-0``, ``wilson_lb 0.000``,
``passed=False``, exactly like an exact no-op. This gate measures the
candidate's MONEY against a fixed opponent instead: continuous, monotone, and
low-variance once paired by seed (measured 2-60x variance reduction).

Known residual, stated rather than hidden: a candidate faulting on 5-25% of
its turns banks $24k-$28k, which sits INSIDE the healthy per-seed range
[$16,063, $57,108]. No crash flag, no money floor and no win-rate gate can
see it -- ``agent.shell.wrap`` catches ``BaseException`` and returns
``pass_action()``, so ``candidate_crashed`` is structurally unreachable for a
shelled champion. Only the paired money statistic sees it, as a consistent
~-$13,240 per seed. The corollary matters when reading a result: a large
negative ``mean_delta`` with clean flags is the signature of SILENT
BREAKAGE, not of a bad tuning choice.

Invoke as ``uv run python -m harness.money_gate``: the afk sandbox grants
``Bash(uv run python:*)`` and nothing matches a bare console-script literal.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.gate import run_money_gate
from harness.ledger import write_money_ledger

#: A `mean_delta` at or below this is worth a distinct diagnostic: no tuning
#: knob measured so far moves money this far backwards.
SILENT_DEGRADATION_DELTA = -5000.0


def _json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON-object CLI flag, rejecting anything that is not a mapping."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise argparse.ArgumentTypeError(f"not valid JSON: {raw!r} ({error})") from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _head_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="money-gate",
        description="Paired, two-arm absolute-money promotion gate against a fixed opponent.",
    )
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--opponent", required=True)
    parser.add_argument("--n-seeds", type=int, default=64)
    parser.add_argument("--seed-base", type=int, required=True)
    parser.add_argument("--agent-config", type=_json_object, default=None)
    parser.add_argument("--baseline-agent-config", type=_json_object, default=None)
    parser.add_argument("--extra-config", type=_json_object, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--threshold", type=float, default=1000.0)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--min-seeds", type=int, default=8)
    parser.add_argument("--catastrophic-k", type=float, default=5.0)
    parser.add_argument("--candidate-money-floor", type=float, default=3000.0)
    parser.add_argument("--opponent-money-floor", type=float, default=10000.0)
    parser.add_argument("--canary-seeds", type=int, default=6)
    parser.add_argument("--no-canary", action="store_true")
    parser.add_argument("--eval-dir", type=Path, default=Path("eval"))
    parser.add_argument("--candidate-commit", default=None)
    parser.add_argument("--no-ledger", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the money gate and print the pinned stdout contract.

    Exit codes: 0 PASS, 1 FAIL (the bound did not clear, no vetoes), 2
    INVALID (any veto fired). A FAIL is ambiguous on its own -- read
    ``mde_80`` alongside it, because precision is a property of the candidate
    diff, not a constant.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    candidate_commit = args.candidate_commit or _head_sha()
    if candidate_commit is None:
        parser.error("could not resolve HEAD; pass --candidate-commit explicitly")

    result = run_money_gate(
        args.candidate,
        args.opponent,
        args.n_seeds,
        args.seed_base,
        baseline=args.baseline,
        baseline_agent_config=args.baseline_agent_config,
        agent_config=args.agent_config,
        workers=args.workers,
        extra_config=args.extra_config,
        threshold=args.threshold,
        alpha=args.alpha,
        min_seeds=args.min_seeds,
        catastrophic_k=args.catastrophic_k,
        candidate_money_floor=args.candidate_money_floor,
        opponent_money_floor=args.opponent_money_floor,
        canary_seeds=args.canary_seeds,
        run_canary=not args.no_canary,
    )
    verdict = result.money_verdict

    ledger_path: Path | None = None
    if not args.no_ledger:
        ledger_path = write_money_ledger(
            result,
            args.eval_dir,
            candidate_commit=candidate_commit,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"),
        )

    print(
        f"candidate={result.candidate} agent_config={json.dumps(result.agent_config)}", flush=True
    )
    print(
        f"baseline={result.baseline} "
        f"baseline_agent_config={json.dumps(result.baseline_agent_config)}",
        flush=True,
    )
    print(
        f"opponent={result.opponent} digest={result.opponent_digest or 'none'}",
        flush=True,
    )
    print(f"seeds: base={result.seed_base} n={result.n_seeds}", flush=True)
    print(
        f"canary: candidate={'ran' if result.candidate_canary_ran else 'skipped'} "
        f"crashed={result.candidate_canary_crashed} "
        f"baseline={'ran' if result.baseline_canary_ran else 'skipped'} "
        f"crashed={result.baseline_canary_crashed}",
        flush=True,
    )
    print(
        f"money: candidate_mean={verdict.candidate_mean} "
        f"baseline_mean={verdict.baseline_mean} mean_delta={verdict.mean_delta} "
        f"median_delta={verdict.median_delta} sd_delta={verdict.sd_delta}",
        flush=True,
    )
    print(
        f"bounds: t_lower={verdict.ci_lower_mean} hl_lower={verdict.ci_lower_hl} "
        f"ci_lower={verdict.ci_lower} threshold={verdict.threshold} mde_80={verdict.mde_80}",
        flush=True,
    )
    print(
        f"diagnostics: skew={verdict.skew_delta} min_delta={verdict.min_delta} "
        f"opponent_mean_delta={result.opponent_mean_delta} "
        f"min_opponent_money={result.min_opponent_money}",
        flush=True,
    )
    print(f"vetoes: {','.join(verdict.vetoes) if verdict.vetoes else 'none'}", flush=True)
    print(f"ledger: {ledger_path if ledger_path is not None else 'none'}", flush=True)

    if verdict.mean_delta < SILENT_DEGRADATION_DELTA:
        print(
            "note: large negative delta is the signature of silent degradation, "
            "not a bad knob — check the canary and packages/agent/shell.py",
            flush=True,
        )

    if verdict.vetoes:
        print("INVALID", flush=True)
        return 2
    if verdict.passed:
        print("PASS", flush=True)
        return 0
    print("FAIL", flush=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
