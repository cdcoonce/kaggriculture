"""Repo-wide test isolation: stop import-state leaks from crossing test boundaries.

Running a submission bundle in-process permanently prepends that bundle's root
to ``sys.path``. Two halves combine to make it stick:

* ``build.ENTRY``'s ``agent()`` does ``sys.path.insert(0, agent_dir)`` so the
  bundled ``agent`` package is importable. That is *correct* on Kaggle, where
  one process serves exactly one bundle and never imports anything else.
* ``kaggle_environments``' file-path agent loader appends the exec dir and then
  pops blindly (``sys.path.pop()``), so it removes its own appended entry, not
  the front-inserted one.

Net effect under pytest: every rehearsal game in ``tests/test_submit.py`` leaves
a bundle root at ``sys.path[0]``, ahead of ``packages/agent/src``. A later
``import agent.policy`` then resolves ``agent`` to the bundle's stub package
(``__init__.py`` + ``main.py``, no ``policy``) and dies with
``ModuleNotFoundError: No module named 'agent.policy'``.

This is the ordering-dependent mirror of the frozen-incumbent collision
``harness.frozen.assert_disjoint`` guards: there a frozen package displaced the
live one in ``sys.modules``; here a bundle stub displaces it on ``sys.path``.

It stayed invisible because CI and ``.afk/config.toml`` only ever run
``pytest -m "not slow"`` then ``pytest -m slow`` — and every polluting test is
marked ``slow`` while its victims in ``packages/harness/tests/`` are not, so the
split happened to keep them apart. A bare ``pytest`` failed 16 tests.
``.github/workflows/ci.yml``'s ``full-suite`` job now runs the unsplit suite so
this cannot regress silently again.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest


def _is_under(module: object, roots: list[Path]) -> bool:
    """Whether ``module`` was loaded from a file inside any of ``roots``.

    Deliberately defensive. Module introspection is hostile in two ways here, and
    a fixture that runs after every single test must never be the thing that
    breaks the suite:

    * Reading through ``__dict__`` rather than ``getattr`` avoids modules defining
      a PEP 562 module-level ``__getattr__`` that raises on names it does not
      handle.
    * A namespace package's ``__path__`` is a ``_NamespacePath`` that recomputes
      on iteration by looking its parent up in ``sys.modules``, which raises
      ``KeyError`` once that parent is gone.

    Anything we cannot locate is reported as not-under, i.e. left alone.
    """
    namespace = getattr(module, "__dict__", None)
    if not isinstance(namespace, dict):
        return False
    locations: list[str] = []
    file = namespace.get("__file__")
    if isinstance(file, str):
        locations.append(file)
    try:
        # Namespace packages carry no __file__, only __path__ entries.
        locations.extend(e for e in namespace.get("__path__") or () if isinstance(e, str))
    except Exception:
        pass  # Unlocatable module: leave it cached.
    try:
        resolved = [Path(location).resolve() for location in locations]
    except OSError:
        return False
    return any(location.is_relative_to(root) for location in resolved for root in roots)


def _evict_modules_under(roots: list[Path]) -> None:
    """Drop cached top-level packages that were imported from a now-removed path entry.

    Restoring ``sys.path`` alone is not enough: a stub package already imported
    from a leaked directory stays cached in ``sys.modules`` and keeps shadowing
    the real one by name.

    Only *top-level* names are candidates. A submodule buried inside an installed
    package can shadow nothing and stays reachable through its parent, so evicting
    it would be pointless churn against a live import registry — and that case is
    real here, since ``kaggle_environments`` appends its per-environment plugin
    directories (``.../kaggle_environments/envs/lux_ai_s3``) to ``sys.path``.
    """
    # Snapshot before scanning: locating a namespace package can invoke a path
    # finder, and anything that imports mid-scan would otherwise raise
    # "dictionary changed size during iteration".
    doomed = {
        name
        for name, module in list(sys.modules.items())
        if "." not in name and _is_under(module, roots)
    }
    if not doomed:
        return
    for name in list(sys.modules):
        if name.partition(".")[0] in doomed:
            del sys.modules[name]


@pytest.fixture(autouse=True)
def _isolate_import_state() -> Iterator[None]:
    """Restore ``sys.path`` after every test, evicting anything imported from a leak."""
    snapshot = list(sys.path)
    yield
    if sys.path == snapshot:
        return
    leaked = [Path(entry).resolve() for entry in sys.path if entry not in snapshot]
    sys.path[:] = snapshot
    if leaked:
        _evict_modules_under(leaked)
