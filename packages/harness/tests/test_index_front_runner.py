"""index-front-runner opponent archetype — index-0 sell-priority exploiter
(zoo design #21). See harness.zoo.index_front_runner's module docstring for
the engine mechanic this fixture exists to exploit and eval-pool-test."""

from __future__ import annotations

from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.index_front_runner import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}

FULL_GAME_SEEDS = [7, 41, 43, 100, 202]


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_index_front_runner_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "index-front-runner" in roster

    def test_index_front_runner_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["index-front-runner"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["index-front-runner"]
        agent = factory()
        assert callable(agent)


class TestRosterArithmetic:
    def test_roster_stays_within_gate_zoo_cap(self) -> None:
        roster = gate_zoo()
        assert len(roster) <= 10

    def test_index_front_runner_is_present(self) -> None:
        roster = gate_zoo()
        assert "index-front-runner" in roster


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = _run_early_game()
        env2 = _run_early_game()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]
        assert money1 == money2

        action1 = env1.steps[1][0].action
        action2 = env2.steps[1][0].action
        assert action1 == action2


class TestIndexZeroPlacement:
    """Teeth-check: SELL WHEAT must sit at market[0], ahead of any other
    order competing for placement -- that's the whole point of an index-0
    front-runner exploiting the engine's process-market-by-index mechanic
    (see the module docstring). A synthetic engine-shaped observation
    isolates market-order logic from movement/harvest choices, the same way
    test_melon_dumper.py's TestHoldThenDump builds its own."""

    def _obs(self, *, shed_wheat: int, price: float, step: int = 5 * 24) -> dict[str, Any]:
        tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
        farm = {
            "money": 3000.0,
            "tiles": tiles,
            "farmer": [9, 9],  # off every TARGET_TILES position
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        }
        return {
            "step": step,
            "player": 0,
            "farms": [farm, farm],
            "private": {
                "seeds": {"WHEAT": 0},
                "shed": {"WHEAT": shed_wheat},
                "inventories": [{}],
            },
            "market": {"prices": {"WHEAT": price}},
        }

    def _sell_order(self, action: dict[str, Any]) -> list[object] | None:
        for order in action["market"]:
            if not isinstance(order, list) or len(order) < 3:
                continue
            if order[0] == "SELL" and order[1] == "WHEAT":
                return order
        return None

    def test_sell_order_is_first_when_price_above_floor_and_shed_has_wheat(self) -> None:
        agent = make_agent()
        # step = 5 * 24 is a day boundary, so HIRE orders are also expected
        # this turn -- proving SELL still wins index 0 over competing orders.
        action = agent(self._obs(shed_wheat=40, price=25, step=5 * 24))
        assert action["market"][0] == ["SELL", "WHEAT", 99999]
        assert ["HIRE"] in action["market"]

    def test_no_sell_order_when_price_at_or_below_floor(self) -> None:
        agent = make_agent()
        action = agent(self._obs(shed_wheat=40, price=4, step=5 * 24 + 1))
        assert self._sell_order(action) is None

    def test_sells_at_exactly_the_floor_price(self) -> None:
        agent = make_agent()
        action = agent(self._obs(shed_wheat=40, price=5, step=5 * 24 + 1))
        assert action["market"][0] == ["SELL", "WHEAT", 99999]

    def test_no_sell_order_when_shed_empty(self) -> None:
        agent = make_agent()
        action = agent(self._obs(shed_wheat=0, price=25, step=5 * 24 + 1))
        assert self._sell_order(action) is None


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held(self) -> None:
        # Same atomic-PLANT trap as wheat-spam's own regression test: the
        # engine rewrites ALL PLANT orders for a crop to PASS for a turn
        # where total demand exceeds seeds held.
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
    @pytest.mark.parametrize("seed", FULL_GAME_SEEDS)
    def test_completes_a_full_720_step_game_without_crashing(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]
        assert statuses == ["DONE", "DONE"]
