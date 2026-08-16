"""Teeth for the root ``conftest.py``'s cross-test import isolation.

These two tests are deliberately coupled and order-dependent: the first leaks
import state exactly the way an in-process submission-bundle run does, and the
second asserts the autouse fixture undid it. pytest runs tests in definition
order within a file, so the pairing is deterministic. Delete the
``_isolate_import_state`` fixture and the second test fails.

A neutral probe package name is used rather than ``agent`` on purpose: this file
proves the fixture's contract without ever displacing the real ``agent`` package
and re-importing it under other tests. The end-to-end proof that the real
symptom is gone is ``ci.yml``'s ``full-suite`` job running an unsplit ``pytest``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

PROBE_PKG = "kagg_import_isolation_probe"
AGENT_SRC = Path(__file__).resolve().parent.parent / "packages" / "agent" / "src"


@pytest.fixture(scope="module")
def leaky_bundle_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A directory holding an importable probe package, mirroring an extracted bundle."""
    root = tmp_path_factory.mktemp("extracted")
    package = root / PROBE_PKG
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    return root


def test_leaking_test_can_still_pollute_its_own_import_state(leaky_bundle_root: Path) -> None:
    """Front-insert and import, the way ``build.ENTRY``'s ``agent()`` does."""
    sys.path.insert(0, str(leaky_bundle_root))
    module = importlib.import_module(PROBE_PKG)

    assert Path(module.__file__ or "").is_relative_to(leaky_bundle_root)
    assert PROBE_PKG in sys.modules


def test_next_test_sees_sys_path_and_sys_modules_restored(leaky_bundle_root: Path) -> None:
    """The leak from the previous test must not survive into this one."""
    assert str(leaky_bundle_root) not in sys.path
    assert PROBE_PKG not in sys.modules

    # The directory still exists on disk, so the probe is only unimportable
    # because the leaked sys.path entry was actually removed.
    assert leaky_bundle_root.is_dir()
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(PROBE_PKG)


def test_live_agent_package_resolves_inside_the_source_tree() -> None:
    """The symptom that made this fixture necessary: ``agent`` must not be a bundle stub.

    Under a bare ``pytest``, ``tests/test_submit.py``'s rehearsal games used to
    leave bundle roots at ``sys.path[0]``, so ``agent`` resolved to a stub
    carrying only ``main.py`` and ``agent.policy`` vanished.
    """
    policy = importlib.import_module("agent.policy")

    assert Path(policy.__file__ or "").is_relative_to(AGENT_SRC)
