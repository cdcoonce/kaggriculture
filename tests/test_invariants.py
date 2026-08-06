"""Engine-mechanics invariant tests for kaggle_environments' kaggriculture env.

Run with the project venv's pytest, e.g.:
    /path/to/venv/bin/python -m pytest test_invariants.py -v

Self-contained: only stdlib, pytest, and kaggle_environments are imported.
Agents below are scripted purely by turn number (``obs["step"]``) rather than
by reading game state -- each test only needs a short, fixed sequence of
actions, so a lookup table is simpler and more deterministic than reactive
logic.

Action shape (from the engine's own spec / source):
    {"farmer": [op, *args], "hands": [[op, *args], ...], "market": [[op, *args], ...]}
Farmer/hand ops include PLANT <crop>, WATER, HARVEST, PASS, movement, etc.
Market ops include BUY_SEED <crop> <n>, BUY_ANIMAL <animal> <n>, SELL <item> <n>.
"""

from __future__ import annotations

from typing import Any

from kaggle_environments import make

Action = dict[str, Any]
Obs = Any  # kaggle_environments Struct: supports both attribute and dict access


def _pass_action() -> Action:
    return {"farmer": ["PASS"], "hands": [], "market": []}


def _idle_agent(obs: Obs) -> Action:
    """Player 1 in every test below: always passes, never touches player 0's farm."""
    return _pass_action()


def _scripted_agent(script: dict[int, Action]) -> Any:
    """Build an agent that plays ``script[step]`` on the given turn, PASS otherwise.

    ``step`` is the turn index the agent is being asked to act for
    (``obs["step"]``); the action it returns is applied by the engine and the
    resulting state is recorded at ``env.steps[step + 1]``.
    """

    def agent(obs: Obs) -> Action:
        return script.get(obs.get("step", 0), _pass_action())

    return agent


def _player_tile(env: Any, step_index: int, player: int = 0) -> Any:
    """Return the tile the given player's farmer stands on, at env.steps[step_index]."""
    obs = env.steps[step_index][player].observation
    farm = obs.farms[player]
    fx, fy = farm["farmer"]
    return farm["tiles"][fy][fx]


def test_same_turn_buy_plant_noops() -> None:
    """Unit actions resolve before that turn's market orders.

    Fails if the engine changed so market orders apply before (or
    interleaved with) unit actions -- i.e. if BUY_SEED credited the seed in
    time for the SAME turn's PLANT to consume it, which would leave a live
    PLANT on the tile after turn 0 instead of an empty one. Also fails if
    PLANT stopped working at all (the positive-control second half below).
    """
    script = {
        0: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]},
        1: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 30, "seed": 101, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    # After turn 0: BUY_SEED and PLANT were submitted together. PLANT must
    # have no-opped -- the seed was not yet in private["seeds"] when PLANT's
    # unit action resolved, since unit actions run before market orders.
    after_turn0 = env.steps[1][0].observation
    assert _player_tile(env, 1) is None
    assert after_turn0.private["seeds"]["WHEAT"] == 1

    # Positive control: PLANTing on the next turn, with the seed already
    # banked from turn 0's market order, must succeed.
    tile_after_turn1 = _player_tile(env, 2)
    assert isinstance(tile_after_turn1, dict)
    assert tile_after_turn1["kind"] == "PLANT"
    assert tile_after_turn1["crop"] == "WHEAT"
    after_turn1 = env.steps[2][0].observation
    assert after_turn1.private["seeds"]["WHEAT"] == 0


def test_fresh_plant_unwatered_weeds_overnight() -> None:
    """A freshly-planted, never-watered tile weeds at the next day boundary.

    ``consecutive_unwatered`` starts at 1 the instant a seed is planted (the
    planting day itself counts as unwatered), so a single unwatered
    day-boundary crossing is enough to weed it -- not two. Fails if that
    off-by-one regressed (the tile would still be a live PLANT after one
    unwatered day), or if watering stopped protecting a plant across the
    boundary (the positive control below).
    """

    def run_day(water_on_planting_day: bool, seed: int) -> Any:
        script: dict[int, Action] = {
            0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]},
            1: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []},
        }
        if water_on_planting_day:
            script[2] = {"farmer": ["WATER"], "hands": [], "market": []}
        env = make(
            "kaggriculture",
            configuration={"episodeSteps": 56, "seed": seed, "weedSpawnChance": 0.0},
        )
        env.run([_scripted_agent(script), _idle_agent])
        # The turn where obs.step == 23 is the 24th turn of day 0; processing
        # it triggers the end-of-day refresh (default turnsPerDay == 24),
        # landing in env.steps[24] (day 1, hour 0).
        return _player_tile(env, 24)

    unwatered_tile = run_day(water_on_planting_day=False, seed=301)
    assert unwatered_tile == {"kind": "WEED"}

    watered_tile = run_day(water_on_planting_day=True, seed=302)
    assert isinstance(watered_tile, dict)
    assert watered_tile["kind"] == "PLANT"
    assert watered_tile["crop"] == "WHEAT"


