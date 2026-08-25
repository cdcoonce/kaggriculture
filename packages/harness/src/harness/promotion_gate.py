"""Win-rate promotion gate: the criterion the Kaggle upload path actually requires.

``submit.py`` refuses to print an upload command unless
``harness.ledger.find_passing_promotion`` finds a ledger entry with
``gate_type == "promotion"`` at the exact candidate SHA. Only ``run_gate``
writes that type, and until this module existed nothing in the repo drove it
from a command line -- ``harness.money_gate`` hardcodes ``gate_type="money"``
specifically to keep money results OUT of the upload path.

That gap is not cosmetic. It meant the last committed promotion entries were
produced by a script that was never committed, so the gate standing between a
local champion and the ladder could not be reproduced from the repo. Every
gate run since has been a money gate, which by design cannot authorise an
upload.

The two gates answer different questions and both are load-bearing:

* ``money_gate`` asks "does this bank more?" -- continuous, paired, and the
  only thing with a gradient against a top-ladder tape we lose to 64/64.
* this gate asks "does this WIN?" -- which is what the ladder and the
  Bradley-Terry final actually score. Money is the proxy; W/L is the objective.

Promoting on money alone is exactly the mistake the split was built to
prevent, so the upload path deliberately requires this one.

Invoke as ``uv run python -m harness.promotion_gate``: the afk sandbox grants
``Bash(uv run python:*)`` and nothing matches a bare console-script literal.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from harness.gate import run_gate
from harness.ledger import write_ledger


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
        prog="promotion-gate",
        description=(
            "Win-rate promotion gate against a fixed opponent. Writes the "
            'gate_type="promotion" ledger entry that submit.py requires.'
        ),
    )
    parser.add_argument("--candidate", default="champion")
    parser.add_argument("--opponent", required=True)
    parser.add_argument(
        "--n-seeds",
        type=int,
        default=250,
        help="seeds; each is played at BOTH seats, so n_games is twice this",
    )
    parser.add_argument("--seed-base", type=int, required=True)
    parser.add_argument("--agent-config", type=_json_object, default=None)
    parser.add_argument("--extra-config", type=_json_object, default=None)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Wilson lower bound must EXCEED this win rate to pass",
    )
    parser.add_argument("--eval-dir", type=Path, default=Path("eval"))
    parser.add_argument("--candidate-commit", default=None)
    parser.add_argument("--no-ledger", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the win-rate gate and print the pinned stdout contract.

    Exit codes: 0 PASS, 1 FAIL, 2 INVALID. INVALID means the RUN cannot be
    trusted (the candidate crashed in at least one game) and is a different
    question from FAIL -- a crashed agent is frozen for the rest of an episode,
    so its banked money and its losses are both meaningless. Rerun it.

    ``passed`` is ``ci_lower > threshold`` on the Wilson lower bound, never the
    point estimate: at n=500 a 52% point estimate is not distinguishable from a
    coin flip, and the repo has a teeth-check pinning exactly that
    (52%@500 must FAIL).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    candidate_commit = args.candidate_commit or _head_sha()
    if candidate_commit is None:
        parser.error("could not resolve HEAD; pass --candidate-commit explicitly")

    result = run_gate(
        args.candidate,
        args.opponent,
        args.n_seeds,
        args.seed_base,
        workers=args.workers,
        extra_config=args.extra_config,
        gate_type="promotion",
        threshold=args.threshold,
        agent_config=args.agent_config,
    )
    verdict = result.verdict

    ledger_path: Path | None = None
    if not args.no_ledger:
        ledger_path = write_ledger(
            result,
            args.eval_dir,
            candidate_commit=candidate_commit,
            timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ"),
        )

    print(
        f"candidate={result.candidate} agent_config={json.dumps(result.agent_config)}", flush=True
    )
    print(f"commit={candidate_commit}", flush=True)
    # NB: no opponent_digest here. That field is MoneyGateResult-only, because
    # money gates run against machine-local tapes that are never committed and
    # so need a content digest to be citable at all. Promotion-gate opponents
    # are zoo members whose code IS in the repo, pinned by candidate_commit.
    print(
        f"opponent={result.opponent} extra_config={json.dumps(result.extra_config)}",
        flush=True,
    )
    print(f"seeds: base={result.seed_base} n={result.n_seeds}", flush=True)
    print(
        f"record: {result.wins}-{result.losses}-{result.ties} "
        f"n_games={verdict.n_games} rate={verdict.rate} score={verdict.score}",
        flush=True,
    )
    print(
        f"bounds: ci_lower={verdict.ci_lower} threshold={result.threshold}",
        flush=True,
    )
    print(f"crash: any_candidate_crash={result.any_candidate_crash}", flush=True)
    print(f"ledger: {ledger_path if ledger_path is not None else 'none'}", flush=True)

    if result.any_candidate_crash:
        print(
            "INVALID: the candidate crashed in at least one game. A crashed agent "
            "is frozen for the rest of its episode, so neither its record nor its "
            "money means anything. Fix the crash and rerun.",
            flush=True,
        )
        return 2

    print("PASS" if verdict.passed else "FAIL", flush=True)
    return 0 if verdict.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
