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


#: Absolute floor on the dispersion veto, as a FRACTION of the money scale.
#: Money lives on a $0.50 grid, so an exact ``sd == 0`` test is trivially
#: evaded: 2500.0 on 63 seeds and 2500.5 on one gives sd = $0.0625 and sails
#: through. At the measured money scale (~$37,167) this tolerance is $0.372,
#: which is still 5.9x above that evasion.
#:
#: It was 1e-4 (~$3.72) and that FALSE-VETOED a real arm: ``survey2/fert_0``
#: is a genuine measured knob with ``mean_delta`` $1.31 and ``sd_delta``
#: $3.40, and it was being reported INVALID (rerun the measurement) when the
#: right answer is FAIL on the bound. It is the only one of the 64 measured
#: arms below $3.72, and none is below $0.372. The dollar floor no longer has
#: to stretch, because the effect-relative leg below carries the evasions.
DISPERSION_REL_TOL = 1e-5

#: Dispersion at or below this fraction of the measured EFFECT is treated as
#: no dispersion at all -- the second leg of ``degenerate_dispersion``.
#:
#: ``DISPERSION_REL_TOL`` alone cannot carry the veto, which is what
#: adversarial2/q3 demonstrated: a fixed dollar tolerance is a fixed dollar
#: hole, so a binary search found ~$30 of wobble on ONE of 64 seeds walks
#: through it and flips the verdict INVALID -> PASS. Widening the dollar
#: figure is not available either, because real arms genuinely live down
#: there (``survey2/fert_0`` above, ``survey2/valve_hard_95`` at
#: -$0.75 / $25.92).
#:
#: Anchoring on the effect instead is available, because paired game noise
#: dwarfs every knob effect measured here: across the 54 real arms with a
#: nonzero ``mean_delta`` the SMALLEST ``sd_delta / |mean_delta|`` is 0.6925
#: (``a2_regression`` / ``a2_improvement_large``). 0.05 is a 13.9x margin
#: under that, and it narrows q3's hole by 31x: re-injecting the old rule
#: and searching put the smallest evading single-seed wobble at $32.31, and
#: on the same $2,500 fixture it now takes $1,008.
#:
#: Residual, stated rather than hidden: this narrows the hole, it does not
#: close it. A fault that spreads the seeds over more than 5% of the effect
#: still reads as dispersion, because at that point it IS dispersion and no
#: rule at this level can tell it from a real low-variance arm.
DISPERSION_EFFECT_REL_TOL = 0.05

