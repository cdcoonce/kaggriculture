"""Wilson score interval and gate-verdict math (eval protocol, issue #4)."""

from __future__ import annotations

import pytest
from harness.stats import gate_verdict, wilson_lower_bound


class TestWilsonLowerBound:
    def test_p_hat_0_6_n_500(self) -> None:
        # Hand-verified with a Decimal-precision reimplementation of the
        # Wilson score formula (z=1.959964): 0.5564541223554871555...
        assert wilson_lower_bound(300, 500) == pytest.approx(0.556454, abs=1e-6)

    def test_p_hat_0_52_n_500(self) -> None:
        # Decimal-precision hand check: 0.4762234526114012383...
        assert wilson_lower_bound(260, 500) == pytest.approx(0.476223, abs=1e-6)

    def test_p_hat_0_5_n_500(self) -> None:
        # Decimal-precision hand check: 0.4563412649607354107...
        assert wilson_lower_bound(250, 500) == pytest.approx(0.456341, abs=1e-6)

    @pytest.mark.parametrize("p_hat", [0.1, 0.3, 0.5, 0.7, 0.9])
    def test_lower_bound_is_below_observed_rate(self, p_hat: float) -> None:
        n = 200
        assert wilson_lower_bound(p_hat * n, n) < p_hat


class TestGateVerdict:
    def test_passes_at_60_percent_of_500(self) -> None:
        verdict = gate_verdict(wins=300, losses=200, ties=0)
        assert verdict.n_games == 500
        assert verdict.score == 300
        assert verdict.rate == pytest.approx(0.6)
        assert verdict.ci_lower == pytest.approx(0.556454, abs=1e-6)
        assert verdict.passed is True

    def test_fails_at_52_percent_of_500(self) -> None:
        # Load-bearing teeth check: this gate exists to refuse noise
        # promotion, and 52% at n=500 is exactly the kind of thin-margin
        # result it must reject.
        verdict = gate_verdict(wins=260, losses=240, ties=0)
        assert verdict.rate == pytest.approx(0.52)
        assert verdict.ci_lower == pytest.approx(0.476223, abs=1e-6)
        assert verdict.passed is False

    def test_fails_at_50_percent_of_500(self) -> None:
        verdict = gate_verdict(wins=250, losses=250, ties=0)
        assert verdict.ci_lower == pytest.approx(0.456341, abs=1e-6)
        assert verdict.passed is False

    def test_ties_are_weighted_as_half_wins(self) -> None:
        # (w=240, l=220, t=40) has score 260, identical to 260 straight wins.
        weighted = gate_verdict(wins=240, losses=220, ties=40)
        straight = gate_verdict(wins=260, losses=240, ties=0)
        assert weighted.score == straight.score == 260
        assert weighted.n_games == straight.n_games == 500
        assert weighted == straight
