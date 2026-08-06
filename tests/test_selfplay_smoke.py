"""Self-play smoke (gate set #3): the validation episode is a mirror match and
all-or-nothing, so every build proves it survives self-play before anything
else matters. Full fuzz sizing belongs to the submission-ops ritual (#10)."""

from __future__ import annotations

import pytest
from agent.main import agent
from kaggle_environments import make

SMOKE_SEEDS = [1, 2, 3]


@pytest.mark.parametrize("seed", SMOKE_SEEDS)
def test_selfplay_finishes_done(seed: int) -> None:
    env = make("kaggriculture", configuration={"seed": seed}, debug=True)
    env.run([agent, agent])
    assert [s.status for s in env.steps[-1]] == ["DONE", "DONE"]


def test_vs_starter_finishes_done() -> None:
    env = make("kaggriculture", configuration={"seed": 7}, debug=True)
    env.run([agent, "starter"])
    assert [s.status for s in env.steps[-1]] == ["DONE", "DONE"]
