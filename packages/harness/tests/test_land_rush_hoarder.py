"""land-rush-hoarder opponent archetype — early triple BUY_LAND
over-expander (zoo #21). See harness.zoo.land_rush_hoarder's module
docstring for the full design."""

from __future__ import annotations

import pytest
from harness.zoo import gate_zoo
from harness.zoo.land_rush_hoarder import TURNS_PER_DAY, make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_land_rush_hoarder_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "land-rush-hoarder" in roster

    def test_land_rush_hoarder_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["land-rush-hoarder"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["land-rush-hoarder"]
        agent = factory()
        assert callable(agent)


class TestRosterArithmetic:
    def test_roster_stays_within_gate_zoo_cap(self) -> None:
        roster = gate_zoo()
        assert len(roster) <= 10
        assert "land-rush-hoarder" in roster


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = _run_early_game()
        env2 = _run_early_game()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        assert money1 == money2

        action1 = env1.steps[1][0].action  # type: ignore[attr-defined]
        action2 = env2.steps[1][0].action  # type: ignore[attr-defined]
        assert action1 == action2


class TestLandRush:
    def test_buy_land_queued_from_the_very_first_turn(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 24})
        env.run([make_agent(), "pass"])

        market = env.steps[1][0].action["market"]  # type: ignore[index]
        assert any(order[0] == "BUY_LAND" for order in market)

    def test_ne_unlocked_by_the_second_recorded_step(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 24})
        env.run([make_agent(), "pass"])

        unlocked = env.steps[1][0].observation["farms"][0]["unlocked_quadrants"]  # type: ignore[index]
        assert "NE" in unlocked

    def test_two_of_three_quadrants_purchased_third_stays_locked_by_cash_ceiling(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        unlocked = env.steps[-1][0].observation["farms"][0]["unlocked_quadrants"]  # type: ignore[index]
        assert unlocked == ["NW", "NE", "SW"]

    def test_hand_count_stays_at_one_per_day(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):  # type: ignore[arg-type]
            prior_observation = env.steps[k - 1][0].observation  # type: ignore[index]
            if prior_observation["step"] % TURNS_PER_DAY != 0:
                continue
            action = env.steps[k][0].action  # type: ignore[index]
            market = action.get("market", [])
            hire_count = sum(
                1 for order in market if isinstance(order, list) and order[:1] == ["HIRE"]
            )
            assert hire_count == 1


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held(self) -> None:
        # Atomic-PLANT trap: the engine rewrites ALL PLANT orders to PASS for a
        # turn where total PLANT demand for a crop exceeds seeds held, so
        # over-ordering silently wastes the whole turn for every unit.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 72})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):  # type: ignore[arg-type]
            prior_observation = env.steps[k - 1][0].observation  # type: ignore[index]
            action = env.steps[k][0].action  # type: ignore[index]
            seeds_held = prior_observation["private"]["seeds"].get("WHEAT", 0)

            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            plant_orders = sum(
                1 for a in unit_actions if isinstance(a, list) and a[:2] == ["PLANT", "WHEAT"]
            )
            assert plant_orders <= seeds_held


class TestFullGame:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", [7, 41, 43, 100, 202])
    def test_crash_free_full_episode(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]  # type: ignore[union-attr]
        assert statuses == ["DONE", "DONE"]
