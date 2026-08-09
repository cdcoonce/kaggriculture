"""public-baseline-approx opponent archetype -- "Barnyard Economist v5"
approximation (zoo #10). See harness.zoo.public_baseline_approx's module
docstring for the source and the defaults chosen where the source doesn't
give concrete numbers."""

from __future__ import annotations

import pytest
from harness.zoo import gate_zoo
from harness.zoo.public_baseline_approx import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
TURNS_PER_DAY = 24


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_public_baseline_approx_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "public-baseline-approx" in roster

    def test_public_baseline_approx_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["public-baseline-approx"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["public-baseline-approx"]
        agent = factory()
        assert callable(agent)


class TestRosterArithmetic:
    def test_gate_zoo_stays_within_the_ten_member_cap(self) -> None:
        assert len(gate_zoo()) <= 10

    def test_public_baseline_approx_is_present(self) -> None:
        assert "public-baseline-approx" in gate_zoo()


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


def _all_market_orders(env: object) -> list[list[object]]:
    orders: list[list[object]] = []
    for step in env.steps:  # type: ignore[attr-defined]
        action = step[0].action or {}
        if not isinstance(action, dict):
            continue
        for order in action.get("market", []):
            if isinstance(order, list):
                orders.append(order)
    return orders


class TestLivestockFirstNoLand:
    """Archetype-specific mutation-sensitive invariants: livestock-first
    day-0 burst, never buy land, never touch fertilizer."""

    def _play(self, episode_steps: int) -> object:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": episode_steps})
        env.run([make_agent(), "pass"])
        return env

    def test_never_buys_land_over_a_full_episode(self) -> None:
        env = self._play(720)
        orders = _all_market_orders(env)
        assert not any(order[0] == "BUY_LAND" for order in orders if order)

    def test_herd_reaches_two_of_each_animal_by_day_three_and_never_exceeds_it(self) -> None:
        env = self._play(720)

        def herd_counts(day: int) -> dict[str, int]:
            obs = env.steps[day * TURNS_PER_DAY][0].observation  # type: ignore[attr-defined,index]
            counts: dict[str, int] = {}
            for row in obs["farms"][0]["tiles"]:
                for tile in row:
                    if isinstance(tile, dict) and "animal" in tile:
                        counts[tile["animal"]] = counts.get(tile["animal"], 0) + 1
            return counts

        expected = {"GOOSE": 2, "COW": 2, "SHEEP": 2}
        assert herd_counts(3) == expected
        for day in range(3, 30):
            assert herd_counts(day) == expected, f"day {day}"

    def test_no_fertilizer_orders_ever(self) -> None:
        env = self._play(720)
        orders = _all_market_orders(env)
        assert not any(
            order[0] == "BUY_PRODUCT" and len(order) > 1 and order[1] == "FERTILIZER" for order in orders
        )
        assert not any(
            order[0] == "SELL" and len(order) > 1 and order[1] == "FERTILIZER" for order in orders
        )

        for step in env.steps:  # type: ignore[attr-defined]
            action = step[0].action or {}
            if not isinstance(action, dict):
                continue
            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            for a in unit_actions:
                if isinstance(a, list) and a:
                    assert a[0] not in ("FERTILIZE", "COLLECT_FERTILIZER")


class TestAtomicPlantBudget:
    def test_never_orders_more_wheat_plants_than_seeds_held(self) -> None:
        # Same atomic-PLANT trap as wheat-spam's own regression test: the
        # engine rewrites ALL PLANT orders for a crop to PASS for a turn
        # where total demand exceeds seeds held.
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
    def test_completes_a_full_720_step_game_without_crashing(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]  # type: ignore[attr-defined]
        assert statuses == ["DONE", "DONE"]
