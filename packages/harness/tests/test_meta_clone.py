"""meta-clone economy-core fixture (slice 1 of 2) — pinned to Kaggle episode
90568437's converged ranch. Not yet registered in the gate zoo (slice 2)."""

from __future__ import annotations

from collections import defaultdict

import pytest
from harness.zoo import gate_zoo
from harness.zoo.meta_clone import make_agent
from kaggle_environments import make

TURNS_PER_DAY = 24
EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
FULL_CONFIG = {"seed": 7, "episodeSteps": 720}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


def _run_full_game(seed: int) -> object:
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
    env.run([make_agent(), "starter"])
    return env


def _all_actions(env: object) -> list[tuple[int, dict]]:
    """(step, action) for every real (non-placeholder) decision in the run."""
    return [(k - 1, env.steps[k][0].action) for k in range(1, len(env.steps))]  # type: ignore[attr-defined]


def _unit_actions(action: dict) -> list[list[str]]:
    return [action.get("farmer", ["PASS"]), *action.get("hands", [])]


class TestFactory:
    def test_factory_is_callable(self) -> None:
        assert callable(make_agent)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        agent = make_agent()
        assert callable(agent)


class TestNotYetRegistered:
    def test_meta_clone_not_in_gate_zoo(self) -> None:
        assert "meta-clone" not in gate_zoo()


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


@pytest.fixture(scope="module")
def full_game_env() -> object:
    return _run_full_game(seed=7)


class TestFullGameCrashFree:
    @pytest.mark.slow
    def test_completes_crash_free_across_multiple_seeds(self) -> None:
        for seed in (2, 3, 5, 11, 13):
            env = _run_full_game(seed)
            statuses = [step.status for step in env.steps[-1]]  # type: ignore[attr-defined]
            assert statuses == ["DONE", "DONE"]


LAND_DAY_HOUR_ZERO_STEP = 9 * TURNS_PER_DAY


class TestLandTiming:
    @pytest.mark.slow
    def test_buy_land_fires_exactly_once_on_day_9(self, full_game_env: object) -> None:
        buy_land_steps = [
            step
            for step, action in _all_actions(full_game_env)
            if ["BUY_LAND"] in action.get("market", [])
        ]
        assert buy_land_steps == [LAND_DAY_HOUR_ZERO_STEP]


class TestHireCadence:
    @pytest.mark.slow
    def test_hire_counts_match_table_for_key_days(self, full_game_env: object) -> None:
        # The engine's own ``hires_today`` counter (reset nightly) is the
        # authoritative measure of *successful* hires -- counting "HIRE"
        # orders in the action stream would overcount, since a turn that
        # queues more than the engine's maxMarketOrdersPerTurn (10) has
        # trailing orders silently dropped. The last observation of the day
        # (hour 23) reflects the day's final total.
        expected = {0: 8, 1: 4, 5: 7, 9: 9, 10: 7, 11: 11, 12: 12}
        for day, expected_hires in expected.items():
            step = (day + 1) * TURNS_PER_DAY - 1
            farm = full_game_env.steps[step][0].observation["farms"][0]  # type: ignore[attr-defined]
            assert farm["hires_today"] == expected_hires, f"day {day}"
            assert len(farm["hands"]) == expected_hires, f"day {day}"


class TestPlantingWindow:
    @pytest.mark.slow
    def test_no_planting_after_day_24_and_no_carrot_or_tomato(self, full_game_env: object) -> None:
        for step, action in _all_actions(full_game_env):
            day = step // TURNS_PER_DAY
            for order in _unit_actions(action):
                if isinstance(order, list) and order[:1] == ["PLANT"]:
                    assert day <= 24, f"planted on day {day}: {order}"
                    assert order[1] not in ("CARROT", "TOMATO"), order


class TestFeedStockBuying:
    @pytest.mark.slow
    def test_buy_product_wheat_only_hour_1_or_2_and_never_before_day_8(
        self, full_game_env: object
    ) -> None:
        found_any = False
        for step, action in _all_actions(full_game_env):
            day = step // TURNS_PER_DAY
            hour = step % TURNS_PER_DAY
            for order in action.get("market", []):
                if order[0] == "BUY_PRODUCT":
                    found_any = True
                    assert order[1] == "WHEAT", order
                    assert hour in (1, 2), f"day {day} hour {hour}: {order}"
                    assert day >= 8, f"day {day} hour {hour}: {order}"
        assert found_any


class TestSellWindows:
    @pytest.mark.slow
    def test_no_sell_outside_hours_0_1_or_19_23(self, full_game_env: object) -> None:
        allowed_hours = {0, 1, 19, 20, 21, 22, 23}
        found_any = False
        for step, action in _all_actions(full_game_env):
            hour = step % TURNS_PER_DAY
            for order in action.get("market", []):
                if order[0] == "SELL":
                    found_any = True
                    assert hour in allowed_hours, f"hour {hour}: {order}"
        assert found_any


class TestWateringWindDown:
    @pytest.mark.slow
    def test_distinct_tiles_watered_meets_floor_through_day_26_and_caps_after(
        self, full_game_env: object
    ) -> None:
        env = full_game_env
        watered_by_day: dict[int, set[tuple[int, int]]] = defaultdict(set)
        for k in range(1, len(env.steps)):  # type: ignore[attr-defined]
            prior_obs = env.steps[k - 1][0].observation  # type: ignore[attr-defined]
            action = env.steps[k][0].action  # type: ignore[attr-defined]
            day = prior_obs["step"] // TURNS_PER_DAY
            farm = prior_obs["farms"][0]
            positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]
            for pos, order in zip(positions, _unit_actions(action), strict=True):
                if isinstance(order, list) and order[:1] == ["WATER"]:
                    watered_by_day[day].add(pos)

        assert len(watered_by_day[26]) >= 14
        for day in (27, 28, 29):
            assert len(watered_by_day[day]) <= 8, f"day {day}: {len(watered_by_day[day])}"
