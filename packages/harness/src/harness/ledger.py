"""Gate-run ledger writer — every run appends a committed JSON record.

Eval protocol, issue #4: identity + verdict + seed manifest + per-game rows,
written under ``eval/gates/``. "A gate run without a ledger entry didn't
happen" (``eval/README.md``).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from harness.episodes import GameRow
from harness.gate import GateResult, MoneyGateResult

SCHEMA_VERSION = 1


def json_float(value: float) -> float | None:
    """``value``, or ``None`` when it is not finite.

    ``json.dumps`` writes ``Infinity`` / ``-Infinity`` / ``NaN`` for
    non-finite floats. Those are a Python extension, NOT JSON: RFC 8259 has
    no such literals, so any conforming reader rejects the file. The money
    verdict emits ``-inf`` bounds whenever ``too_few_seeds`` fires, which is
    exactly the run most worth recording, so the ledger has to encode them.
    ``null`` is the encoding: it round-trips through ``json.loads`` on every
    parser and reads as "no bound", which is what ``-inf`` meant.
    """
    return value if math.isfinite(value) else None


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


def _row_payload(row: GameRow) -> dict[str, object]:
    return {
        "seed": row.seed,
        "candidate_seat": row.candidate_seat,
        "candidate_money": row.candidate_money,
        "opponent_money": row.opponent_money,
        "outcome": row.outcome,
        "candidate_crashed": row.candidate_crashed,
        "opponent_crashed": row.opponent_crashed,
    }


def write_money_ledger(
    result: MoneyGateResult,
    eval_dir: Path,
    *,
    candidate_commit: str,
    timestamp: str,
) -> Path:
    """Write a paired money-gate ``result`` as a JSON ledger entry.

    A SUPERSET of the standard shape, deliberately: ``find_passing_promotion``
    hard-indexes ``identity.gate_type`` / ``candidate`` / ``candidate_commit``
    and ``verdict.passed`` across *every* ``*.json`` in the directory, and
    ``rerun_ledger`` hard-indexes ``identity.extra_config`` and
    ``verdict.threshold``. Keeping those blocks intact keeps the corpus
    homogeneous; the money statistic lives in its own top-level block.

    ``verdict`` is the CANDIDATE arm's WIN-RATE verdict, unchanged in shape
    and meaning. The money PASS/FAIL is ``money_verdict.passed`` and nothing
    else. ``SCHEMA_VERSION`` stays 1: the change is purely additive, exactly
    as ``identity.agent_config`` was.
    """
    filename = (
        f"{timestamp}-{_sanitize(result.candidate)}-vs-"
        f"{_sanitize(result.opponent)}-{result.gate_type}.json"
    )
    gates_dir = eval_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    path = gates_dir / filename

    verdict = result.money_verdict
    payload = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "candidate": result.candidate,
            "candidate_commit": candidate_commit,
            "opponent": result.opponent,
            "gate_type": result.gate_type,
            "extra_config": result.extra_config,
            "agent_config": result.agent_config,
            "baseline": result.baseline,
            "baseline_agent_config": result.baseline_agent_config,
            "opponent_digest": result.opponent_digest,
        },
        "verdict": {
            "n_games": result.candidate_result.verdict.n_games,
            "wins": result.candidate_result.wins,
            "losses": result.candidate_result.losses,
            "ties": result.candidate_result.ties,
            "score": result.candidate_result.verdict.score,
            "rate": result.candidate_result.verdict.rate,
            "ci_lower": result.candidate_result.verdict.ci_lower,
            "threshold": result.candidate_result.threshold,
            "passed": result.candidate_result.verdict.passed,
            "any_candidate_crash": result.candidate_result.any_candidate_crash,
        },
        "money_verdict": {
            "n_seeds": verdict.n_seeds,
            "alpha": verdict.alpha,
            "threshold": verdict.threshold,
            "candidate_mean": verdict.candidate_mean,
            "baseline_mean": verdict.baseline_mean,
            "mean_delta": verdict.mean_delta,
            "median_delta": verdict.median_delta,
            "sd_delta": verdict.sd_delta,
            "stderr": verdict.stderr,
            "skew_delta": verdict.skew_delta,
            "min_delta": verdict.min_delta,
            "n_regressed": verdict.n_regressed,
            "df": verdict.df,
            "t_crit": verdict.t_crit,
            "ci_lower_mean": json_float(verdict.ci_lower_mean),
            "hl_shift": verdict.hl_shift,
            "hl_skip": verdict.hl_skip,
            "hl_exact_alpha": verdict.hl_exact_alpha,
            "ci_lower_hl": json_float(verdict.ci_lower_hl),
            "ci_lower": json_float(verdict.ci_lower),
            "mde_80": json_float(verdict.mde_80),
            "vetoes": list(verdict.vetoes),
            "blockers": list(verdict.blockers),
            "passed": verdict.passed,
            "opponent_mean_delta": result.opponent_mean_delta,
            "min_opponent_money": result.min_opponent_money,
            "candidate_canary_ran": result.candidate_canary_ran,
            "candidate_canary_crashed": result.candidate_canary_crashed,
            "baseline_canary_ran": result.baseline_canary_ran,
            "baseline_canary_crashed": result.baseline_canary_crashed,
            "min_seeds": result.min_seeds,
            "catastrophic_k": result.catastrophic_k,
            "candidate_money_floor": result.candidate_money_floor,
            "opponent_money_floor": result.opponent_money_floor,
            "degenerate_seed_fraction": result.degenerate_seed_fraction,
        },
        "seed_manifest": {
            "seed_base": result.seed_base,
            "n_seeds": result.n_seeds,
            "seeds": result.seeds,
        },
        "per_seed": [
            {
                "seed": entry.seed,
                "candidate_money": entry.candidate_money,
                "baseline_money": entry.baseline_money,
                "delta": entry.delta,
            }
            for entry in result.per_seed
        ],
        "rows": [_row_payload(row) for row in result.candidate_result.rows],
        "baseline_rows": [_row_payload(row) for row in result.baseline_result.rows],
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
