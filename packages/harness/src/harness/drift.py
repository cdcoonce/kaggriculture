"""Offline release-channel pin-drift check (issue #33).

Compares the installed `kaggle_environments` engine's version and
`MARKET_PARAMS` against a frozen snapshot of transcribed literals. This is
the offline half of #11's two-channel release check -- it catches "the
locally installed engine silently moved off the verified pin", not "a newer
release now exists on PyPI/GitHub".
"""

from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass, field

# Transcribed from docs/recon/engine-mechanics.md:149-161 ("MARKET_PARAMS (lines
# 41-51) -- dumped verbatim"). Do not import this from the engine -- it is the
# EXPECTED value this module checks the installed engine against.
EXPECTED_MARKET_PARAMS: dict[str, dict[str, object]] = {
    "WHEAT": {
        "base": 25,
        "I0": 10000,
        "T": 400,
        "below_func": "sqrt",
        "below_target": 0.80,
        "above_func": "log",
        "above_target": 0.20,
    },
    "CARROT": {
        "base": 35,
        "I0": 10000,
        "T": 450,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sqrt",
        "above_target": 0.70,
    },
    "TOMATO": {
        "base": 60,
        "I0": 10000,
        "T": 200,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "sqrt",
        "above_target": 0.60,
    },
    "STRAWBERRY": {
        "base": 120,
        "I0": 10000,
        "T": 100,
        "below_func": "sqrt",
        "below_target": 0.70,
        "above_func": "linear",
        "above_target": 1.60,
    },
    "MELON": {
        "base": 250,
        "I0": 10000,
        "T": 300,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sq",
        "above_target": 3.60,
    },
    "EGG": {
        "base": 50,
        "I0": 10000,
        "T": 332,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "log",
        "above_target": 0.20,
    },
    "MILK": {
        "base": 160,
        "I0": 10000,
        "T": 122,
        "below_func": "sqrt",
        "below_target": 0.60,
        "above_func": "linear",
        "above_target": 1.60,
    },
    "WOOL": {
        "base": 200,
        "I0": 10000,
        "T": 105,
        "below_func": "log",
        "below_target": 0.20,
        "above_func": "sq",
        "above_target": 3.20,
    },
    "FERTILIZER": {
        "base": 100,
        "I0": 10000,
        "T": 200,
        "below_func": "linear",
        "below_target": 0.40,
        "above_func": "linear",
        "above_target": 0.40,
    },
}

# Pinned to 1.32.6 per #24's decision on #42's verification trail: ladder probe
# (episodes 91106026/91105152, module_version=1.32.6, townCenterSellInterval=24),
# source-level diff (TOWN_CENTER_DEMAND_SCHEDULE removed, MARKET_PARAMS unchanged),
# and byte-exact local reproduction (0/1438 transitions mismatched on each of two
# committed 1.32.6 fixtures).
EXPECTED_ENGINE_VERSION = "1.32.6"


@dataclass(frozen=True)
class DriftResult:
    """Release-channel verdict: installed engine vs. transcribed expected values."""

    drifted: bool
    version_mismatch: bool
    installed_version: str
    expected_version: str
    param_mismatches: list[str] = field(default_factory=list)


def check_release_drift(
    installed_version: str | None = None,
    installed_market_params: dict[str, dict[str, object]] | None = None,
) -> DriftResult:
    """Compare the installed engine's version + MARKET_PARAMS against the
    transcribed expected values. `installed_version`/`installed_market_params`
    are injectable seams for tests; production callers omit both and this
    reads the real installed `kaggle_environments` package.
    """
    if installed_version is None:
        installed_version = importlib.metadata.version("kaggle-environments")
    if installed_market_params is None:
        from kaggle_environments.envs.kaggriculture.kaggriculture import (
            MARKET_PARAMS,
        )

        installed_market_params = MARKET_PARAMS

    version_mismatch = installed_version != EXPECTED_ENGINE_VERSION

    mismatches: list[str] = []
    for product, expected_fields in EXPECTED_MARKET_PARAMS.items():
        installed_fields = installed_market_params.get(product)
        if installed_fields is None:
            mismatches.append(f"{product}: missing from installed MARKET_PARAMS")
            continue
        for field_name, expected_value in expected_fields.items():
            installed_value = installed_fields.get(field_name)
            if installed_value != expected_value:
                mismatches.append(
                    f"{product}.{field_name}: expected {expected_value!r}, "
                    f"installed {installed_value!r}"
                )

    return DriftResult(
        drifted=version_mismatch or bool(mismatches),
        version_mismatch=version_mismatch,
        installed_version=installed_version,
        expected_version=EXPECTED_ENGINE_VERSION,
        param_mismatches=mismatches,
    )
