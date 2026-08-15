"""Wilson score interval and gate-verdict math (eval protocol, issue #4)."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
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


_MDE_Z_SUM = 2.486475  # z_.95 + z_.80, one-sided alpha=.05 at 80% power


@dataclass(frozen=True)
class MoneyVerdict:
    """PASS/FAIL summary of a paired per-seed money-difference gate.

    One observation is one SEED (both seats averaged), never one game: money
    seat-correlation is rho ~= 0.79 (measured 0.682-0.817), so 2*n_seeds games
    carry only 2*n_seeds/(1+rho) games of information. Treating them as
    independent -- the defect ``gate_verdict`` inherits at ``gate.py:98-101``
    -- inflates one-sided Type I error to 0.079-0.124 against a nominal 0.05.

    The gate is a CONJUNCTION of two one-sided 95% lower bounds on the paired
    difference: a Student-t bound on the mean and a distribution-free
    Hodges-Lehmann bound on the pseudomedian. ``ci_lower`` is the binding
    (smaller) one. Neither is redundant: on right-skewed differences the HL
    leg binds, on symmetric ones the t leg binds, and each catches a failure
    the other cannot (a jackpot that hurts 80% of seeds; a rare catastrophic
    seed).
    """

    n_seeds: int
    alpha: float
    threshold: float
    candidate_mean: float
    baseline_mean: float
    mean_delta: float
    median_delta: float
    sd_delta: float
    stderr: float
    skew_delta: float
    min_delta: float
    df: int
    t_crit: float
    ci_lower_mean: float
    hl_shift: float
    hl_skip: int
    hl_exact_alpha: float
    ci_lower_hl: float
    ci_lower: float
    mde_80: float
    vetoes: tuple[str, ...]
    passed: bool


def regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta ``I_x(a, b)``.

    Numerical Recipes' modified Lentz continued fraction, with the standard
    symmetry swap ``I_x(a,b) = 1 - I_{1-x}(b,a)`` on the slow-converging side.
    Used only to invert the Student-t CDF; the whole path is deterministic
    for a given input, which is what lets ``rerun-ledger`` compare a recorded
    bound against a freshly computed one.
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    log_prefactor = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(log_prefactor) * _beta_continued_fraction(a, b, x) / a
    mirror = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + b * math.log1p(-x) + a * math.log(x)
    )
    return 1.0 - math.exp(mirror) * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Lentz evaluation of the incomplete-beta continued fraction (``betacf``)."""
    tiny = 1e-30
    eps = 3e-16
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d

    for m in range(1, 201):
        m2 = 2 * m
        numerator = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + numerator * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + numerator / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c

        numerator = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + numerator * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + numerator / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break

    return h


def student_t_ppf(p: float, df: int) -> float:
    """Quantile function of Student's t with ``df`` degrees of freedom.

    Inverted by EXACTLY 200 bisections on the fixed bracket ``[0, 1000]``,
    returning the midpoint. A fixed iteration count on a fixed bracket makes
    the result a deterministic function of ``(p, df)`` on any platform whose
    libm agrees, rather than a function of a convergence race.
    """
    if df < 1:
        raise ValueError(f"student_t_ppf needs df >= 1, got {df}")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -student_t_ppf(1.0 - p, df)

    low, high = 0.0, 1000.0
    for _ in range(200):
        mid = 0.5 * (low + high)
        if _student_t_cdf(mid, df) < p:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def _student_t_cdf(t: float, df: int) -> float:
    """CDF of Student's t at ``t >= 0``."""
    x = df / (df + t * t)
    return 1.0 - 0.5 * regularized_incomplete_beta(x, df / 2.0, 0.5)


