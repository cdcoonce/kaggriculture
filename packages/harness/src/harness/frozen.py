"""Frozen-incumbent materialization: renamed-package freeze + mirror guard.

Runbook (freeze a champion at a SHA, then gate the current champion against
it):

    freeze_incumbent(sha="fc23e66", name="m1", repo_root=REPO_ROOT, dest_root=Path("eval/frozen"))
    run_gate(candidate="champion", opponent="frozen:m1", n_seeds=..., seed_base=...)

Why renamed packages: an earlier promotion gate imported a frozen incumbent
under the SAME package name as the live champion (``agent``). Python's
``sys.modules`` caches by name, so the second import silently returned the
first module object — "old vs new" secretly ran new-vs-new (signature:
every game a win, byte-identical money totals). The fix is to never let a
frozen incumbent share a module name with the live package: it is
materialized as ``frozen_<name>`` with its internal imports rewritten, so
``agent.*`` and ``frozen_<name>.*`` coexist as distinct entries in
``sys.modules``. ``assert_disjoint`` is the loud, fail-fast check that this
held.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

_FROM_AGENT_DOTTED = re.compile(r"\bfrom agent\.")
_FROM_AGENT_IMPORT = re.compile(r"\bfrom agent import\b")
_IMPORT_AGENT_DOTTED = re.compile(r"\bimport agent\.")
_IMPORT_AGENT_BARE = re.compile(r"\bimport agent\b(?!\.)")


def sanitize_name(name: str) -> str:
    """Sanitize a freeze name into a valid Python identifier suffix (dashes -> underscores)."""
    return name.replace("-", "_")


def frozen_package_name(name: str) -> str:
    """The renamed package name a frozen incumbent is materialized under."""
    return f"frozen_{sanitize_name(name)}"


def _rewrite_imports(text: str, pkg: str) -> str:
    """Rewrite absolute ``agent`` imports to the renamed ``pkg`` package."""
    text = _FROM_AGENT_DOTTED.sub(f"from {pkg}.", text)
    text = _FROM_AGENT_IMPORT.sub(f"from {pkg} import", text)
    text = _IMPORT_AGENT_DOTTED.sub(f"import {pkg}.", text)
    text = _IMPORT_AGENT_BARE.sub(f"import {pkg}", text)
    return text


def freeze_incumbent(sha: str, name: str, repo_root: Path, dest_root: Path) -> Path:
    """Materialize ``packages/agent/src/agent`` at ``sha`` into a renamed package.

    Extracts the agent tree via ``git archive`` (so the working tree's
    current, possibly-dirty state is irrelevant — only the pinned commit's
    content is used), rewrites its internal ``agent.*`` imports to
    ``frozen_<name>.*``, and places the result at
    ``dest_root/frozen_<name>/``. Idempotent: a re-freeze over an existing
    directory removes the old content first.
    """
    pkg = frozen_package_name(name)
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / pkg
    scratch = dest_root / f".{pkg}.tmp-extract"

    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir()

    try:
        archive = subprocess.run(
            ["git", "archive", sha, "--", "packages/agent/src/agent"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(scratch)  # noqa: S202 - trusted, first-party repo history

        extracted = scratch / "packages" / "agent" / "src" / "agent"
        for py_file in sorted(extracted.rglob("*.py")):
            rewritten = _rewrite_imports(py_file.read_text(encoding="utf-8"), pkg)
            py_file.write_text(rewritten, encoding="utf-8")

        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(extracted), str(dest))
    finally:
        if scratch.exists():
            shutil.rmtree(scratch)

    return dest


def assert_disjoint(name: str) -> None:
    """Fail loudly if the frozen incumbent is not actually disjoint from the champion.

    Guards against the historical sys.modules mirror bug: a frozen
    incumbent whose ``policy`` module resolves inside the LIVE ``agent``
    package's source tree, or whose module object is literally the same
    object as ``agent.policy`` (meaning the frozen import displaced the
    live one in ``sys.modules``), means "frozen vs champion" is secretly
    running champion-vs-itself.
    """
    pkg = frozen_package_name(name)
    frozen_policy = sys.modules.get(f"{pkg}.policy")
    if frozen_policy is None or getattr(frozen_policy, "__file__", None) is None:
        raise RuntimeError(f"{pkg}.policy has not been imported — cannot verify disjointness")
    frozen_file = Path(frozen_policy.__file__).resolve()

    import agent as live_agent_pkg

    live_file = getattr(live_agent_pkg, "__file__", None)
    if live_file is not None:
        live_root = Path(live_file).resolve().parent
        if frozen_file.parent == live_root:
            raise RuntimeError(
                f"mirror bug: {pkg}.policy resolves inside the live agent package "
                f"tree ({live_root}) — this is not a disjoint frozen incumbent"
            )

    live_policy = sys.modules.get("agent.policy")
    if live_policy is not None and live_policy is frozen_policy:
        raise RuntimeError(
            f"mirror bug: frozen {pkg}.policy IS agent.policy — importing the "
            "frozen package displaced the live agent.policy module in sys.modules"
        )
