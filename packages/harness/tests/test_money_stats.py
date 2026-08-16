"""Paired money-difference gate math — t bound, HL diagnostic, vetoes (issue #4)."""

from __future__ import annotations

import itertools
import math
from dataclasses import fields
from fractions import Fraction

import pytest
from harness.stats import (
    GateVerdict,
    MoneyVerdict,
    gate_verdict,
    hl_lower_bound,
    hodges_lehmann,
    lower_tail_quantile,
    mde_multiplier,
    money_verdict,
    sample_skewness,
    signed_rank_null_counts,
    signed_rank_skip_count,
    student_t_ppf,
    t_lower_bound,
    walsh_averages,
)

# One-sided 95% Student-t quantiles, hand-checked against published tables.
T_95_BY_DF = {
    2: 2.9199855803537242,
    7: 1.8945786050900058,
    9: 1.8331129326562368,
    19: 1.7291328115213687,
    31: 1.6955187825458646,
    39: 1.684875121711225,
    63: 1.6694022217068127,
    127: 1.6569403435420644,
    255: 1.6508510924986624,
}

# (n, M, k, exact one-sided alpha) — the index is the LARGEST k with
# P(W+ <= k) <= 0.05, and the alpha column is that exact tail, which is also
# the REALIZED level of walsh[k]. Cross-checked against exhaustive 2**n
# sign-flip enumeration below.
SIGNED_RANK_TABLE = [
    (6, 21, 2, Fraction(3, 64)),
    (7, 28, 3, Fraction(5, 128)),
    (8, 36, 5, Fraction(5, 128)),
    (10, 55, 10, Fraction(43, 1024)),
    (12, 78, 17, Fraction(189, 4096)),
]
SIGNED_RANK_LARGE = [
    (20, 210, 60, 0.048653602600097656),
    (40, 820, 286, 0.04861724743295781),
    (60, 1830, 690, 0.04931442483830082),
    (64, 2080, 793, 0.04974316507678737),
]


def _paired(
    deltas: list[float], baseline: list[float]
) -> tuple[dict[int, float], dict[int, float]]:
    """Build (candidate_by_seed, baseline_by_seed) realizing ``deltas``."""
    assert len(deltas) == len(baseline)
    base = {seed: value for seed, value in enumerate(baseline)}
    cand = {seed: baseline[seed] + deltas[seed] for seed in base}
    return cand, base


def _flat_baseline(n: int) -> list[float]:
    """A baseline with modest, nonzero seed-to-seed spread (sd ~= 1414)."""
    return [37167.0 + 1000.0 * (i % 5) for i in range(n)]


def _spread_baseline(n: int, sd: float) -> list[float]:
    """A baseline whose per-seed money has EXACTLY dispersion ``sd``.

    Uniform on a symmetric grid: sd = range / sqrt(12). Lets a fixture vary
    the baseline's dispersion while holding the candidate's per-seed
    behaviour fixed, which is how the `catastrophic_seed` scale defect was
    found.
    """
    half_range = sd * math.sqrt(3.0)
    step = 2.0 * half_range / (n - 1)
    return [37167.0 - half_range + i * step for i in range(n)]


class TestStudentTPpf:
    def test_student_t_ppf_matches_published_quantiles(self) -> None:
        for df, expected in T_95_BY_DF.items():
            assert student_t_ppf(0.95, df) == pytest.approx(expected, abs=1e-9)

    def test_student_t_ppf_is_monotone_decreasing_in_df_and_increasing_in_p(self) -> None:
        by_df = [student_t_ppf(0.95, df) for df in (1, 2, 5, 10, 30, 100, 500)]
        assert all(a > b for a, b in zip(by_df, by_df[1:], strict=False))
        by_p = [student_t_ppf(p, 12) for p in (0.6, 0.75, 0.9, 0.95, 0.99)]
        assert all(a < b for a, b in zip(by_p, by_p[1:], strict=False))

    def test_student_t_ppf_is_antisymmetric_about_one_half(self) -> None:
        assert student_t_ppf(0.5, 9) == 0.0
        for p in (0.6, 0.9, 0.975):
            assert student_t_ppf(1 - p, 9) == pytest.approx(-student_t_ppf(p, 9), abs=1e-12)

    def test_student_t_ppf_rejects_zero_degrees_of_freedom(self) -> None:
        with pytest.raises(ValueError):
            student_t_ppf(0.95, 0)


class TestTLowerBound:
    def test_t_lower_bound_with_zero_sd_returns_the_mean_exactly(self) -> None:
        # No multiplication by t_crit: a zero-dispersion sample must not pick
        # up a float rounding artefact in the last ulp of the reported bound.
        assert t_lower_bound(2500.0, 0.0, 10) == 2500.0

    def test_t_lower_bound_sits_below_the_mean_for_a_dispersed_sample(self) -> None:
        assert t_lower_bound(4500.0, 2449.489742783178, 8) == pytest.approx(
            2859.246798525569, abs=1e-9
        )


