"""Agent-tree law enforcement (repo architecture #2, gate set #3).

Two laws with teeth: the import allowlist (stdlib + numpy only) and the
import-time budget (the 60 s overage bank is for thinking, not imports).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from harness.importlaw import find_violations

REPO = Path(__file__).resolve().parent.parent
AGENT_TREE = REPO / "packages" / "agent" / "src"

IMPORT_TIME_BUDGET_S = 1.0


def test_agent_tree_imports_only_stdlib_and_numpy() -> None:
    assert find_violations(AGENT_TREE) == []


def test_teeth_checker_flags_smuggled_import(tmp_path: Path) -> None:
    """Teeth-check: the walker actually catches a violation. If this fails,
    the allowlist test above is testing nothing."""
    bad = tmp_path / "sneaky.py"
    bad.write_text("import pandas\nfrom torch import nn\n")
    flagged = {name for _, name in find_violations(tmp_path)}
    assert flagged == {"pandas", "torch"}


def test_agent_import_time_within_budget() -> None:
    code = "import time; t = time.perf_counter(); import agent.main; print(time.perf_counter() - t)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    elapsed = float(out.stdout.strip())
    assert elapsed < IMPORT_TIME_BUDGET_S, f"agent import took {elapsed:.2f}s"
