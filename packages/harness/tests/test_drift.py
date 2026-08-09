"""Offline release-channel pin-drift check (issue #33)."""

from __future__ import annotations

from harness.drift import EXPECTED_MARKET_PARAMS, check_release_drift


def test_no_drift_against_installed_engine() -> None:
    result = check_release_drift()

    assert result.drifted is False
    assert result.version_mismatch is False
    assert result.param_mismatches == []


def test_market_param_mutation_trips_drift() -> None:
    mutated_params = {
        **EXPECTED_MARKET_PARAMS,
        "WHEAT": {**EXPECTED_MARKET_PARAMS["WHEAT"], "base": 999},
    }

    result = check_release_drift(installed_market_params=mutated_params)

    assert result.drifted is True
    assert any("WHEAT.base" in mismatch for mismatch in result.param_mismatches)


def test_version_mutation_trips_drift() -> None:
    result = check_release_drift(installed_version="1.32.5")

    assert result.drifted is True
    assert result.version_mismatch is True
