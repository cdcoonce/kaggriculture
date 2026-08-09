"""meta-clone economy core (slice 1/2, issue #23) -- land, hires, planting,
feed-stock buying, sell timing, watering wind-down. NOT registered in
harness.zoo.SCRIPTED yet (registration is slice 2's job); see
harness.zoo.meta_clone's module docstring for the full design."""

from __future__ import annotations

import collections
from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.meta_clone import (
    LAND_DAY,
    LAST_PLANT_DAY,
    PLANT_SCHEDULE,
    TURNS_PER_DAY,
    WATER_CAP_LATE,
    WATER_WIND_DOWN_DAY,
    WHEAT_TILES,
    make_agent,
)
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}
FULL_GAME_SEEDS = [7, 41, 43, 100, 202]
CANONICAL_SEED = 7
HIRE_TABLE_CHECK_DAYS = [(0, 8), (1, 4), (5, 7), (9, 9), (10, 7), (11, 11), (12, 12)]


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


def _run_full_game(seed: int) -> object:
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": 720})
    env.run([make_agent(), "starter"])
    return env


def _obs(
    *,
    day: int,
    hour: int,
    money: float = 5000.0,
    shed: dict[str, int] | None = None,
    seeds: dict[str, int] | None = None,
    wheat_price: float = 10.0,
) -> dict[str, Any]:
    """A minimal synthetic obs isolating market-order decisions from
    movement/tile choices (mirrors test_fert_market_crasher.py's own
    ``_obs`` helper): farmer parked at (9, 9), an all-empty tile grid so no
    PLANT/WATER/HARVEST need ever competes with the market assertions."""
    tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
    farm = {
        "money": money,
        "tiles": tiles,
        "farmer": [9, 9],
        "hands": [],
        "unlocked_quadrants": ["NW"],
        "hires_today": 0,
    }
    step = day * TURNS_PER_DAY + hour
    return {
        "step": step,
        "player": 0,
        "farms": [farm, farm],
        "market": {"prices": {"WHEAT": wheat_price}},
        "private": {
            "seeds": seeds or {},
            "shed": shed or {},
            "inventories": [{}],
        },
    }


def _obs_with_live_wheat_tiles(
    *, day: int, hour: int, positions: list[tuple[int, int]]
) -> dict[str, Any]:
    """A synthetic obs with one live, unwatered WHEAT PLANT tile per
    position, and one unit (farmer or hand) standing on each -- isolates the
    watering wind-down cap from pathing/claiming logic."""
    tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
    for x, y in positions:
        tiles[y][x] = {
            "kind": "PLANT",
            "crop": "WHEAT",
            "planted_day": 0,
            "yield_units": 0,
            "watered_today": False,
        }
    farm = {
        "money": 1_000_000.0,
        "tiles": tiles,
        "farmer": list(positions[0]),
        "hands": [list(p) for p in positions[1:]],
        "unlocked_quadrants": ["NW", "NE"],
        "hires_today": 0,
    }
    step = day * TURNS_PER_DAY + hour
    return {
        "step": step,
        "player": 0,
        "farms": [farm, farm],
        "market": {"prices": {"WHEAT": 10.0}},
        "private": {
            "seeds": {},
            "shed": {},
            "inventories": [{} for _ in positions],
        },
    }


class _Trace:
    """Facts extracted from a full-game run's recorded action stream."""

    def __init__(self, env: object) -> None:
        self.land_buy_days: list[int] = []
        self.hires_by_day: dict[int, int] = collections.defaultdict(int)
        self.plant_days: set[int] = set()
        self.crops_planted: set[str] = set()
        self.watered_by_day: dict[int, set[tuple[int, int]]] = collections.defaultdict(set)

        for k in range(1, len(env.steps)):
            obs = env.steps[k - 1][0].observation
            action = env.steps[k][0].action
            step = obs["step"]
            day = step // TURNS_PER_DAY
            farm = obs["farms"][0]
            positions = [tuple(farm["farmer"])] + [tuple(h) for h in farm["hands"]]

            market = action.get("market", []) if isinstance(action, dict) else []
            for order in market:
                if not isinstance(order, list) or not order:
                    continue
                op = order[0]
                if op == "BUY_LAND":
                    self.land_buy_days.append(day)
                elif op == "HIRE":
                    self.hires_by_day[day] += 1

            farmer_a = action.get("farmer", ["PASS"]) if isinstance(action, dict) else ["PASS"]
            hands_a = action.get("hands", []) if isinstance(action, dict) else []
            if not isinstance(hands_a, list):
                hands_a = []
            for idx, a in enumerate([farmer_a, *hands_a]):
                if not isinstance(a, list) or not a:
                    continue
                if a[0] == "PLANT" and len(a) >= 2:
                    self.plant_days.add(day)
                    self.crops_planted.add(a[1])
                elif a[0] == "WATER" and idx < len(positions):
                    self.watered_by_day[day].add(positions[idx])