def test_animals_cannot_be_sold() -> None:
    """BUY_ANIMAL works; a subsequent SELL of that animal is a complete no-op.

    Fails if SELL started accepting non-PRODUCTS items (an animal would then
    become sellable, draining the shed and paying out money on the SELL
    turn), or if BUY_ANIMAL stopped charging money / stocking the shed (the
    positive-control first half below).
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_ANIMAL", "GOOSE", 1]]},
        1: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "GOOSE", 1]]},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 30, "seed": 202, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    starting_money = env.steps[0][0].observation.farms[0]["money"]

    after_buy = env.steps[1][0].observation
    # ANIMALS["GOOSE"]["cost"] == 300 in the engine's own price table.
    assert after_buy.farms[0]["money"] == starting_money - 300
    assert after_buy.private["shed"]["GOOSE"] == 1

    after_sell = env.steps[2][0].observation
    assert after_sell.farms[0]["money"] == after_buy.farms[0]["money"]
    assert after_sell.private["shed"]["GOOSE"] == 1


def test_melon_fertilizer_is_worthless() -> None:
    """Mechanics trap 4 (melon leg): fertilizing melon changes nothing.

    MELON's watering-bonus window (ages [(12+1)//2..12] == days [7..13]
    relative to planting, 7 days wide) is long enough that even unfertilized
    +1/watering hits max_yield (6) before the window closes. Fertilizing
    mid-window (+2/watering) reaches the same cap just sooner -- final yield
    is identical either way. Fails if MELON's cap or window widened enough
    that the fertilized and unfertilized runs diverge (fertilizer would then
    matter after all).
    """

    def run(fertilize_on_day7: bool, seed: int) -> Any:
        turns_per_day = 3
        script: dict[int, Action] = {
            0: {
                "farmer": ["PASS"],
                "hands": [],
                "market": [["BUY_SEED", "MELON", 1], ["BUY_PRODUCT", "FERTILIZER", 1]],
            },
            1 * turns_per_day: {"farmer": ["PLANT", "MELON"], "hands": [], "market": []},
            1 * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        }
        for day in range(2, 14):
            script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
        if fertilize_on_day7:
            script[7 * turns_per_day] = {
                "farmer": ["PICKUP", "FERTILIZER", 1],
                "hands": [],
                "market": [],
            }
            script[7 * turns_per_day + 1] = {"farmer": ["FERTILIZE"], "hands": [], "market": []}
            script[7 * turns_per_day + 2] = {"farmer": ["WATER"], "hands": [], "market": []}
        env = make(
            "kaggriculture",
            configuration={
                "episodeSteps": 60,
                "seed": seed,
                "weedSpawnChance": 0.0,
                "turnsPerDay": turns_per_day,
            },
        )
        env.run([_scripted_agent(script), _idle_agent])
        return _player_tile(env, 14 * turns_per_day)

    unfertilized = run(fertilize_on_day7=False, seed=901)
    fertilized = run(fertilize_on_day7=True, seed=902)

    assert unfertilized["kind"] == "PLANT"
    assert unfertilized["yield_units"] == 6
    assert fertilized["kind"] == "PLANT"
    assert fertilized["yield_units"] == unfertilized["yield_units"]


def test_ongoing_crop_fertilizer_must_land_the_day_before_a_production_tick() -> None:
    """Mechanics trap 4 (tomato/strawberry leg): fertilizer coverage is only
    3 days (fertilize_day..fertilize_day+2), and an ongoing crop's tick bonus
    checks ``fertilized_until_day >= current_day`` on the day the tick fires
    -- not at planting or any earlier day. TOMATO's first tick fires
    transitioning day8->day9 (interval 1, first_yield_day 8, planted day1).
    Fertilizing on day8 (the day before that tick shows up as day9) is in
    time; fertilizing on day4 has expired (4+2=6 < 8) by tick time. Fails if
    the bonus stopped requiring last-minute fertilizing (e.g. any earlier
    application counted, or coverage lasted indefinitely).
    """

    def run(fertilize_day: int, seed: int) -> Any:
        turns_per_day = 3
        script: dict[int, Action] = {
            0: {
                "farmer": ["PASS"],
                "hands": [],
                "market": [["BUY_SEED", "TOMATO", 1], ["BUY_PRODUCT", "FERTILIZER", 1]],
            },
            1 * turns_per_day: {"farmer": ["PLANT", "TOMATO"], "hands": [], "market": []},
            1 * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        }
        for day in range(2, 9):
            script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
        script[fertilize_day * turns_per_day] = {
            "farmer": ["PICKUP", "FERTILIZER", 1],
            "hands": [],
            "market": [],
        }
        script[fertilize_day * turns_per_day + 1] = {
            "farmer": ["FERTILIZE"],
            "hands": [],
            "market": [],
        }
        script[fertilize_day * turns_per_day + 2] = {"farmer": ["WATER"], "hands": [], "market": []}
        env = make(
            "kaggriculture",
            configuration={
                "episodeSteps": 40,
                "seed": seed,
                "weedSpawnChance": 0.0,
                "turnsPerDay": turns_per_day,
            },
        )
        env.run([_scripted_agent(script), _idle_agent])
        return _player_tile(env, 9 * turns_per_day)

    on_time = run(fertilize_day=8, seed=1001)
    too_early = run(fertilize_day=4, seed=1002)

    assert on_time["yield_units"] == 2
    assert too_early["yield_units"] == 1


def test_refertilizing_a_covered_plant_burns_the_unit() -> None:
    """Mechanics trap 4 (waste leg): FERTILIZE consumes 1 FERTILIZER from the
    unit's inventory unconditionally once the tile qualifies (kind ==
    PLANT), even when the tile is already covered through day+2 or later.
    Fails if FERTILIZE started refusing to consume a unit when the coverage
    wouldn't change (which would make this stop being a trap).
    """
    script = {
        0: {
            "farmer": ["PASS"],
            "hands": [],
            "market": [["BUY_SEED", "WHEAT", 1], ["BUY_PRODUCT", "FERTILIZER", 2]],
        },
        1: {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": []},
        2: {"farmer": ["PICKUP", "FERTILIZER", 2], "hands": [], "market": []},
        3: {"farmer": ["FERTILIZE"], "hands": [], "market": []},
        4: {"farmer": ["FERTILIZE"], "hands": [], "market": []},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 10, "seed": 903, "weedSpawnChance": 0.0, "turnsPerDay": 8},
    )
    env.run([_scripted_agent(script), _idle_agent])

    after_first = env.steps[4][0].observation
    assert after_first.private["inventories"][0].get("FERTILIZER", 0) == 1
    assert after_first.farms[0]["tiles"][4][4]["fertilized_until_day"] == 2

    after_second = env.steps[5][0].observation
    assert after_second.private["inventories"][0].get("FERTILIZER", 0) == 0
    assert after_second.farms[0]["tiles"][4][4]["fertilized_until_day"] == 2


def test_ongoing_crop_survives_and_produces_on_every_other_day_watering() -> None:
    """Mechanics trap 5: an ongoing crop only needs every-other-day watering
    to survive (consecutive_unwatered never reaches 2) -- and production
    ticks still fire on the calendar interval regardless of whether that
    specific day was watered. Fails if unwatered days silently skipped
    production (not just the fertilizer bonus), or if every-other-day
    watering weeded the plant despite never hitting 2 consecutive unwatered
    days.
    """
    turns_per_day = 2
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "TOMATO", 1]]},
        1 * turns_per_day: {"farmer": ["PLANT", "TOMATO"], "hands": [], "market": []},
        1 * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        3 * turns_per_day: {"farmer": ["WATER"], "hands": [], "market": []},
        5 * turns_per_day: {"farmer": ["WATER"], "hands": [], "market": []},
        7 * turns_per_day: {"farmer": ["WATER"], "hands": [], "market": []},
        9 * turns_per_day: {"farmer": ["WATER"], "hands": [], "market": []},
        # Days 2, 4, 6, 8 are deliberately left unwatered.
    }
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 30,
            "seed": 1101,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    final_tile = _player_tile(env, 10 * turns_per_day)
    assert final_tile["kind"] == "PLANT"
    assert final_tile["crop"] == "TOMATO"
    # Two ticks (day8->9, day9->10) fired despite alternating watering.
    assert final_tile["yield_units"] == 2


def test_shed_cap_silently_discards_overflow_at_end_of_day() -> None:
    """Mechanics trap 6: the end-of-day auto-drop from unit inventory to
    shed silently discards whatever doesn't fit -- it does not error, clamp
    the purchase/pickup that caused the overflow, or carry the excess to the
    next day. Fails if overflow started being preserved (e.g. left sitting
    in the unit inventory instead of vanishing) or if it started pushing the
    shed above its configured cap.
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_PRODUCT", "FERTILIZER", 3]]},
        1: {
            "farmer": ["PICKUP", "FERTILIZER", 3],
            "hands": [],
            "market": [["BUY_PRODUCT", "FERTILIZER", 3]],
        },
    }
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 10,
            "seed": 501,
            "weedSpawnChance": 0.0,
            "shedCapacity": 3,
            "turnsPerDay": 2,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    # Turn 1 (day 0's last turn): PICKUP moves turn 0's 3 shed FERTILIZER
    # into the farmer's inventory, then that turn's market buys 3 more
    # straight into the (now empty) shed -- shed back at cap (3). Turn 1's
    # end-of-day drop then tries to add the farmer's carried 3 on top of a
    # shed already at cap; both resolve within processing turn 1.
    after_turn1 = env.steps[2][0].observation
    assert after_turn1.private["shed"]["FERTILIZER"] == 3  # not 6
    assert after_turn1.private["inventories"] == [{}]


