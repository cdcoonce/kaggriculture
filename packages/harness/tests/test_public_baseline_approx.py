"""public-baseline-approx opponent archetype — an approximation of the
public "Barnyard Economist v5" notebook (zoo #10, the final gate-zoo
member). See harness.zoo.public_baseline_approx's module docstring for the
full design and source citations."""

from __future__ import annotations

import pytest
from harness.zoo import gate_zoo
from harness.zoo.public_baseline_approx import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
SEEDS = [7, 41, 43, 100, 202]


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
    def test_gate_zoo_stays_at_or_under_the_ten_member_cap(self) -> None:
        assert len(gate_zoo()) <= 10

    def test_public_baseline_approx_is_registered(self) -> None:
        assert "public-baseline-approx" in gate_zoo()


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        def _run() -> object:
            env = make("kaggriculture", configuration=EARLY_CONFIG)
            env.run([make_agent(), "pass"])
            return env

        env1 = _run()
        env2 = _run()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        assert money1 == money2

        action1 = env1.steps[1][0].action  # type: ignore[attr-defined]
        action2 = env2.steps[1][0].action  # type: ignore[attr-defined]
        assert action1 == action2


class TestLivestockFirstNoLand:
    def _play(self, episode_steps: int) -> object:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": episode_steps})
        env.run([make_agent(), "pass"])
        return env

    def test_never_buys_land_over_a_full_episode(self) -> None:
        env = self._play(720)
        for step in env.steps:  # type: ignore[attr-defined]
            action = step[0].action or {}
            if not isinstance(action, dict):
                continue
            for order in action.get("market", []):
                if isinstance(order, list) and order and order[0] == "BUY_LAND":
                    raise AssertionError(f"unexpected BUY_LAND order: {order}")

    def test_herd_reaches_two_of_each_animal_by_day_three_and_never_exceeds_it(self) -> None:
        env = self._play(720)

        def _herd_counts(day: int) -> dict[str, int]:
            obs = env.steps[day * 24][0].observation  # type: ignore[attr-defined,index]
            counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
            for row in obs["farms"][0]["tiles"]:
                for tile in row:
                    if isinstance(tile, dict) and "animal" in tile:
                        counts[tile["animal"]] = counts.get(tile["animal"], 0) + 1
            return counts

        expected = {"GOOSE": 2, "COW": 2, "SHEEP": 2}
        assert _herd_counts(3) == expected
        for day in range(3, 30):
            assert _herd_counts(day) == expected, f"day {day}"

    def test_no_fertilizer_orders_ever(self) -> None:
        env = self._play(720)
        for step in env.steps:  # type: ignore[attr-defined]
            action = step[0].action or {}
            if not isinstance(action, dict):
                continue
            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            for a in unit_actions:
                if isinstance(a, list) and a and a[0] in ("FERTILIZE", "COLLECT_FERTILIZER"):
                    raise AssertionError(f"unexpected fertilizer unit action: {a}")
            for order in action.get("market", []):
                if not isinstance(order, list) or not order:
                    continue
                if order[0] == "BUY_PRODUCT" and len(order) >= 2 and order[1] == "FERTILIZER":
                    raise AssertionError(f"unexpected BUY_PRODUCT FERTILIZER order: {order}")
                if order[0] == "SELL" and len(order) >= 2 and order[1] == "FERTILIZER":
                    raise AssertionError(f"unexpected SELL FERTILIZER order: {order}")


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held(self) -> None:
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
    @pytest.mark.parametrize("seed", SEEDS)
    def test_completes_a_full_720_step_game_without_crashing(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]  # type: ignore[attr-defined]
        assert statuses == ["DONE", "DONE"]
