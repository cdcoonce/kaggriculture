"""Gate-run ledger writer — every run appends a committed JSON record.

Eval protocol, issue #4: identity + verdict + seed manifest + per-game rows,
written under ``eval/gates/``. "A gate run without a ledger entry didn't
happen" (``eval/README.md``).
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.gate import GateResult

SCHEMA_VERSION = 1


def _sanitize(spec: str) -> str:
    return spec.replace(":", "_")


def write_ledger(
    result: GateResult,
    eval_dir: Path,
    *,
    candidate_commit: str,
    timestamp: str,
) -> Path:
    """Write ``result`` as a JSON ledger entry and return the written path.

    Deterministic and testable: ``timestamp`` is supplied by the caller
    rather than generated here.
    """
    filename = (
        f"{timestamp}-{_sanitize(result.candidate)}-vs-"
        f"{_sanitize(result.opponent)}-{result.gate_type}.json"
    )
    gates_dir = eval_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    path = gates_dir / filename

    payload = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "candidate": result.candidate,
            "candidate_commit": candidate_commit,
            "opponent": result.opponent,
            "gate_type": result.gate_type,
            "extra_config": result.extra_config,
            "agent_config": result.agent_config,
        },
        "verdict": {
            "n_games": result.verdict.n_games,
            "wins": result.wins,
            "losses": result.losses,
            "ties": result.ties,
            "score": result.verdict.score,
            "rate": result.verdict.rate,
            "ci_lower": result.verdict.ci_lower,
            "threshold": result.threshold,
            "passed": result.verdict.passed,
            "any_candidate_crash": result.any_candidate_crash,
        },
        "seed_manifest": {
            "seed_base": result.seed_base,
            "n_seeds": result.n_seeds,
            "seeds": result.seeds,
        },
        "rows": [
            {
                "seed": row.seed,
                "candidate_seat": row.candidate_seat,
                "candidate_money": row.candidate_money,
                "opponent_money": row.opponent_money,
                "outcome": row.outcome,
                "candidate_crashed": row.candidate_crashed,
                "opponent_crashed": row.opponent_crashed,
            }
            for row in result.rows
        ],
    }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def find_passing_promotion(gates_dir: Path, candidate_sha: str) -> Path | None:
    """Return the first ledger entry recording a passing champion promotion at
    ``candidate_sha``, or ``None`` if no such entry exists. Read-only."""
    for path in sorted(gates_dir.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        identity = entry["identity"]
        if (
            identity["gate_type"] == "promotion"
            and identity["candidate"] == "champion"
            and identity["candidate_commit"] == candidate_sha
            and entry["verdict"]["passed"] is True
        ):
            return path
    return None