class TestSignedRankNull:
    @pytest.mark.parametrize("n", [1, 2, 5, 8, 13, 20])
    def test_signed_rank_null_counts_sum_to_two_to_the_n_and_are_symmetric(self, n: int) -> None:
        counts = signed_rank_null_counts(n)
        assert len(counts) == n * (n + 1) // 2 + 1
        assert sum(counts) == 2**n
        assert counts == counts[::-1]

    def test_signed_rank_skip_count_matches_the_exact_table(self) -> None:
        for n, m, k, exact in SIGNED_RANK_TABLE:
            assert n * (n + 1) // 2 == m
            skip, alpha = signed_rank_skip_count(n)
            assert skip == k
            # The reported alpha is the INCLUSIVE tail P(W+ <= k), which is
            # the level walsh[k] actually realizes.
            assert Fraction(sum(signed_rank_null_counts(n)[: k + 1]), 2**n) == exact
            assert alpha == pytest.approx(float(exact), abs=1e-15)
        for n, m, k, exact_float in SIGNED_RANK_LARGE:
            assert n * (n + 1) // 2 == m
            skip, alpha = signed_rank_skip_count(n)
            assert skip == k
            assert alpha == pytest.approx(exact_float, abs=1e-9)

    @pytest.mark.parametrize("n", list(range(5, 65)))
    def test_signed_rank_reported_alpha_is_the_realized_level_and_is_maximal(self, n: int) -> None:
        # The reported number must be the level the bound REALIZES, not an
        # optimistic neighbour of it. `walsh[skip]` beats the null value iff
        # W+ > skip, so the realized one-sided error is P(W+ <= skip).
        skip, alpha = signed_rank_skip_count(n, 0.05)
        assert skip is not None
        counts = signed_rank_null_counts(n)
        realized = Fraction(sum(counts[: skip + 1]), 2**n)
        assert alpha == pytest.approx(float(realized), abs=1e-15)
        assert realized <= Fraction(1, 20)
        # ...and it is the LARGEST such index: one more would overshoot.
        assert Fraction(sum(counts[: skip + 2]), 2**n) > Fraction(1, 20)

    @pytest.mark.parametrize("n", [1, 2, 3, 4])
    def test_no_distribution_free_bound_exists_below_five_seeds(self, n: int) -> None:
        # With 2**4 = 16 sign assignments the smallest attainable tail is
        # 1/16 = 0.0625. Returning the sample minimum and calling it a 95%
        # bound would be a 1-in-16 lie, so there is no index at all.
        assert signed_rank_skip_count(n, 0.05) == (None, 1.0)
        assert hl_lower_bound([100.0 * (i + 1) for i in range(n)]) == -math.inf

    @pytest.mark.parametrize("n", list(range(5, 14)))
    def test_hl_bound_realized_level_by_exhaustive_sign_flip_enumeration(self, n: int) -> None:
        # THE oracle for the index: for data symmetric about 0 the sign-flip
        # randomization distribution IS the exact null, so enumerating all
        # 2**n patterns gives the EXACT realized one-sided error of the
        # shipped bound. Off-by-one indexing measured 0.078125 here at n=6.
        base = [100.0 * (i + 1) + 0.5 * i * i for i in range(n)]  # distinct, no ties
        hits = sum(
            1
            for signs in itertools.product((-1.0, 1.0), repeat=n)
            if hl_lower_bound([s * b for s, b in zip(signs, base, strict=True)], 0.05) > 0.0
        )
        realized = Fraction(hits, 2**n)
        _, reported = signed_rank_skip_count(n, 0.05)
        assert realized <= Fraction(1, 20)
        assert float(realized) == pytest.approx(reported, abs=1e-15)


