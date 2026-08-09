"""Actions CI crash-only smoke check orchestration (issue #29)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from harness import strength_gate
from harness.zoo import SCRIPTED


@dataclass
class _FakeResult:
    any_candidate_crash: bool


class TestMain:
    def test_calls_run_gate_once_per_scripted_member_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            calls.append(kwargs)
            return _FakeResult(any_candidate_crash=False)

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        exit_code = strength_gate.main()

        assert exit_code == 0
        assert [c["opponent"] for c in calls] == [f"zoo:{name}" for name in SCRIPTED]
        assert all(c["candidate"] == "champion-unshelled" for c in calls)
        assert all(c["workers"] == 1 for c in calls)

    def test_seed_split_is_17_17_17_17_16_16_totaling_100(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[dict[str, object]] = []

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            calls.append(kwargs)
            return _FakeResult(any_candidate_crash=False)

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        strength_gate.main()

        n_seeds = [c["n_seeds"] for c in calls]
        assert n_seeds == [17, 17, 17, 17, 16, 16]
        assert sum(n_seeds) == 100

    def test_seed_bases_are_non_overlapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[dict[str, object]] = []

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            calls.append(kwargs)
            return _FakeResult(any_candidate_crash=False)

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        strength_gate.main()

        seen: set[int] = set()
        for call in calls:
            seed_base = int(call["seed_base"])  # type: ignore[arg-type]
            n_seeds = int(call["n_seeds"])  # type: ignore[arg-type]
            this_range = set(range(seed_base, seed_base + n_seeds))
            assert not (seen & this_range)
            seen |= this_range

    def test_returns_zero_and_prints_pass_when_no_crash(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            strength_gate,
            "run_gate",
            lambda **kwargs: _FakeResult(any_candidate_crash=False),
        )

        exit_code = strength_gate.main()

        assert exit_code == 0
        assert capsys.readouterr().out.strip().splitlines()[-1] == "PASS"

    def test_returns_one_and_prints_fail_when_any_opponent_crashes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        names = list(SCRIPTED)
        crash_on = names[2]

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            return _FakeResult(any_candidate_crash=(kwargs["opponent"] == f"zoo:{crash_on}"))

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)

        exit_code = strength_gate.main()

        assert exit_code == 1
        assert capsys.readouterr().out.strip().splitlines()[-1] == "FAIL"
