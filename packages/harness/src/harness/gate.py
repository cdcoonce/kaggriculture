"""Promotion-gate runner: paired seeds, both seats, parallel or sequential.

Eval protocol, issue #4.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Any

from harness.episodes import GameRow, play_game
from harness.stats import GateVerdict, gate_verdict


@dataclass(frozen=True)
class GateResult:
    """Aggregate outcome of a full gate run."""

    candidate: str
    opponent: str
    gate_type: str
    n_seeds: int
    seed_base: int
    seeds: list[int]
    rows: list[GameRow]
    wins: int
    losses: int
    ties: int
    verdict: GateVerdict
    any_candidate_crash: bool
    extra_config: dict[str, Any] | None
    agent_config: dict[str, Any] | None
    threshold: float


def _play_seed_pair(
    seed: int,
    candidate: str,
    opponent: str,
    extra_config: dict[str, Any] | None,
    agent_config: dict[str, Any] | None,
) -> list[GameRow]:
    return [
        play_game(seed, 0, candidate, opponent, extra_config, agent_config),
        play_game(seed, 1, candidate, opponent, extra_config, agent_config),
    ]


def run_gate(
    candidate: str,
    opponent: str,
    n_seeds: int,
    seed_base: int,
    workers: int = 8,
    extra_config: dict[str, Any] | None = None,
    gate_type: str = "promotion",
    threshold: float = 0.5,
    agent_config: dict[str, Any] | None = None,
) -> GateResult:
    """Run a candidate-vs-opponent gate over paired seeds, both seats.

    Each seed in ``range(seed_base, seed_base + n_seeds)`` produces two
    games: the candidate as seat 0 and as seat 1. Sequential (``workers<=1``)
    and parallel (``ProcessPoolExecutor``) execution modes both call the
    module-level, picklable ``harness.episodes.play_game``.

    macOS/spawn caveat: with ``workers > 1`` the CALLING script must guard its
    entry point with ``if __name__ == "__main__":`` — spawn re-imports the
    caller's main module in every worker, and an unguarded module-level call
    recurses into a BrokenProcessPool.

    ``agent_config`` overrides the candidate champion's ``PolicyConfig`` (see
    ``harness.episodes.resolve_agent``); it is passed as a plain picklable
    dict so it survives ``ProcessPoolExecutor`` worker re-import.

    ``workers`` is forced to 1 when ``candidate == "champion-unshelled"``: that
    spec resolves to a bound closure from ``make_policy()``, which is not
    guaranteed picklable, so parallel workers are out of scope for it.
    """
    if candidate == "champion-unshelled":
        workers = 1
    seeds = list(range(seed_base, seed_base + n_seeds))
    rows: list[GameRow] = []

    if workers <= 1:
        for seed in seeds:
            rows.extend(_play_seed_pair(seed, candidate, opponent, extra_config, agent_config))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(play_game, seed, seat, candidate, opponent, extra_config, agent_config)
                for seed in seeds
                for seat in (0, 1)
            ]
            rows = [future.result() for future in futures]

    wins = sum(1 for row in rows if row.outcome == "win")
    losses = sum(1 for row in rows if row.outcome == "loss")
    ties = sum(1 for row in rows if row.outcome == "tie")
    verdict = gate_verdict(wins=wins, losses=losses, ties=ties, threshold=threshold)
    any_candidate_crash = any(row.candidate_crashed for row in rows)

    return GateResult(
        candidate=candidate,
        opponent=opponent,
        gate_type=gate_type,
        n_seeds=n_seeds,
        seed_base=seed_base,
        seeds=seeds,
        rows=rows,
        wins=wins,
        losses=losses,
        ties=ties,
        verdict=verdict,
        any_candidate_crash=any_candidate_crash,
        extra_config=extra_config,
        agent_config=agent_config,
        threshold=threshold,
    )
