"""fert-market-crasher opponent archetype — modest wheat economy funding an
accumulate-then-dump FERTILIZER cycle (zoo #21c). See
harness.zoo.fert_market_crasher's module docstring for the full design."""

from __future__ import annotations

from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.fert_market_crasher import TURNS_PER_DAY, make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
FULL_GAME_SEEDS = [7, 41, 43, 100, 202]


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_fert_market_crasher_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "fert-market-crasher" in roster

    def test_fert_market_crasher_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["fert-market-crasher"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["fert-market-crasher"]
        agent = factory()
        assert callable(agent)


class TestRosterArithmetic:
    def test_roster_stays_at_or_under_the_gate_zoo_cap(self) -> None:
        assert len(gate_zoo()) <= 10

    def test_fert_market_crasher_is_present(self) -> None:
        assert "fert-market-crasher" in gate_zoo()


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


class TestAccumulateThenDump:
    """Teeth-check: the archetype's own accumulate-then-dump mechanism,
    verified against a synthetic engine-shaped observation with the farmer
    parked off-tile at [9, 9] so market logic is isolated from movement/
    harvest choices (mirrors test_melon_dumper.py's TestHoldThenDump)."""

    def _obs(
        self,
        *,
        day: int,
        hour: int,
        money: float = 3000.0,
        fertilizer_shed: int = 0,
        fertilizer_price: int = 100,
    ) -> dict[str, Any]:
        tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
        farm = {
            "money": money,
            "tiles": tiles,
            "farmer": [9, 9],  # off every WHEAT_TILES position
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        }
        step = day * TURNS_PER_DAY + hour
        return {
            "step": step,
            "player": 0,
            "farms": [farm, farm],
            "market": {"prices": {"FERTILIZER": fertilizer_price}},
            "private": {
                "seeds": {"WHEAT": 0},
                "shed": {"WHEAT": 0, "FERTILIZER": fertilizer_shed},
                "inventories": [{}],
            },
        }

    def _fert_orders(self, action: dict[str, Any]) -> list[list[object]]:
        return [
            order
            for order in action["market"]
            if isinstance(order, list) and len(order) >= 2 and order[1] == "FERTILIZER"
        ]

    def test_buys_fertilizer_during_accumulate_phase_window_hour(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=5, hour=1, money=3000, fertilizer_shed=0))
        orders = self._fert_orders(action)
        buys = [o for o in orders if o[0] == "BUY_PRODUCT"]
        sells = [o for o in orders if o[0] == "SELL"]
        assert len(buys) == 1
        assert buys[0][2] > 0
        assert sells == []

    def test_buy_quantity_is_capped_at_ten_units_per_window(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=5, hour=1, money=100000, fertilizer_shed=0))
        orders = self._fert_orders(action)
        buys = [o for o in orders if o[0] == "BUY_PRODUCT"]
        assert len(buys) == 1
        assert buys[0][2] == 10

    def test_no_fertilizer_orders_outside_window_hours_in_accumulate_phase(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=5, hour=10, money=3000, fertilizer_shed=0))
        assert self._fert_orders(action) == []

    def test_sells_everything_during_dump_phase_window_hour(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=20, hour=19, money=100, fertilizer_shed=37))
        orders = self._fert_orders(action)
        assert orders == [["SELL", "FERTILIZER", 37]]

    def test_no_fertilizer_orders_outside_window_hours_in_dump_phase(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=20, hour=10, money=100, fertilizer_shed=37))
        assert self._fert_orders(action) == []

    def test_no_buying_at_the_exact_dump_day_boundary(self) -> None:
        agent = make_agent()
        action = agent(self._obs(day=15, hour=1, money=3000, fertilizer_shed=0))
        orders = self._fert_orders(action)
        buys = [o for o in orders if o[0] == "BUY_PRODUCT"]
        assert buys == []


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
