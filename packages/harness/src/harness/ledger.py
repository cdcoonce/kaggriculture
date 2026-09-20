"""Gate-run ledger writer — every run appends a committed JSON record.

Eval protocol, issue #4: identity + verdict + seed manifest + per-game rows,
written under ``eval/gates/``. "A gate run without a ledger entry didn't
happen" (``eval/README.md``).
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Any

from harness.episodes import GameRow
from harness.gate import TUNABLE_SPECS, GateResult, MoneyGateResult

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


_PUBLIC_LEADERS_SUBTREE = "eval/opponents/public-leaders"


def _opponent_source_rev() -> str | None:
    """The committed git tree sha of ``eval/opponents/public-leaders`` at HEAD.

    Mirrors ``harness.money_gate._head_sha``: inherits the process cwd (no
    ``cwd`` argument), swallows a missing/broken git rather than raising, and
    returns ``None`` on failure. Deliberately independent of
    ``harness.public_leaders._panel_root``'s ``KAGG_PUBLIC_LEADERS_ROOT``
    override -- that env var is a test hook for pointing resolution at a
    tmp-dir copy, and this field exists to pin the COMMITTED source, not
    wherever a test happened to point the resolver.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", f"HEAD:{_PUBLIC_LEADERS_SUBTREE}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _opponent_source_dirty() -> bool | None:
    """Whether ``eval/opponents/public-leaders`` has uncommitted changes.

    Includes untracked files under that path. ``None`` when the git call
    itself fails (no repo, no git binary), distinct from ``False`` (clean) --
    see ``_opponent_source_rev`` for the shared inherited-cwd git pattern.
    """
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain", "--", _PUBLIC_LEADERS_SUBTREE],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return bool(completed.stdout.strip())


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

    When ``result.opponent`` starts with ``"public:"``, ``identity`` also
    carries ``opponent_source_rev`` / ``opponent_source_dirty``, pinning the
    committed ``eval/opponents/public-leaders`` source at write time; every
    other opponent leaves both keys absent.
    """
    filename = (
        f"{timestamp}-{_sanitize(result.candidate)}-vs-"
        f"{_sanitize(result.opponent)}-{result.gate_type}.json"
    )
    gates_dir = eval_dir / "gates"
    gates_dir.mkdir(parents=True, exist_ok=True)
    path = gates_dir / filename

    identity: dict[str, Any] = {
        "candidate": result.candidate,
        "candidate_commit": candidate_commit,
        "opponent": result.opponent,
        "gate_type": result.gate_type,
        "extra_config": result.extra_config,
        "agent_config": result.agent_config,
        "baseline": result.baseline,
        "baseline_agent_config": result.baseline_agent_config,
        "opponent_digest": result.opponent_digest,
    }
    if result.opponent.startswith("public:"):
        identity["opponent_source_rev"] = _opponent_source_rev()
        identity["opponent_source_dirty"] = _opponent_source_dirty()

    verdict = result.money_verdict
    payload = {
        "schema_version": SCHEMA_VERSION,
        "identity": identity,
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
            "tail_quantile": verdict.tail_quantile,
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
            "catastrophic_tail_quantile": result.catastrophic_tail_quantile,
            "catastrophic_tail_floor": result.catastrophic_tail_floor,
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


def _is_trivial_opponent(opponent: str) -> bool:
    """Whether ``opponent`` cannot constitute evidence of build strength.

    A ``builtin:*`` opponent is a do-nothing baseline beaten at rate 1.0 by
    any working build; a ``TUNABLE_SPECS`` opponent is a same-codebase
    config-vs-config comparison, not an external result. Both satisfy a
    win-rate promotion gate without saying anything about real strength
    (issue #166).
    """
    return opponent.startswith("builtin:") or opponent in TUNABLE_SPECS


def _passing_champion_entries(gates_dir: Path, candidate_sha: str) -> list[tuple[Path, Any]]:
    """Every ledger entry recording a passing champion promotion at
    ``candidate_sha``, opponent unconstrained, in ``glob`` order. Read-only.

    Factored out of ``find_passing_promotion`` so it and
    ``promotion_refusal_reason`` share one definition of "matches" and
    cannot disagree about it.
    """
    matches = []
    for path in sorted(gates_dir.glob("*.json")):
        entry = json.loads(path.read_text(encoding="utf-8"))
        identity = entry["identity"]
        if (
            identity["gate_type"] == "promotion"
            and identity["candidate"] == "champion"
            and identity["candidate_commit"] == candidate_sha
            and entry["verdict"]["passed"] is True
        ):
            matches.append((path, entry))
    return matches


def find_passing_promotion(gates_dir: Path, candidate_sha: str) -> Path | None:
    """Return the first ledger entry recording a passing champion promotion at
    ``candidate_sha`` against an opponent that can constitute evidence of
    strength, or ``None`` if no such entry exists. Read-only.

    Excludes ``builtin:*`` opponents and any ``TUNABLE_SPECS`` opponent (see
    ``_is_trivial_opponent``) — issue #166. When this returns ``None``, a
    caller should report ``promotion_refusal_reason`` rather than a generic
    message, so an excluded opponent is not silently indistinguishable from
    no entry at all.
    """
    for path, entry in _passing_champion_entries(gates_dir, candidate_sha):
        if not _is_trivial_opponent(entry["identity"]["opponent"]):
            return path
    return None


def promotion_refusal_reason(gates_dir: Path, candidate_sha: str) -> str:
    """The refusal message for ``find_passing_promotion(gates_dir,
    candidate_sha)`` returning ``None``.

    Names every excluded opponent by value when passing entries exist for
    ``candidate_sha`` but were all trivial (issue #166), instead of the
    generic "nothing found" message that made that loophole indistinguishable
    from an honest absence. ``submit.py`` and ``record_submission.py`` both
    call this, so their refusal wording cannot drift apart.
    """
    excluded = sorted(
        {
            entry["identity"]["opponent"]
            for _, entry in _passing_champion_entries(gates_dir, candidate_sha)
            if _is_trivial_opponent(entry["identity"]["opponent"])
        }
    )
    base = f"no passing champion promotion found in {gates_dir} for candidate {candidate_sha}"
    if not excluded:
        return base
    named = "; ".join(
        f"opponent {opponent!r} is excluded: not evidence of strength" for opponent in excluded
    )
    return f"{base} ({named})"
