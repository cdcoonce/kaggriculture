"""Agent-tree import law (repo architecture, issue #2).

The submission tree may import only the standard library, numpy, and itself.
This module provides the checker; tests/test_import_laws.py applies it to
``packages/agent/src`` and teeth-checks it against a fixture violation.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ALLOWED_TOP_LEVEL = set(sys.stdlib_module_names) | {"numpy", "agent"}


def find_violations(tree_root: Path, allowed: set[str] | None = None) -> list[tuple[Path, str]]:
    """Walk every .py under ``tree_root``; return (file, module) import violations."""
    allow = ALLOWED_TOP_LEVEL if allowed is None else allowed
    violations: list[tuple[Path, str]] = []
    for py in sorted(tree_root.rglob("*.py")):
        node = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Import):
                names = [alias.name for alias in stmt.names]
            elif isinstance(stmt, ast.ImportFrom):
                if stmt.level and stmt.level > 0:
                    continue  # relative import stays inside the package
                names = [stmt.module] if stmt.module else []
            else:
                continue
            for name in names:
                top = name.split(".", 1)[0]
                if top not in allow:
                    violations.append((py, name))
    return violations
