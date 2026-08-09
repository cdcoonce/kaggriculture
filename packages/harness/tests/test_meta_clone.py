"""meta-clone opponent archetype — economy core, slice 1/2 (zoo #21, issue
#23). See harness.zoo.meta_clone's module docstring for the full pacing
spec pinned to Kaggle episode 90568437. This slice is deliberately NOT
registered in harness.zoo.SCRIPTED -- registration is slice 2's job."""

from __future__ import annotations

from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.meta_clone import (
    ALL_TILES,
    PLANT_ORDERS,
    PLANT_SCHEDULE,
    TURNS_PER_DAY,
    make_agent,
)
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
FULL_CONFIG = {"seed": 7, "episodeSteps": 720}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


@pytest.fixture(scope="module")
def full_episode() -> object:
    env = make("kaggriculture", configuration=FULL_CONFIG)
    env.run([make_agent(), "starter"])
    return env


def _max_hires_today(env: Any, day: int, player: int = 0) -> int:
    steps = env.steps
    lo = day * TURNS_PER_DAY
    hi = min((day + 1) * TURNS_PER_DAY, len(steps))
    return max(steps[i][0].observation["farms"][player]["hires_today"] for i in range(lo, hi))


def _market_orders(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict):
        return []
    orders = action.get("market", [])
    return orders if isinstance(orders, list) else []


def _unit_actions(action: Any) -> list[list[Any]]:
    if not isinstance(action, dict):
        return []
    return [action.get("farmer", ["PASS"]), *action.get("hands", [])]


class TestRegistration:
    def test_meta_clone_not_registered_in_gate_zoo(self) -> None:
        assert "meta-clone" not in gate_zoo()

    def test_factory_is_callable(self) -> None:
        agent = make_agent()
        assert callable(agent)


class TestTilePool:
    def test_pool_is_the_forty_eight_nw_ne_farmable_tiles(self) -> None:
        # NW (24, excluding its shed-access tile) + NE (24, excluding its own)
        # == 48 farmable tiles, all north of the NW/NE quadrant split at y<5.
        assert len(ALL_TILES) == 48
        assert len(set(ALL_TILES)) == 48
        assert all(0 <= x < 10 and 0 <= y < 5 for x, y in ALL_TILES)

    def test_shed_access_tiles_excluded_from_the_pool(self) -> None:
        assert (4, 4) not in ALL_TILES
        assert (5, 4) not in ALL_TILES

    def test_every_crop_can_reach_every_tile_in_the_shared_pool(self) -> None:
        # The pool is shared, not partitioned into fixed per-crop zones: peak
        # concurrent occupancy per crop does not fit a static split, but the
        # peaks do not coincide. A partition would silently cap a crop below
        # what PLANT_SCHEDULE asks for.
        for crop in ("MELON", "STRAWBERRY", "WHEAT"):
            assert set(PLANT_ORDERS[crop]) == set(ALL_TILES)

    def test_pool_is_large_enough_for_the_peak_wheat_cohort(self) -> None:
        # Days 19-24 plant 5+6+10+5+6 wheat while wheat sits 4 days before
        # harvest, so the late-game wheat cohort alone wants ~27 tiles --
        # more than the 11 a static wheat zone could offer.
        late_wheat = sum(PLANT_SCHEDULE[d].get("WHEAT", 0) for d in (20, 21, 23, 24))
        assert late_wheat == 27
        assert len(ALL_TILES) >= late_wheat


class TestEarlyBehavior:
    def test_has_planted_wheat_by_step_96(self) -> None:
        env = _run_early_game()
        farm0 = env.steps[-1][0].observation["farms"][0]
        found = any(
            isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "WHEAT"
            for row in farm0["tiles"]
            for tile in row
        )
        assert found

    def test_orders_wheat_and_melon_seed_and_holds_it_by_step_96(self) -> None:
        # Day-0 hires alone would drop money below its $3,000 start, so a
        # money check is no evidence of seed buying: assert the BUY_SEED
        # orders themselves, and that they actually land in the seed bag.
        env = _run_early_game()
        crops_ordered = {
            order[1]
            for step in env.steps[1:]
            for order in _market_orders(step[0].action)
            if isinstance(order, list) and order[:1] == ["BUY_SEED"]
        }
        assert crops_ordered == {"WHEAT", "MELON"}
        assert any(
            step[0].observation["private"]["seeds"].get("WHEAT", 0) > 0 for step in env.steps
        )
        assert any(
            step[0].observation["private"]["seeds"].get("MELON", 0) > 0 for step in env.steps
        )


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = _run_early_game()
        env2 = _run_early_game()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]
        assert money1 == money2

        # env.steps[0].action is always a ["PASS"] placeholder; the agent's
        # actual first decision is recorded at env.steps[1].action.
        action1 = env1.steps[1][0].action
        action2 = env2.steps[1][0].action
        assert action1 == action2


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_than_seeds_held_for_any_crop(self) -> None:
        # Atomic-PLANT trap: the engine rewrites ALL PLANT orders for a crop
        # to PASS for a turn where total demand exceeds seeds held.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 96})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):
            prior_observation = env.steps[k - 1][0].observation
            action = env.steps[k][0].action
            seeds_held = prior_observation["private"]["seeds"]

            demand: dict[str, int] = {}
            for a in _unit_actions(action):
                if isinstance(a, list) and a[:1] == ["PLANT"]:
                    demand[a[1]] = demand.get(a[1], 0) + 1
            for crop, n in demand.items():
                assert n <= seeds_held.get(crop, 0)


