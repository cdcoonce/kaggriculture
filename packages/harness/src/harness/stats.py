"""Wilson score interval and gate-verdict math (eval protocol, issue #4)."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class GateVerdict:
    """PASS/FAIL summary of a gate run's win/loss/tie counts."""

    n_games: int
    score: float
    rate: float
    ci_lower: float
    passed: bool


def wilson_lower_bound(successes: float, n: int, z: float = 1.959964) -> float:
    """Lower bound of the Wilson score confidence interval for a binomial rate.

    ``successes`` may be fractional (ties are scored 0.5).
    """
    p_hat = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = p_hat + z2 / (2 * n)
    margin = z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))
    return (center - margin) / denominator


def gate_verdict(wins: int, losses: int, ties: int, threshold: float = 0.5) -> GateVerdict:
    """Aggregate win/loss/tie counts into a PASS/FAIL gate verdict."""
    n_games = wins + losses + ties
    score = wins + 0.5 * ties
    rate = score / n_games
    ci_lower = wilson_lower_bound(score, n_games)
    return GateVerdict(
        n_games=n_games,
        score=score,
        rate=rate,
        ci_lower=ci_lower,
        passed=ci_lower > threshold,
    )