def test_unsold_inventory_is_worth_zero_at_game_end() -> None:
    """Mechanics trap 7: the terminal reward is farm money only -- unsold
    shed inventory is not liquidated or valued at game end. Fails if the
    engine started folding unsold shed inventory into the final reward
    (reward would then exceed money whenever the shed holds anything
    unsold).
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_PRODUCT", "FERTILIZER", 1]]},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 6, "seed": 601, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    final = env.steps[-1][0]
    assert final.status == "DONE"
    assert final.observation.private["shed"]["FERTILIZER"] >= 1  # unsold, still in the shed
    assert final.reward == final.observation.farms[0]["money"]


def test_skipping_feed_on_a_production_day_zeroes_the_banked_care_bonus() -> None:
    """Mechanics trap 8: ``pending_care_bonus`` is only popped into yield
    when ``fed_today`` is True on a production-tick day -- and is reset to 0
    unconditionally whenever that tick fires, fed or not. Banking a bonus
    (CARE+FEED) on a non-production day survives until the next tick, but
    skipping FEED on the tick day itself discards the bank instead of
    carrying it forward to a later fed day. Fails if the bonus started
    rolling over past an unfed tick, or stopped being consumed/reset on a
    tick at all.
    """

    def run(feed_on_day3: bool, seed: int) -> Any:
        turns_per_day = 4
        script: dict[int, Action] = {
            0: {
                "farmer": ["BUILD_COOP"],
                "hands": [],
                "market": [["BUY_ANIMAL", "GOOSE", 1], ["BUY_PRODUCT", "WHEAT", 5]],
            },
            1: {"farmer": ["PICKUP", "GOOSE", 1], "hands": [], "market": []},
            2: {"farmer": ["PLACE", "GOOSE"], "hands": [], "market": []},
            1 * turns_per_day: {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": []},
            1 * turns_per_day + 1: {"farmer": ["FEED"], "hands": [], "market": []},
            1 * turns_per_day + 2: {"farmer": ["CARE"], "hands": [], "market": []},
            2 * turns_per_day: {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": []},
            2 * turns_per_day + 1: {"farmer": ["FEED"], "hands": [], "market": []},
        }
        if feed_on_day3:
            script[3 * turns_per_day] = {
                "farmer": ["PICKUP", "WHEAT", 1],
                "hands": [],
                "market": [],
            }
            script[3 * turns_per_day + 1] = {"farmer": ["FEED"], "hands": [], "market": []}
        env = make(
            "kaggriculture",
            configuration={
                "episodeSteps": 30,
                "seed": seed,
                "weedSpawnChance": 0.0,
                "turnsPerDay": turns_per_day,
            },
        )
        env.run([_scripted_agent(script), _idle_agent])
        return _player_tile(env, 4 * turns_per_day)

    # Day 1: CARE+FEED banks a bonus (GOOSE's first_yield_day is 4, so day 1
    # has no tick yet to consume/reset it). Day 2: FEED only, to keep
    # consecutive_unfed at 0 -- skipping it would escape the goose before
    # day 3's tick even fires. Day 3 is the first production tick.
    skipped = run(feed_on_day3=False, seed=1201)
    fed = run(feed_on_day3=True, seed=1202)

    assert skipped["yield_units"] == 1  # base only -- the banked bonus was discarded
    assert skipped["pending_care_bonus"] == 0
    assert fed["yield_units"] == 2  # base + the day-1 banked bonus, redeemed


def test_first_hire_spawns_on_locked_tile_until_ne_bought() -> None:
    """Mechanics trap 9: with the farmer parked on (4,4), the first hire of
    the day spawns on (5,4) -- a shed-access tile inside the NE quadrant,
    which starts LOCKED until NE land is bought. Tile ops silently no-op on
    a LOCKED tile; movement off it still works, so the hand's first turn is
    effectively movement-only. Fails if the NWSE spawn tie-break changed (a
    fresh hire landing on an already-unlocked tile) or if movement off a
    LOCKED tile stopped working (the hand would be stranded forever).
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]},
        1: {"farmer": ["PASS"], "hands": [["BUILD_COOP"]], "market": []},
        2: {"farmer": ["PASS"], "hands": [["WEST"]], "market": []},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 10, "seed": 401, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    after_hire = env.steps[1][0].observation
    assert after_hire.farms[0]["hands"] == [[5, 4]]
    assert after_hire.farms[0]["tiles"][4][5] == "LOCKED"

    # A tile op on the locked spawn tile is a silent no-op.
    after_tile_op = env.steps[2][0].observation
    assert after_tile_op.farms[0]["tiles"][4][5] == "LOCKED"
    assert after_tile_op.farms[0]["hands"] == [[5, 4]]

    # Movement off the locked tile works (movement-only first turn).
    after_move = env.steps[3][0].observation
    assert after_move.farms[0]["hands"] == [[4, 4]]


