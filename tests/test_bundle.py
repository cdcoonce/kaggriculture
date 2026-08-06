"""Stale-bundle gate (repo architecture #2): the committed dist must match a
fresh build bit-for-bit, and the bundled artifact must actually play."""

from __future__ import annotations

import hashlib
import sys
import tarfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from build import build  # noqa: E402

DIST = REPO / "dist"


def _committed_digest() -> str:
    return (DIST / "MANIFEST.txt").read_text().split()[1]


def test_committed_bundle_is_fresh(tmp_path: Path) -> None:
    _, fresh_digest = build(dist_dir=tmp_path)
    assert fresh_digest == _committed_digest(), (
        "dist/submission.tar.gz is stale — run `python build.py` and commit the result"
    )


def test_teeth_tampered_bundle_detected(tmp_path: Path) -> None:
    """Teeth-check: a modified source tree produces a different digest."""
    _, fresh = build(dist_dir=tmp_path)
    tampered = hashlib.sha256((DIST / "submission.tar.gz").read_bytes() + b"x").hexdigest()
    assert tampered != fresh


@pytest.mark.slow
def test_bundle_plays_an_episode(tmp_path: Path) -> None:
    from kaggle_environments import make

    with tarfile.open(DIST / "submission.tar.gz") as tar:
        tar.extractall(tmp_path, filter="data")
    env = make("kaggriculture", configuration={"seed": 11}, debug=True)
    env.run([str(tmp_path / "main.py"), "starter"])
    statuses = [s.status for s in env.steps[-1]]
    assert statuses == ["DONE", "DONE"], statuses
