"""wheat-spam opponent archetype — wheat monoculture, price-blind (zoo #5)."""

from __future__ import annotations

import pytest
from harness.zoo import gate_zoo
from harness.zoo.wheat_spam import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


def _any_wheat_plant_tile(env: object) -> bool:
    farm0 = env.steps[-1][0].observation["farms"][0]
    for row in farm0["tiles"]:
        for tile in row:
            if (
                isinstance(tile, dict)
                and tile.get("kind") == "PLANT"
                and tile.get("crop") == "WHEAT"
            ):
                return True
    return False


class TestRegistration:
    def test_wheat_spam_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "wheat-spam" in roster

    def test_wheat_spam_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["wheat-spam"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["wheat-spam"]
        agent = factory()
        assert callable(agent)


class TestEarlyBehavior:
    def test_has_planted_wheat_by_step_96(self) -> None:
        env = _run_early_game()
        assert _any_wheat_plant_tile(env)

    def test_has_bought_seeds_or_spent_money_by_step_96(self) -> None:
        env = _run_early_game()
        money_at_step_1 = env.steps[1][0].observation["farms"][0]["money"]
        seeds_ever_positive = any(
            step[0].observation["private"]["seeds"].get("WHEAT", 0) > 0 for step in env.steps
        )
        assert money_at_step_1 < 3000 or seeds_ever_positive


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = _run_early_game()
        env2 = _run_early_game()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]
        assert money1 == money2

        # env.steps[0].action is always a ["PASS"] placeholder (there is no
        # prior observation to have decided it from); the agent's actual
        # first decision — made from the step-0 observation — is recorded
        # at env.steps[1].action.
        action1 = env1.steps[1][0].action
        action2 = env2.steps[1][0].action
        assert action1 == action2


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held(self) -> None:
        # Atomic-PLANT trap: the engine rewrites ALL PLANT orders to PASS for a
        # turn where total PLANT demand for a crop exceeds seeds held, so
        # over-ordering silently wastes the whole turn for every unit.
        #
        # env.steps[k].action is the action decided from env.steps[k-1]'s
        # observation (env.steps[0].action is a ["PASS"] placeholder with no
        # prior observation), so each action must be checked against the
        # *previous* step's seed count, not its own.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 72})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):
            prior_observation = env.steps[k - 1][0].observation
            action = env.steps[k][0].action
            seeds_held = prior_observation["private"]["seeds"].get("WHEAT", 0)

            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            plant_orders = sum(
                1 for a in unit_actions if isinstance(a, list) and a[:2] == ["PLANT", "WHEAT"]
            )
            assert plant_orders <= seeds_held


class TestFullGame:
    @pytest.mark.slow
    def test_beats_pass_over_a_full_720_step_game(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        statuses = [step.status for step in env.steps[-1]]
        assert statuses == ["DONE", "DONE"]

        wheat_spam_money = env.steps[-1][0].observation["farms"][0]["money"]
        pass_money = env.steps[-1][0].observation["farms"][1]["money"]
        assert pass_money == pytest.approx(3000.0)
        assert wheat_spam_money > 4000

    @pytest.mark.slow
    def test_beats_starter_over_a_full_720_step_game(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]
        assert statuses == ["DONE", "DONE"]

        wheat_spam_money = env.steps[-1][0].observation["farms"][0]["money"]
        starter_money = env.steps[-1][0].observation["farms"][1]["money"]
        assert wheat_spam_money > starter_money
