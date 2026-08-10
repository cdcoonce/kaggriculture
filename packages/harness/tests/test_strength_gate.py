"""CI crash-only smoke gate orchestration (issue #29)."""

from __future__ import annotations

import pytest
from harness import strength_gate


class TestOpponentSeedCounts:
    def test_splits_evenly_when_total_divides_roster(self) -> None:
        assert strength_gate._opponent_seed_counts(["a", "b", "c", "d", "e"], total=50) == [
            10,
            10,
            10,
            10,
            10,
        ]

    def test_remainder_goes_to_first_members_in_order(self) -> None:
        # 50 // 7 == 7, remainder 1 -> first member gets one extra.
        names = ["a", "b", "c", "d", "e", "f", "g"]
        assert strength_gate._opponent_seed_counts(names, total=50) == [8, 7, 7, 7, 7, 7, 7]

    def test_counts_always_sum_to_total(self) -> None:
        for n in range(1, 12):
            names = [f"member-{i}" for i in range(n)]
            assert sum(strength_gate._opponent_seed_counts(names, total=50)) == 50

    def test_derived_from_current_scripted_roster_sums_to_50(self) -> None:
        # Guards against a hardcoded roster silently drifting from the real
        # harness.zoo.SCRIPTED membership (issue #29's roster has gone stale
        # three times already).
        names = list(strength_gate.SCRIPTED)
        assert sum(strength_gate._opponent_seed_counts(names)) == 50


class _FakeResult:
    def __init__(self, any_candidate_crash: bool) -> None:
        self.any_candidate_crash = any_candidate_crash


class TestMain:
    def test_iterates_every_scripted_member_in_dict_order(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_scripted = {"alpha": lambda: "a", "beta": lambda: "b", "gamma": lambda: "c"}
        monkeypatch.setattr(strength_gate, "SCRIPTED", fake_scripted)

        calls: list[dict[str, object]] = []

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            calls.append(kwargs)
            return _FakeResult(any_candidate_crash=False)

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        assert strength_gate.main() == 0
        assert "PASS" in capsys.readouterr().out

        assert len(calls) == 3
        assert all(call["candidate"] == "champion-unshelled" for call in calls)
        assert all(call["workers"] == 1 for call in calls)
        assert [call["opponent"] for call in calls] == [
            "zoo:alpha",
            "zoo:beta",
            "zoo:gamma",
        ]
        assert [call["n_seeds"] for call in calls] == strength_gate._opponent_seed_counts(
            list(fake_scripted)
        )
        assert sum(call["n_seeds"] for call in calls) == 50

        seed_bases = [call["seed_base"] for call in calls]
        assert seed_bases == sorted(seed_bases)
        assert len(set(seed_bases)) == len(seed_bases)

    def test_returns_1_and_prints_fail_when_any_opponent_crashes(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_scripted = {"alpha": lambda: "a", "beta": lambda: "b"}
        monkeypatch.setattr(strength_gate, "SCRIPTED", fake_scripted)

        def fake_run_gate(**kwargs: object) -> _FakeResult:
            return _FakeResult(any_candidate_crash=kwargs["opponent"] == "zoo:beta")

        monkeypatch.setattr(strength_gate, "run_gate", fake_run_gate)
        assert strength_gate.main() == 1
        assert "FAIL" in capsys.readouterr().out
