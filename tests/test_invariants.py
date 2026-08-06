"""Engine-mechanics invariant tests for kaggle_environments' kaggriculture env.

Run with the project venv's pytest, e.g.:
    /path/to/venv/bin/python -m pytest test_invariants.py -v

Self-contained: only stdlib, pytest, and kaggle_environments are imported.
Agents below are scripted purely by turn number (``obs["step"]``) rather than
by reading game state -- each test only needs a short, fixed sequence of
actions, so a lookup table is simpler and more deterministic than reactive
logic.

Action shape (from the engine's own spec / source):
    {"farmer": [op, *args], "hands": [[op, *args], ...], "market": [[op, *args], ...]}
Farmer/hand ops include PLANT <crop>, WATER, HARVEST, PASS, movement, etc.
Market ops include BUY_SEED <crop> <n>, BUY_ANIMAL <animal> <n>, SELL <item> <n>.
"""

from __future__ import annotations

from typing import Any

from kaggle_environments import make

Action = dict[str, Any]
Obs = Any  # kaggle_environments Struct: supports both attribute and dict access


def _pass_action() -> Action:
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _idle_agent(obs: Obs) -> Action:
    """Player 1 in every test below: always passes, never touches player 0's farm."""
    return _pass_action()


def _scripted_agent(script: dict[int, Action]) -> Any:
    """Build an agent that plays ``script[step]`` on the given turn, PASS otherwise.

    ``step`` is the turn index the agent is being asked to act for
    (``obs["step"]``); the action it returns is applied by the engine and the
    resulting state is recorded at ``env.steps[step + 1]``.
    """

    def agent(obs: Obs) -> Action:
        return script.get(obs.get("step", 0), _pass_action())

    return agent


def _player_tile(env: Any, step_index: int, player: int = 0) -> Any:
    """Return the tile the given player's farmer stands on, at env.steps[step_index]."""
    obs = env.steps[step_index][player].observation
    farm = obs.farms[player]
    fx, fy = farm["farmer"]
    return farm["tiles"][fy][fx]


def test_same_turn_buy_plant_noops() -> None:
    """Unit actions resolve before that turn's market orders.

    Fails if the engine changed so market orders apply before (or
    interleaved with) unit actions -- i.e. if BUY_SEED credited the seed in
    time for the SAME turn's PLANT to consume it, which would leave a live
    PLANT on the tile after turn 0 instead of an empty one. Also fails if
    PLANT stopped working at all (the positive-control second half below).
    """
    script = {
        0: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]},
        1: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 30, "seed": 101, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    # After turn 0: BUY_SEED and PLANT were submitted together. PLANT must
    # have no-opped -- the seed was not yet in private["seeds"] when PLANT's
    # unit action resolved, since unit actions run before market orders.
    after_turn0 = env.steps[1][0].observation
    assert _player_tile(env, 1) is None
    assert after_turn0.private["seeds"]["WHEAT"] == 1

    # Positive control: PLANTing on the next turn, with the seed already
    # banked from turn 0's market order, must succeed.
    tile_after_turn1 = _player_tile(env, 2)
    assert isinstance(tile_after_turn1, dict)
    assert tile_after_turn1["kind"] == "PLANT"
    assert tile_after_turn1["crop"] == "WHEAT"
    after_turn1 = env.steps[2][0].observation
    assert after_turn1.private["seeds"]["WHEAT"] == 0


def test_fresh_plant_unwatered_weeds_overnight() -> None:
    """A freshly-planted, never-watered tile weeds at the next day boundary.

    ``consecutive_unwatered`` starts at 1 the instant a seed is planted (the
    planting day itself counts as unwatered), so a single unwatered
    day-boundary crossing is enough to weed it -- not two. Fails if that
    off-by-one regressed (the tile would still be a live PLANT after one
    unwatered day), or if watering stopped protecting a plant across the
    boundary (the positive control below).
    """

    def run_day(water_on_planting_day: bool, seed: int) -> Any:
        script: dict[int, Action] = {
            0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]},
            1: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []},
        }
        if water_on_planting_day:
            script[2] = {"farmer": ["WATER"], "hands": [], "market": []}
        env = make(
            "kaggriculture",
            configuration={"episodeSteps": 56, "seed": seed, "weedSpawnChance": 0.0},
        )
        env.run([_scripted_agent(script), _idle_agent])
        # The turn where obs.step == 23 is the 24th turn of day 0; processing
        # it triggers the end-of-day refresh (default turnsPerDay == 24),
        # landing in env.steps[24] (day 1, hour 0).
        return _player_tile(env, 24)

    unwatered_tile = run_day(water_on_planting_day=False, seed=301)
    assert unwatered_tile == {"kind": "WEED"}

    watered_tile = run_day(water_on_planting_day=True, seed=302)
    assert isinstance(watered_tile, dict)
    assert watered_tile["kind"] == "PLANT"
    assert watered_tile["crop"] == "WHEAT"


def test_animals_cannot_be_sold() -> None:
    """BUY_ANIMAL works; a subsequent SELL of that animal is a complete no-op.

    Fails if SELL started accepting non-PRODUCTS items (an animal would then
    become sellable, draining the shed and paying out money on the SELL
    turn), or if BUY_ANIMAL stopped charging money / stocking the shed (the
    positive-control first half below).
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_ANIMAL", "GOOSE", 1]]},
        1: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "GOOSE", 1]]},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 30, "seed": 202, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    starting_money = env.steps[0][0].observation.farms[0]["money"]

    after_buy = env.steps[1][0].observation
    # ANIMALS["GOOSE"]["cost"] == 300 in the engine's own price table.
    assert after_buy.farms[0]["money"] == starting_money - 300
    assert after_buy.private["shed"]["GOOSE"] == 1

    after_sell = env.steps[2][0].observation
    assert after_sell.farms[0]["money"] == after_buy.farms[0]["money"]
    assert after_sell.private["shed"]["GOOSE"] == 1
