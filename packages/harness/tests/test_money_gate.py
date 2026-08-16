"""Two-arm, same-seed, same-opponent paired money gate (issue #4)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from harness.episodes import GameRow
from harness.gate import (
    GateResult,
    opponent_digest,
    run_gate,
    run_money_gate,
    seat_mean_money,
    seat_mean_opponent_money,
)
from harness.stats import gate_verdict

TINY_CONFIG = {"episodeSteps": 48}
#: Long enough that champion money actually DIFFERS seed to seed, which is
#: what makes the pairing observable at all (see the self-comparison test).
SEED_VARYING_CONFIG = {"episodeSteps": 120}
TAPE_ENTRY = {"farmer": ["PASS"], "hands": [["PASS"]], "market": []}


def _row(
    seed: int, seat: int, money: float, opponent_money: float = 50000.0, **kwargs: Any
) -> GameRow:
    return GameRow(
        seed=seed,
        candidate_seat=seat,
        candidate_money=money,
        opponent_money=opponent_money,
        outcome=kwargs.pop("outcome", "loss"),
        candidate_crashed=kwargs.pop("candidate_crashed", False),
        opponent_crashed=kwargs.pop("opponent_crashed", False),
    )


def _result(rows: list[GameRow], **kwargs: Any) -> GateResult:
    seeds = sorted({row.seed for row in rows})
    return GateResult(
        candidate=kwargs.pop("candidate", "champion"),
        opponent=kwargs.pop("opponent", "zoo:tape-thunder-719"),
        gate_type=kwargs.pop("gate_type", "money"),
        n_seeds=len(seeds),
        seed_base=seeds[0] if seeds else 0,
        seeds=seeds,
        rows=rows,
        wins=0,
        losses=len(rows),
        ties=0,
        verdict=gate_verdict(wins=0, losses=len(rows), ties=0),
        any_candidate_crash=kwargs.pop("any_candidate_crash", False),
        extra_config=None,
        agent_config=kwargs.pop("agent_config", None),
        threshold=0.5,
    )


def _arm(deltas: dict[int, float], base: float = 40000.0, **kwargs: Any) -> GateResult:
    rows = [
        _row(seed, seat, base + delta, **kwargs)
        for seed, delta in sorted(deltas.items())
        for seat in (0, 1)
    ]
    return _result(rows, **kwargs)


class TestSeatMeanMoney:
    def test_seat_mean_money_averages_both_seats(self) -> None:
        rows = [_row(5, 0, 10000.0), _row(5, 1, 20000.0), _row(6, 1, 1.0), _row(6, 0, 3.0)]
        assert seat_mean_money(rows) == {5: 15000.0, 6: 2.0}

    def test_seat_mean_opponent_money_averages_both_seats(self) -> None:
        rows = [
            _row(5, 0, 1.0, opponent_money=100.0),
            _row(5, 1, 1.0, opponent_money=300.0),
        ]
        assert seat_mean_opponent_money(rows) == {5: 200.0}

    def test_seat_mean_money_raises_when_a_seed_lacks_a_seat(self) -> None:
        with pytest.raises(ValueError, match="seat"):
            seat_mean_money([_row(5, 0, 1.0), _row(6, 0, 2.0), _row(6, 1, 2.0)])

    def test_seat_mean_money_raises_when_a_seat_is_duplicated(self) -> None:
        with pytest.raises(ValueError, match="seat"):
            seat_mean_money([_row(5, 0, 1.0), _row(5, 0, 2.0)])


class TestOpponentDigest:
    def test_opponent_digest_is_none_for_non_tape_specs_and_hashes_a_tape_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("KAGGRICULTURE_TAPE_DIR", str(tmp_path))
        tape = tmp_path / "thunder-719.json"
        tape.write_text(json.dumps([TAPE_ENTRY, TAPE_ENTRY]), encoding="utf-8")

        assert opponent_digest("builtin:pass") is None
        assert opponent_digest("champion") is None
        assert opponent_digest("zoo:meta-clone") is None
        assert opponent_digest("zoo:tape-absent") is None

        digest = opponent_digest("zoo:tape-thunder-719")
        assert digest is not None
        assert digest == "sha256:" + hashlib.sha256(tape.read_bytes()).hexdigest()

        tape.write_text(json.dumps([TAPE_ENTRY, TAPE_ENTRY, TAPE_ENTRY]), encoding="utf-8")
        assert opponent_digest("zoo:tape-thunder-719") != digest


class TestRunMoneyGateEndToEnd:
    def test_self_comparison_yields_exactly_zero_deltas_and_fails(self) -> None:
        # TEETH-CHECK and determinism proof in one: the same spec on the same
        # seeds against the same opponent must produce IDENTICAL money in
        # both arms, so every paired difference is exactly zero.
        #
        # The fixture is deliberately `champion` vs `builtin:starter` and not
        # the cheaper starter-vs-pass matchup: starter's money is CONSTANT
        # across seeds on the tiny fixture, so a baseline arm that silently
        # forked a different seed band would still difference to zero and
        # this test would be worthless. Here money varies seed to seed
        # ($540 vs $633 vs $588.50), so a broken pairing shows up as nonzero.
        result = run_money_gate(
            "champion",
            "builtin:starter",
            4,
            5,
            baseline="champion",
            workers=1,
            extra_config=SEED_VARYING_CONFIG,
            min_seeds=4,
            candidate_money_floor=0.0,
            opponent_money_floor=0.0,
            run_canary=False,
        )
        assert len({entry.candidate_money for entry in result.per_seed}) > 1
        assert [entry.delta for entry in result.per_seed] == [0.0] * 4
        assert result.money_verdict.n_seeds == 4
        assert result.money_verdict.mean_delta == 0.0
        assert result.money_verdict.ci_lower == 0.0
        assert result.money_verdict.vetoes == ()
        assert result.money_verdict.passed is False
        assert result.opponent_mean_delta == 0.0
        assert result.gate_type == "money"

    def test_both_arms_use_the_identical_seed_list(self) -> None:
        result = run_money_gate(
            "builtin:starter",
            "builtin:pass",
            8,
            5,
            baseline="builtin:starter",
            workers=1,
            extra_config=TINY_CONFIG,
            candidate_money_floor=0.0,
            opponent_money_floor=0.0,
            run_canary=False,
        )
        assert result.seeds == list(range(5, 13))
        assert result.candidate_result.seeds == result.baseline_result.seeds == result.seeds
        assert [entry.seed for entry in result.per_seed] == result.seeds


class TestRunMoneyGateVetoes:
    def _patch_arms(
        self,
        monkeypatch: pytest.MonkeyPatch,
        candidate_arm: GateResult,
        baseline_arm: GateResult,
    ) -> list[dict[str, Any]]:
        import harness.gate as gate_module

        calls: list[dict[str, Any]] = []

        def fake_run_gate(**kwargs: Any) -> GateResult:
            calls.append(kwargs)
            if kwargs["gate_type"] == "money-canary":
                return _result([_row(0, 0, 40000.0), _row(0, 1, 40000.0)])
            return candidate_arm if kwargs["candidate"] == "champion" else baseline_arm

        monkeypatch.setattr(gate_module, "run_gate", fake_run_gate)
        return calls

    def test_candidate_crash_vetoes_regardless_of_money(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deltas = {seed: 20000.0 for seed in range(10)}
        candidate_arm = _arm(deltas, any_candidate_crash=True)
        baseline_arm = _arm({seed: 0.0 for seed in range(10)}, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion",
            "zoo:tape-thunder-719",
            10,
            0,
            baseline="frozen:base",
            run_canary=False,
        )
        assert result.money_verdict.mean_delta == 20000.0
        assert "candidate_crash" in result.money_verdict.vetoes
        assert result.money_verdict.passed is False

    def test_baseline_crash_vetoes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        candidate_arm = _arm({seed: 20000.0 for seed in range(10)})
        baseline_arm = _arm(
            {seed: 0.0 for seed in range(10)}, candidate="frozen:base", any_candidate_crash=True
        )
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert "baseline_crash" in result.money_verdict.vetoes

    def test_opponent_crash_in_either_arm_vetoes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        candidate_arm = _arm({seed: 20000.0 for seed in range(10)})
        baseline_arm = _arm(
            {seed: 0.0 for seed in range(10)}, candidate="frozen:base", opponent_crashed=True
        )
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert "opponent_crash" in result.money_verdict.vetoes

    def test_a_dead_candidate_arm_is_vetoed_as_degenerate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # `<=`, not `<`: a fully degraded agent banks EXACTLY the $3,000 of
        # starting cash, so the floor has to be inclusive. A dead arm is dead
        # on every seed, which is what this looks like.
        rows = [_row(seed, seat, 3000.0) for seed in range(10) for seat in (0, 1)]
        candidate_arm = _result(rows)
        baseline_arm = _arm({seed: 0.0 for seed in range(10)}, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert "candidate_degenerate" in result.money_verdict.vetoes

    def test_a_dead_baseline_arm_is_vetoed_as_degenerate(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate_arm = _arm({seed: 0.0 for seed in range(10)})
        rows = [_row(seed, seat, 2500.0) for seed in range(10) for seat in (0, 1)]
        baseline_arm = _result(rows, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert "baseline_degenerate" in result.money_verdict.vetoes

    @pytest.mark.parametrize(
        ("n_dead_seeds", "expected"),
        [(0, False), (1, False), (2, False), (3, True), (10, True)],
    )
    def test_the_money_floor_needs_a_fraction_of_seeds_not_a_single_game(
        self, monkeypatch: pytest.MonkeyPatch, n_dead_seeds: int, expected: bool
    ) -> None:
        # D3 TEETH-CHECK. The per-GAME `any(row.candidate_money <= floor)`
        # form had NO tolerance: one game in 80 turned a measured +$18,764
        # gain whose bound cleared the threshold 14.7x into INVALID. The unit
        # is now the seed and the trigger is `degenerate_seed_fraction`
        # (0.25), so 2 of 10 seeds is a low tail and 3 of 10 is a dead arm.
        rows = [
            _row(seed, seat, 3000.0 if seed < n_dead_seeds else 40000.0)
            for seed in range(10)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _arm({seed: 0.0 for seed in range(10)}, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert ("candidate_degenerate" in result.money_verdict.vetoes) is expected

    def test_an_arm_dead_in_one_seat_only_is_still_vetoed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # N3, adversarial2/q6. The seed unit is (seat0 + seat1) / 2, so an arm
        # that banks the $2,000 starting-cash signature in seat 0 and a
        # healthy $37,167 in seat 1 averages to $19,583 on EVERY seed: the
        # fraction at or below the $3,000 floor was 0.000 and NO veto fired,
        # while under the per-game rule this replaced every seat-0 row was
        # under the floor. Half a dead agent is a dead agent.
        rows = [
            _row(seed, seat, 2000.0 if seat == 0 else 37167.0)
            for seed in range(40)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _arm({seed: 0.0 for seed in range(40)}, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 40, 0, baseline="frozen:base", run_canary=False
        )
        assert seat_mean_money(rows)[0] == 19583.5  # the seed average is healthy
        assert "candidate_degenerate" in result.money_verdict.vetoes

    def test_a_healthy_arm_with_an_ordinary_low_seat_is_not_vetoed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # N3 calibration. Watching the seats separately doubles the number of
        # observations the fraction is computed over, so it has to stay clear
        # of a healthy arm's low tail. Measured on this machine over 3 healthy
        # 40-seed arms against `zoo:tape-thunder-719` (scratchpad seatprobe,
        # seed_base 950000): the fraction of seat-0 games at or below $3,000
        # is 0.000 and of seat-1 games 0.000, with per-seat MINIMA of $20,014
        # / $14,080 (default), $18,818 / $20,329 (melon_tile_target=16) and
        # $20,758 / $21,443 (cow+sheep=0). Even the deliberate
        # `wheat_rush_tiles=0` regression only put 0.025 of its seat-0 games
        # under the floor -- ten times below the 0.25 trigger.
        rows = [
            _row(seed, seat, 2000.0 if (seed == 0 and seat == 0) else 37167.0)
            for seed in range(40)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _arm({seed: 0.0 for seed in range(40)}, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 40, 0, baseline="frozen:base", run_canary=False
        )
        assert result.money_verdict.vetoes == ()

    def test_a_baseline_dead_in_one_seat_only_is_still_vetoed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate_arm = _arm({seed: 40000.0 for seed in range(40)})
        baseline_rows = [
            _row(seed, seat, 2000.0 if seat == 1 else 37167.0)
            for seed in range(40)
            for seat in (0, 1)
        ]
        baseline_arm = _result(baseline_rows, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 40, 0, baseline="frozen:base", run_canary=False
        )
        assert "baseline_degenerate" in result.money_verdict.vetoes

    def test_an_opponent_starved_in_one_seat_only_is_still_vetoed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The same blindness on the opponent floor: an opponent held at the
        # starting-cash signature in one seat is a broken matchup whatever
        # the seat average says.
        rows = [
            _row(seed, seat, 40000.0, opponent_money=500.0 if seat == 0 else 110000.0)
            for seed in range(40)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _result(
            [
                _row(seed, seat, 20000.0, opponent_money=500.0 if seat == 0 else 110000.0)
                for seed in range(40)
                for seat in (0, 1)
            ],
            candidate="frozen:base",
        )
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 40, 0, baseline="frozen:base", run_canary=False
        )
        assert seat_mean_opponent_money(rows)[0] == 55250.0  # the seed average is healthy
        assert "opponent_degenerate" in result.money_verdict.vetoes

    def test_a_single_low_seed_no_longer_invalidates_a_large_real_gain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # D3, the empirical reproduction (empirical/tc_regression_swapped):
        # +$18,764/seed measured, bound $14,689 — 14.7x the threshold — and
        # ONE baseline seed at $2,749.50 made the whole run INVALID.
        candidate_arm = _arm({seed: 18764.0 for seed in range(40)}, base=40000.0)
        baseline_rows = [
            _row(seed, seat, 2749.5 if seed == 0 else 40000.0)
            for seed in range(40)
            for seat in (0, 1)
        ]
        baseline_arm = _result(baseline_rows, candidate="frozen:base")
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 40, 0, baseline="frozen:base", run_canary=False
        )
        assert result.money_verdict.vetoes == ()
        assert result.money_verdict.passed is True

    def test_a_silently_dead_opponent_is_vetoed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A tape whose blanket `except Exception` fires degrades to all-PASS
        # and ~$3,000 while `opponent_crashed` stays False: the floor is the
        # only detector for a silently dead opponent. It is dead on every
        # seed, not on one game.
        rows = [
            _row(seed, seat, 40000.0, opponent_money=3000.0)
            for seed in range(10)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _arm(
            {seed: 0.0 for seed in range(10)}, candidate="frozen:base", opponent_money=3000.0
        )
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert result.min_opponent_money == 3000.0
        assert "opponent_degenerate" in result.money_verdict.vetoes

    def test_one_weak_opponent_seed_does_not_veto(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The opponent is the same tape on the same seed in BOTH arms, so a
        # single weak opponent seed shifts both arms equally and cancels out
        # of the paired difference entirely. Vetoing on it costs a whole run
        # to protect a statistic it cannot move.
        rows = [
            _row(seed, seat, 40000.0, opponent_money=3000.0 if seed == 3 else 120000.0)
            for seed in range(10)
            for seat in (0, 1)
        ]
        candidate_arm = _result(rows)
        baseline_arm = _result(
            [
                _row(seed, seat, 40000.0, opponent_money=3000.0 if seed == 3 else 120000.0)
                for seed in range(10)
                for seat in (0, 1)
            ],
            candidate="frozen:base",
        )
        self._patch_arms(monkeypatch, candidate_arm, baseline_arm)

        result = run_money_gate(
            "champion", "zoo:tape-thunder-719", 10, 0, baseline="frozen:base", run_canary=False
        )
        assert result.min_opponent_money == 3000.0
        assert "opponent_degenerate" not in result.money_verdict.vetoes


class TestRunMoneyGateCanary:
    def test_canary_is_skipped_for_a_frozen_candidate_and_recorded_as_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import harness.gate as gate_module

        calls: list[dict[str, Any]] = []

        def fake_run_gate(**kwargs: Any) -> GateResult:
            calls.append(kwargs)
            return _arm({seed: 0.0 for seed in range(10)})

        monkeypatch.setattr(gate_module, "run_gate", fake_run_gate)
        result = run_money_gate("frozen:m2a", "zoo:tape-thunder-719", 10, 0, baseline="frozen:m2b")
        assert result.candidate_canary_ran is False
        assert result.baseline_canary_ran is False
        assert result.candidate_canary_crashed is False
        assert [call["gate_type"] for call in calls] == ["money", "money"]

    def test_baseline_canary_runs_only_when_the_baseline_carries_a_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import harness.gate as gate_module

        calls: list[dict[str, Any]] = []

        def fake_run_gate(**kwargs: Any) -> GateResult:
            calls.append(kwargs)
            return _arm({seed: 0.0 for seed in range(10)})

        monkeypatch.setattr(gate_module, "run_gate", fake_run_gate)

        plain = run_money_gate("champion", "zoo:tape-thunder-719", 10, 0, baseline="champion")
        assert plain.candidate_canary_ran is True
        assert plain.baseline_canary_ran is False

        calls.clear()
        tuned = run_money_gate(
            "champion",
            "zoo:tape-thunder-719",
            10,
            0,
            baseline="champion",
            baseline_agent_config={"feed_reserve": 20},
        )
        assert tuned.baseline_canary_ran is True
        assert [call["gate_type"] for call in calls[:2]] == ["money-canary", "money-canary"]
        assert all(call["candidate"] == "champion-unshelled" for call in calls[:2])

    def test_canary_crash_vetoes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import harness.gate as gate_module

        def fake_run_gate(**kwargs: Any) -> GateResult:
            crashed = kwargs["gate_type"] == "money-canary"
            return _arm({seed: 0.0 for seed in range(10)}, any_candidate_crash=crashed)

        monkeypatch.setattr(gate_module, "run_gate", fake_run_gate)
        result = run_money_gate("champion", "zoo:tape-thunder-719", 10, 0, baseline="champion")
        assert result.candidate_canary_crashed is True
        assert "canary_crash" in result.money_verdict.vetoes
        assert result.money_verdict.passed is False


class TestRunMoneyGateValidation:
    def test_agent_config_for_a_non_champion_spec_raises_before_any_game_is_played(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import harness.gate as gate_module

        def exploding_run_gate(**kwargs: Any) -> GateResult:
            raise AssertionError("no game may be played before the spec is validated")

        monkeypatch.setattr(gate_module, "run_gate", exploding_run_gate)

        with pytest.raises(ValueError, match="builtin:starter"):
            run_money_gate(
                "builtin:starter",
                "builtin:pass",
                10,
                0,
                baseline="champion",
                agent_config={"feed_reserve": 20},
            )
        with pytest.raises(ValueError, match="frozen:m2a"):
            run_money_gate(
                "champion",
                "builtin:pass",
                10,
                0,
                baseline="frozen:m2a",
                baseline_agent_config={"feed_reserve": 20},
            )

    def test_non_positive_n_seeds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import harness.gate as gate_module

        def exploding_run_gate(**kwargs: Any) -> GateResult:
            raise AssertionError("no game may be played before the spec is validated")

        monkeypatch.setattr(gate_module, "run_gate", exploding_run_gate)
        with pytest.raises(ValueError, match="n_seeds"):
            run_money_gate("champion", "builtin:pass", 0, 0, baseline="champion")


class TestExistingGateSurfaceIsUntouched:
    def test_run_gate_positional_signature_is_unchanged(self) -> None:
        # TEETH-CHECK. `rerun_ledger.py:34-37` calls run_gate positionally
        # through the 4th argument and `workers`/`extra_config` sit at 5 and
        # 6; inserting a parameter anywhere in that prefix silently re-binds
        # every legacy replay.
        result = run_gate("builtin:starter", "builtin:pass", 1, 0, 1, TINY_CONFIG)
        assert result.n_seeds == 1
        assert result.seed_base == 0
        assert result.seeds == [0]
        assert result.extra_config == TINY_CONFIG
        assert len(result.rows) == 2
