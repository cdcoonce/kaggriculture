"""Opponent zoo — frozen fixtures (zoo design, issue #5).

Contract: members are IMMUTABLE once registered; any behavior change is a NEW
member under a new name. Members implement the same callable interface as
champions but carry no safety shell (they are local fixtures, not
submissions). Engine built-ins are referenced by their kaggle_environments
name strings.

Gate zoo cap: ~10 members. Everything beyond the cap lives in the extended
zoo, swept only by the nightly; an extended member that beats a current
champion earns gate promotion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Agent = Callable[..., Any] | str

# Engine built-ins — free anchors, always in the gate zoo.
BUILTIN_ANCHORS: dict[str, str] = {
    "starter": "starter",
    "pass": "pass",
}

# Scripted archetypes register here as they land (zoo design #5):
# wheat-spam, melon-rusher, index-front-runner, meta-clone, land-rush-hoarder,
# fert-market-crasher, chaos-legal-random, public-baseline-approx.
SCRIPTED: dict[str, Agent] = {}


def gate_zoo() -> dict[str, Agent]:
    """The current gate-zoo roster (anchors + registered scripted members)."""
    return {**BUILTIN_ANCHORS, **SCRIPTED}
