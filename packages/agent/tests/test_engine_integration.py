"""Chassis v1 against the real engine: rush pace, egg pipeline, liquidation.

Bars are behavioral floors, not tuned snapshots: the day-6 bar is set where a
working wheat rush lands comfortably above the starter agent's whole-game pace
(~$3.5k); the full-game bar proves compounding, not a specific number.
"""

from __future__ import annotations

from typing import Any

from agent.main import agent
from kaggle_environments import make


def _run(steps: int, seed: int, opponent: str = "pass") -> Any:
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    env.run([agent, opponent])
    return env


def _money(env: Any, player: int = 0) -> float:
    return float(env.steps[-1][0].observation["farms"][player]["money"])


def test_wheat_rush_outearns_starter_pace_by_day_six() -> None:
    env = _run(steps=144, seed=41)
    assert _money(env) > 3600.0


def test_goose_eggs_are_sold_within_eleven_days() -> None:
    env = _run(steps=264, seed=42)
    sold_egg = any(
        any(o[0] == "SELL" and o[1] == "EGG" for o in (step[0].action or {}).get("market", []))
        for step in env.steps[1:]
    )
    assert sold_egg


def test_full_game_beats_pass_and_liquidates() -> None:
    env = _run(steps=720, seed=43)
    assert [s.status for s in env.steps[-1]] == ["DONE", "DONE"]
    assert _money(env) > 12000.0  # observed ~18k on seed 43; floor leaves seed margin

    shed = env.steps[-1][0].observation["private"]["shed"]
    residue = sum(n for item, n in shed.items() if item in ("WHEAT", "EGG", "FERTILIZER"))
    assert residue <= 4  # feed reserve at most; unsold produce is $0 at game end
