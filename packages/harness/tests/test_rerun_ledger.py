"""Teeth-check for rerun-ledger: reproduces a verdict, and catches a doctored one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness.gate import run_gate
from harness.ledger import write_ledger
from harness.rerun_ledger import main

TINY_CONFIG = {"episodeSteps": 48}


def _write_sample_ledger(tmp_path: Path) -> Path:
    result = run_gate(
        candidate="builtin:starter",
        opponent="builtin:pass",
        n_seeds=1,
        seed_base=5,
        workers=1,
        extra_config=TINY_CONFIG,
    )
    return write_ledger(
        result,
        tmp_path,
        candidate_commit="abc123",
        timestamp="2026-08-05T21-14-03Z",
    )


class TestRerunLedger:
    def test_reproduces_a_committed_ledgers_verdict(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_sample_ledger(tmp_path)

        exit_code = main([str(path)])

        assert exit_code == 0
        assert "PASS" in capsys.readouterr().out

    def test_doctored_verdict_is_reported_as_mismatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_sample_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["verdict"]["passed"] = not payload["verdict"]["passed"]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code != 0
        assert "MISMATCH" in output
