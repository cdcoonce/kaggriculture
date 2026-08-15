"""Paired money-difference gate math — t bound, HL bound, vetoes (issue #4)."""

from __future__ import annotations

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

# (n, M, k, exact one-sided alpha) — recomputed by integer subset-sum DP and
# cross-checked against exhaustive 2**n enumeration for every n <= 16.
SIGNED_RANK_TABLE = [
    (6, 21, 3, Fraction(3, 64)),
    (7, 28, 4, Fraction(5, 128)),
    (8, 36, 6, Fraction(5, 128)),
    (10, 55, 11, Fraction(43, 1024)),
    (12, 78, 18, Fraction(189, 4096)),
]
SIGNED_RANK_LARGE = [
    (20, 210, 61, 0.048653602600097656),
    (40, 820, 287, 0.04861724743295781),
    (60, 1830, 691, 0.04931442483830082),
    (64, 2080, 794, 0.04974316507678737),
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
            assert Fraction(sum(signed_rank_null_counts(n)[:k]), 2**n) == exact
            assert alpha == pytest.approx(float(exact), abs=1e-15)
        for n, m, k, exact_float in SIGNED_RANK_LARGE:
            assert n * (n + 1) // 2 == m
            skip, alpha = signed_rank_skip_count(n)
            assert skip == k
            assert alpha == pytest.approx(exact_float, abs=1e-9)

    @pytest.mark.parametrize("n", list(range(6, 65)))
    def test_signed_rank_exact_alpha_never_exceeds_nominal(self, n: int) -> None:
        skip, alpha = signed_rank_skip_count(n, 0.05)
        assert skip is not None
        assert alpha <= 0.05
        # ...and it is the LARGEST such skip: one more would overshoot.
        counts = signed_rank_null_counts(n)
        assert Fraction(sum(counts[: skip + 1]), 2**n) > Fraction(1, 20)


class TestWalshAverages:
    def test_walsh_averages_has_n_times_n_plus_one_over_two_entries_and_is_sorted(self) -> None:
        diffs = [5.0, -3.0, 11.0, 2.0, 0.5]
        walsh = walsh_averages(diffs)
        assert len(walsh) == 5 * 6 // 2
        assert walsh == sorted(walsh)
        assert min(walsh) == -3.0
        assert max(walsh) == 11.0

    def test_hodges_lehmann_equals_the_median_for_symmetric_input(self) -> None:
        diffs = [-4.0, -1.0, 0.0, 1.0, 4.0]
        assert hodges_lehmann(diffs) == 0.0
        shifted = [d + 250.0 for d in diffs]
        assert hodges_lehmann(shifted) == 250.0

    def test_hl_lower_bound_is_always_one_of_the_walsh_averages(self) -> None:
        diffs = [1200.0, -300.0, 4400.0, 800.0, 2100.0, 90.0, 5000.0, -50.0, 700.0, 1500.0]
        assert hl_lower_bound(diffs) in set(walsh_averages(diffs))


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
        assert verdict.t_crit == pytest.approx(1.8945786050900058, abs=1e-9)
        assert verdict.ci_lower_mean == pytest.approx(2859.246798525569, abs=1e-9)
        assert verdict.hl_shift == 4500.0
        assert verdict.hl_skip == 6
        assert verdict.ci_lower_hl == 3000.0
        assert verdict.ci_lower == pytest.approx(2859.246798525569, abs=1e-9)
        assert verdict.mde_80 == pytest.approx(2153.3505158749117, abs=1e-9)
        assert verdict.vetoes == ()
        assert verdict.passed is True

    def test_jackpot_passes_the_mean_leg_and_is_stopped_by_the_rank_leg(self) -> None:
        # TEETH-CHECK. 32 of 40 seeds get WORSE; eight jackpots drag the mean
        # over the bar. Only the distribution-free rank leg refuses it.
        deltas = [-300.0] * 32 + [14000.0] * 8
        cand, base = _paired(deltas, _flat_baseline(40))
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.ci_lower_mean == pytest.approx(1016.7672081464327, abs=1e-9)
        assert verdict.ci_lower_mean > 1000.0
        assert verdict.ci_lower_hl == -300.0
        assert verdict.ci_lower == -300.0
        assert verdict.vetoes == ()
        assert verdict.passed is False

    def test_catastrophic_tail_passes_the_rank_leg_and_is_stopped_by_the_mean_leg(self) -> None:
        # TEETH-CHECK. 19 of 20 seeds improve; one seed loses $100,000 and the
        # true mean is NEGATIVE. Only the mean leg refuses it.
        deltas = [2000.0] * 19 + [-100000.0]
        # A wide baseline keeps `catastrophic_seed` out of it, so this fixture
        # isolates the mean leg as the sole stopper.
        baseline = [0.0 if i % 2 else 60000.0 for i in range(20)]
        cand, base = _paired(deltas, baseline)
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.ci_lower_hl == 2000.0
        assert verdict.ci_lower_hl > 1000.0
        assert verdict.ci_lower_mean == pytest.approx(-11918.577338758969, abs=1e-9)
        assert verdict.ci_lower == pytest.approx(-11918.577338758969, abs=1e-9)
        assert verdict.vetoes == ()
        assert verdict.passed is False

    def test_catastrophic_seed_veto_stops_what_both_bounds_pass(self) -> None:
        # TEETH-CHECK. Neither bound is sufficient: 63 seeds at +$6,000 clear
        # BOTH legs, and only the veto notices the seed that was torched.
        deltas = [6000.0] * 63 + [-100000.0]
        baseline = [24609.0 if i % 2 else 49725.0 for i in range(64)]
        cand, base = _paired(deltas, baseline)
        verdict = money_verdict(cand, base, threshold=1000.0)

        assert verdict.ci_lower_mean == pytest.approx(1578.8025702979971, abs=1e-9)
        assert verdict.ci_lower_mean > 1000.0
        assert verdict.ci_lower_hl == 6000.0
        assert verdict.ci_lower_hl > 1000.0
        assert "catastrophic_seed" in verdict.vetoes
        assert verdict.passed is False


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
        # certainty — both bounds read $2,500 and the run is still refused.
        cand, base = _paired([2500.0] * 10, _flat_baseline(10))
        verdict = money_verdict(cand, base, threshold=1000.0)
        assert verdict.ci_lower_mean == 2500.0
        assert verdict.ci_lower_hl == 2500.0
        assert verdict.vetoes == ("degenerate_dispersion",)
        assert verdict.passed is False

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
