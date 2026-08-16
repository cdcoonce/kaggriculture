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


#: Dispersion at or below this FRACTION of the money scale is treated as no
#: dispersion at all. Money lives on a $0.50 grid, so an exact ``sd == 0``
#: test is trivially evaded: 2500.0 on 63 seeds and 2500.5 on one gives
#: sd = $0.0625 and sails through. At the measured money scale (~$37,000)
#: this tolerance is ~$3.70, about seven grid steps, while the SMALLEST
#: paired per-seed sd ever measured on a real arm is $6,214 -- 1,679x larger.
DISPERSION_REL_TOL = 1e-4


@dataclass(frozen=True)
class MoneyVerdict:
    """PASS/FAIL summary of a paired per-seed money-difference gate.

    One observation is one SEED (both seats averaged), never one game: money
    seat-correlation is rho ~= 0.79 (measured 0.682-0.817), so 2*n_seeds games
    carry only 2*n_seeds/(1+rho) games of information. Treating them as
    independent -- the defect ``gate_verdict`` inherits at ``gate.py:98-101``
    -- inflates one-sided Type I error to 0.079-0.124 against a nominal 0.05.

    PASS is the one-sided ``1 - alpha`` Student-t lower bound on the MEAN
    paired difference, and nothing else: ``ci_lower > threshold``, with an
    empty ``vetoes`` and an empty ``blockers``.

    The Hodges-Lehmann bound (``hl_shift``, ``hl_skip``, ``hl_exact_alpha``,
    ``ci_lower_hl``) is RECORDED but does NOT gate. It used to be ANDed with
    the t bound, and that conjunction was measured to be a mistake three ways:

    * it makes sparse-but-real gains structurally unpassable. Every Walsh
      average of two at-or-below-threshold seeds is itself at or below
      threshold, so with ``z`` unchanged seeds the HL leg can only clear the
      threshold when ``z(z+1)/2 <= skip``. At n=64 that caps ``z`` at 39: 40
      unchanged seeds plus 24 seeds improved by $1,000,000 each (a true
      +$375,000/seed) could not pass at ANY effect size.
    * it costs enormous power on ordinary sparse effects. On a genuine
      +$4,000/seed improvement delivered by a quarter of the seeds, power was
      0.0092 for the conjunction against 0.9813 for the t bound alone.
    * it supplies no Type-I protection where the t leg leaks. On left-skewed
      and catastrophe-mixture nulls the t leg realized 0.075-0.146 while the
      HL leg realized 0.27-1.00, so the conjunction's level is the t leg's.

    Its stated job -- protecting the typical seed -- it never did: it bounds
    the PSEUDOMEDIAN (the median of pairwise averages), not the median, and
    it passed a candidate measured to regress on 60.9% of its seeds. That job
    now belongs to the ``half_the_seeds_regress`` blocker.

    ``vetoes`` and ``blockers`` both force ``passed`` False and are kept
    separate because they mean different things to an operator:
    ``vetoes`` says the RUN cannot be trusted (INVALID, rerun it);
    ``blockers`` says the run is fine and the CANDIDATE is not good enough
    (FAIL, keep tuning).

    ``mde_80`` PROMISES: a true improvement of ``threshold + mde_80`` per
    seed clears the t bound about 80% of the time, if the per-seed
    differences are roughly normal and the true sd equals the ``sd_delta``
    this run happened to observe. It does NOT promise that ``mde_80`` alone
    is detectable -- the gate tests against ``threshold``, not against zero,
    so the detectable EFFECT is ``threshold + mde_80``. It is an estimate,
    not a bound: ``sd_delta`` at n=64 is itself uncertain to about +-9%, and
    the multiplier is the normal-theory ``t + t`` approximation to the
    noncentral t, not the noncentral t. It says nothing about ``blockers``:
    an improvement of any size still fails if half the seeds regress.
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
    n_regressed: int
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
    blockers: tuple[str, ...]
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

    Returns the LARGEST ``k`` whose exact null tail ``P(W+ <= k)`` still fits
    inside ``alpha``, together with that exact probability -- which is the
    REALIZED one-sided level of ``walsh[k]``, not an optimistic neighbour of
    it. ``(None, 1.0)`` when no ``k`` qualifies, which is every ``n <= 4``:
    with 16 sign assignments the smallest attainable tail is 1/16 = 0.0625,
    so no distribution-free 95% bound exists there and the caller must say so
    rather than return the sample minimum and call it a bound.

    The tail has to be ``P(W+ <= k)`` and not ``P(W+ < k)``: the bound
    ``walsh[k]`` exceeds the null value exactly when ``W+ > k``, so the
    one-sided error is ``P(W+ <= k)`` under the null. Indexing on the strict
    tail returns ``k + 1`` and overshoots at every legal ``n`` -- measured by
    exhaustive 2**n sign-flip enumeration at 0.078125 for n=6 against a
    reported 0.046875, and still 0.05270 / 0.05002 / 0.05044 at n = 20 / 40 /
    64.
    """
    counts = signed_rank_null_counts(n)
    total = 2**n
    cumulative = 0
    best: int | None = None
    best_alpha = 1.0
    for k in range(len(counts)):
        cumulative += counts[k]
        exact = cumulative / total
        if exact > alpha:
            break
        best, best_alpha = k, exact
    return best, best_alpha


def hodges_lehmann(diffs: Sequence[float]) -> float:
    """Hodges-Lehmann pseudomedian: the median of the Walsh averages."""
    return statistics.median(walsh_averages(diffs))