@pytest.fixture(scope="module")
def canonical_trace() -> _Trace:
    return _Trace(_run_full_game(CANONICAL_SEED))


class TestRegistration:
    def test_meta_clone_is_not_in_gate_zoo(self) -> None:
        # Registration is slice 2's job -- zoo members are immutable once
        # registered, so this slice must land without touching SCRIPTED.
        assert "meta-clone" not in gate_zoo()

    def test_factory_is_callable(self) -> None:
        assert callable(make_agent)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        agent = make_agent()
        assert callable(agent)


class TestDeterminism:
    def test_same_seed_same_final_money_and_same_first_action(self) -> None:
        env1 = _run_early_game()
        env2 = _run_early_game()

        money1 = env1.steps[-1][0].observation["farms"][0]["money"]
        money2 = env2.steps[-1][0].observation["farms"][0]["money"]
        assert money1 == money2

        # env.steps[0].action is always a ["PASS"] placeholder (no prior
        # observation); the agent's first real decision lands at steps[1].
        action1 = env1.steps[1][0].action
        action2 = env2.steps[1][0].action
        assert action1 == action2


class TestLandPurchaseTiming:
    def test_buys_land_only_at_day9_hour0(self) -> None:
        agent = make_agent()
        for day in range(0, 15):
            for hour in (0, 1, 3, 12, 23):
                action = agent(_obs(day=day, hour=hour, money=1_000_000))
                land_orders = [
                    o for o in action["market"] if isinstance(o, list) and o[:1] == ["BUY_LAND"]
                ]
                if day == LAND_DAY and hour == 0:
                    assert land_orders == [["BUY_LAND"]]
                else:
                    assert land_orders == []


class TestHireCounts:
    @pytest.mark.parametrize("day,expected", HIRE_TABLE_CHECK_DAYS)
    def test_hire_count_matches_table_for_day(self, day: int, expected: int) -> None:
        agent = make_agent()
        total = 0
        for hour in range(TURNS_PER_DAY):
            action = agent(_obs(day=day, hour=hour, money=1_000_000))
            total += sum(1 for o in action["market"] if isinstance(o, list) and o[:1] == ["HIRE"])
        assert total == expected


class TestPlantScheduleTable:
    def test_last_plant_day_matches_issue_spec(self) -> None:
        # Pinned to the issue's fixed spec value (24), independent of
        # LAST_PLANT_DAY itself, so a mutation that raises the constant
        # alongside the schedule can't silently pass.
        assert LAST_PLANT_DAY == 24

    def test_no_entries_after_last_plant_day(self) -> None:
        assert all(day <= 24 for day in PLANT_SCHEDULE)

    def test_never_carrot_or_tomato(self) -> None:
        planted_crops = {crop for budget in PLANT_SCHEDULE.values() for crop in budget}
        assert planted_crops <= {"WHEAT", "MELON", "STRAWBERRY"}


class TestFeedStockBuying:
    def test_buys_wheat_at_hour1_and_hour2_from_day8(self) -> None:
        agent = make_agent()
        for hour in (1, 2):
            action = agent(_obs(day=8, hour=hour, money=5000, wheat_price=10.0))
            buys = [
                o
                for o in action["market"]
                if isinstance(o, list) and o[:1] == ["BUY_PRODUCT"] and o[1] == "WHEAT"
            ]
            assert len(buys) == 1
            assert buys[0][2] > 0

    def test_no_wheat_buy_outside_hour1_2(self) -> None:
        agent = make_agent()
        for hour in (0, 3, 10, 15, 20, 23):
            action = agent(_obs(day=8, hour=hour, money=5000, wheat_price=10.0))
            buys = [o for o in action["market"] if isinstance(o, list) and o[:1] == ["BUY_PRODUCT"]]
            assert buys == []

    def test_no_wheat_buy_before_day8(self) -> None:
        agent = make_agent()
        for day in range(0, 8):
            action = agent(_obs(day=day, hour=1, money=5000, wheat_price=10.0))
            buys = [o for o in action["market"] if isinstance(o, list) and o[:1] == ["BUY_PRODUCT"]]
            assert buys == []

    def test_no_wheat_buy_below_money_floor(self) -> None:
        agent = make_agent()
        action = agent(_obs(day=10, hour=1, money=100, wheat_price=10.0))
        buys = [o for o in action["market"] if isinstance(o, list) and o[:1] == ["BUY_PRODUCT"]]
        assert buys == []


