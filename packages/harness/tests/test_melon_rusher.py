"""melon-rusher opponent archetype -- melon monoculture, price-blind
flood-sell (zoo #21 batch). See harness.zoo.melon_rusher's module docstring
for the full design and its contrast with melon-dumper's hold-then-latch."""

from __future__ import annotations

from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.melon_rusher import TARGET_TILES, make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_melon_rusher_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "melon-rusher" in roster

    def test_melon_rusher_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["melon-rusher"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["melon-rusher"]
        agent = factory()
        assert callable(agent)


class TestRosterArithmetic:
    def test_roster_stays_within_gate_cap_and_includes_melon_rusher(self) -> None:
        roster = gate_zoo()
        assert len(roster) <= 10
        assert "melon-rusher" in roster


class TestZoneShape:
    def test_target_tiles_is_twenty_four_tiles(self) -> None:
        assert len(TARGET_TILES) == 24

    def test_shed_tile_excluded(self) -> None:
        assert (4, 4) not in TARGET_TILES


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


class TestFloodNoHold:
    """Teeth-check: melon-rusher sells price-blind and hold-blind on a fixed
    7-hour-of-day window, with no cross-turn latch -- the opposite of
    melon-dumper's withhold-then-burst archetype."""

    def _obs(self, *, melon_shed: int, step: int) -> dict[str, Any]:
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
            "hour": step % 24,
            "player": 0,
            "farms": [farm, farm],
            "private": {
                "seeds": {"WHEAT": 0, "MELON": 0},
                "shed": {"MELON": melon_shed},
                "inventories": [{}],
            },
        }

    def _melon_sell(self, action: dict[str, Any]) -> list[object] | None:
        for order in action["market"]:
            if not isinstance(order, list) or len(order) < 3:
                continue
            if order[0] == "SELL" and order[1] == "MELON":
                return order
        return None

    def test_sells_within_window_hours_when_shed_has_melon(self) -> None:
        agent = make_agent()
        action_hour0 = agent(self._obs(melon_shed=12, step=5 * 24 + 0))
        assert self._melon_sell(action_hour0) == ["SELL", "MELON", 12]

        action_hour19 = agent(self._obs(melon_shed=12, step=5 * 24 + 19))
        assert self._melon_sell(action_hour19) == ["SELL", "MELON", 12]

    def test_no_melon_sell_outside_window_hours(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=12, step=5 * 24 + 10))
        assert self._melon_sell(action) is None

    def test_sells_from_the_very_first_opportunity_no_hold(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=5, step=0 * 24 + 0))
        assert self._melon_sell(action) == ["SELL", "MELON", 5]

    def test_no_wheat_tile_ever_appears(self) -> None:
        env = make("kaggriculture", configuration=EARLY_CONFIG)
        env.run([make_agent(), "pass"])

        for step in env.steps:  # type: ignore[attr-defined]
            farm0 = step[0].observation["farms"][0]
            for row in farm0["tiles"]:
                for tile in row:
                    assert not (isinstance(tile, dict) and tile.get("crop") == "WHEAT")


class TestHiresThreeHandsPerDay:
    def _obs(self, *, step: int) -> dict[str, Any]:
        tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
        farm = {
            "money": 3000.0,
            "tiles": tiles,
            "farmer": [9, 9],
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        }
        return {
            "step": step,
            "hour": step % 24,
            "player": 0,
            "farms": [farm, farm],
            "private": {
                "seeds": {"WHEAT": 0, "MELON": 0},
                "shed": {"MELON": 0},
                "inventories": [{}],
            },
        }

    def test_hires_three_hands_at_start_of_each_day(self) -> None:
        agent = make_agent()
        action = agent(self._obs(step=5 * 24))
        hire_orders = [order for order in action["market"] if order == ["HIRE"]]
        assert len(hire_orders) == 3


class TestAtomicPlantBudget:
    def test_never_orders_more_melon_plants_than_seeds_held(self) -> None:
        # Same atomic-PLANT trap as wheat-spam's/melon-dumper's own
        # regression test: the engine rewrites ALL PLANT orders for a crop to
        # PASS for a turn where total demand exceeds seeds held.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 72})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):  # type: ignore[arg-type]
            prior_observation = env.steps[k - 1][0].observation  # type: ignore[index]
            action = env.steps[k][0].action  # type: ignore[index]
            seeds_held = prior_observation["private"]["seeds"].get("MELON", 0)

            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            plant_orders = sum(
                1 for a in unit_actions if isinstance(a, list) and a[:2] == ["PLANT", "MELON"]
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
