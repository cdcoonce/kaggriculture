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

from harness.zoo.chaos_legal_random import make_agent as _make_chaos_legal_random
from harness.zoo.fert_market_crasher import make_agent as _make_fert_market_crasher
from harness.zoo.index_front_runner import make_agent as _make_index_front_runner
from harness.zoo.land_rush_hoarder import make_agent as _make_land_rush_hoarder
from harness.zoo.melon_dumper import make_agent as _make_melon_dumper
from harness.zoo.melon_rusher import make_agent as _make_melon_rusher
from harness.zoo.meta_clone import make_agent as _make_meta_clone
from harness.zoo.public_baseline_approx import make_agent as _make_public_baseline_approx
from harness.zoo.wheat_spam import make_agent as _make_wheat_spam

Agent = Callable[..., Any] | str

# Engine built-ins — free anchors, always in the gate zoo.
BUILTIN_ANCHORS: dict[str, str] = {
    "starter": "starter",
    "pass": "pass",
}

# Scripted archetypes register here as they land (zoo design #5):
# wheat-spam, melon-dumper, index-front-runner, meta-clone, land-rush-hoarder,
# fert-market-crasher, chaos-legal-random, public-baseline-approx.
SCRIPTED: dict[str, Agent] = {
    "wheat-spam": _make_wheat_spam,
    "melon-dumper": _make_melon_dumper,
    "melon-rusher": _make_melon_rusher,
    "index-front-runner": _make_index_front_runner,
    "land-rush-hoarder": _make_land_rush_hoarder,
    "fert-market-crasher": _make_fert_market_crasher,
    "public-baseline-approx": _make_public_baseline_approx,
    "meta-clone": _make_meta_clone,
}


def gate_zoo() -> dict[str, Agent]:
    """The current gate-zoo roster (anchors + registered scripted members)."""
    return {**BUILTIN_ANCHORS, **SCRIPTED}


# Extended-only members: swept only by the nightly, not part of the gate zoo.
EXTENDED: dict[str, Agent] = {
    "chaos-legal-random": _make_chaos_legal_random,
}


def extended_zoo() -> dict[str, Agent]:
    """Gate zoo plus extended-only members, swept only by the nightly."""
    return {**BUILTIN_ANCHORS, **SCRIPTED, **EXTENDED}