class TestSellTiming:
    def test_sells_within_window_hours(self) -> None:
        agent = make_agent()
        for hour in (0, 1, 19, 20, 21, 22, 23):
            action = agent(_obs(day=15, hour=hour, shed={"WHEAT": 5}))
            sells = [o for o in action["market"] if isinstance(o, list) and o[:1] == ["SELL"]]
            assert sells == [["SELL", "WHEAT", 99999]]

    def test_no_sells_outside_window_hours(self) -> None:
        agent = make_agent()
        for hour in range(2, 19):
            action = agent(_obs(day=15, hour=hour, shed={"WHEAT": 5, "MELON": 3, "STRAWBERRY": 2}))
            sells = [o for o in action["market"] if isinstance(o, list) and o[:1] == ["SELL"]]
            assert sells == []


class TestWateringWindDown:
    def test_uncapped_before_wind_down_waters_every_live_tile(self) -> None:
        agent = make_agent()
        positions = list(WHEAT_TILES[:16])
        # day 18: no PLANT_SCHEDULE entry, so this exercises watering in
        # isolation from any incidental same-turn planting.
        obs = _obs_with_live_wheat_tiles(day=18, hour=10, positions=positions)
        action = agent(obs)
        unit_actions = [action["farmer"], *action["hands"]]
        water_count = sum(1 for a in unit_actions if a[:1] == ["WATER"])
        assert water_count == 16

    def test_day_before_wind_down_still_uncapped(self) -> None:
        agent = make_agent()
        positions = list(WHEAT_TILES[:16])
        obs = _obs_with_live_wheat_tiles(day=WATER_WIND_DOWN_DAY - 1, hour=10, positions=positions)
        action = agent(obs)
        unit_actions = [action["farmer"], *action["hands"]]
        water_count = sum(1 for a in unit_actions if a[:1] == ["WATER"])
        assert water_count == 16

    def test_capped_at_water_cap_late_from_wind_down_day(self) -> None:
        agent = make_agent()
        positions = list(WHEAT_TILES[:16])
        obs = _obs_with_live_wheat_tiles(day=WATER_WIND_DOWN_DAY, hour=10, positions=positions)
        action = agent(obs)
        unit_actions = [action["farmer"], *action["hands"]]
        water_count = sum(1 for a in unit_actions if a[:1] == ["WATER"])
        assert water_count == WATER_CAP_LATE


class TestAtomicPlantBudget:
    def test_never_orders_more_plants_of_a_crop_than_seeds_held(self) -> None:
        # Same atomic-PLANT trap as wheat-spam's own regression test: the
        # engine rewrites ALL PLANT orders for a crop to PASS for a turn
        # where total demand exceeds seeds held.
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 288})
        env.run([make_agent(), "pass"])

        for k in range(1, len(env.steps)):
            prior_observation = env.steps[k - 1][0].observation
            action = env.steps[k][0].action
            seeds_held = prior_observation["private"]["seeds"]

            unit_actions = [action.get("farmer", ["PASS"]), *action.get("hands", [])]
            plant_demand: dict[str, int] = collections.defaultdict(int)
            for a in unit_actions:
                if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT":
                    plant_demand[a[1]] += 1
            for crop, demand in plant_demand.items():
                assert demand <= seeds_held.get(crop, 0)


@pytest.mark.slow
class TestFullGameBehavior:
    def test_buys_land_exactly_once_on_day9(self, canonical_trace: _Trace) -> None:
        assert canonical_trace.land_buy_days == [LAND_DAY]

    def test_hire_counts_match_table_in_full_episode(self, canonical_trace: _Trace) -> None:
        for day, expected in HIRE_TABLE_CHECK_DAYS:
            assert canonical_trace.hires_by_day[day] == expected

    def test_no_planting_after_day24(self, canonical_trace: _Trace) -> None:
        assert max(canonical_trace.plant_days) <= 24

    def test_never_plants_carrot_or_tomato(self, canonical_trace: _Trace) -> None:
        assert canonical_trace.crops_planted <= {"WHEAT", "MELON", "STRAWBERRY"}

    def test_watering_meets_floor_through_day26(self, canonical_trace: _Trace) -> None:
        for day in range(9, WATER_WIND_DOWN_DAY):
            count = len(canonical_trace.watered_by_day.get(day, set()))
            assert count >= 14, f"day {day}: only {count} distinct tiles watered"

    def test_watering_drops_for_wind_down_days(self, canonical_trace: _Trace) -> None:
        for day in range(WATER_WIND_DOWN_DAY, 30):
            count = len(canonical_trace.watered_by_day.get(day, set()))
            assert count <= WATER_CAP_LATE, f"day {day}: {count} tiles watered, expected <=8"


class TestFullGame:
    @pytest.mark.slow
    @pytest.mark.parametrize("seed", FULL_GAME_SEEDS)
    def test_completes_a_full_720_step_game_without_crashing(self, seed: int) -> None:
        env = _run_full_game(seed)
        statuses = [step.status for step in env.steps[-1]]
        assert statuses == ["DONE", "DONE"]