class TestWalshAverages:
    def test_walsh_averages_enumerates_every_pair_including_the_diagonal(self) -> None:
        walsh = walsh_averages([5.0, -3.0, 2.0])
        # (i <= j), so the three singletons appear alongside the three pairs.
        assert walsh == [-3.0, -0.5, 1.0, 2.0, 3.5, 5.0]
        assert len(walsh_averages([0.0] * 5)) == 5 * 6 // 2

    def test_hodges_lehmann_equals_the_median_for_symmetric_input(self) -> None:
        diffs = [-4.0, -1.0, 0.0, 1.0, 4.0]
        assert hodges_lehmann(diffs) == 0.0
        shifted = [d + 250.0 for d in diffs]
        assert hodges_lehmann(shifted) == 250.0

    def test_hodges_lehmann_is_not_the_median_of_the_sample(self) -> None:
        # The distinction the removed gate leg turned on: HL estimates the
        # PSEUDOMEDIAN, and on a skewed sample it sits well away from the
        # median of the data. Bounding it is not bounding the typical seed.
        diffs = [-3000.0] * 9 + [12000.0] * 6
        assert hodges_lehmann(diffs) == 4500.0
        assert sorted(diffs)[len(diffs) // 2] == -3000.0

    def test_hl_lower_bound_is_the_exact_order_statistic_the_index_names(self) -> None:
        diffs = [1200.0, -300.0, 4400.0, 800.0, 2100.0, 90.0, 5000.0, -50.0, 700.0, 1500.0]
        skip, _ = signed_rank_skip_count(len(diffs))
        assert skip == 10
        assert hl_lower_bound(diffs) == walsh_averages(diffs)[10] == 395.0


class TestLowerTailQuantile:
    def test_it_is_the_linear_interpolated_order_statistic(self) -> None:
        values = [float(x) for x in range(10)]  # h = q * 9
        assert lower_tail_quantile(values, 0.0) == 0.0
        assert lower_tail_quantile(values, 1.0) == 9.0
        assert lower_tail_quantile(values, 0.5) == 4.5
        assert lower_tail_quantile(values, 0.15) == pytest.approx(1.35, abs=1e-12)

    def test_it_does_not_care_about_input_order(self) -> None:
        assert lower_tail_quantile([9.0, 1.0, 5.0, 3.0], 0.25) == lower_tail_quantile(
            [1.0, 3.0, 5.0, 9.0], 0.25
        )

    def test_a_single_observation_is_its_own_quantile(self) -> None:
        assert lower_tail_quantile([1234.5], 0.15) == 1234.5

    def test_it_is_monotone_non_increasing_when_any_value_is_lowered(self) -> None:
        # The property the whole guard rests on: worsening a seed can never
        # RAISE the tail statistic, so more damage never buys silence.
        values = [1000.0 * i for i in range(20)]
        previous = lower_tail_quantile(values, 0.15)
        for index in range(20):
            values[index] -= 50_000.0
            current = lower_tail_quantile(values, 0.15)
            assert current <= previous
            previous = current

    def test_it_is_one_lipschitz_in_every_observation(self) -> None:
        # No knife edge: a $0.50 grid step on one seed moves the statistic by
        # at most $0.50, whatever the sample looks like.
        values = [-500.0] * 31 + [0.5] + [9000.0] * 32
        before = lower_tail_quantile(values, 0.15)
        for index in range(len(values)):
            nudged = list(values)
            nudged[index] -= 0.5
            assert abs(lower_tail_quantile(nudged, 0.15) - before) <= 0.5

    def test_it_rejects_an_empty_sample(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            lower_tail_quantile([], 0.15)


class TestSampleSkewness:
    def test_skewness_matches_hand_computed_values_and_is_zero_for_constant_input(self) -> None:
        assert sample_skewness([1.0, 2.0, 3.0, 4.0, 10.0]) == pytest.approx(
            1.697056274847714, abs=1e-12
        )
        assert sample_skewness([float(x) for x in range(1000, 8001, 1000)]) == 0.0
        assert sample_skewness([2.0] * 4) == 0.0
        assert sample_skewness([7.0, 7.0]) == 0.0


class TestMoneyVerdictFixtures:
    def test_ramp_fixture_matches_hand_computed_bounds(self) -> None:
        deltas = [float(x) for x in range(1000, 8001, 1000)]
        cand, base = _paired(deltas, _flat_baseline(8))
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.n_seeds == 8
        assert verdict.df == 7
        assert verdict.mean_delta == 4500.0
        assert verdict.median_delta == 4500.0
        assert verdict.sd_delta == pytest.approx(2449.489742783178, abs=1e-12)
        assert verdict.stderr == pytest.approx(866.0254037844385, abs=1e-12)
        assert verdict.min_delta == 1000.0
        assert verdict.n_regressed == 0
        assert verdict.t_crit == pytest.approx(1.8945786050900058, abs=1e-9)
        assert verdict.ci_lower_mean == pytest.approx(2859.246798525569, abs=1e-9)
        assert verdict.hl_shift == 4500.0
        assert verdict.hl_skip == 5
        assert verdict.ci_lower_hl == 2500.0
        assert verdict.ci_lower == pytest.approx(2859.246798525569, abs=1e-9)
        assert verdict.mde_80 == pytest.approx(2416.737635994086, abs=1e-9)
        assert verdict.vetoes == ()
        assert verdict.blockers == ()
        assert verdict.passed is True

    @pytest.mark.parametrize(
        ("hl_side", "deltas"),
        [
            ("below", [0.0] * 24 + [20000.0] * 16),
            ("above", [2000.0] * 39 + [-100000.0]),
            ("equal", [2500.0] * 40),
        ],
    )
    def test_ci_lower_is_the_t_bound_whatever_the_hl_diagnostic_says(
        self, hl_side: str, deltas: list[float]
    ) -> None:
        # D1. `ci_lower` is the t bound on the mean, full stop. It used to be
        # `min(t, hl)`, so on every shape where HL was the smaller number the
        # HL leg silently WAS the gate. `hl_side` pins that this fixture set
        # actually covers that case rather than only cases where t binds.
        verdict = money_verdict(*_paired(deltas, _flat_baseline(40)), threshold=1000.0)
        side = (
            "equal"
            if verdict.ci_lower_hl == verdict.ci_lower_mean
            else ("below" if verdict.ci_lower_hl < verdict.ci_lower_mean else "above")
        )
        assert side == hl_side
        assert verdict.ci_lower == verdict.ci_lower_mean

    def test_a_sparse_but_real_gain_passes_where_the_conjunction_was_unpassable(self) -> None:
        # D1 TEETH-CHECK, straight from adversarial/p6b. 40 of 64 seeds are
        # EXACTLY unchanged and 24 gain $1,000,000 each: a true +$375,000 per
        # seed. Every Walsh average of two unchanged seeds is itself zero, so
        # the old HL leg reported a $0 bound and the conjunction could not
        # pass this at ANY effect size.
        deltas = [0.0] * 40 + [1_000_000.0] * 24
        cand, base = _paired(deltas, _flat_baseline(64))
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.mean_delta == 375_000.0
        assert verdict.median_delta == 0.0
        assert verdict.ci_lower_hl == 0.0  # the leg that used to veto this
        assert verdict.ci_lower == pytest.approx(273176.89062849234, abs=1e-6)
        assert verdict.n_regressed == 0
        assert verdict.vetoes == ()
        assert verdict.blockers == ()
        assert verdict.passed is True

    def test_the_hl_diagnostic_is_recorded_and_never_decides_the_jackpot(self) -> None:
        # CORRECTED (N2). Was
        # `test_jackpot_that_regresses_most_seeds_is_blocked_not_passed` and
        # asserted `blockers == ("half_the_seeds_regress",)`, pinning the
        # count rule. The p4 fixture's verdict now lives in
        # `TestRegressionCountsAreDiagnosticsNow`; what survives here is the
        # part that is still true -- the HL bound is computed, recorded, and
        # decides nothing.
        deltas = [-3000.0] * 39 + [12000.0] * 25
        cand, base = _paired(deltas, _spread_baseline(64, 12558.0))
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.median_delta == -3000.0
        assert verdict.n_regressed == 39
        assert verdict.ci_lower == pytest.approx(1320.14221408821, abs=1e-9)
        assert verdict.ci_lower > 1000.0
        assert verdict.ci_lower_hl == 4500.0  # bounds the pseudomedian, not the median
        assert verdict.ci_lower == verdict.ci_lower_mean
        assert verdict.vetoes == ()

    def test_one_wiped_out_seed_in_twenty_is_stopped_by_the_mean_bound(self) -> None:
        # 19 of 20 seeds improve; one seed loses $100,000 and the true mean is
        # NEGATIVE. The HL diagnostic reads +$2,000 and is ignored.
        #
        # CORRECTED (N1). This test used to be named
        # `test_catastrophic_tail_is_stopped_by_the_mean_bound` and asserted
        # `vetoes == ()` at n=20 as INTENDED behaviour. It was pinning a dead
        # zone: the old `catastrophic_seed` cut was a studentized extreme
        # deviate, which obeys `(mean - min)/sd <= (n-1)/sqrt(n)`, so with
        # k=5 it could not fire below n=27 at ANY loss magnitude while
        # `min_seeds` defaults to 8. The empty tuple was an algebraic
        # impossibility being read as a judgement.
        deltas = [2000.0] * 19 + [-100000.0]
        baseline = [0.0 if i % 2 else 60000.0 for i in range(20)]
        cand, base = _paired(deltas, baseline)
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.ci_lower_hl == 2000.0
        assert verdict.ci_lower_hl > 1000.0
        assert verdict.ci_lower_mean == pytest.approx(-11918.577338758969, abs=1e-9)
        assert verdict.ci_lower == pytest.approx(-11918.577338758969, abs=1e-9)
        assert verdict.vetoes == ()
        assert verdict.blockers == ()
        assert verdict.passed is False


class TestCatastrophicTailIsNotDecidedByN:
    """N1. The same failure SHAPE must get the same verdict at every ``n``."""

    #: adversarial2/q4's closing fixture: all but one seed at +$30,000 and
    #: ONE seed losing $100,000 -- 2.7x the measured champion bank. Under the
    #: studentized cut this PASSED at n=20 and n=26 and was INVALID at n=64:
    #: the identical failure, opposite verdicts, decided only by n.
    N_VALUES = (20, 26, 27, 40, 64)

    @pytest.mark.parametrize("n", (8, *N_VALUES))
    def test_the_guard_reads_that_shape_the_same_way_at_every_n(self, n: int) -> None:
        deltas = [-100000.0] + [30000.0] * (n - 1)
        verdict = money_verdict(*_paired(deltas, _flat_baseline(n)), threshold=1000.0)

        assert verdict.min_delta == -100000.0
        assert verdict.vetoes == ()
        assert verdict.blockers == ()

    @pytest.mark.parametrize("n", N_VALUES)
    def test_the_whole_verdict_is_the_same_at_every_n_q4_measured(self, n: int) -> None:
        # n=8 is excluded here and only here: at eight seeds the BOUND cannot
        # resolve this effect (ci_lower -$17,037), which is a precision fact
        # about n and not a guard firing. q4 measured n = 20, 26, 27, 40, 64.
        deltas = [-100000.0] + [30000.0] * (n - 1)
        verdict = money_verdict(*_paired(deltas, _flat_baseline(n)), threshold=1000.0)
        assert verdict.ci_lower > 1000.0
        assert verdict.passed is True

    def test_the_verdict_is_literally_constant_across_that_n_sweep(self) -> None:
        verdicts = [
            money_verdict(
                *_paired([-100000.0] + [30000.0] * (n - 1), _flat_baseline(n)), threshold=1000.0
            )
            for n in self.N_VALUES
        ]
        assert {(v.vetoes, v.blockers, v.passed) for v in verdicts} == {((), (), True)}

    def test_the_guard_has_no_studentized_ceiling(self) -> None:
        # The old cut `min(0, mean) - k*sd` could not exceed (n-1)/sqrt(n)
        # standard deviations, so at n=20 a seed losing TEN MILLION DOLLARS
        # produced `vetoes == ()`. A dollar floor on an order statistic has
        # no such ceiling.
        for n in (8, 20, 26):
            deltas = [-10_000_000.0] * (n // 4) + [1000.0] * (n - n // 4)
            verdict = money_verdict(*_paired(deltas, _flat_baseline(n)), min_seeds=n)
            assert verdict.blockers == ("catastrophic_tail",)


class TestCatastrophicTailBlocker:
    """The single magnitude-aware lower-tail guard that replaced N1 + N2."""

    def test_it_blocks_a_real_regression_the_count_rule_permitted(self) -> None:
        # PROPERTY 1a, adversarial2/q5(b) verbatim. 31 of 64 seeds are
        # BANKRUPTED (-$37,000, the whole measured bank) while 33 gain
        # $80,000. `2 * n_regressed >= n` is 62 >= 64 -- FALSE -- so the
        # count rule reported `blockers = ()` and the run PASSED.
        deltas = [-37000.0] * 31 + [80000.0] * 33
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.n_regressed == 31  # one short of the old count trigger
        assert verdict.tail_quantile == -37000.0
        assert verdict.ci_lower > 1000.0  # the bound alone would promote this
        assert verdict.blockers == ("catastrophic_tail",)
        assert verdict.passed is False

    def test_it_permits_a_real_gain_the_count_rule_refused(self) -> None:
        # PROPERTY 1b, adversarial2/q5(a) verbatim. 32 seeds are worse by
        # FIFTY CENTS and 32 gain a million dollars: a true +$500,000/seed.
        # The count rule blocked this, and ramping the gain to 1e12 never
        # passed -- unbounded true improvement, structurally refused.
        deltas = [-0.5] * 32 + [1_000_000.0] * 32
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.n_regressed == 32  # exactly the old count trigger
        assert verdict.mean_delta == pytest.approx(499_999.75, abs=1e-9)
        assert verdict.tail_quantile == -0.5
        assert verdict.ci_lower == pytest.approx(394837.2422574607, abs=1e-6)
        assert verdict.blockers == ()
        assert verdict.passed is True

    def test_it_permits_the_realistic_sparse_gain(self) -> None:
        # PROPERTY 2, adversarial2/q5(a) row 3. A knob that costs $200 on 40
        # seeds and earns $20,000 on 24 is a true +$7,375/seed -- more than
        # SEVEN TIMES the promotion threshold -- and the count rule refused it.
        deltas = [-200.0] * 40 + [20000.0] * 24
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.n_regressed == 40
        assert verdict.mean_delta == pytest.approx(7375.0, abs=1e-9)
        assert verdict.tail_quantile == -200.0
        assert verdict.ci_lower == pytest.approx(5318.173190695476, abs=1e-6)
        assert verdict.blockers == ()
        assert verdict.passed is True

    @pytest.mark.parametrize("n", [8, 20, 26, 27, 40, 64])
    def test_it_fires_at_every_n_from_min_seeds_upward(self, n: int) -> None:
        # PROPERTY 3. A quarter of the seeds bankrupted at -$37,000 while the
        # rest gain $80,000: the bound clears the threshold at every n, and
        # the guard stops it at every n -- including n=8 and n=20, the whole
        # of the old veto's dead zone.
        n_bad = n // 4
        deltas = [-37000.0] * n_bad + [80000.0] * (n - n_bad)
        verdict = money_verdict(*_paired(deltas, _flat_baseline(n)), threshold=1000.0, min_seeds=8)

        assert verdict.ci_lower > 1000.0
        assert verdict.tail_quantile < -19000.0
        assert verdict.blockers == ("catastrophic_tail",)
        assert verdict.passed is False

    def test_it_fires_at_n_eight_on_two_bankrupted_seeds(self) -> None:
        # PROPERTY 3, stated as a single explicit fixture at `min_seeds`.
        deltas = [-37000.0, -37000.0, 80000.0, 80000.0, 80000.0, 80000.0, 80000.0, 80000.0]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(8)), threshold=1000.0)

        assert verdict.n_seeds == 8
        assert verdict.tail_quantile == pytest.approx(-31150.0, abs=1e-9)
        assert verdict.ci_lower > 1000.0
        assert verdict.blockers == ("catastrophic_tail",)
        assert verdict.passed is False

    @pytest.mark.parametrize("epsilon", [0.5, -0.5])
    def test_one_grid_step_on_one_seed_does_not_flip_the_verdict(self, epsilon: float) -> None:
        # PROPERTY 4, adversarial2/q5(c) verbatim. Flipping seed 31 from
        # +$0.50 to -$0.50 -- ONE money grid step -- took `n_regressed` from
        # 31 to 32 and flipped PASS to FAIL while the bound moved under two
        # cents. A dollar floor on an order statistic cannot do that.
        deltas = [-500.0] * 31 + [epsilon] + [9000.0] * 32
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.n_regressed == (32 if epsilon < 0 else 31)
        assert verdict.tail_quantile == -500.0
        assert verdict.ci_lower > 1000.0
        assert verdict.blockers == ()
        assert verdict.passed is True

    def test_the_bound_and_the_tail_both_move_by_cents_for_a_cent_of_input(self) -> None:
        # PROPERTY 4 as the general statement: the guard's statistic is
        # 1-Lipschitz in every seed, so no single grid step can move it far
        # enough to change a verdict that was not already on the line.
        base_deltas = [-500.0] * 31 + [0.5] + [9000.0] * 32
        flipped = [-500.0] * 31 + [-0.5] + [9000.0] * 32
        first = money_verdict(*_paired(base_deltas, _flat_baseline(64)), threshold=1000.0)
        second = money_verdict(*_paired(flipped, _flat_baseline(64)), threshold=1000.0)

        assert abs(first.tail_quantile - second.tail_quantile) <= 1.0
        assert abs(first.ci_lower - second.ci_lower) < 0.05

    def test_more_catastrophes_never_switch_the_guard_off(self) -> None:
        # PROPERTY 5, adversarial2/q4's masking fixture. The studentized cut
        # fired for 1 and 2 catastrophic seeds at -$200,000 and went SILENT
        # at 3 and 4, because sd inflates faster than the cut moves. An order
        # statistic is monotone: worsening any seed can only lower it.
        fired = []
        for n_bad in range(65):
            deltas = [-200000.0] * n_bad + [1000.0] * (64 - n_bad)
            verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
            fired.append(bool(verdict.blockers))

        first_true = fired.index(True)
        assert all(fired[k] for k in range(first_true, 65))  # an up-set: never switches off
        assert first_true == 10  # 10 of 64 = 15.6%, just over the 15% tail
        assert fired[1:5] == [False] * 4  # no alternation where masking used to live

    def test_making_a_catastrophe_worse_never_switches_the_guard_off(self) -> None:
        # PROPERTY 5 along the magnitude axis rather than the count axis.
        tails = []
        for loss in (20000.0, 50000.0, 200000.0, 1e9, 1e15):
            deltas = [-loss] * 12 + [1000.0] * 52
            verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
            tails.append(verdict.tail_quantile)
            assert verdict.blockers == ("catastrophic_tail",)
        assert all(a > b for a, b in zip(tails, tails[1:], strict=False))

    def test_the_guard_ignores_the_dispersion_of_the_differences(self) -> None:
        # CORRECTED (N1). This fixture used to be
        # `test_the_veto_tracks_the_dispersion_of_the_differences` and
        # asserted that the SAME -$3,000 seed is "catastrophic" in a tight arm
        # and "ordinary" in a loose one. Scaling by sd(d) is exactly what
        # produced the masking above: the adversary buys silence by adding
        # noise. The dollar floor is scale-free, so both arms now agree.
        tight = [1500.0 + 10.0 * (i % 33) for i in range(64)]
        tight[0] = -3000.0
        loose = [1500.0 + 200.0 * (i % 33) for i in range(64)]
        loose[0] = -3000.0

        tight_verdict = money_verdict(*_paired(tight, _flat_baseline(64)), threshold=1000.0)
        loose_verdict = money_verdict(*_paired(loose, _flat_baseline(64)), threshold=1000.0)
        assert tight_verdict.blockers == loose_verdict.blockers == ()
        assert tight_verdict.passed is loose_verdict.passed is True

    def test_the_guard_is_invariant_to_the_baseline_arms_dispersion(self) -> None:
        # D4 TEETH-CHECK, the adversarial/p8 reproduction, retained. IDENTICAL
        # candidate behaviour against four baselines that differ only in how
        # much money varies seed to seed. Scaling the cut by sd(baseline
        # LEVELS) fired at sd $512 and was silent at sd $40,951.
        deltas = [1500.0 + 40.0 * (i % 37) for i in range(64)]
        deltas[0] = -3000.0
        verdicts = [
            money_verdict(*_paired(deltas, _spread_baseline(64, sd)), threshold=1000.0)
            for sd in (512.0, 2048.0, 12558.0, 40951.0)
        ]
        assert [v.vetoes for v in verdicts] == [()] * 4
        assert [v.blockers for v in verdicts] == [()] * 4
        assert [v.passed for v in verdicts] == [True] * 4

    def test_a_uniformly_degraded_arm_fails_on_the_bound_with_no_guard_at_all(self) -> None:
        # The silent-degradation signature: every seed ~-$13,240 with small
        # dispersion. The BOUND is the instrument for a uniform regression --
        # it reads far below the threshold -- and the tail guard stays quiet,
        # so `harness.money_gate`'s large-negative-delta diagnostic survives.
        deltas = [-13240.0 + 100.0 * i for i in range(64)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.mean_delta < -5000.0
        assert verdict.ci_lower < 0.0
        assert verdict.vetoes == ()
        assert verdict.blockers == ()
        assert verdict.passed is False

    def test_the_floor_clears_the_worst_tail_measured_on_a_real_passing_arm(self) -> None:
        # The lower anchor of the $19,000 derivation. `empirical/arms2.json`
        # arm `improve_feed_8` is a REAL +$5,510/seed improvement whose bound
        # clears the threshold at $2,137, and its 15th-percentile seed is
        # -$9,835. Nothing that reaches promotion may be within reach of the
        # floor; this pins the 1.93x margin.
        worst_real_tail = -9835.0
        deltas = [worst_real_tail] * 11 + [12000.0] * 53
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.tail_quantile == pytest.approx(worst_real_tail, abs=1e-9)
        assert verdict.blockers == ()

    def test_the_floor_fires_below_a_full_bank_loss(self) -> None:
        # The upper anchor: the measured champion bank against the tape is
        # $37,167, so a seed at -$37,167 has lost everything it had.
        deltas = [-37167.0] * 11 + [25000.0] * 53
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)

        assert verdict.tail_quantile == pytest.approx(-37167.0, abs=1e-9)
        assert verdict.ci_lower > 1000.0
        assert verdict.blockers == ("catastrophic_tail",)

    def test_both_knobs_are_overridable(self) -> None:
        deltas = [-25000.0] * 16 + [90000.0] * 48
        assert money_verdict(*_paired(deltas, _flat_baseline(64))).blockers == (
            "catastrophic_tail",
        )
        # Raise the floor above the tail: the same run stops being blocked.
        assert (
            money_verdict(
                *_paired(deltas, _flat_baseline(64)), catastrophic_tail_floor=30000.0
            ).blockers
            == ()
        )
        # Or move the quantile past the 16 bad seeds (25% of 64).
        assert (
            money_verdict(
                *_paired(deltas, _flat_baseline(64)), catastrophic_tail_quantile=0.40
            ).blockers
            == ()
        )


class TestRegressionCountsAreDiagnosticsNow:
    def test_an_exactly_even_split_of_tiny_losses_is_no_longer_blocked(self) -> None:
        # CORRECTED (N2). This fixture used to assert
        # `blockers == ("half_the_seeds_regress",)`. 32 seeds worse by $100
        # against 32 seeds better by $50,000 is a true +$24,950/seed; refusing
        # it was the structural unpassability D1 removed from the HL leg,
        # reintroduced with a harsher trigger.
        deltas = [-100.0] * 32 + [50000.0] * 32
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.n_regressed == 32  # still RECORDED
        assert verdict.blockers == ()  # but no longer GATING
        assert verdict.passed is True

    def test_one_seed_short_of_half_gets_the_same_verdict_as_half(self) -> None:
        # The count rule's knife edge, stated as the property it violated.
        even = money_verdict(
            *_paired([-100.0] * 32 + [50000.0] * 32, _flat_baseline(64)), threshold=1000.0
        )
        odd = money_verdict(
            *_paired([-100.0] * 31 + [50000.0] * 33, _flat_baseline(64)), threshold=1000.0
        )
        assert (even.n_regressed, odd.n_regressed) == (32, 31)
        assert even.blockers == odd.blockers == ()
        assert even.passed is odd.passed is True

    def test_unchanged_seeds_are_still_not_counted_as_regressions(self) -> None:
        # A knob that does not bite on most seeds leaves them at EXACTLY
        # zero, so the median is zero while nothing got worse. `n_regressed`
        # counts strictly negative deltas and keeps reporting that honestly.
        deltas = [0.0] * 40 + [20000.0] * 24
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.median_delta == 0.0
        assert verdict.n_regressed == 0
        assert verdict.blockers == ()
        assert verdict.passed is True

    def test_the_diagnostics_survive_on_the_verdict(self) -> None:
        deltas = [-100.0] * 19 + [4000.0] * 21
        verdict = money_verdict(*_paired(deltas, _flat_baseline(40)), threshold=1000.0)
        assert verdict.n_regressed == 19
        assert verdict.median_delta == 4000.0
        assert verdict.min_delta == -100.0
        assert verdict.blockers == ()

    def test_the_p4_jackpot_now_passes_and_that_is_a_decision_not_an_accident(self) -> None:
        # HONEST COVERAGE CHANGE. The adversarial/p4 fixture the count rule
        # was introduced for: 39 of 64 seeds LOSE $3,000 and 25 gain $12,000,
        # a true +$2,859/seed whose bound clears the threshold. Under the
        # count rule this was blocked; under a magnitude-aware guard at the
        # measured default floor it PASSES, because -$3,000 is 8% of the
        # $37,167 bank and real healthy arms produce 15th-percentile seeds
        # three times worse than that (-$9,835 on `arms2/improve_feed_8`).
        # Refusing it would need a $2,500 floor, which would block real
        # promotable arms. The knob is the lever, and it is recorded.
        deltas = [-3000.0] * 39 + [12000.0] * 25
        cand, base = _paired(deltas, _spread_baseline(64, 12558.0))

        default = money_verdict(cand, base, threshold=1000.0)
        assert default.median_delta == -3000.0
        assert default.n_regressed == 39
        assert default.tail_quantile == -3000.0
        assert default.ci_lower > 1000.0
        assert default.blockers == ()
        assert default.passed is True

        strict = money_verdict(cand, base, threshold=1000.0, catastrophic_tail_floor=2500.0)
        assert strict.blockers == ("catastrophic_tail",)
        assert strict.passed is False


class TestMoneyVerdictVetoes:
    def test_exact_no_op_fails_without_a_degeneracy_veto(self) -> None:
        cand, base = _paired([0.0] * 12, _flat_baseline(12))
        verdict = money_verdict(cand, base, threshold=1000.0)
        assert verdict.mean_delta == 0.0
        assert verdict.sd_delta == 0.0
        assert verdict.ci_lower == 0.0
        assert "degenerate_dispersion" not in verdict.vetoes
        assert verdict.vetoes == ()
        assert verdict.passed is False

    def test_constant_nonzero_deltas_are_vetoed_as_degenerate_dispersion(self) -> None:
        # Zero dispersion across independent seeds is a harness fault, never
        # certainty — the bound reads $2,500 and the run is still refused.
        cand, base = _paired([2500.0] * 10, _flat_baseline(10))
        verdict = money_verdict(cand, base, threshold=1000.0)
        assert verdict.ci_lower_mean == 2500.0
        assert verdict.ci_lower_hl == 2500.0
        assert verdict.vetoes == ("degenerate_dispersion",)
        assert verdict.passed is False

    def test_a_single_grid_step_of_wobble_does_not_evade_degenerate_dispersion(self) -> None:
        # D6 TEETH-CHECK, from adversarial/p3. Money lives on a $0.50 grid, so
        # an exact `sd == 0` test is evaded by one seed differing by one grid
        # step: 2500.0 on 63 seeds and 2500.5 on one gives sd $0.0625 and used
        # to sail straight through to PASS.
        deltas = [2500.0] * 63 + [2500.5]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.sd_delta == pytest.approx(0.0625, abs=1e-9)
        assert verdict.ci_lower > 1000.0
        assert verdict.vetoes == ("degenerate_dispersion",)
        assert verdict.passed is False

    @pytest.mark.parametrize("wobble", [0.5, 30.0, 31.0, 100.0, 500.0, 1000.0])
    def test_the_dollar_sized_wobble_hole_is_closed_by_the_effect_relative_leg(
        self, wobble: float
    ) -> None:
        # N5, adversarial2/q3. The sd tolerance used to be a fixed number of
        # DOLLARS (1e-4 of the money scale, ~$3.72 here), so q3's binary
        # search found that ~$30 of wobble on ONE of 64 seeds walked straight
        # through it and flipped the verdict INVALID -> PASS. The dollar
        # figure cannot simply be widened -- real arms live down there
        # (`survey2/fert_0`: mean $1.31, sd $3.40) -- so the veto gained a leg
        # anchored on the EFFECT, whose tolerance here is 5% of $2,500 = $125.
        deltas = [2500.0] * 63 + [2500.0 + wobble]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.sd_delta < 0.05 * abs(verdict.mean_delta)
        assert verdict.vetoes == ("degenerate_dispersion",)
        assert verdict.passed is False

    def test_the_evasion_now_costs_thirty_one_times_more_wobble(self) -> None:
        # The measured width of what is left. Re-injecting the old fixed-dollar
        # rule and running this same search puts the smallest evading
        # single-seed wobble at $32.31; anchoring on the effect moves it to
        # $1,008, because sd(one wobbled seed of 64) is w*sqrt(63)/64 and that
        # has to exceed 5% of the $2,500 effect. (q3 reported "~$30" from a
        # search bracketed at [0, 1000], which saturates.)
        low, high = 0.0, 100_000.0
        for _ in range(80):
            middle = 0.5 * (low + high)
            deltas = [2500.0] * 63 + [2500.0 + middle]
            if money_verdict(*_paired(deltas, _flat_baseline(64))).vetoes:
                low = middle
            else:
                high = middle
        assert high == pytest.approx(1008.0, rel=0.02)

    def test_a_uniform_million_dollar_gain_stays_invalid_when_one_seed_wobbles(self) -> None:
        # N5's sharpest form in q3: a $1,000,000/seed "gain" with sd 0 is a
        # harness fault across independent seeds, and the old rule agreed --
        # until ONE seed was moved by ~$3,800, at which point the SAME run
        # became a PASS, because the tolerance did not scale with the effect.
        # It does now: at a $1,000,000 effect the tolerance is $50,000.
        for wobble in (0.0, 3800.0, 100_000.0):
            deltas = [*[1_000_000.0] * 63, 1_000_000.0 + wobble]
            verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
            assert verdict.vetoes == ("degenerate_dispersion",)
            assert verdict.passed is False

    def test_a_real_low_effect_arm_is_no_longer_false_vetoed(self) -> None:
        # N5's other half. `survey2/fert_0` is a REAL measured arm -- mean
        # $1.31, sd $3.40 over 32 seeds -- and the old $3.72 dollar tolerance
        # called it INVALID ("rerun the measurement") when the right answer is
        # FAIL on the bound. It is the only one of the 64 measured arms that
        # sat under $3.72; the floor is now $0.372 and nothing sits under it.
        deltas = [1.31 + 3.4 * math.sin(i * 1.9) for i in range(32)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(32)), threshold=1000.0)
        assert verdict.sd_delta == pytest.approx(2.407, abs=0.01)
        assert verdict.sd_delta > 0.05 * abs(verdict.mean_delta)
        assert verdict.vetoes == ()
        assert verdict.passed is False

    def test_a_sparse_knob_leaving_most_seeds_at_exactly_zero_is_not_degenerate(self) -> None:
        # A knob that does not bite leaves seeds at EXACTLY 0.0 -- measured at
        # 18 of 40 on `empirical2/sparse_scan` arm `milk_crash_trigger=0`.
        # Its `sd_delta` is far above 5% of the mean, so neither leg fires and
        # the sparse gains the remediation exists to let through get through.
        deltas = [0.0] * 40 + [float(20000 + 7 * i) for i in range(24)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.vetoes == ()
        assert verdict.passed is True

    def test_every_real_arm_clears_the_dispersion_ratio_by_at_least_thirteen_times(self) -> None:
        # Calibration. Across the 54 real arms with a nonzero mean_delta the
        # SMALLEST sd_delta/|mean_delta| is 0.6925 (`a2_regression` and
        # `a2_improvement_large`). The 0.05 trigger is 13.9x below that.
        worst_real_ratio = 0.6925
        deltas = [22548.85 + 15615.37 * math.sin(i * 1.3) for i in range(40)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(40)), threshold=1000.0)
        assert verdict.sd_delta / abs(verdict.mean_delta) > 0.05
        assert worst_real_ratio / 0.05 == pytest.approx(13.85, abs=0.01)
        assert verdict.vetoes == ()

    def test_the_dispersion_ratio_is_an_overridable_knob(self) -> None:
        deltas = [2500.0 + 400.0 * math.sin(i * 1.1) for i in range(64)]
        assert money_verdict(*_paired(deltas, _flat_baseline(64))).vetoes == ()
        tightened = money_verdict(
            *_paired(deltas, _flat_baseline(64)), degenerate_dispersion_ratio=0.5
        )
        assert tightened.vetoes == ("degenerate_dispersion",)

    def test_a_real_arms_dispersion_is_nowhere_near_the_degeneracy_tolerance(self) -> None:
        # The tolerance has to sit in the gap between "constant to within the
        # money grid" and any real arm. The SMALLEST paired per-seed sd ever
        # measured here is $6,214; the tolerance at this money scale is ~$3.70.
        deltas = [3000.0 + 6214.0 * math.sin(i * 1.7) for i in range(64)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        assert verdict.sd_delta > 4000.0
        assert verdict.vetoes == ()

    def test_too_few_seeds_never_passes_and_reports_infinite_lower_bounds(self) -> None:
        cand, base = _paired([50000.0] * 4, _flat_baseline(4))
        verdict = money_verdict(cand, base, threshold=1000.0, min_seeds=8)
        assert verdict.n_seeds == 4
        assert "too_few_seeds" in verdict.vetoes
        assert verdict.ci_lower_mean == -math.inf
        assert verdict.ci_lower_hl == -math.inf
        assert verdict.ci_lower == -math.inf
        assert verdict.hl_skip == -1
        assert verdict.t_crit == 0.0
        assert verdict.passed is False

    def test_mismatched_seed_sets_raise_value_error(self) -> None:
        cand = {1: 100.0, 2: 200.0}
        base = {1: 100.0, 3: 200.0}
        with pytest.raises(ValueError, match="seed"):
            money_verdict(cand, base)

    def test_any_veto_forces_passed_false_against_a_huge_bound(self) -> None:
        # TEETH-CHECK. A veto invalidates the run; it can never be outvoted
        # by the size of the measured gain.
        cand, base = _paired([50000.0] * 20, _flat_baseline(20))
        verdict = money_verdict(cand, base, threshold=1000.0, extra_vetoes=("candidate_crash",))
        assert verdict.ci_lower_hl == 50000.0
        assert "candidate_crash" in verdict.vetoes
        assert verdict.passed is False

    def test_vetoes_and_blockers_are_separate_tuples(self) -> None:
        # They mean different things downstream: a veto is INVALID (exit 2,
        # rerun the measurement), a blocker is FAIL (exit 1, keep tuning).
        # A wiped-out lower tail is a property of the CANDIDATE and is
        # deterministic on rerun, so it is a blocker and not a veto.
        deltas = [-37000.0] * 16 + [80000.0] * 48
        verdict = money_verdict(
            *_paired(deltas, _flat_baseline(64)),
            threshold=1000.0,
            extra_vetoes=("candidate_crash",),
        )
        assert verdict.vetoes == ("candidate_crash",)
        assert verdict.blockers == ("catastrophic_tail",)

    def test_vetoes_are_sorted_and_deduplicated(self) -> None:
        cand, base = _paired([2500.0] * 4, _flat_baseline(4))
        verdict = money_verdict(
            cand,
            base,
            threshold=1000.0,
            min_seeds=8,
            extra_vetoes=("opponent_crash", "candidate_crash", "opponent_crash"),
        )
        assert verdict.vetoes == (
            "candidate_crash",
            "degenerate_dispersion",
            "opponent_crash",
            "too_few_seeds",
        )

    def test_threshold_is_strict_greater_than(self) -> None:
        deltas = [1200.0, 900.0, 4400.0, 2800.0, 2100.0, 1900.0, 5000.0, 1050.0, 700.0, 1500.0]
        cand, base = _paired(deltas, _flat_baseline(10))
        loose = money_verdict(cand, base, threshold=0.0)
        assert loose.passed is True
        exact = money_verdict(cand, base, threshold=loose.ci_lower)
        assert exact.ci_lower == loose.ci_lower
        assert exact.passed is False


class TestMde80:
    def test_mde_multiplier_is_the_t_sum_at_the_runs_own_df(self) -> None:
        # D8. The z-sum 2.486475 is the n -> inf limit and understates the
        # requirement at every finite n: 1.22% low at the default n=64.
        assert mde_multiplier(64) == pytest.approx(2.516766, abs=1e-6)
        assert mde_multiplier(64) > 2.486475
        assert mde_multiplier(8) == pytest.approx(
            student_t_ppf(0.95, 7) + student_t_ppf(0.80, 7), abs=1e-15
        )
        # ...and it converges DOWN to the normal constant from above.
        assert mde_multiplier(100_000) == pytest.approx(2.486475, abs=1e-4)
        assert mde_multiplier(1) == math.inf

    def test_mde_80_is_the_multiplier_times_the_standard_error(self) -> None:
        deltas = [float(x) for x in range(1000, 8001, 1000)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(8)), threshold=1000.0)
        assert verdict.mde_80 == pytest.approx(mde_multiplier(8) * verdict.stderr, abs=1e-12)

    def test_mde_80_is_an_effect_ABOVE_the_threshold_not_an_absolute_effect(self) -> None:
        # What the number does not promise: it is measured from the threshold
        # the gate tests against, not from zero. An arm whose true per-seed
        # gain equals mde_80 exactly sits ON the threshold-relative boundary
        # only if the threshold is zero.
        deltas = [2000.0 + 500.0 * math.sin(i) for i in range(64)]
        verdict = money_verdict(*_paired(deltas, _flat_baseline(64)), threshold=1000.0)
        detectable = verdict.threshold + verdict.mde_80
        assert detectable > verdict.mde_80
        assert verdict.mean_delta > detectable
        assert verdict.passed is True