@pytest.mark.slow
class TestFullEpisode:
    def test_crash_free_across_five_seeds(self) -> None:
        for seed in range(5):
            env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
            env.run([make_agent(), "starter"])
            statuses = [step.status for step in env.steps[-1]]
            assert statuses == ["DONE", "DONE"]

    def test_buy_land_fires_exactly_once_on_day_9(self, full_episode: Any) -> None:
        steps = full_episode.steps

        unlock_days = []
        prev_len = 1
        for i in range(len(steps)):
            obs = steps[i][0].observation
            cur_len = len(obs["farms"][0]["unlocked_quadrants"])
            if cur_len > prev_len:
                unlock_days.append(obs["step"] // TURNS_PER_DAY)
            prev_len = cur_len
        assert unlock_days == [9]

        land_orders = sum(
            1
            for k in range(1, len(steps))
            for order in _market_orders(steps[k][0].action)
            if isinstance(order, list) and order[:1] == ["BUY_LAND"]
        )
        assert land_orders == 1

    @pytest.mark.parametrize(
        ("day", "expected_hires"),
        [(0, 8), (1, 4), (5, 7), (11, 11), (12, 12)],
    )
    def test_hire_counts_match_schedule(
        self, full_episode: Any, day: int, expected_hires: int
    ) -> None:
        assert _max_hires_today(full_episode, day) == expected_hires

    def test_no_planting_after_day_24(self, full_episode: Any) -> None:
        steps = full_episode.steps

        # Asserted against a literal boundary, not the LAST_PLANT_DAY
        # constant itself -- a mutation that widens that constant must not
        # be able to move this test's goalposts along with it.
        for k in range(1, len(steps)):
            prior_day = steps[k - 1][0].observation["step"] // TURNS_PER_DAY
            for a in _unit_actions(steps[k][0].action):
                if isinstance(a, list) and a[:1] == ["PLANT"]:
                    assert prior_day <= 24

    def test_never_plants_carrot_or_tomato(self, full_episode: Any) -> None:
        steps = full_episode.steps
        for k in range(1, len(steps)):
            for a in _unit_actions(steps[k][0].action):
                if isinstance(a, list) and a[:1] == ["PLANT"]:
                    assert a[1] not in ("CARROT", "TOMATO")

    def test_buy_product_wheat_only_at_hour_1_or_2_and_never_before_day_8(
        self, full_episode: Any
    ) -> None:
        # Asserted against literal hour/day boundaries, not the module's own
        # WHEAT_PRODUCT_BUY_HOURS/WHEAT_PRODUCT_BUY_FIRST_DAY constants -- a
        # mutation that widens those constants must not move this test's
        # goalposts along with it.
        steps = full_episode.steps
        saw_at_least_one = False
        for k in range(1, len(steps)):
            prior_step = steps[k - 1][0].observation["step"]
            day = prior_step // TURNS_PER_DAY
            hour = prior_step % TURNS_PER_DAY
            for order in _market_orders(steps[k][0].action):
                if isinstance(order, list) and order[:2] == ["BUY_PRODUCT", "WHEAT"]:
                    saw_at_least_one = True
                    assert hour in (1, 2)
                    assert day >= 8
        assert saw_at_least_one

    def test_no_sell_order_outside_the_town_tick_windows(self, full_episode: Any) -> None:
        # Literal hour set, not the module's own SELL_HOURS constant -- see
        # the wheat-buy test above for why.
        steps = full_episode.steps
        saw_at_least_one = False
        for k in range(1, len(steps)):
            prior_step = steps[k - 1][0].observation["step"]
            hour = prior_step % TURNS_PER_DAY
            for order in _market_orders(steps[k][0].action):
                if isinstance(order, list) and order[:1] == ["SELL"]:
                    saw_at_least_one = True
                    assert hour in (0, 1, 19, 20, 21, 22, 23)
        assert saw_at_least_one

    def test_watering_winds_down_for_the_final_three_days(self, full_episode: Any) -> None:
        # Literal day/cap boundaries, not the module's own
        # WATER_WINDDOWN_DAY/WATER_WINDDOWN_CAP constants -- see the
        # wheat-buy test above for why.
        steps = full_episode.steps

        def water_ops_on_day(day: int) -> int:
            # steps[k].action is the action DECIDED from steps[k-1]'s
            # observation, so a day's own ops are the actions recorded at
            # k = lo+1 .. hi; counting from k = lo would fold in the last
            # turn of the previous day.
            lo = day * TURNS_PER_DAY
            hi = (day + 1) * TURNS_PER_DAY
            count = 0
            for k in range(lo + 1, min(hi + 1, len(steps))):
                for a in _unit_actions(steps[k][0].action):
                    if isinstance(a, list) and a == ["WATER"]:
                        count += 1
            return count

        # Day 26 -- the criterion's own boundary, the last unthrottled day --
        # not a more comfortable day further from the cliff.
        assert water_ops_on_day(26) >= 18
        for day in (27, 28, 29):
            assert water_ops_on_day(day) <= 8