#: Lower-tail quantile of the per-seed differences that the ``catastrophic_tail``
#: blocker reads, and the dollar floor it must clear.
#:
#: DERIVATION, from the real arms in scratchpad/money-gate/empirical and
#: empirical2 (64 arms, 40-seed and 64-seed blocks against
#: ``zoo:tape-thunder-719``).
#:
#: The quantile. Only arms whose t bound already CLEARS the threshold can be
#: cost anything by a promotion guard; there are 11 such arms. Their
#: worst (most negative) tail quantile is
#:
#:     q = 0.05  -$15,039      q = 0.15   -$9,835
#:     q = 0.10  -$12,889      q = 0.20   -$8,338
#:
#: all four realized on ``arms2/improve_feed_8``, a genuine +$5,510/seed
#: improvement that clears the bound at $2,137. Against the upper anchor
#: below, q = 0.15 is the smallest tail fraction that still leaves a ~2x
#: margin at both ends (1.70x at q = 0.10, 1.57x at q = 0.05). It also has
#: teeth at the smallest legal run: at ``min_seeds`` = 8 the interpolation
#: index is 0.15 * 7 = 1.05, so two bankrupted seeds of eight fire it.
#:
#: The floor. Lower anchor: the -$9,835 above -- nothing that can reach
#: promotion may be within reach of the floor. Upper anchor: the measured
#: champion bank against the tape is $37,167, so a seed at -$37,167 has lost
#: everything it had, which is catastrophic by inspection and needs no
#: fixture to justify. The geometric midpoint of [$9,835, $37,167] is
#: $19,119; rounded to $19,000 that is 1.93x above the worst real passing
#: tail and 1.96x below a total wipeout.
#:
#: What this deliberately tolerates: up to 15% of seeds may sit anywhere
#: above -$19,000 without the guard firing, and a smaller fraction may sit
#: arbitrarily far below it. Both are the price of a rule whose verdict
#: depends on the SHAPE of the failure rather than on ``n``; the mean bound
#: is what covers concentrated damage, since a few very large losses move
#: ``mean_delta`` enough for ``ci_lower`` to refuse the run on its own.
CATASTROPHIC_TAIL_QUANTILE = 0.15
CATASTROPHIC_TAIL_FLOOR = 19000.0


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
    it passed a candidate measured to regress on 60.9% of its seeds.

    That job passed to a ``half_the_seeds_regress`` blocker, which failed for
    the SAME reason the HL leg did -- a rank/count rule is blind to magnitude
    -- and is now gone too. ``2 * n_regressed >= n`` refused an UNBOUNDED true
    gain (32 seeds worse by fifty cents against 32 seeds better by a million,
    bound $394,837, blocked; ramping the gain to 1e12 never passed) while
    permitting unbounded real damage (31 of 64 seeds bankrupted at -$37,000
    against 33 gaining $80,000, ``blockers = ()``, PASS). The asymmetry
    measured 71,688x, and flipping ONE seed from +$0.50 to -$0.50 flipped the
    verdict while moving the bound two cents. ``n_regressed`` and
    ``median_delta`` are still RECORDED; they no longer gate.

    Both are replaced by one magnitude-aware guard, ``catastrophic_tail``.

    ``vetoes`` and ``blockers`` both force ``passed`` False and are kept
    separate because they mean different things to an operator:
    ``vetoes`` says the RUN cannot be trusted (INVALID, rerun it);
    ``blockers`` says the run is fine and the CANDIDATE is not good enough
    (FAIL, keep tuning).

    KNOWN LIMITATION, stated rather than hidden: the t bound's one-sided
    level is not 0.05 on a strongly LEFT-SKEWED per-seed difference. Measured
    with the true mean pinned at the threshold and the worst real paired sd
    ($9,495), the realized level is 0.0494 on a normal null and 0.0492 on a
    Laplace null -- but 0.0753 at skew -1.75 and 0.1196 at skew -6.2. This is
    the textbook behaviour of a t interval under skew and it is ACCEPTED, not
    fixed: the real arms measure at skew +0.117 (``tc_improvement``) and
    -0.054, so the leak lives at shapes nothing here has produced. Read
    ``skew_delta`` on any run whose bound only just clears the threshold.

    ``mde_80`` PROMISES: a true improvement of ``threshold + mde_80`` per
    seed clears the t bound about 80% of the time, if the per-seed
    differences are roughly normal and the true sd equals the ``sd_delta``
    this run happened to observe. It does NOT promise that ``mde_80`` alone
    is detectable -- the gate tests against ``threshold``, not against zero,
    so the detectable EFFECT is ``threshold + mde_80``. It is an estimate,
    not a bound: ``sd_delta`` at n=64 is itself uncertain to about +-9%, and
    the multiplier is the normal-theory ``t + t`` approximation to the
    noncentral t, not the noncentral t. It says nothing about ``blockers``:
    an improvement of any size still fails if its lower tail is wiped out.
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
    tail_quantile: float
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


