"""chaos-legal-random opponent archetype -- seeded uniformly-random-but-legal
actions, registered in the EXTENDED zoo only (issue #39). See
harness.zoo.chaos_legal_random's module docstring for the full design."""

from __future__ import annotations

import pytest
from harness.zoo import extended_zoo, gate_zoo
from harness.zoo.chaos_legal_random import make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
_NON_CRASH_STATUSES = {"ACTIVE", "DONE"}

# Independent copies of the engine's legal vocabulary (not imported from
# harness.zoo.chaos_legal_random): mirroring the implementation's own
# constants here would let a mutation to those constants escape undetected,
# since the mutated "ground truth" would agree with the mutated sampler.
# Values transcribed from _apply_unit_action / _parse_order in
# kaggle_environments/envs/kaggriculture/kaggriculture.py, per this issue's
# own "Verified engine facts" section.
_UNIT_OPS = {
    "PASS",
    "NORTH",
    "SOUTH",
    "EAST",
    "WEST",
    "PLANT",
    "WATER",
    "HARVEST",
    "DIG",
    "DROP",
    "PICKUP",
    "FERTILIZE",
    "BUILD_COOP",
    "BUILD_PASTURE",
    "PLACE",
    "FEED",
    "COLLECT_FERTILIZER",
    "CARE",
}
_MARKET_OPS = {"HIRE", "BUY_LAND", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"}
_CROPS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
_ANIMALS = {"GOOSE", "COW", "SHEEP"}
_PRODUCTS = {
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
}
_PICKUP_ITEMS = _PRODUCTS | _ANIMALS
_BUY_PRODUCT_ITEMS = {"WHEAT", "FERTILIZER"}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


class TestRegistration:
    def test_chaos_legal_random_is_in_extended_zoo(self) -> None:
        roster = extended_zoo()
        assert "chaos-legal-random" in roster

    def test_chaos_legal_random_factory_is_callable(self) -> None:
        roster = extended_zoo()
        factory = roster["chaos-legal-random"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = extended_zoo()
        factory = roster["chaos-legal-random"]
        agent = factory()
        assert callable(agent)

    def test_chaos_legal_random_not_in_gate_zoo(self) -> None:
        assert "chaos-legal-random" not in gate_zoo()

    def test_gate_zoo_stays_under_cap(self) -> None:
        assert len(gate_zoo()) <= 10


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


class TestLegalVocabulary:
    """Teeth-check: the engine silently no-ops any malformed/unrecognized
    action rather than crashing or flagging it, so nothing else in this
    suite would catch a made-up or mistyped op string sneaking into the
    sampler -- this is the only test that would."""

    def _check_unit_action(self, unit_action: object) -> None:
        assert isinstance(unit_action, list) and unit_action
        op = unit_action[0]
        assert op in _UNIT_OPS
        if op == "PLANT":
            assert unit_action[1] in _CROPS
        elif op == "PICKUP":
            assert unit_action[1] in _PICKUP_ITEMS
            assert isinstance(unit_action[2], int)
        elif op == "PLACE":
            assert unit_action[1] in _ANIMALS
            assert isinstance(unit_action[2], int)

    def _check_market_order(self, order: object) -> None:
        assert isinstance(order, list) and order
        op = order[0]
        assert op in _MARKET_OPS
        if op == "BUY_SEED":
            assert order[1] in _CROPS
        elif op == "BUY_PRODUCT":
            assert order[1] in _BUY_PRODUCT_ITEMS
        elif op == "BUY_ANIMAL":
            assert order[1] in _ANIMALS
        elif op == "SELL":
            assert order[1] in _PRODUCTS

    def test_every_action_uses_only_the_legal_vocabulary(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 240})
        env.run([make_agent(), "starter"])

        checked_any = False
        for step in env.steps[1:]:  # type: ignore[attr-defined]
            action = step[0].action
            if not isinstance(action, dict):
                continue
            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            for unit_action in unit_actions:
                self._check_unit_action(unit_action)
                checked_any = True
            for order in action.get("market", []):
                self._check_market_order(order)
                checked_any = True
        assert checked_any

    def test_cross_seed_divergence_after_day_zero(self) -> None:
        env_a = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 96})
        env_a.run([make_agent(), "pass"])
        env_b = make("kaggriculture", configuration={"seed": 41, "episodeSteps": 96})
        env_b.run([make_agent(), "pass"])

        steps = min(len(env_a.steps), len(env_b.steps))  # type: ignore[arg-type]
        diverged = any(
            env_a.steps[k][0].action != env_b.steps[k][0].action  # type: ignore[index]
            for k in range(24, steps)
        )
        assert diverged


class TestFullGame:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", [7, 41, 43, 100, 202])
    def test_completes_a_full_720_step_game_without_crashing(self, seed: int) -> None:
        env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        for step in env.steps:  # type: ignore[attr-defined]
            for state in step:
                assert state.status in _NON_CRASH_STATUSES