def test_sell_over_quantity_is_a_safe_sell_all_idiom() -> None:
    """Mechanics trap 10: ``SELL <item> 99999`` is a safe "sell all" -- the
    per-unit lockstep loop just stops committing once the shed empties, with
    no error, no negative shed, and each unit sold at its correctly
    re-quoted price. Fails if an over-quantity SELL started erroring or
    no-opping instead of partial-filling, or shorted the payout.
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_PRODUCT", "FERTILIZER", 5]]},
        1: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "FERTILIZER", 99999]]},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 10, "seed": 701, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    starting_money = env.steps[0][0].observation.farms[0]["money"]
    after_sell = env.steps[2][0].observation
    assert after_sell.private["shed"]["FERTILIZER"] == 0
    # Buying 5 then selling all 5 back nets to zero: BUY_PRODUCT quotes at
    # post-buy inventory specifically so a round trip against an otherwise
    # unmoved market breaks even (see the engine's own comment on that
    # quote in _process_market).
    assert after_sell.farms[0]["money"] == starting_money


def test_market_sell_has_no_shed_adjacency_requirement() -> None:
    """Public-meta claim check: a forum report suggested market orders
    require shed adjacency. The engine's own SELL handling (``_commit_unit``)
    never reads farmer/hand position at all -- it only checks
    ``private["shed"]``. Selling from a tile that is not one of the four
    shed-access tiles succeeds here, so the forum claim does NOT hold for
    this kaggle_environments version: encoded below is the engine's real (no
    adjacency requirement) behavior. Fails if a future engine version added
    the adjacency check the forum described.
    """
    script = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_PRODUCT", "FERTILIZER", 1]]},
        1: {"farmer": ["WEST"], "hands": [], "market": []},
        2: {"farmer": ["PASS"], "hands": [], "market": [["SELL", "FERTILIZER", 1]]},
    }
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 10, "seed": 801, "weedSpawnChance": 0.0},
    )
    env.run([_scripted_agent(script), _idle_agent])

    shed_access_tiles = {(4, 4), (5, 4), (4, 5), (5, 5)}
    after_move = env.steps[2][0].observation
    farmer_pos = tuple(after_move.farms[0]["farmer"])
    assert farmer_pos == (3, 4)
    assert farmer_pos not in shed_access_tiles

    starting_money = env.steps[0][0].observation.farms[0]["money"]
    after_sell = env.steps[3][0].observation
    assert after_sell.private["shed"]["FERTILIZER"] == 0
    # Sale succeeded from a non-adjacent tile, and at correct proceeds.
    assert after_sell.farms[0]["money"] == starting_money
