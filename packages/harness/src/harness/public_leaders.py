"""Loading the pre-registered public-leader opponent panel as harness agents.

The demand-aware-seasonal-controller pre-registration
(``eval/prereg/2026-09-08-demand-aware-seasonal-controller.md``) defines an
opponent panel of three immutable, SHA-256-pinned public Kaggle leader
submissions, committed at
``eval/opponents/public-leaders/{sokolovsky-v12,rayk-v11,kaito-v4}/main.py``
with their ids, public scores and per-file hashes recorded in that
directory's ``panel.json``. This module is the only thing that loads them as
harness opponents, reached through the ``public:<id>`` agent spec
(``harness.episodes.resolve_agent``).

Loading these files correctly means matching two things exactly:

* **Entrypoint selection.** The live Kaggle ladder loads a file agent with
  ``kaggle_environments.agent.get_last_callable``, which executes the source
  and returns the LAST callable bound at module level -- not whichever
  function happens to be named ``agent``. ``kaito-v4/main.py`` defines both
  ``agent`` and, after it, a thin ``_kaggle_submission_entrypoint`` wrapper;
  the ladder runs the wrapper. Calling the real ``get_last_callable`` (rather
  than reimplementing its selection rule) is what keeps this exact,
  including its refusal to inject a ``__file__`` into the executed
  namespace.

* **Namespace freshness.** All three files keep mutable module-level globals
  across calls -- e.g. ``kaito-v4``'s ``_WEED_STATE`` (keyed by seat) and
  ``sokolovsky-v12``'s ``_LAST_STEP`` / ``_CLONE_CONFIDENCE`` / ``_PREV_SHED``.
  The harness reuses worker processes across games (the same class of hazard
  ``harness.frozen``'s module docstring documents for the historical
  ``sys.modules`` mirror bug, where a second import of a "frozen" package
  silently returned the first module object). ``get_last_callable`` already
  builds a brand-new ``{}`` namespace and execs the source into it on every
  call, without ever touching ``sys.modules`` -- so calling it fresh per
  resolution, and never caching or memoizing ``resolve_public_leader`` or its
  result, is what keeps two resolutions of the same id isolated. Do not wrap
  this module's loader in a cache.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kaggle_environments.agent import get_last_callable

_ROOT_ENV_VAR = "KAGG_PUBLIC_LEADERS_ROOT"


def _panel_root() -> Path:
    """CWD-relative ``eval/opponents/public-leaders``, overridable by env var.

    Mirrors ``harness.episodes``'s ``frozen:`` spec, which resolves
    ``KAGG_FROZEN_ROOT`` against ``Path.cwd() / "eval" / "frozen"`` the same
    way -- tests point this at a tmp-dir copy instead of the pinned panel.
    """
    override = os.environ.get(_ROOT_ENV_VAR)
    if override is not None:
        return Path(override)
    return Path.cwd() / "eval" / "opponents" / "public-leaders"


def _panel_entry(root: Path, agent_id: str) -> dict[str, Any]:
    panel = json.loads((root / "panel.json").read_text(encoding="utf-8"))
    opponents: list[dict[str, Any]] = panel["opponents"]
    for opponent in opponents:
        if opponent["id"] == agent_id:
            return opponent
    known = sorted(opponent["id"] for opponent in opponents)
    raise ValueError(f"unknown public leader id {agent_id!r}; known ids: {known}")


def resolve_public_leader(agent_id: str) -> Callable[..., Any]:
    """Resolve a public-leader panel id to a freshly-loaded agent callable.

    Verifies the decoded agent file's SHA-256 against ``panel.json`` before
    executing anything: an unknown id or a hash mismatch raises
    ``ValueError`` naming the id and, for a mismatch, both the expected and
    actual hashes.

    Every call executes the pinned source into a brand-new namespace via
    ``kaggle_environments.agent.get_last_callable`` (see the module
    docstring) -- the result must never be cached or reused across
    resolutions.
    """
    root = _panel_root()
    entry = _panel_entry(root, agent_id)

    agent_path = root / entry["decoded_agent_path"]
    source_bytes = agent_path.read_bytes()

    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    expected_hash = entry["decoded_agent_sha256"]
    if actual_hash != expected_hash:
        raise ValueError(
            f"public leader {agent_id!r} failed provenance check at {agent_path}: "
            f"expected sha256 {expected_hash}, got {actual_hash}"
        )

    source_text = source_bytes.decode("utf-8")
    # kaggle_environments ships no py.typed marker, so mypy sees this call's
    # result as Any; the explicit annotation pins it back to the declared
    # return type instead of silently propagating Any out of this function.
    entrypoint: Callable[..., Any] = get_last_callable(source_text, path=str(agent_path))
    return entrypoint


def resolve_file_agent(relpath: str) -> Callable[..., Any]:
    """Resolve an arbitrary repo-relative single-file agent (the ``file:``
    spec in ``harness.episodes.resolve_agent``).

    For a local, uncommitted-panel file such as a fork under ``forks/`` that
    has no ``panel.json`` entry to verify against. Reuses exactly the loading
    half of ``resolve_public_leader`` above -- ``get_last_callable`` against a
    brand-new namespace on every call, never cached -- but skips the SHA-256
    provenance check, since there is no panel entry for an arbitrary path.

    ``relpath`` is resolved against ``Path.cwd()``, mirroring
    ``_panel_root()`` and ``harness.episodes``'s ``frozen:`` spec: run from
    the repo root.
    """
    path = Path.cwd() / relpath
    source_text = path.read_text(encoding="utf-8")
    entrypoint: Callable[..., Any] = get_last_callable(source_text, path=str(path))
    return entrypoint
