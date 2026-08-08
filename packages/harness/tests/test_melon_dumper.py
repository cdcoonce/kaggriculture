"""melon-dumper opponent archetype — melon-burst hold-then-dump (zoo #M2b,
hardened v2). See harness.zoo.melon_dumper's module docstring for the full
design and the tuning history that produced it."""

from __future__ import annotations

from typing import Any

import pytest
from harness.zoo import gate_zoo
from harness.zoo.melon_dumper import MELON_TILES, WHEAT_TILES, make_agent
from kaggle_environments import make

EARLY_CONFIG = {"seed": 7, "episodeSteps": 96}


def _run_early_game() -> object:
    env = make("kaggriculture", configuration=EARLY_CONFIG)
    env.run([make_agent(), "pass"])
    return env


def _any_plant_tile(env: object, crop: str) -> bool:
    farm0 = env.steps[-1][0].observation["farms"][0]  # type: ignore[attr-defined]
    for row in farm0["tiles"]:
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
                return True
    return False


class TestRegistration:
    def test_melon_dumper_is_in_gate_zoo(self) -> None:
        roster = gate_zoo()
        assert "melon-dumper" in roster

    def test_melon_dumper_factory_is_callable(self) -> None:
        roster = gate_zoo()
        factory = roster["melon-dumper"]
        assert callable(factory)

    def test_calling_the_factory_returns_a_callable_agent(self) -> None:
        roster = gate_zoo()
        factory = roster["melon-dumper"]
        agent = factory()
        assert callable(agent)


class TestZoneShape:
    def test_melon_zone_is_twenty_tiles(self) -> None:
        assert len(MELON_TILES) == 20

    def test_wheat_zone_is_four_tiles(self) -> None:
        assert len(WHEAT_TILES) == 4

    def test_zones_are_disjoint(self) -> None:
        assert set(MELON_TILES).isdisjoint(WHEAT_TILES)

    def test_shed_tile_excluded_from_both_zones(self) -> None:
        assert (4, 4) not in MELON_TILES
        assert (4, 4) not in WHEAT_TILES

    def test_zones_fill_the_entire_nw_quadrant_budget(self) -> None:
        # 5x5 NW quadrant minus the shed-access tile itself == 24 tiles;
        # melon (20) + wheat (4) is an exact fit, no tiles left unclaimed.
        assert len(MELON_TILES) + len(WHEAT_TILES) == 24


class TestEarlyBehavior:
    def test_has_planted_melon_by_step_96(self) -> None:
        env = _run_early_game()
        assert _any_plant_tile(env, "MELON")

    def test_has_planted_wheat_by_step_96(self) -> None:
        env = _run_early_game()
        assert _any_plant_tile(env, "WHEAT")

    def test_has_bought_seeds_or_spent_money_by_step_96(self) -> None:
        env = _run_early_game()
        money_at_step_1 = env.steps[1][0].observation["farms"][0]["money"]  # type: ignore[attr-defined]
        seeds_ever_positive = any(
            step[0].observation["private"]["seeds"].get("MELON", 0) > 0  # type: ignore[attr-defined]
            or step[0].observation["private"]["seeds"].get("WHEAT", 0) > 0  # type: ignore[attr-defined]
            for step in env.steps  # type: ignore[attr-defined]
        )
        assert money_at_step_1 < 3000 or seeds_ever_positive


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


class TestAtomicPlantBudget:
    def test_never_orders_more_melon_plants_than_seeds_held(self) -> None:
        # Same atomic-PLANT trap as wheat-spam's own regression test: the
        # engine rewrites ALL PLANT orders for a crop to PASS for a turn
        # where total demand exceeds seeds held.
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


