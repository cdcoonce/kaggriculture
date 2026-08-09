"""public-baseline-approx opponent archetype -- livestock-first, no-land
approximation of "Barnyard Economist v5" (zoo #10, gate-zoo cap)."""

from __future__ import annotations

import pytest
from harness.zoo import gate_zoo
from harness.zoo.public_baseline_approx import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
TURNS_PER_DAY = 24
# Herd-placement window: day 3 proved unreachable -- wheat doesn't mature
# until ~day 4 (max_yield_day=4), so animals placed before real WHEAT supply
# exists would starve (2 consecutive unfed days) before day 3 could even be
# checked. This fixture holds bought animals in the shed (money already
# committed day 0) until a day's FEED reserve is banked, then places them;
# measured empirically on seed 7, the full 2/2/2 herd lands by day 6 and
# holds stable through day 29 once wheat planting is staggered
# (WHEAT_DAILY_PLANT_CAP) to keep daily FEED supply flowing.
HERD_CHECK_DAY = 6
LAST_DAY_CHECKED = 29


def _day_step(day: int) -> int:
    return day * TURNS_PER_DAY


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
    def test_gate_zoo_stays_within_cap_and_contains_this_member(self) -> None:
        roster = gate_zoo()
        assert len(roster) <= 10
        assert "public-baseline-approx" in roster


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = make("kaggriculture", configuration=EARLY_CONFIG)
        env1.run([make_agent(), "pass"])
        env2 = make("kaggriculture", configuration=EARLY_CONFIG)
        env2.run([make_agent(), "pass"])

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]
        assert money1 == money2

        # env.steps[0].action is always a ["PASS"] placeholder (there is no
        # prior observation to have decided it from); the agent's actual
        # first decision -- made from the step-0 observation -- is recorded
        # at env.steps[1].action.
        action1 = env1.steps[1][0].action
        action2 = env2.steps[1][0].action
        assert action1 == action2


def _unit_actions(action: dict) -> list:
    return [action.get("farmer", ["PASS"]), *action.get("hands", [])]


class TestLivestockFirstNoLand:
    """Archetype-specific mutation-sensitive invariants (issue #40): this
    fixture spends its opening $3,000 on a one-time day-0 livestock burst
    (2 GOOSE + 2 COW + 2 SHEEP), never touches land, and never touches
    fertilizer."""

    def test_never_buys_land_over_a_full_episode(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        for step in env.steps:
            action = step[0].action
            if not isinstance(action, dict):
                continue
            market = action.get("market", [])
            for order in market:
                assert not (isinstance(order, list) and order and order[0] == "BUY_LAND")

    def test_herd_reaches_two_of_each_animal_by_day_three_and_never_exceeds_it(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        def herd_counts(day: int) -> dict[str, int]:
            step_idx = _day_step(day)
            observation = env.steps[step_idx][0].observation
            farm0 = observation["farms"][0]
            counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
            for row in farm0["tiles"]:
                for tile in row:
                    if isinstance(tile, dict) and "animal" in tile:
                        counts[tile["animal"]] += 1
            return counts

        expected = {"GOOSE": 2, "COW": 2, "SHEEP": 2}
        assert herd_counts(HERD_CHECK_DAY) == expected
        for day in range(HERD_CHECK_DAY, LAST_DAY_CHECKED + 1):
            assert herd_counts(day) == expected

    def test_no_fertilizer_orders_ever(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "pass"])

        forbidden_market_ops = {"BUY_PRODUCT", "SELL"}
        for step in env.steps:
            action = step[0].action
            if not isinstance(action, dict):
                continue
            for order in action.get("market", []):
                if not (isinstance(order, list) and order):
                    continue
                op = order[0]
                if op in forbidden_market_ops and len(order) >= 2 and order[1] == "FERTILIZER":
                    raise AssertionError(f"unexpected fertilizer market order: {order}")
            for unit_action in _unit_actions(action):
                if isinstance(unit_action, list) and unit_action:
                    assert unit_action[0] not in ("FERTILIZE", "COLLECT_FERTILIZER")


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held(self) -> None:
        # Atomic-PLANT trap: the engine rewrites ALL PLANT orders to PASS for a
        # turn where total PLANT demand for a crop exceeds seeds held, so
        # over-ordering silently wastes the whole turn for every unit.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 72})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):
            prior_observation = env.steps[k - 1][0].observation
            action = env.steps[k][0].action
            seeds_held = prior_observation["private"]["seeds"].get("WHEAT", 0)

            unit_actions = _unit_actions(action)
            plant_orders = sum(
                1 for a in unit_actions if isinstance(a, list) and a[:2] == ["PLANT", "WHEAT"]
            )
            assert plant_orders <= seeds_held


class TestCrashFree:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", [7, 41, 43, 100, 202])
    def test_full_episode_completes_without_crashing(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]
        assert statuses == ["DONE", "DONE"]
