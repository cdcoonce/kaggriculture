"""Rerun a committed ledger entry and compare its verdict against a fresh run.

Versioning/traceability slice of #9. Reads a ledger JSON written by
``harness.ledger.write_ledger``, re-invokes ``harness.gate.run_gate`` with the
recorded identity and seed manifest, and checks that the freshly computed
result reproduces the recorded verdict exactly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from harness.gate import run_gate

COMPARED_FIELDS = ("wins", "losses", "ties", "any_candidate_crash", "passed")


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


if __name__ == "__main__":
    raise SystemExit(main())
