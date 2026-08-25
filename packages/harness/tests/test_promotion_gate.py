"""Teeth for the win-rate gate that stands in front of the Kaggle upload.

The contract under test is narrow and was, until this module existed, unowned:
``submit.py`` refuses to print an upload command unless
``find_passing_promotion`` finds a ``gate_type == "promotion"`` entry at the
exact candidate SHA, and nothing in the repo drove ``run_gate`` from a command
line to produce one. A CLI that ran cleanly but wrote ``gate_type="money"``
would look fine and still leave the upload path dead, so the assertions below
check the ARTIFACT, not the exit code.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness.ledger import find_passing_promotion
from harness.promotion_gate import main

# ~45s: three real 720-step episodes' worth of games. The `full-suite` job
# gates every PR alongside `fast-set`, so this still blocks a merge -- it just
# does not sit in the fast leg's budget.
pytestmark = pytest.mark.slow


def test_it_writes_an_entry_find_passing_promotion_accepts(tmp_path: Path) -> None:
    """The end-to-end contract: run the gate, then have submit.py's own
    lookup find what it wrote. Asserting `exit == 0` would not catch a
    gate_type regression; asserting on the lookup is what closes the loop.
    """
    sha = "0" * 40
    code = main(
        [
            "--opponent",
            "zoo:pass",
            "--n-seeds",
            "8",
            "--seed-base",
            "990000",
            "--workers",
            "2",
            "--eval-dir",
            str(tmp_path),
            "--candidate-commit",
            sha,
        ]
    )
    assert code == 0

    found = find_passing_promotion(tmp_path / "gates", sha)
    assert found is not None, "submit.py would refuse this SHA"

    entry = json.loads(found.read_text(encoding="utf-8"))
    assert entry["identity"]["gate_type"] == "promotion"
    assert entry["identity"]["candidate"] == "champion"
    assert entry["identity"]["candidate_commit"] == sha
    assert entry["verdict"]["passed"] is True


def test_a_different_sha_is_not_accepted(tmp_path: Path) -> None:
    """The SHA pin is the point: a gate run at some other commit must not
    authorise an upload of the tree in front of you. Without this, editing the
    agent after gating would still find a passing entry.
    """
    main(
        [
            "--opponent",
            "zoo:pass",
            "--n-seeds",
            "8",
            "--seed-base",
            "990000",
            "--workers",
            "2",
            "--eval-dir",
            str(tmp_path),
            "--candidate-commit",
            "a" * 40,
        ]
    )
    assert find_passing_promotion(tmp_path / "gates", "b" * 40) is None


def test_no_ledger_writes_nothing(tmp_path: Path) -> None:
    """--no-ledger must not leave an entry behind: a dry run that silently
    authorised an upload would be worse than no dry run.
    """
    code = main(
        [
            "--opponent",
            "zoo:pass",
            "--n-seeds",
            "8",
            "--seed-base",
            "990000",
            "--workers",
            "2",
            "--eval-dir",
            str(tmp_path),
            "--candidate-commit",
            "c" * 40,
            "--no-ledger",
        ]
    )
    assert code == 0
    assert not (tmp_path / "gates").exists()
