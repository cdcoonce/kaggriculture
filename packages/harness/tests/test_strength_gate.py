"""CI crash-only smoke gate orchestration (issue #29)."""

from __future__ import annotations

import pytest
from harness import strength_gate


def test_opponents_sum_to_100_paired_seeds() -> None:
    assert sum(n for _, n in strength_gate.OPPONENTS) == 100


def test_opponents_match_issue_named_roster_and_split() -> None:
    assert strength_gate.OPPONENTS == [
        ("wheat-spam", 17),
        ("melon-dumper", 17),
        ("melon-rusher", 17),
        ("index-front-runner", 17),
        ("land-rush-hoarder", 16),
        ("fert-market-crasher", 16),
    ]


class _FakeResult:
    def __init__(self, any_candidate_crash: bool) -> None:
        self.any_candidate_crash = any_candidate_crash


class TestMain:
    def test_returns_0_and_prints_pass_when_no_crash(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            calls.append(kwargs)
            return _FakeResult(any_candidate_crash=False)

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        assert strength_gate.main() == 0
        assert "PASS" in capsys.readouterr().out
        assert len(calls) == len(strength_gate.OPPONENTS)
        assert all(call["candidate"] == "champion-unshelled" for call in calls)
        assert all(call["workers"] == 1 for call in calls)
        assert [call["opponent"] for call in calls] == [
            f"zoo:{name}" for name, _ in strength_gate.OPPONENTS
        ]
        assert [call["n_seeds"] for call in calls] == [n for _, n in strength_gate.OPPONENTS]
        seed_bases = [call["seed_base"] for call in calls]
        assert seed_bases == sorted(seed_bases)
        assert len(set(seed_bases)) == len(seed_bases)

    def test_returns_1_and_prints_fail_when_any_opponent_crashes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def fake_run_gate(**kwargs: object) -> _FakeResult:
            return _FakeResult(any_candidate_crash=kwargs["opponent"] == "zoo:melon-rusher")

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        assert strength_gate.main() == 1
        assert "FAIL" in capsys.readouterr().out
