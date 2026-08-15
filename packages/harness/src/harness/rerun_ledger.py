"""Rerun a committed ledger entry and compare its verdict against a fresh run.

Versioning/traceability slice of #9. Reads a ledger JSON written by
``harness.ledger.write_ledger``, re-invokes ``harness.gate.run_gate`` with the
recorded identity and seed manifest, and checks that the freshly computed
result reproduces the recorded verdict exactly.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from harness.gate import opponent_digest, run_gate, run_money_gate

COMPARED_FIELDS = ("wins", "losses", "ties", "any_candidate_crash", "passed")

#: Money fields compared with ``!=``. Episodes are seed-deterministic and
#: sums, medians, Walsh averages and ``sqrt`` are IEEE-exact, so exact
#: equality is correct here and any drift is a real determinism regression.
MONEY_EXACT_FIELDS = (
    "n_seeds",
    "candidate_mean",
    "baseline_mean",
    "mean_delta",
    "median_delta",
    "sd_delta",
    "stderr",
    "min_delta",
    "hl_shift",
    "hl_skip",
    "hl_exact_alpha",
    "ci_lower_hl",
    "mde_80",
    "vetoes",
    "passed",
)

#: ``t_crit`` alone routes through ``lgamma``/``exp``/``log``, which are libm
#: and may differ in the last ulp across platforms; ``ci_lower_mean`` and
#: ``ci_lower`` inherit that. This is exactly why a bootstrap bound was
#: rejected -- it would put a stochastic number into this comparison.
MONEY_CLOSE_FIELDS = ("t_crit", "ci_lower_mean", "ci_lower", "skew_delta")

#: Knobs recorded inside the money block, with the defaults that applied
#: before each knob existed, so an older entry still replays.
_MONEY_KNOB_DEFAULTS = {
    "alpha": 0.05,
    "min_seeds": 8,
    "catastrophic_k": 5.0,
    "candidate_money_floor": 3000.0,
    "opponent_money_floor": 10000.0,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rerun-ledger",
        description="Reproduce a committed ledger's verdict and check it against the recorded one.",
    )
    parser.add_argument("ledger_path", type=Path, help="Path to a committed ledger JSON file")
    args = parser.parse_args(argv)

    payload = json.loads(args.ledger_path.read_text(encoding="utf-8"))
    identity = payload["identity"]
    recorded_verdict = payload["verdict"]
    seed_manifest = payload["seed_manifest"]

    # A money entry records TWO arms; a single `run_gate` call cannot
    # reproduce it, so the money block has to dispatch rather than bolt extra
    # fields onto a comparison that was never computed.
    if identity.get("baseline") is not None:
        return _rerun_money(args.ledger_path, payload)

    result = run_gate(
        identity["candidate"],
        identity["opponent"],
        seed_manifest["n_seeds"],
        seed_manifest["seed_base"],
        extra_config=identity["extra_config"],
        gate_type=identity["gate_type"],
        threshold=recorded_verdict["threshold"],
        agent_config=identity.get("agent_config"),
    )

    fresh = {
        "wins": result.wins,
        "losses": result.losses,
        "ties": result.ties,
        "any_candidate_crash": result.any_candidate_crash,
        "passed": result.verdict.passed,
    }
    recorded = {field: recorded_verdict[field] for field in COMPARED_FIELDS}

    print(f"rerun-ledger: {args.ledger_path}")
    print(
        f"  candidate={identity['candidate']} opponent={identity['opponent']} "
        f"gate_type={identity['gate_type']}"
    )

    mismatched = []
    for field in COMPARED_FIELDS:
        if fresh[field] != recorded[field]:
            mismatched.append(field)
        status = "match" if fresh[field] == recorded[field] else "MISMATCH"
        print(f"  {field}: recorded={recorded[field]!r} fresh={fresh[field]!r} [{status}]")

    if mismatched:
        print(f"MISMATCH: {', '.join(mismatched)}")
        return 1

    print("PASS")
    return 0


def _rerun_money(ledger_path: Path, payload: dict[str, Any]) -> int:
    """Replay a two-arm money entry and compare its money verdict.

    Returns 2 without playing a single game when the opponent tape on this
    machine is not the one the entry was measured against: reproducing money
    from a different tape file is worse than not reproducing it.
    """
    identity = payload["identity"]
    seed_manifest = payload["seed_manifest"]
    recorded_money = payload["money_verdict"]
    knob = {
        name: recorded_money.get(name, default) for name, default in _MONEY_KNOB_DEFAULTS.items()
    }

    print(f"rerun-ledger: {ledger_path}")
    print(
        f"  candidate={identity['candidate']} baseline={identity['baseline']} "
        f"opponent={identity['opponent']} gate_type={identity['gate_type']}"
    )

    recorded_digest = identity.get("opponent_digest")
    if recorded_digest:
        fresh_digest = opponent_digest(identity["opponent"])
        if fresh_digest != recorded_digest:
            print(f"  opponent_digest: recorded={recorded_digest!r} fresh={fresh_digest!r}")
            print("OPPONENT DIGEST MISMATCH")
            return 2

    result = run_money_gate(
        identity["candidate"],
        identity["opponent"],
        seed_manifest["n_seeds"],
        seed_manifest["seed_base"],
        baseline=identity["baseline"],
        baseline_agent_config=identity.get("baseline_agent_config"),
        agent_config=identity.get("agent_config"),
        extra_config=identity["extra_config"],
        gate_type=identity["gate_type"],
        threshold=recorded_money["threshold"],
        # The canary is a precondition, not a recorded measurement, and
        # re-running it doubles the wall clock for nothing.
        run_canary=False,
        **knob,
    )

    verdict = result.money_verdict
    fresh_win_rate = {
        "wins": result.candidate_result.wins,
        "losses": result.candidate_result.losses,
        "ties": result.candidate_result.ties,
        "any_candidate_crash": result.candidate_result.any_candidate_crash,
        "passed": result.candidate_result.verdict.passed,
    }
    fresh_money: dict[str, Any] = {
        field: getattr(verdict, field) for field in MONEY_EXACT_FIELDS + MONEY_CLOSE_FIELDS
    }
    fresh_money["vetoes"] = list(verdict.vetoes)

    mismatched = []
    for field in COMPARED_FIELDS:
        recorded = payload["verdict"][field]
        matched = fresh_win_rate[field] == recorded
        if not matched:
            mismatched.append(field)
        print(
            f"  {field}: recorded={recorded!r} fresh={fresh_win_rate[field]!r} "
            f"[{'match' if matched else 'MISMATCH'}]"
        )
    for field in MONEY_EXACT_FIELDS:
        recorded = recorded_money[field]
        matched = fresh_money[field] == recorded
        if not matched:
            mismatched.append(field)
        print(
            f"  money.{field}: recorded={recorded!r} fresh={fresh_money[field]!r} "
            f"[{'match' if matched else 'MISMATCH'}]"
        )
    for field in MONEY_CLOSE_FIELDS:
        recorded = recorded_money[field]
        matched = math.isclose(fresh_money[field], recorded, rel_tol=1e-9, abs_tol=1e-6)
        if not matched:
            mismatched.append(field)
        print(
            f"  money.{field}: recorded={recorded!r} fresh={fresh_money[field]!r} "
            f"[{'match' if matched else 'MISMATCH'}]"
        )

    if mismatched:
        print(f"MISMATCH: {', '.join(mismatched)}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
