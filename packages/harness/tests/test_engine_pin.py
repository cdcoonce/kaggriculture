"""Engine pin — packages/harness/pyproject.toml declares, uv.lock resolves, both
must agree with the installed kaggle-environments (issue #24, decision on #42)."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

EXPECTED_PIN = "1.32.7"


def test_installed_engine_is_exact_pin() -> None:
    assert importlib.metadata.version("kaggle-environments") == EXPECTED_PIN


def test_pyproject_declares_exact_pin() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text())
    deps = data["project"]["dependencies"]
    assert f"kaggle-environments=={EXPECTED_PIN}" in deps
