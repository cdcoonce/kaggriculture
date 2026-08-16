"""Teeth-check for rerun-ledger: reproduces a verdict, and catches a doctored one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from harness.gate import run_gate, run_money_gate
from harness.ledger import write_ledger, write_money_ledger
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


def _write_sample_money_ledger(tmp_path: Path) -> Path:
    result = run_money_gate(
        "builtin:starter",
        "builtin:pass",
        2,
        5,
        baseline="builtin:starter",
        workers=1,
        extra_config=TINY_CONFIG,
        min_seeds=2,
        candidate_money_floor=0.0,
        opponent_money_floor=0.0,
        run_canary=False,
    )
    return write_money_ledger(
        result,
        tmp_path,
        candidate_commit="abc123",
        timestamp="2026-08-14T09-30-00Z",
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


class TestRerunMoneyLedger:
    def test_legacy_entry_without_baseline_still_reruns_through_run_gate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The 47 committed legacy entries carry no `identity.baseline`; their
        # replay must stay byte-identical to what it was before the money
        # gate existed, and must never touch the two-arm runner.
        import harness.rerun_ledger as rerun_module

        def exploding_run_money_gate(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("a legacy entry must not dispatch to run_money_gate")

        monkeypatch.setattr(rerun_module, "run_money_gate", exploding_run_money_gate)
        path = _write_sample_ledger(tmp_path)

        exit_code = main([str(path)])

        assert exit_code == 0
        assert "PASS" in capsys.readouterr().out

    def test_money_entry_dispatches_to_run_money_gate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_sample_money_ledger(tmp_path)

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code == 0
        assert "PASS" in output
        assert "mean_delta" in output
        assert "baseline=builtin:starter" in output

    def test_doctored_money_field_reports_mismatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # TEETH-CHECK, twin of `test_doctored_verdict_is_reported_as_mismatch`:
        # without `mean_delta` in MONEY_EXACT_FIELDS the new comparison is
        # silently inert and a money ledger reproduces nothing.
        path = _write_sample_money_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["money_verdict"]["mean_delta"] = 12345.0
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code != 0
        assert "MISMATCH" in output
        assert "mean_delta" in output

    def test_a_money_entry_without_a_baseline_is_refused_not_silently_downgraded(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # N4. The dispatch was `if identity.get("baseline") is not None`, so a
        # money entry that lost `identity.baseline` fell through to the
        # SINGLE-ARM replay: it compared wins/losses/ties, ignored the entire
        # money block, printed PASS and exited 0. A green reproduction of a
        # statistic that was never recomputed is worse than a crash.
        import harness.rerun_ledger as rerun_module

        def exploding_run_gate(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("a money entry must never replay as a single-arm gate")

        monkeypatch.setattr(rerun_module, "run_gate", exploding_run_gate)
        path = _write_sample_money_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["identity"]["baseline"]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code == 2
        assert "UNREPLAYABLE" in output
        assert "identity.baseline" in output
        assert "PASS" not in output

    def test_a_money_entry_missing_a_recorded_field_reports_it_instead_of_raising(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # N4, adversarial2/q8(b). `_MONEY_KNOB_DEFAULTS` reads every knob with
        # `.get(name, default)` so "an older entry still replays", but
        # `MONEY_EXACT_FIELDS` read `recorded_money[field]` with no default --
        # and that tuple keeps GAINING fields. An entry written before a field
        # existed raised KeyError from inside the comparison loop, AFTER
        # paying for a full two-arm replay, and printed a traceback instead of
        # a verdict.
        path = _write_sample_money_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        for field in ("n_regressed", "tail_quantile", "blockers"):
            payload["money_verdict"].pop(field, None)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code == 1
        assert "NOT RECORDED" in output
        assert "money.n_regressed" in output
        assert "MISMATCH" in output
        # ...and the fields that ARE recorded still get compared.
        assert "money.mean_delta: recorded=" in output

    def test_a_money_entry_missing_a_close_compared_field_is_also_reported(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _write_sample_money_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["money_verdict"].pop("mde_80")
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        output = capsys.readouterr().out
        assert exit_code == 1
        assert "money.mde_80: recorded=NOT RECORDED" in output

    def test_opponent_digest_mismatch_exits_2_without_playing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import harness.rerun_ledger as rerun_module

        def exploding_run_money_gate(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("no game may be played against the wrong tape")

        monkeypatch.setattr(rerun_module, "run_money_gate", exploding_run_money_gate)
        path = _write_sample_money_ledger(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["identity"]["opponent_digest"] = "sha256:" + "de" * 32
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        exit_code = main([str(path)])

        assert exit_code == 2
        assert "OPPONENT DIGEST MISMATCH" in capsys.readouterr().out
