"""Gate-run ledger writer — eval/gates/*.json (eval protocol, issue #4)."""

from __future__ import annotations

import json
from pathlib import Path

from harness.gate import GateResult, run_gate
from harness.ledger import write_ledger

TINY_CONFIG = {"episodeSteps": 48}


def _sample_result(n_seeds: int = 1) -> GateResult:
    return run_gate(
        candidate="builtin:starter",
        opponent="builtin:pass",
        n_seeds=n_seeds,
        seed_base=5,
        workers=1,
        extra_config=TINY_CONFIG,
    )


class TestWriteLedger:
    def test_file_lands_at_expected_path(self, tmp_path: Path) -> None:
        result = _sample_result()
        path = write_ledger(
            result,
            tmp_path,
            candidate_commit="abc123",
            timestamp="2026-08-05T21-14-03Z",
        )
        expected = (
            tmp_path
            / "gates"
            / "2026-08-05T21-14-03Z-builtin_starter-vs-builtin_pass-promotion.json"
        )
        assert path == expected
        assert path.exists()

    def test_json_round_trips_with_required_keys_and_row_count(self, tmp_path: Path) -> None:
        result = _sample_result(n_seeds=2)
        path = write_ledger(
            result,
            tmp_path,
            candidate_commit="abc123",
            timestamp="2026-08-05T21-14-03Z",
        )

        payload = json.loads(path.read_text(encoding="utf-8"))

        assert payload["schema_version"] == 1

        identity = payload["identity"]
        assert identity["candidate"] == "builtin:starter"
        assert identity["candidate_commit"] == "abc123"
        assert identity["opponent"] == "builtin:pass"
        assert identity["gate_type"] == "promotion"
        assert identity["extra_config"] == TINY_CONFIG

        verdict = payload["verdict"]
        assert verdict["n_games"] == 4
        assert verdict["wins"] == 0
        assert verdict["losses"] == 4
        assert verdict["ties"] == 0
        assert verdict["score"] == 0
        assert verdict["rate"] == 0
        assert verdict["ci_lower"] < 0.5
        assert verdict["threshold"] == 0.5
        assert verdict["passed"] is False
        assert verdict["any_candidate_crash"] is False

        seed_manifest = payload["seed_manifest"]
        assert seed_manifest["seed_base"] == 5
        assert seed_manifest["n_seeds"] == 2
        assert seed_manifest["seeds"] == [5, 6]

        assert len(payload["rows"]) == 4
        first_row = payload["rows"][0]
        assert set(first_row) == {
            "seed",
            "candidate_seat",
            "candidate_money",
            "opponent_money",
            "outcome",
            "candidate_crashed",
            "opponent_crashed",
        }