def hl_lower_bound(diffs: Sequence[float], alpha: float = 0.05) -> float:
    """Distribution-free one-sided lower confidence bound on the pseudomedian.

    ``walsh[k]`` with ``k`` from ``signed_rank_skip_count``; ``-inf`` when
    ``n`` is too small for any valid bound. Exact under symmetry.

    Reported by ``money_verdict`` as a DIAGNOSTIC only. It does not gate --
    see ``MoneyVerdict`` for the measurements that removed it from the PASS
    rule -- but it is still recorded, so its index has to be right.
    """
    skip, _ = signed_rank_skip_count(len(diffs), alpha)
    if skip is None:
        return -math.inf
    return walsh_averages(diffs)[skip]


def mde_multiplier(n: int, alpha: float = 0.05, power: float = 0.80) -> float:
    """``t_{1-alpha, n-1} + t_{power, n-1}``: standard errors needed for ``power``.

    The n-dependent form of the textbook ``z_{1-alpha} + z_{power}``. The
    normal constant understates the requirement at every finite ``n`` -- at
    the gate's default n=64 the z-sum is 2.486475 against a t-sum of
    2.516766, a 1.22% understatement of the effect the run can actually
    resolve. ``inf`` below n=2, where there is no dispersion estimate at all.
    """
    if n < 2:
        return math.inf
    return student_t_ppf(1.0 - alpha, n - 1) + student_t_ppf(power, n - 1)


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

    PASS requires ALL THREE of

    * ``ci_lower > threshold``, where ``ci_lower`` is the one-sided
      ``1 - alpha`` Student-t lower bound on the MEAN paired difference and
      nothing else. The Hodges-Lehmann bound is computed and recorded, but it
      does not gate (see ``MoneyVerdict``);
    * an empty ``vetoes`` -- the run is measuring what it claims to measure;
    * an empty ``blockers`` -- the candidate itself is acceptable.

    ``vetoes`` (the run is INVALID):

    ``too_few_seeds``
        fewer than ``min_seeds`` paired observations.
    ``degenerate_dispersion``
        a nonzero mean difference with no usable seed-to-seed dispersion,
        judged against ``DISPERSION_REL_TOL`` times the money scale rather
        than by ``sd == 0``. Across independent seeds that is a harness
        fault, never certainty: the smallest paired sd measured on a real
        40-seed arm is $6,214, and a genuine no-op differences to EXACTLY
        zero on every seed (mean 0), which is not vetoed.
    ``catastrophic_seed``
        one seed lost more than ``catastrophic_k`` paired standard deviations
        below ``min(0, mean_delta)``. The scale is the dispersion of the
        DIFFERENCES; scaling it by the dispersion of baseline money LEVELS
        (as this once did) makes the veto a property of the opponent -- the
        same candidate behaviour fired at sd(baseline) $512 and was silent at
        $40,951. Anchoring the cut at ``min(0, mean_delta)`` rather than at
        zero keeps a uniformly-degraded arm (every seed ~-$13,240, tiny
        dispersion) reading as the regression it is instead of as a single
        catastrophe, and keeps an ordinary flat seed inside a large genuine
        gain from tripping it.

    ``blockers`` (the run is valid, the candidate FAILS):

    ``half_the_seeds_regress``
        at least half the seeds are strictly WORSE. This is the guard the
        Hodges-Lehmann leg was justified by and never delivered: with the
        conjunction in place a candidate that lost $3,000 on 39 of 64 seeds
        and gained $12,000 on the other 25 PASSED, median difference
        -$3,000. It is deliberately a count of REGRESSED seeds and not a
        sign test on ``median_delta``: a sparse but real improvement leaves
        most seeds EXACTLY unchanged and so has a zero median, and blocking
        on a zero median would refuse the very gains the conjunction already
        refused (40 unchanged seeds + 24 seeds at +$1,000,000). Measured on
        the fixtures: 39/64 regressed blocks; 0/64 regressed with 24 seeds
        improved does not; a 19/40 real tuning gain does not; an exact no-op
        (0 regressed) does not, and fails on the bound instead.
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
    n_regressed = sum(1 for delta in diffs if delta < 0.0)
    mde_80 = mde_multiplier(n, alpha) * stderr if n > 1 else math.inf

    #: Scale-free stand-in for "one dollar": the typical absolute money in
    #: play across both arms. Used only by `degenerate_dispersion`, so that
    #: the tolerance does not grow with the size of the measured effect.
    money_scale = (
        sum(abs(candidate_by_seed[seed]) + abs(baseline_by_seed[seed]) for seed in seeds) / (2 * n)
        if n
        else 0.0
    )

    computed: set[str] = set()
    if n < min_seeds:
        computed.add("too_few_seeds")
    if mean_delta != 0.0 and sd_delta <= DISPERSION_REL_TOL * money_scale:
        computed.add("degenerate_dispersion")
    if sd_delta > 0.0 and min_delta < min(0.0, mean_delta) - catastrophic_k * sd_delta:
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
        ci_lower_mean = t_lower_bound(mean_delta, sd_delta, n, alpha)
        hl_shift = hodges_lehmann(diffs)
        skip, hl_exact_alpha = signed_rank_skip_count(n, alpha)
        hl_skip = -1 if skip is None else skip
        ci_lower_hl = hl_lower_bound(diffs, alpha)

    # The t bound on the mean IS the criterion; `ci_lower` is kept as its
    # name so ledger readers and `rerun-ledger` keep one field to compare.
    ci_lower = ci_lower_mean
    vetoes = tuple(sorted(computed | set(extra_vetoes)))
    blockers = ("half_the_seeds_regress",) if n > 0 and 2 * n_regressed >= n else ()

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
        n_regressed=n_regressed,
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
        blockers=blockers,
        passed=ci_lower > threshold and not vetoes and not blockers,
    )
