"""tape-player: replays a fixed, observation-blind action tape recorded from
a real top-ladder game (zoo issue #59).

A "tape" is a JSON list of action dicts -- one entry per engine step, each
shaped exactly like a zoo agent's return value (``{"farmer": [...], "hands":
[[...], ...], "market": [[...], ...]}``). Playing it back is observation-
blind: the agent never looks at board state, only at the observation's own
step counter, to pick which tape entry to replay.

Tapes are third-party competition data and are deliberately MACHINE-LOCAL --
never committed to this repo (see ``DEFAULT_TAPE_DIR``). ``discover_tapes()``
scans that directory at call time and is wired into ``harness.zoo.
extended_zoo()`` only, never ``harness.zoo.gate_zoo()``: a checkout without
any tape files populated must still produce the exact same gate roster as
one that has them, so the gate stays reproducible and machine-independent
by construction, not by convention.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

#: Default tape directory, overridable at call time via the
#: ``KAGGRICULTURE_TAPE_DIR`` environment variable (see ``_tape_dir``).
DEFAULT_TAPE_DIR = Path.home() / ".kaggriculture" / "tapes"

_REQUIRED_KEYS = frozenset({"farmer", "hands", "market"})


def _tape_dir() -> Path:
    """Resolve the tape directory from the environment.

    Resolved at CALL time, not import time, so tests can monkeypatch
    ``KAGGRICULTURE_TAPE_DIR`` (module-level resolution would freeze the
    directory the first time this module gets imported in a process)."""
    override = os.environ.get("KAGGRICULTURE_TAPE_DIR")
    return Path(override) if override else DEFAULT_TAPE_DIR


def tape_path(stem: str) -> Path:
    """Absolute path of the tape file backing ``zoo:tape-<stem>``.

    Resolved at CALL time via ``_tape_dir()``, matching ``discover_tapes``."""
    return _tape_dir() / f"{stem}.json"


def load_tape(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate a tape JSON file.

    A valid tape is a nonempty JSON list, every entry of which is an object
    carrying at least ``farmer``, ``hands``, and ``market`` keys. Raises
    ``ValueError`` (with the offending path/entry named) on any structural
    problem -- caller decides whether that's fatal (``load_tape`` used
    directly) or skip-worthy (``discover_tapes``)."""
    path = Path(path)
    with path.open() as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"tape {path}: expected a JSON list, got {type(data).__name__}")
    if not data:
        raise ValueError(f"tape {path}: tape is empty")

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ValueError(f"tape {path}: entry {i} is not an object")
        missing = _REQUIRED_KEYS - entry.keys()
        if missing:
            raise ValueError(f"tape {path}: entry {i} missing keys {sorted(missing)}")

    return data


def _all_pass(num_hands: int) -> dict[str, Any]:
    """A safe all-PASS action sized to ``num_hands`` -- the fallback for any
    tape-agent failure (see ``make_tape_agent``)."""
    return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(num_hands)], "market": []}


def _align_hands(hands: Any, num_hands: int) -> list[list[Any]]:
    """Truncate/pad a tape entry's ``hands`` list to the observation's
    actual hand count.

    Hire cadence differs game to game, so the tape-recording player's hand
    count at a given step and the live observation's hand count at that same
    step drift apart. Extra tape entries are dropped; missing ones are
    padded with ``["PASS"]`` so every present hand still gets a legal
    action."""
    entries = hands if isinstance(hands, list) else []
    aligned = [action if isinstance(action, list) else ["PASS"] for action in entries[:num_hands]]
    aligned.extend(["PASS"] for _ in range(num_hands - len(aligned)))
    return aligned


def make_tape_agent(tape: list[dict[str, Any]]) -> Callable[[Any], dict[str, Any]]:
    """Return an agent callable that replays ``tape``, observation-blind,
    indexed by the observation's own step counter (``obs["step"]`` -- the
    same accessor every other zoo member and the engine's own interpreter
    use; see ``harness.zoo.meta_clone`` and ``kaggle_environments.envs.
    kaggriculture.kaggriculture.interpreter``).

    The index is clipped into ``[0, len(tape) - 1]`` so an episode longer
    than the tape can never ``IndexError`` -- the last entry simply repeats.
    ``hands`` is realigned to the observation's actual hand count (see
    ``_align_hands``). The whole body runs under a blanket ``except``: a
    zoo fixture must never crash a gate run, so any failure -- a malformed
    entry, an unexpected observation shape, anything -- degrades to a safe
    all-PASS action sized to whatever hand count could be determined before
    the failure (0 if even that lookup failed)."""

    def agent(obs: Any) -> dict[str, Any]:
        num_hands = 0
        try:
            farm = obs["farms"][obs["player"]]
            num_hands = len(farm["hands"])

            index = max(0, min(int(obs["step"]), len(tape) - 1))
            entry = tape[index]

            farmer_action = entry.get("farmer")
            market = entry.get("market")

            return {
                "farmer": farmer_action if isinstance(farmer_action, list) else ["PASS"],
                "hands": _align_hands(entry.get("hands"), num_hands),
                "market": market if isinstance(market, list) else [],
            }
        except Exception:
            return _all_pass(num_hands)

    return agent


def discover_tapes() -> dict[str, Callable[[], Callable[[Any], dict[str, Any]]]]:
    """Scan the tape directory for ``*.json`` files and return
    ``{"tape-<stem>": factory}`` for each one that loads cleanly.

    Returns ``{}`` if the directory doesn't exist -- a machine with no tapes
    populated is a normal, fully-supported state, not an error. Never
    raises: a malformed tape file is skipped silently, with nothing written
    to stdout (a gate run parses stdout, so this must stay silent). Each
    returned factory is zero-arg and produces a fresh agent closure per
    call, matching every other zoo member's factory contract."""
    tape_dir = _tape_dir()
    if not tape_dir.is_dir():
        return {}

    discovered: dict[str, Callable[[], Callable[[Any], dict[str, Any]]]] = {}
    for stem in sorted(path.stem for path in tape_dir.glob("*.json")):
        try:
            tape = load_tape(tape_path(stem))
        except (ValueError, OSError):
            continue

        def factory(tape: list[dict[str, Any]] = tape) -> Callable[[Any], dict[str, Any]]:
            return make_tape_agent(tape)

        discovered[f"tape-{stem}"] = factory

    return discovered