def t_lower_bound(mean: float, sd: float, n: int, alpha: float = 0.05) -> float:
    """One-sided ``1 - alpha`` Student-t lower confidence bound on a mean.

    A zero-dispersion sample returns ``mean`` EXACTLY -- no multiplication by
    ``t_crit``, so the bound cannot pick up a last-ulp artefact that a
    ledger rerun would then read as a determinism regression.
    """
    if sd == 0.0:
        return mean
    return mean - student_t_ppf(1.0 - alpha, n - 1) * sd / math.sqrt(n)


def walsh_averages(diffs: Sequence[float]) -> list[float]:
    """Sorted Walsh averages ``(d_i + d_j) / 2`` for all ``i <= j``.

    ``n(n+1)/2`` entries; their median is the Hodges-Lehmann estimator and
    their order statistics are the endpoints of its distribution-free
    confidence interval.
    """
    return sorted(
        (diffs[i] + diffs[j]) / 2.0 for i in range(len(diffs)) for j in range(i, len(diffs))
    )


def signed_rank_null_counts(n: int) -> list[int]:
    """Exact null distribution of the Wilcoxon ``W+`` statistic.

    ``counts[w]`` is the number of the ``2**n`` sign assignments whose
    positive ranks sum to ``w``. Computed by integer subset-sum DP over the
    ranks ``1..n``, so the distribution is exact -- no normal approximation,
    no continuity correction, nothing that drifts with ``n``.
    """
    counts = [0] * (n * (n + 1) // 2 + 1)
    counts[0] = 1
    for rank in range(1, n + 1):
        new = counts[:]
        for w in range(len(counts) - 1, rank - 1, -1):
            new[w] += counts[w - rank]
        counts = new
    return counts


def signed_rank_skip_count(n: int, alpha: float = 0.05) -> tuple[int | None, float]:
    """Walsh-average index for a one-sided ``1 - alpha`` HL lower bound.

    Returns the LARGEST ``k`` whose exact null tail ``P(W+ < k)`` still fits
    inside ``alpha``, together with that exact probability -- so the realized
    level is reported rather than assumed. ``(None, 1.0)`` when no ``k``
    qualifies at all.
    """
    counts = signed_rank_null_counts(n)
    total = 2**n
    cumulative = 0
    best: int | None = None
    best_alpha = 1.0
    for k in range(len(counts)):
        exact = cumulative / total
        if exact > alpha:
            break
        best, best_alpha = k, exact
        cumulative += counts[k]
    return best, best_alpha


def hodges_lehmann(diffs: Sequence[float]) -> float:
    """Hodges-Lehmann pseudomedian: the median of the Walsh averages."""
    return statistics.median(walsh_averages(diffs))


def hl_lower_bound(diffs: Sequence[float], alpha: float = 0.05) -> float:
    """Distribution-free one-sided lower confidence bound on the pseudomedian.

    The ``k``-th smallest Walsh average, with ``k`` from
    ``signed_rank_skip_count``. Exact under symmetry and robust to the
    right-skewed difference distributions this gate actually sees; ``-inf``
    when ``n`` is too small for any valid bound.
    """
    skip, _ = signed_rank_skip_count(len(diffs), alpha)
    if skip is None:
        return -math.inf
    return walsh_averages(diffs)[skip]


def sample_skewness(values: Sequence[float]) -> float:
    """Adjusted Fisher-Pearson sample skewness ``g1 * n / ((n-1)(n-2))``.

    Reported as a diagnostic, never as a gate condition: it tells a reader
    which of the two bounds is expected to bind.
    """
    n = len(values)
    if n < 3:
        return 0.0
    mean = sum(values) / n
    sd = statistics.stdev(values)
    if sd == 0.0:
        return 0.0
    return n / ((n - 1) * (n - 2)) * sum(((value - mean) / sd) ** 3 for value in values)


def money_verdict(
    candidate_by_seed: Mapping[int, float],
    baseline_by_seed: Mapping[int, float],
    *,
    threshold: float = 1000.0,
    alpha: float = 0.05,
    min_seeds: int = 8,
    catastrophic_k: float = 5.0,
    extra_vetoes: Sequence[str] = (),
) -> MoneyVerdict:
    """PASS/FAIL on the paired per-seed money difference candidate - baseline.

    Both maps must cover the SAME seed set: an unpaired comparison is a
    silently different, ~3x noisier statistic (measured sd(d) $6,214 paired
    vs $18,497 unpaired), not a degraded version of this one, so a mismatch
    raises rather than falling back.

    Every reduction iterates the seeds in sorted order. Float summation order
    is part of the contract -- ``rerun-ledger`` compares the recorded bound
    against a freshly computed one by exact equality.

    PASS requires ``ci_lower > threshold`` AND an empty veto tuple. A veto
    invalidates the whole run and can never be outvoted by the size of the
    measured gain.
    """
    if set(candidate_by_seed) != set(baseline_by_seed):
        raise ValueError(
            "money_verdict needs the SAME seed set in both arms; "
            f"candidate-only={sorted(set(candidate_by_seed) - set(baseline_by_seed))} "
            f"baseline-only={sorted(set(baseline_by_seed) - set(candidate_by_seed))}"
        )

    seeds = sorted(candidate_by_seed)
    n = len(seeds)
    diffs = [candidate_by_seed[seed] - baseline_by_seed[seed] for seed in seeds]
    candidate_mean = sum(candidate_by_seed[seed] for seed in seeds) / n if n else 0.0
    baseline_mean = sum(baseline_by_seed[seed] for seed in seeds) / n if n else 0.0

    mean_delta = sum(diffs) / n if n else 0.0
    median_delta = statistics.median(diffs) if n else 0.0
    sd_delta = statistics.stdev(diffs) if n > 1 else 0.0
    stderr = sd_delta / math.sqrt(n) if n else 0.0
    min_delta = min(diffs) if n else 0.0
    mde_80 = _MDE_Z_SUM * stderr

    computed: set[str] = set()
    if n < min_seeds:
        computed.add("too_few_seeds")
    if sd_delta == 0.0 and mean_delta != 0.0:
        computed.add("degenerate_dispersion")
    sd_base = statistics.stdev([baseline_by_seed[seed] for seed in seeds]) if n > 1 else 0.0
    if sd_base > 0.0 and min_delta < -catastrophic_k * sd_base:
        computed.add("catastrophic_seed")

    if "too_few_seeds" in computed:
        t_crit = 0.0
        ci_lower_mean = -math.inf
        hl_shift = 0.0
        hl_skip = -1
        hl_exact_alpha = 1.0
        ci_lower_hl = -math.inf
    else:
        t_crit = student_t_ppf(1.0 - alpha, n - 1)
        ci_lower_mean = mean_delta if sd_delta == 0.0 else mean_delta - t_crit * stderr
        walsh = walsh_averages(diffs)
        hl_shift = statistics.median(walsh)
        skip, hl_exact_alpha = signed_rank_skip_count(n, alpha)
        hl_skip = -1 if skip is None else skip
        ci_lower_hl = -math.inf if skip is None else walsh[skip]

    ci_lower = min(ci_lower_mean, ci_lower_hl)
    vetoes = tuple(sorted(computed | set(extra_vetoes)))

    return MoneyVerdict(
        n_seeds=n,
        alpha=alpha,
        threshold=threshold,
        candidate_mean=candidate_mean,
        baseline_mean=baseline_mean,
        mean_delta=mean_delta,
        median_delta=median_delta,
        sd_delta=sd_delta,
        stderr=stderr,
        skew_delta=sample_skewness(diffs),
        min_delta=min_delta,
        df=n - 1,
        t_crit=t_crit,
        ci_lower_mean=ci_lower_mean,
        hl_shift=hl_shift,
        hl_skip=hl_skip,
        hl_exact_alpha=hl_exact_alpha,
        ci_lower_hl=ci_lower_hl,
        ci_lower=ci_lower,
        mde_80=mde_80,
        vetoes=vetoes,
        passed=ci_lower > threshold and not vetoes,
    )