class TestVerdictUsesTheExportedHelpers:
    def test_the_verdicts_bounds_are_the_public_helpers_own_output(self) -> None:
        # D9. These helpers are tested API; if `money_verdict` reimplements
        # them inline, every test of them is testing something the gate does
        # not run. Pin them to the shipped path.
        deltas = [1200.0, -300.0, 4400.0, 800.0, 2100.0, 90.0, 5000.0, -50.0, 700.0, 1500.0]
        cand, base = _paired(deltas, _flat_baseline(10))
        verdict = money_verdict(cand, base, threshold=1000.0, min_seeds=8)

        assert verdict.ci_lower_mean == t_lower_bound(
            verdict.mean_delta, verdict.sd_delta, verdict.n_seeds, verdict.alpha
        )
        assert verdict.ci_lower_hl == hl_lower_bound(deltas, verdict.alpha)
        assert verdict.hl_shift == hodges_lehmann(deltas)
        assert verdict.mde_80 == mde_multiplier(verdict.n_seeds, verdict.alpha) * verdict.stderr

    def test_a_zero_dispersion_bound_still_routes_through_t_lower_bound(self) -> None:
        cand, base = _paired([2500.0] * 10, _flat_baseline(10))
        verdict = money_verdict(cand, base, threshold=1000.0, min_seeds=8)
        assert verdict.ci_lower_mean == t_lower_bound(2500.0, 0.0, 10) == 2500.0


class TestExistingSurfaceIsUntouched:
    def test_existing_gate_verdict_surface_is_unchanged(self) -> None:
        # TEETH-CHECK. The money gate is purely additive: `GateVerdict` keeps
        # its five fields and `verdict.passed` keeps meaning WIN RATE.
        assert [f.name for f in fields(GateVerdict)] == [
            "n_games",
            "score",
            "rate",
            "ci_lower",
            "passed",
        ]
        verdict = gate_verdict(wins=60, losses=40, ties=0)
        assert verdict.n_games == 100
        assert verdict.score == 60
        assert verdict.rate == pytest.approx(0.6)
        assert verdict.ci_lower == pytest.approx(0.502003, abs=1e-6)
        assert verdict.passed is True
        assert MoneyVerdict is not GateVerdict