def lower_tail_quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolated ``q``-th quantile of ``values`` (the ``numpy`` default).

    ``h = q * (n - 1)`` indexes the sorted sample and the result interpolates
    between its two neighbours. Two properties are load-bearing for the
    ``catastrophic_tail`` blocker and both follow directly from that form:

    * MONOTONE -- lowering any observation can only lower the result, so more
      damage can never buy silence. The studentized cut this replaced was not
      monotone: it fired for 1 and 2 catastrophic seeds at -$200,000 and went
      silent at 3 and 4, because ``sd`` inflates faster than the cut moves.
    * 1-LIPSCHITZ -- moving one observation by one $0.50 money grid step moves
      the result by at most $0.50, so no verdict flips on a grid step that was
      not already sitting on the boundary. The count rule it replaced flipped
      PASS to FAIL on exactly such a step.

    It has no ``n``-dependent ceiling either: it is a dollar figure read off
    an order statistic, so it can reach any value the sample contains at every
    ``n``, including ``min_seeds``.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("lower_tail_quantile needs a non-empty sample")
    if n == 1:
        return ordered[0]
    position = q * (n - 1)
    lower = int(position)
    if lower >= n - 1:
        return ordered[-1]
    return ordered[lower] + (position - lower) * (ordered[lower + 1] - ordered[lower])


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
    catastrophic_tail_quantile: float = CATASTROPHIC_TAIL_QUANTILE,
    catastrophic_tail_floor: float = CATASTROPHIC_TAIL_FLOOR,
    degenerate_dispersion_ratio: float = DISPERSION_EFFECT_REL_TOL,
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
        the seeds carry no independent information. Two legs, because one
        instrument cannot see both shapes of the fault:

        * an absolute floor: ``sd_delta`` at or below ``DISPERSION_REL_TOL``
          times the money scale. Across independent seeds a constant
          difference is a harness fault, never certainty. A genuine no-op
          differences to EXACTLY zero on every seed (mean 0), which is
          exempt.
        * an effect-relative leg: ``sd_delta`` at or below
          ``degenerate_dispersion_ratio`` times ``|mean_delta|``. The first
          leg is a fixed number of dollars and therefore a fixed dollar hole
          -- ~$30 of wobble on ONE of 64 seeds evaded it and flipped INVALID
          to PASS -- and it cannot simply be widened, because real arms
          measure at ``sd_delta`` $3.40 and $25.92. See
          ``DISPERSION_EFFECT_REL_TOL``.

    ``blockers`` (the run is valid, the candidate FAILS):

    ``catastrophic_tail``
        the ``catastrophic_tail_quantile``-th quantile of the per-seed
        differences sits below ``-catastrophic_tail_floor`` -- that is, the
        worst-off 15% of seeds lost more than $19,000 each. See
        ``CATASTROPHIC_TAIL_QUANTILE`` for how both numbers come off the
        measured arms.

        This is ONE guard replacing two that failed for opposite reasons. The
        ``catastrophic_seed`` veto (``min_delta < min(0, mean) - k*sd``) was a
        studentized extreme deviate and so obeyed the algebraic ceiling
        ``(mean - min)/sd <= (n-1)/sqrt(n)``: at ``k = 5`` it could not fire
        below n=27 while ``min_seeds`` defaults to 8, so at n=20 a seed losing
        TEN MILLION DOLLARS produced ``vetoes = ()``, and the identical
        failure was INVALID at n=64 and PASS at n=20. It also masked -- it
        fired for 1 and 2 catastrophes at -$200,000 and went silent at 3 and
        4. The ``half_the_seeds_regress`` blocker was a magnitude-blind count;
        see ``MoneyVerdict``.

        It is a BLOCKER and not a veto: a wiped-out lower tail is a property
        of the candidate, reproducible on rerun, so the operator's next move
        is to keep tuning (FAIL), not to remeasure (INVALID).

        Measured on the fixtures: 31 of 64 seeds at -$37,000 against 33 at
        +$80,000 blocks (the count rule passed it); 32 seeds at -$0.50 against
        32 at +$1,000,000 does not (the count rule refused it); 40 seeds at
        -$200 against 24 at +$20,000 does not; two of eight seeds at -$37,000
        blocks. It fires at every ``n >= min_seeds`` and never stops firing
        when more seeds are wiped out.
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
    tail_quantile = lower_tail_quantile(diffs, catastrophic_tail_quantile) if n else 0.0
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
    dispersion_tolerance = max(
        DISPERSION_REL_TOL * money_scale, degenerate_dispersion_ratio * abs(mean_delta)
    )
    if mean_delta != 0.0 and sd_delta <= dispersion_tolerance:
        computed.add("degenerate_dispersion")

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
    wiped_out_tail = n > 0 and tail_quantile < -catastrophic_tail_floor
    blockers = ("catastrophic_tail",) if wiped_out_tail else ()

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
        tail_quantile=tail_quantile,
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
