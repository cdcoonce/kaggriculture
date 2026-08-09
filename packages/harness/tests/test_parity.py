"""Byte-exact replay comparator tests (issue #32)."""

from __future__ import annotations

import copy
from pathlib import Path
from unittest.mock import patch

import kaggle_environments.core
import pytest
from harness.parity import (
    compare_trajectories,
    installed_engine_version,
    load_replay,
    replay_locally,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROBE_REPLAY_PATH = REPO_ROOT / "docs" / "recon" / "probe-server-replay.json.gz"
OWN_LADDER_FIXTURES = [
    REPO_ROOT / "packages" / "harness" / "tests" / "fixtures" / "replays" / name
    for name in (
        "episode-91087847-m2b-selfplay.json.gz",
        "episode-90826392-m2a-selfplay.json.gz",
        "episode-90563134-m1-selfplay.json.gz",
    )
]


def test_seed0_probe_fixture_byte_exact() -> None:
    data = load_replay(PROBE_REPLAY_PATH)
    local_steps = replay_locally(data)
    report = compare_trajectories(data["steps"], local_steps)
    assert report.mismatch_count == 0
    assert report.steps_compared == len(data["steps"])


@pytest.mark.slow
@pytest.mark.parametrize("fixture_path", OWN_LADDER_FIXTURES, ids=lambda p: p.name)
def test_own_ladder_fixtures_byte_exact(fixture_path: Path) -> None:
    data = load_replay(fixture_path)
    recorded_version = data["module_version"]
    installed_version = installed_engine_version()
    if recorded_version != installed_version:
        pytest.skip(
            f"fixture recorded module_version={recorded_version!r}, "
            f"installed kaggle-environments={installed_version!r}"
        )
    local_steps = replay_locally(data)
    report = compare_trajectories(data["steps"], local_steps)
    assert report.mismatch_count == 0


def test_mutated_field_is_detected() -> None:
    data = load_replay(PROBE_REPLAY_PATH)
    local_steps = replay_locally(data)
    mutated = copy.deepcopy(local_steps)
    mutated[100][0]["market"]["inventory"]["WHEAT"] += 1

    report = compare_trajectories(data["steps"], mutated)

    assert report.mismatch_count == 1
    mismatch = report.mismatches[0]
    assert mismatch.step == 100
    assert mismatch.agent == 0
    assert mismatch.field == "market"


def test_excluded_field_is_ignored() -> None:
    data = load_replay(PROBE_REPLAY_PATH)
    local_steps = replay_locally(data)
    mutated = copy.deepcopy(local_steps)
    mutated[100][0]["remainingOverageTime"] += 1

    report = compare_trajectories(data["steps"], mutated)

    assert report.mismatch_count == 0


def test_replay_locally_calls_env_step() -> None:
    # autospec=True preserves the descriptor/binding protocol so the patched
    # mock still receives `self` when called as env.step(...) -- a plain
    # wraps= mock (per the issue's literal recipe) is not a descriptor and
    # silently drops `self`, raising instead of counting calls.
    data = load_replay(PROBE_REPLAY_PATH)
    with patch.object(
        kaggle_environments.core.Environment,
        "step",
        autospec=True,
        side_effect=kaggle_environments.core.Environment.step,
    ) as spy:
        replay_locally(data)
    assert spy.call_count == len(data["steps"]) - 1