class TestHoldThenDump:
    """Teeth-check (f), hardened for the burst-mode v2 fixture: melon-dumper
    HOLDS all melon (zero sells) until a trigger fires (shed >= 40 OR day >=
    12), then LATCHES into permanent dump mode -- floorless, uncapped, every
    turn, for the rest of the game. The latch is the load-bearing behavior:
    a purely re-evaluated-every-turn OR would flap back to "hold" the instant
    shed drops back under 40 while day is still < 12, contradicting "dump for
    the rest of the game" -- see the module docstring for why."""

    def _obs(self, *, melon_shed: int, step: int = 5 * 24) -> dict[str, Any]:
        """A minimal engine-shaped observation with the farmer parked away
        from every target tile (so the returned action is pure market logic,
        not entangled with movement/harvest choices). ``step`` defaults to
        day 5 -- below both hold triggers -- so callers opt into a trigger
        explicitly via step/melon_shed."""
        tiles: list[list[Any]] = [[None for _ in range(10)] for _ in range(10)]
        farm = {
            "money": 3000.0,
            "tiles": tiles,
            "farmer": [9, 9],  # off every MELON_TILES/WHEAT_TILES position
            "hands": [],
            "unlocked_quadrants": ["NW"],
            "hires_today": 0,
        }
        return {
            "step": step,
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

    def test_holds_below_both_triggers(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=15, step=5 * 24))  # day 5, shed 15: neither trigger
        assert self._melon_sell(action) is None

    def test_dump_triggers_at_shed_threshold_even_before_day_twelve(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=45, step=5 * 24))  # day 5, shed 45 >= 40
        assert self._melon_sell(action) == ["SELL", "MELON", 45]

    def test_no_dump_one_unit_under_the_shed_trigger(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=39, step=5 * 24))
        assert self._melon_sell(action) is None

    def test_dump_triggers_at_day_twelve_even_with_a_small_shed(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=5, step=12 * 24))  # day 12, shed only 5
        assert self._melon_sell(action) == ["SELL", "MELON", 5]

    def test_no_dump_one_day_before_the_day_trigger(self) -> None:
        agent = make_agent()
        action = agent(self._obs(melon_shed=5, step=11 * 24))  # day 11, shed only 5
        assert self._melon_sell(action) is None

    def test_dump_is_a_one_way_latch_surviving_shed_dropping_back_down(self) -> None:
        agent = make_agent()
        first = agent(self._obs(melon_shed=50, step=5 * 24))  # day 5: triggers via shed >= 40
        assert self._melon_sell(first) == ["SELL", "MELON", 50]

        second = agent(self._obs(melon_shed=3, step=6 * 24))  # day 6: shed < 40 AND day < 12
        assert self._melon_sell(second) == ["SELL", "MELON", 3]  # still dumping -- latched

    def test_step_zero_resets_the_latch_for_a_fresh_episode(self) -> None:
        agent = make_agent()
        triggered = agent(self._obs(melon_shed=5, step=15 * 24))  # day 15: latches via day trigger
        assert self._melon_sell(triggered) == ["SELL", "MELON", 5]

        fresh = agent(self._obs(melon_shed=10, step=0))  # a new episode, same process
        assert self._melon_sell(fresh) is None  # latch reset; day 0 holds again

    def test_dump_quantity_matches_the_whole_shed_no_cap_once_latched(self) -> None:
        agent = make_agent()
        agent(self._obs(melon_shed=45, step=5 * 24))  # latch it
        for qty in (1, 60, 138, 270):
            action = agent(self._obs(melon_shed=qty, step=13 * 24))
            assert self._melon_sell(action) == ["SELL", "MELON", qty], f"qty={qty}"

    def test_no_melon_order_when_shed_is_empty_even_while_latched(self) -> None:
        agent = make_agent()
        agent(self._obs(melon_shed=45, step=5 * 24))  # latch it
        action = agent(self._obs(melon_shed=0, step=13 * 24))
        assert self._melon_sell(action) is None


class TestFullGame:
    @pytest.mark.slow
    def test_completes_a_full_720_step_game_without_crashing(self) -> None:
        env = make("kaggriculture", configuration={"seed": 7, "episodeSteps": 720})
        env.run([make_agent(), "starter"])

        statuses = [step.status for step in env.steps[-1]]  # type: ignore[attr-defined]
        assert statuses == ["DONE", "DONE"]


