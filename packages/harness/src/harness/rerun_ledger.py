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
from harness.ledger import json_float
from harness.stats import CATASTROPHIC_TAIL_FLOOR, CATASTROPHIC_TAIL_QUANTILE

COMPARED_FIELDS = ("wins", "losses", "ties", "any_candidate_crash", "passed")

#: Money fields compared with ``!=``. Episodes are seed-deterministic and
#: sums, medians, Walsh averages and ``sqrt`` are IEEE-exact, so exact
#: equality is correct here and any drift is a real determinism regression.
MONEY_EXACT_FIELDS = (
    "n_seeds",
    "tail_quantile",
    "candidate_mean",
    "baseline_mean",
    "mean_delta",
    "median_delta",
    "sd_delta",
    "stderr",
    "min_delta",
    "n_regressed",
    "hl_shift",
    "hl_skip",
    "hl_exact_alpha",
    "ci_lower_hl",
    "vetoes",
    "blockers",
    "passed",
)

#: ``t_crit`` alone routes through ``lgamma``/``exp``/``log``, which are libm
#: and may differ in the last ulp across platforms; ``ci_lower_mean`` and
#: ``ci_lower`` inherit that. This is exactly why a bootstrap bound was
#: rejected -- it would put a stochastic number into this comparison.
MONEY_CLOSE_FIELDS = ("t_crit", "ci_lower_mean", "ci_lower", "skew_delta", "mde_80")

#: Money fields the ledger encodes as ``null`` when they are not finite (see
#: ``harness.ledger.json_float``); the fresh value gets the same encoding
#: before comparison, or a ``-inf`` bound would read as a mismatch.
MONEY_NULLABLE_FIELDS = frozenset({"ci_lower_mean", "ci_lower", "ci_lower_hl", "mde_80"})

#: Knobs recorded inside the money block, with the defaults that applied
#: before each knob existed, so an older entry still replays. A knob that has
#: been REMOVED (``catastrophic_k``, whose studentized veto no longer exists)
#: simply drops out: an older entry's recorded value is ignored, and the rule
#: change shows up honestly as a ``vetoes`` / ``blockers`` mismatch rather
#: than as a crash.
_MONEY_KNOB_DEFAULTS = {
    "alpha": 0.05,
    "min_seeds": 8,
    "catastrophic_tail_quantile": CATASTROPHIC_TAIL_QUANTILE,
    "catastrophic_tail_floor": CATASTROPHIC_TAIL_FLOOR,
    "candidate_money_floor": 3000.0,
    "opponent_money_floor": 10000.0,
    "degenerate_seed_fraction": 0.25,
}

#: Printed in place of a recorded value the entry does not carry. A field
#: added to ``MONEY_EXACT_FIELDS`` after an entry was written used to raise
#: ``KeyError`` from inside the comparison loop, after paying for a full
#: two-arm replay; a sentinel compares unequal to every fresh value, so the
#: run reports a MISMATCH naming the field instead of a traceback.
NOT_RECORDED = "NOT RECORDED"


def _show(recorded: object) -> str:
    """``repr`` of a recorded value, or the bare sentinel for a missing one."""
    return NOT_RECORDED if recorded is NOT_RECORDED else repr(recorded)


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
    #
    # The dispatch keys on THREE independent signals, any one of which marks
    # the entry as a money run: `identity.gate_type == "money"`, a present
    # `money_verdict` block, or a non-null `identity.baseline`. A single key
    # is not enough -- keying on `identity.baseline` alone meant a money
    # entry that lost that one field fell through to the single-arm path,
    # compared wins/losses/ties, ignored the whole money statistic and
    # printed PASS: a green reproduction of something never recomputed. Any
    # of the three still present is enough to route here, so no money entry
    # can be silently scored as a single-arm win-rate run by losing exactly
    # one field.
    is_money_entry = (
        identity.get("gate_type") == "money"
        or "money_verdict" in payload
        or identity.get("baseline") is not None
    )
    if is_money_entry:
        if identity.get("baseline") is None:
            print(f"rerun-ledger: {args.ledger_path}")
            print(
                "  this entry records a money_verdict but no identity.baseline, "
                "so the second arm cannot be replayed"
            )
            print("UNREPLAYABLE: identity.baseline is missing")
            return 2
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
    from a different tape file is worse than not reproducing it. Also
    returns 2 without playing when the whole `money_verdict` block is
    missing -- dispatch here can now be reached by `gate_type == "money"` or
    a non-null `identity.baseline` alone, neither of which guarantees the
    block survived, and a raw `KeyError` is a worse failure mode than an
    explicit UNREPLAYABLE.
    """
    identity = payload["identity"]
    seed_manifest = payload["seed_manifest"]
    if "money_verdict" not in payload:
        print(f"rerun-ledger: {ledger_path}")
        print("  this entry looks like a money run but carries no money_verdict block")
        print("UNREPLAYABLE: money_verdict is missing")
        return 2
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
        field: json_float(value) if field in MONEY_NULLABLE_FIELDS else value
        for field in MONEY_EXACT_FIELDS + MONEY_CLOSE_FIELDS
        for value in (getattr(verdict, field),)
    }
    fresh_money["vetoes"] = list(verdict.vetoes)
    fresh_money["blockers"] = list(verdict.blockers)

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
        recorded = recorded_money.get(field, NOT_RECORDED)
        matched = recorded is not NOT_RECORDED and fresh_money[field] == recorded
        if not matched:
            mismatched.append(field)
        print(
            f"  money.{field}: recorded={_show(recorded)} "
            f"fresh={fresh_money[field]!r} [{'match' if matched else 'MISMATCH'}]"
        )
    for field in MONEY_CLOSE_FIELDS:
        recorded = recorded_money.get(field, NOT_RECORDED)
        fresh = fresh_money[field]
        if recorded is NOT_RECORDED:
            matched = False
        elif recorded is None or fresh is None:
            matched = recorded is None and fresh is None
        else:
            matched = math.isclose(fresh, recorded, rel_tol=1e-9, abs_tol=1e-6)
        if not matched:
            mismatched.append(field)
        print(
            f"  money.{field}: recorded={_show(recorded)} "
            f"fresh={fresh_money[field]!r} [{'match' if matched else 'MISMATCH'}]"
        )

    if mismatched:
        print(f"MISMATCH: {', '.join(mismatched)}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
