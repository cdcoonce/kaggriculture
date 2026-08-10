"""Parallel/sequential gate runner over paired seeds, both seats (issue #4)."""

from __future__ import annotations

import pytest
from harness.gate import run_gate

TINY_CONFIG = {"episodeSteps": 48}


class TestRunGateSequential:
    def test_two_seeds_produce_four_rows(self) -> None:
        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=2,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        assert len(result.rows) == 4

    def test_each_seed_appears_with_both_seats(self) -> None:
        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=2,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        assert result.seeds == [5, 6]
        seat_pairs_by_seed: dict[int, set[int]] = {}
        for row in result.rows:
            seat_pairs_by_seed.setdefault(row.seed, set()).add(row.candidate_seat)
        assert seat_pairs_by_seed == {5: {0, 1}, 6: {0, 1}}

    def test_verdict_math_is_consistent_with_rows(self) -> None:
        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=2,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        # starter reliably loses to pass on this fixture (verified empirically).
        assert result.wins == 0
        assert result.losses == 4
        assert result.ties == 0
        assert result.verdict.n_games == 4
        assert result.verdict.passed is False
        assert result.any_candidate_crash is False


class TestRunGateParallel:
    def test_parallel_matches_sequential_aggregate(self) -> None:
        sequential = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=2,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        parallel = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=2,
            seed_base=5,
            workers=2,
            extra_config=TINY_CONFIG,
        )
        assert parallel.seeds == sequential.seeds
        assert parallel.wins == sequential.wins
        assert parallel.losses == sequential.losses
        assert parallel.ties == sequential.ties
        assert parallel.verdict == sequential.verdict
        assert {(row.seed, row.candidate_seat, row.outcome) for row in parallel.rows} == {
            (row.seed, row.candidate_seat, row.outcome) for row in sequential.rows
        }


class TestRunGateAgentConfig:
    def test_agent_config_survives_worker_pool_pickling(self) -> None:
        # champion + a zeroed soft budget PASSes every turn -- a clearly
        # non-default, deterministic-per-seed outcome that proves the plain
        # dict round-trips through ProcessPoolExecutor's re-import/pickling
        # rather than silently falling back to the un-overridden champion.
        agent_config = {"soft_budget_seconds": 0.0}
        sequential = run_gate(
            candidate="champion",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
            agent_config=agent_config,
        )
        parallel = run_gate(
            candidate="champion",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=2,
            extra_config=TINY_CONFIG,
            agent_config=agent_config,
        )
        assert parallel.agent_config == sequential.agent_config == agent_config
        assert {
            (row.seed, row.candidate_seat, row.candidate_money, row.outcome)
            for row in parallel.rows
        } == {
            (row.seed, row.candidate_seat, row.candidate_money, row.outcome)
            for row in sequential.rows
        }


class TestGateResultIdentity:
    def test_result_carries_extra_config_and_threshold(self) -> None:
        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
            threshold=0.55,
        )
        assert result.extra_config == TINY_CONFIG
        assert result.threshold == 0.55

    def test_result_carries_agent_config(self) -> None:
        agent_config = {"soft_budget_seconds": 0.0}
        result = run_gate(
            candidate="champion",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
            agent_config=agent_config,
        )
        assert result.agent_config == agent_config

    def test_result_agent_config_defaults_to_none(self) -> None:
        result = run_gate(
            candidate="builtin:starter",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        assert result.agent_config is None


class TestRunGateChampionUnshelled:
    def test_forces_workers_to_1_even_when_requested_higher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A bound closure from make_policy() isn't guaranteed picklable, so
        # this spec must never reach the ProcessPoolExecutor branch.
        import harness.gate as gate_module

        def exploding_pool(*args: object, **kwargs: object) -> object:
            raise AssertionError("ProcessPoolExecutor must not be constructed")

        monkeypatch.setattr(gate_module, "ProcessPoolExecutor", exploding_pool)
        result = run_gate(
            candidate="champion-unshelled",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=8,
            extra_config=TINY_CONFIG,
        )
        assert result.any_candidate_crash is False

    def test_raising_candidate_trips_any_candidate_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Teeth-check (issue #29): the raw, unshelled policy must let a
        # crash surface as a real ERROR status, not get swallowed the way
        # agent.shell.wrap's never-raise boundary would swallow it.
        import agent.policy as policy_module

        def raising_policy(obs: object, config: object = None) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(
            policy_module, "make_policy", lambda clock=None, policy_config=None: raising_policy
        )
        result = run_gate(
            candidate="champion-unshelled",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        assert result.any_candidate_crash is True

    def test_legal_losing_candidate_does_not_trip_any_candidate_crash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Companion to the crash teeth-check: a candidate that never raises
        # and only ever returns a legal (if losing) move must pass clean.
        import agent.policy as policy_module

        def passing_policy(obs: object, config: object = None) -> object:
            return {"farmer": ["PASS"], "hands": [], "market": []}

        monkeypatch.setattr(
            policy_module, "make_policy", lambda clock=None, policy_config=None: passing_policy
        )
        result = run_gate(
            candidate="champion-unshelled",
            opponent="builtin:pass",
            n_seeds=1,
            seed_base=5,
            workers=1,
            extra_config=TINY_CONFIG,
        )
        assert result.any_candidate_crash is False
