"""Parallel/sequential gate runner over paired seeds, both seats (issue #4)."""

from __future__ import annotations

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