class TestSeverityAcceptance:
    """This fixture's own acceptance test (coordinator directive after the
    M2b comparative run's stop at +$1963 recovered value, under the +$2k
    bar): the ladder-observed opponent that motivated M2b sold 231-270
    melons cumulative, concentrated into a ~138-unit dump over days 11-13,
    crashing the shared price hard. melon-dumper v1 (10 tiles, sell-on-
    sight, no hold) only produced ~99 melons spread thin across the whole
    game and never even cleared the champion's original $195 static floor --
    a fixture too mild to validate the feature it exists to test.

    Three criteria, all lifted directly from the ladder replays, gate this
    fixture against regressing back into that decorative state:
        (i)   cumulative MELON sold >= 180
        (ii)  a single 3-day window with >= 90 MELON sold
        (iii) melon price < $180 for >= 3 consecutive days

    Validated (this exact tuning) against frozen M2a (bb133b5) across 5
    seeds (7/41/43/100/202): cumulative 234, best 3-day window 114 (days
    12-14), longest sub-$180 run 5-6 days, price dipping as low as $1 --
    all with real margin above the bar, and IDENTICAL across every seed
    tried (melon-dumper's own tiles are watered every single day they're
    planted, so the weed-spawn RNG never touches them; this fixture's
    behavior is fully deterministic regardless of seed or opponent).

    The permanent test below runs against "pass" rather than frozen M2a --
    frozen M2a is a scratch-only artifact built fresh per session for the
    comparative run and cannot be a portable, committed test dependency.
    melon-dumper's own severity doesn't depend on the opponent (neither
    "pass" nor a real opponent sells melon in any volume that matters here);
    vs "pass" specifically: cumulative 234, 3-day window 114, price-under-
    $180 run of exactly 3 days (27-29, the endgame's second dump wave) --
    still a real, deterministic pass, not a coincidental boundary.
    """

    SEED = 7  # arbitrary, fixed for reproducibility (matches wheat-spam's own convention)

    def _play(self) -> Any:
        env = make("kaggriculture", configuration={"seed": self.SEED, "episodeSteps": 720})
        env.run([make_agent(), "pass"])
        return env

    def _melon_sold_by_day(self, env: Any) -> dict[int, int]:
        sold: dict[int, int] = {}
        for step in env.steps[1:]:
            action = step[0].action or {}
            if not isinstance(action, dict):
                continue
            day = step[0].observation["day"]
            for order in action.get("market", []):
                if isinstance(order, list) and len(order) >= 3 and order[:2] == ["SELL", "MELON"]:
                    sold[day] = sold.get(day, 0) + order[2]
        return sold

    @pytest.mark.slow
    def test_cumulative_melon_sold_at_least_180(self) -> None:
        env = self._play()
        by_day = self._melon_sold_by_day(env)
        assert sum(by_day.values()) >= 180

    @pytest.mark.slow
    def test_a_three_day_window_dumps_at_least_ninety(self) -> None:
        env = self._play()
        by_day = self._melon_sold_by_day(env)
        best = max(
            sum(by_day.get(d, 0) for d in (start, start + 1, start + 2)) for start in range(28)
        )
        assert best >= 90

    @pytest.mark.slow
    def test_melon_price_stays_under_180_for_three_consecutive_days(self) -> None:
        env = self._play()
        # Day-end price (hour 23) per day -- the same field the champion's
        # own MelonMarketMemory reads (market["prices"]["MELON"]).
        price_by_day: dict[int, float] = {}
        for step in env.steps:
            obs = step[0].observation
            if obs["hour"] == 23:
                price_by_day[obs["day"]] = obs["market"]["prices"].get("MELON", 999.0)
        longest_run = 0
        current_run = 0
        for day in range(30):
            if price_by_day.get(day, 999.0) < 180.0:
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        assert longest_run >= 3
