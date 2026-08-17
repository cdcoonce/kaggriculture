"""Opponent zoo — frozen fixtures (zoo design, issue #5).

Contract: members are IMMUTABLE once registered; any behavior change is a NEW
member under a new name. Members implement the same callable interface as
champions but carry no safety shell (they are local fixtures, not
submissions). Engine built-ins are referenced by their kaggle_environments
name strings.

Gate zoo cap: ~10 members. Everything beyond the cap lives in the extended
zoo, swept only by the nightly; an extended member that beats a current
champion earns gate promotion.

Tape-player members (``tape-<stem>``, issue #59) are a special case of the
extended zoo: each one replays a fixed, observation-blind action tape read
from a MACHINE-LOCAL directory (``harness.zoo.tape_player.DEFAULT_TAPE_DIR``,
by default ``~/.kaggriculture/tapes``). Tapes are third-party data and are
never committed to this repo, so they are discovered at runtime rather than
imported, and gate-excluded by design: they join ``extended_zoo()`` only,
never ``SCRIPTED``/``gate_zoo()``, so the gate roster stays reproducible and
machine-independent regardless of which tapes (if any) happen to be present
on the machine running it.

Kernel-player members (``kernel-<stem>``) are the same kind of special case:
each one plays a decoded action plan ported from a published Kaggle
competitor solution, self-repairing against the live observation rather than
replaying blind (see ``harness.zoo.kernel_player``'s module docstring for the
full design). The plan JSON is likewise third-party data, MACHINE-LOCAL by
default at ``harness.zoo.kernel_player.DEFAULT_KERNEL_DIR``
(``~/.kaggriculture/kernels``), discovered at runtime, and gate-excluded by
the same construction as tapes: ``extended_zoo()`` only, never
``SCRIPTED``/``gate_zoo()``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from harness.zoo.chaos_legal_random import make_agent as _make_chaos_legal_random
from harness.zoo.fert_market_crasher import make_agent as _make_fert_market_crasher
from harness.zoo.index_front_runner import make_agent as _make_index_front_runner
from harness.zoo.kernel_player import discover_kernels as _discover_kernels
from harness.zoo.land_rush_hoarder import make_agent as _make_land_rush_hoarder
from harness.zoo.melon_dumper import make_agent as _make_melon_dumper
from harness.zoo.melon_rusher import make_agent as _make_melon_rusher
from harness.zoo.meta_clone import make_agent as _make_meta_clone
from harness.zoo.public_baseline_approx import make_agent as _make_public_baseline_approx
from harness.zoo.tape_player import discover_tapes as _discover_tapes
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
    """Gate zoo plus extended-only members, swept only by the nightly.

    Tape-player and kernel-player members are merged in dynamically via
    ``discover_tapes()``/``discover_kernels()`` on every call, rather than
    being folded into ``EXTENDED`` at import time: both live in a
    machine-local directory that can change between calls (or be entirely
    absent), and import time must stay filesystem-free so importing this
    module never depends on either kind of file existing.
    """
    return {
        **BUILTIN_ANCHORS,
        **SCRIPTED,
        **EXTENDED,
        **_discover_tapes(),
        **_discover_kernels(),
    }
