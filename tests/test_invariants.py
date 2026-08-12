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
from kaggle_environments.envs.kaggriculture import kaggriculture as kagg

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


# --- Ongoing-crop mechanics claims (issue #59) -----------------------------
#
# The tests below turn twelve claims about kaggle_environments 1.32.6's
# ongoing-crop / fertilizer / town-demand mechanics -- derived from a source
# read ahead of an agent redesign -- into executable checks against the real
# engine, so the redesign is built on verified behavior rather than a
# read-through. Each test's failure message names the claim (1-12) it
# checks. Claim 6 holds, but only conditionally: fertilizer doubles an
# ongoing crop's realized output (8 vs 4 units for one strawberry tile) when
# the tile is harvested right after every production tick; leaving the tile
# unharvested runs every tick's addition through the shared max_yield clamp
# and wastes the bonus down to the same 4 units either way -- see that
# test's docstring for the full explanation.


def test_claim1_crop_table_matches_engine_constants() -> None:
    """Claim 1: STRAWBERRY (seed 100, first_yield_day 10, max_yield_day 10,
    interval 2, max_yield 4, ongoing) and TOMATO (seed 50, first_yield_day 8,
    interval 1, max_yield 4, ongoing) match the engine's own CROPS table;
    WHEAT/CARROT/MELON are not ongoing.

    Structural check against kaggriculture.py's CROPS dict. Fails if a
    future engine version changes any of these constants -- the agent
    redesign's ongoing-crop economics depend on these exact numbers.
    """
    strawberry = kagg.CROPS["STRAWBERRY"]
    assert strawberry["seed"] == 100, "claim 1: STRAWBERRY seed cost changed"
    assert strawberry["first_yield_day"] == 10, "claim 1: STRAWBERRY first_yield_day changed"
    assert strawberry["max_yield_day"] == 10, "claim 1: STRAWBERRY max_yield_day changed"
    assert strawberry["interval"] == 2, "claim 1: STRAWBERRY interval changed"
    assert strawberry["max_yield"] == 4, "claim 1: STRAWBERRY max_yield changed"
    assert strawberry["ongoing"] is True, "claim 1: STRAWBERRY is no longer ongoing"

    tomato = kagg.CROPS["TOMATO"]
    assert tomato["seed"] == 50, "claim 1: TOMATO seed cost changed"
    assert tomato["first_yield_day"] == 8, "claim 1: TOMATO first_yield_day changed"
    assert tomato["interval"] == 1, "claim 1: TOMATO interval changed"
    assert tomato["max_yield"] == 4, "claim 1: TOMATO max_yield changed"
    assert tomato["ongoing"] is True, "claim 1: TOMATO is no longer ongoing"

    for crop in ("WHEAT", "CARROT", "MELON"):
        assert kagg.CROPS[crop]["ongoing"] is False, f"claim 1: {crop} unexpectedly became ongoing"


def test_claim2_watering_ongoing_crop_never_changes_yield_within_the_turn() -> None:
    """Claim 2: WATER is gated ``if not crop_data["ongoing"]`` in
    _apply_unit_action, so for an ongoing crop (STRAWBERRY) the WATER op sets
    watered_today but never touches yield_units itself -- all yield growth
    for ongoing crops comes from the end-of-day tick (claim 3), never from
    the WATER action in the same turn.

    Waters a strawberry every day of its life and checks, turn by turn, that
    yield_units immediately before and immediately after each WATER
    submission (same day, no day boundary in between) is unchanged -- even
    on days where that day's end-of-day tick will later add yield. Fails if
    WATER started granting a yield bonus to ongoing crops (the non-ongoing
    WATER bonus path leaking into the ongoing branch).
    """
    turns_per_day = 3
    planted_day = 1
    last_day = planted_day + 17
    script: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 1]]},
        planted_day * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        planted_day * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(planted_day + 1, last_day):
        script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": (last_day + 2) * turns_per_day,
            "seed": 10001,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    checked_any = False
    for day in range(planted_day + 1, last_day):
        turn = day * turns_per_day
        before = _player_tile(env, turn)
        after = _player_tile(env, turn + 1)
        if not (isinstance(before, dict) and before.get("kind") == "PLANT"):
            continue  # tile already decayed past its final tick; nothing left to check
        checked_any = True
        assert before["yield_units"] == after["yield_units"], (
            f"claim 2 REFUTED: WATER changed yield_units on day {day} "
            f"({before['yield_units']} -> {after['yield_units']})"
        )
    assert checked_any, "test setup: no live PLANT tile was ever observed -- widen the day range"


def test_claim3_ongoing_crop_produces_on_exact_calendar_ticks() -> None:
    """Claim 3: an ongoing crop accrues yield only in the end-of-day tick
    (_daily_refresh_plants), on days planted_day+first_yield_day + k*interval
    for k = 0..max_yield-1 -- for STRAWBERRY (first_yield_day=10, interval=2,
    max_yield=4) that's exactly planted_day+10, +12, +14, +16, and no more
    (production_count is gated by cd["max_yield"]).

    Waters a strawberry every day of its life (isolating the calendar-tick
    mechanism from watering/weeding noise, per claim 2) and records the
    exact days yield_units increases. Fails if the tick days shift or the
    total production count is not exactly 4.
    """
    turns_per_day = 3
    planted_day = 1
    last_day = planted_day + 17
    script: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 1]]},
        planted_day * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        planted_day * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(planted_day + 1, last_day):
        script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": (last_day + 2) * turns_per_day,
            "seed": 10002,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    # day == planted_day itself is read before that day's PLANT action has run
    # (the tile is still empty), so start the day-by-day trace the day after.
    yields_by_day = {}
    for day in range(planted_day + 1, last_day):
        yields_by_day[day] = _player_tile(env, day * turns_per_day)["yield_units"]

    production_days = [
        day
        for day in range(planted_day + 2, last_day)
        if yields_by_day[day] > yields_by_day[day - 1]
    ]
    expected_days = [planted_day + 10, planted_day + 12, planted_day + 14, planted_day + 16]
    assert production_days == expected_days, (
        f"claim 3: production ticks fired on {production_days}, expected {expected_days}"
    )
    total_produced = yields_by_day[last_day - 1] - yields_by_day[planted_day + 1]
    assert total_produced == 4, (
        f"claim 3: total production was {total_produced}, expected exactly 4 (max_yield)"
    )


def test_claim4_two_unwatered_days_weeds_ongoing_crop_but_alternating_watering_survives() -> None:
    """Claim 4: consecutive_unwatered >= 2 turns ANY plant into a WEED in
    _daily_refresh_plants -- the check runs before the ongoing/non-ongoing
    branch, so ongoing crops get no special protection. Converse: watering
    every other day never lets consecutive_unwatered reach 2, so an ongoing
    crop survives on alternate-day watering all the way to its own calendar
    lifespan (claim 7), well past the point two-unwatered-days would have
    weeded it.

    Fails if ongoing crops became weed-immune, or if every-other-day
    watering started weeding a plant despite never accumulating 2
    consecutive unwatered days.
    """
    # (a) two consecutive unwatered days -> WEED, for an ongoing crop.
    turns_per_day = 2
    script_a: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 1]]},
        1 * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        1 * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        # days 2 and 3 deliberately left unwatered.
    }
    env_a = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 20,
            "seed": 10101,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env_a.run([_scripted_agent(script_a), _idle_agent])
    assert _player_tile(env_a, 4 * turns_per_day) == {"kind": "WEED"}, (
        "claim 4 REFUTED: ongoing crop (STRAWBERRY) survived 2 consecutive unwatered days"
    )

    # (b) alternate-day watering survives well past where (a) weeded it, all
    # the way to the plant's natural (max_yield-driven) lifespan.
    script_b: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 1]]},
        1 * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        1 * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(3, 18, 2):  # every OTHER day: 3, 5, 7, ..., 17
        script_b[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
    env_b = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 40,
            "seed": 10102,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env_b.run([_scripted_agent(script_b), _idle_agent])
    tile_b = _player_tile(env_b, 18 * turns_per_day)
    assert isinstance(tile_b, dict) and tile_b.get("kind") == "PLANT", (
        f"claim 4 REFUTED: alternate-day watering still weeded the plant (tile={tile_b})"
    )
    assert tile_b["yield_units"] == 4, (
        "claim 4: alternate-day-watered strawberry did not reach max_yield by day 18"
    )


def test_claim5_fertilizer_bonus_requires_watering_on_the_exact_tick_day() -> None:
    """Claim 5: the +2-instead-of-+1 fertilizer bonus in _daily_refresh_plants
    checks ``fertilized = was_watered and fertilized_until_day >= current_day``
    -- BOTH conditions, evaluated on the day the tick fires. Being fertilized
    (coverage window includes that day) is not sufficient on its own if that
    specific day was not watered.

    Fertilizes on day 8 (fertilized_until_day = 10, covering days 8-10) but
    deliberately skips watering on day 10 -- the exact day STRAWBERRY's first
    production tick fires (current_day = planted_day+9 = 10). Despite full
    fertilizer coverage, the tick must add only the base +1, not +2. Fails if
    the bonus started applying from coverage alone, without that day's
    watering.
    """
    turns_per_day = 3
    planted_day = 1
    script: dict[int, Action] = {
        0: {
            "farmer": ["PASS"],
            "hands": [],
            "market": [["BUY_SEED", "STRAWBERRY", 1], ["BUY_PRODUCT", "FERTILIZER", 1]],
        },
        planted_day * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        planted_day * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(2, 18):
        if day == 10:
            continue  # deliberately skip watering on the tick day (current_day=10)
        script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
    # Fertilize on day 8 -> fertilized_until_day = 10, covering days 8, 9, 10.
    script[8 * turns_per_day + 1] = {
        "farmer": ["PICKUP", "FERTILIZER", 1],
        "hands": [],
        "market": [],
    }
    script[8 * turns_per_day + 2] = {"farmer": ["FERTILIZE"], "hands": [], "market": []}
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 60,
            "seed": 10201,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    before_tick = _player_tile(env, 10 * turns_per_day)
    assert before_tick["fertilized_until_day"] == 10, (
        "test setup: FERTILIZE did not set the expected coverage window"
    )
    after_tick = _player_tile(env, 11 * turns_per_day)
    assert after_tick["yield_units"] == 1, (
        f"claim 5 REFUTED: fertilizer bonus applied on an unwatered tick day "
        f"(yield_units={after_tick['yield_units']}, expected 1 = base only, "
        f"despite fertilized_until_day covering that day)"
    )


def test_claim6_ongoing_crop_fertilizer_doubles_yield_under_prompt_harvest_cadence() -> None:
    """Claim 6, corrected: the original claim under test was "one FERTILIZE
    covers two strawberry productions; fertilizing at crop age 9 and again
    at age 13, with watering aligned, yields 8 total units from one tile
    versus 4 with no fertilizer." An earlier version of this test called
    that claim REFUTED because a fertilized and an unfertilized run both
    finish at tile ``yield_units == 4`` -- but that measurement never
    harvested the tile between production ticks, so every tick's addition
    ran through ``min(cd["max_yield"], tile["yield_units"] + bonus)`` in
    _daily_refresh_plants and got clamped to the shared cap (4). The 4-vs-4
    result was an artifact of a never-harvest policy, not evidence that
    fertilizer is worthless for an ongoing crop like it genuinely is for
    MELON (test_melon_fertilizer_is_worthless, a non-ongoing crop whose
    yield comes from the WATER path's own bonus/cap, a different mechanism).

    HARVEST (see test_claim8) resets an ongoing tile's yield_units to 0 on
    every call without clearing the tile itself. A policy that harvests
    right after each production tick therefore empties the tile before the
    next tick's addition ever lands -- the cap never binds, because no
    single tick adds more than 2. Under THAT cadence fertilizer really does
    double the realized total: 8 units (4 ticks x 2) vs 4 (4 ticks x 1). The
    cap only wastes the bonus when the tile is left to sit unharvested,
    which is exactly what the previous version of this test measured.

    Pins, against the real engine:
      1. fertilized + harvest after every tick -> 8 total units.
      2. unfertilized + harvest after every tick -> 4 total units.
      3. fertilized + NEVER harvested until the end -> only 4 units --
         a lazy harvest cadence silently halves fertilized ongoing-crop
         output by running every tick's addition through the shared
         max_yield clamp.
      4. fertilizing at every tick-eve (ages 9, 11, 13, 15) adds nothing
         over fertilizing at just ages 9 and 13 -- both 3-day coverage
         windows already span all four production ticks.
    """
    turns_per_day = 3
    planted_day = 1
    # Ticks fire on current_day in {10, 12, 14, 16} (see claim 5/7) and
    # become visible in the tile's yield_units at the start of the day
    # after each -- {11, 13, 15, 17}.
    tick_visible_days = (11, 13, 15, 17)
    end_step = 19 * turns_per_day  # well past the 4th (final) tick

    def run(fertilize_ages: tuple[int, ...], harvest_after_each_tick: bool, seed: int) -> Any:
        script: dict[int, Action] = {
            0: {
                "farmer": ["PASS"],
                "hands": [],
                "market": [["BUY_SEED", "STRAWBERRY", 1], ["BUY_PRODUCT", "FERTILIZER", 4]],
            },
            planted_day * turns_per_day: {
                "farmer": ["PLANT", "STRAWBERRY"],
                "hands": [],
                "market": [],
            },
            planted_day * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        }
        for day in range(planted_day + 1, planted_day + 18):
            script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
        for age in fertilize_ages:
            day = planted_day + age
            script[day * turns_per_day] = {
                "farmer": ["PICKUP", "FERTILIZER", 1],
                "hands": [],
                "market": [],
            }
            script[day * turns_per_day + 1] = {
                "farmer": ["FERTILIZE"],
                "hands": [],
                "market": [],
            }
            script[day * turns_per_day + 2] = {"farmer": ["WATER"], "hands": [], "market": []}
        if harvest_after_each_tick:
            for day in tick_visible_days:
                script[day * turns_per_day] = {"farmer": ["HARVEST"], "hands": [], "market": []}
                script[day * turns_per_day + 1] = {"farmer": ["WATER"], "hands": [], "market": []}
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
        return env

    def total_strawberry_units(env: Any, step_index: int, player: int = 0) -> int:
        """Shed + any not-yet-dropped unit inventory -- every harvested unit
        that hasn't been sold, since none of these scripts issue SELL."""
        obs = env.steps[step_index][player].observation
        shed = obs.private["shed"].get("STRAWBERRY", 0)
        carried = obs.private["inventories"][player].get("STRAWBERRY", 0)
        return shed + carried

    # 1 & 2: harvest right after every production tick.
    fertilized_prompt = run(fertilize_ages=(9, 13), harvest_after_each_tick=True, seed=17011)
    unfertilized_prompt = run(fertilize_ages=(), harvest_after_each_tick=True, seed=17012)
    fertilized_prompt_total = total_strawberry_units(fertilized_prompt, end_step)
    unfertilized_prompt_total = total_strawberry_units(unfertilized_prompt, end_step)
    assert unfertilized_prompt_total == 4, (
        f"claim 6 baseline: unfertilized strawberry harvested after every tick did "
        f"not total 4 units (got {unfertilized_prompt_total})"
    )
    assert fertilized_prompt_total == 8, (
        f"claim 6: fertilizing a strawberry at ages 9 and 13, harvested right after "
        f"every production tick, did not double the unfertilized total to 8 (got "
        f"{fertilized_prompt_total}) -- fertilizer should double an ongoing crop's "
        f"realized output under a prompt harvest cadence"
    )

    # 3: fertilized but never harvested until the end -- the max_yield cap
    # wastes the bonus. Read right at the 4th tick's max_lifespan_step
    # (mls, see claim 7): yield_units == 4 there, before _decay_plants'
    # every-other-step decrements (which start exactly at mls) erode it, so
    # reading any later than this would conflate the cap trap with decay.
    mls_step = (planted_day + 17) * turns_per_day
    fertilized_lazy = run(fertilize_ages=(9, 13), harvest_after_each_tick=False, seed=17013)
    fertilized_lazy_final = _player_tile(fertilized_lazy, mls_step)
    assert fertilized_lazy_final["yield_units"] == 4, (
        f"claim 6: fertilized strawberry left unharvested until the end did not land "
        f"on the max_yield cap (4) (got {fertilized_lazy_final['yield_units']}) -- a "
        f"lazy harvest cadence should silently halve fertilized ongoing-crop output "
        f"(8 realizable, only 4 actually banked) by running every tick's addition "
        f"through the shared max_yield clamp"
    )

    # 4: fertilizing every tick-eve is no better than fertilizing at 9 and
    # 13 -- both coverage windows already reach all four ticks.
    fertilized_every_tick = run(
        fertilize_ages=(9, 11, 13, 15), harvest_after_each_tick=True, seed=17014
    )
    fertilized_every_tick_total = total_strawberry_units(fertilized_every_tick, end_step)
    assert fertilized_every_tick_total == fertilized_prompt_total == 8, (
        f"claim 6: fertilizing at every tick-eve (9, 11, 13, 15) yielded "
        f"{fertilized_every_tick_total} units, expected the same 8 as fertilizing "
        f"only at ages 9 and 13 -- the 3-day coverage window from each of those two "
        f"applications should already span all four production ticks"
    )


def test_claim7_ongoing_crop_decays_to_weed_after_its_final_production_tick() -> None:
    """Claim 7: on the tick where production_count == cd["max_yield"] (the
    final scheduled production), _daily_refresh_plants sets
    max_lifespan_step = (next_day + 1) * turns_per_day; from then on,
    _decay_plants (which runs every turn, not just at day boundaries)
    decrements yield_units by 1 every other step once step >= max_lifespan_step,
    converting the tile to a WEED once yield_units reaches 0.

    Waters a strawberry through its whole life and watches the tile past its
    4th (final) production tick. Fails if the lifespan wasn't set on the
    final tick, if decay used a different cadence, or if the tile never
    actually became a WEED.
    """
    turns_per_day = 3
    planted_day = 1
    script: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "STRAWBERRY", 1]]},
        planted_day * turns_per_day: {"farmer": ["PLANT", "STRAWBERRY"], "hands": [], "market": []},
        planted_day * turns_per_day + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(planted_day + 1, planted_day + 18):
        script[day * turns_per_day] = {"farmer": ["WATER"], "hands": [], "market": []}
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 90,
            "seed": 16001,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    final_tile = _player_tile(env, (planted_day + 17) * turns_per_day)
    assert final_tile["kind"] == "PLANT" and final_tile["yield_units"] == 4, (
        "claim 7: strawberry did not reach max_yield (4) on its 4th tick"
    )
    mls = final_tile["max_lifespan_step"]
    # The 4th (final) tick fires transitioning into next_day = planted_day+16;
    # max_lifespan_step = (next_day + 1) * turns_per_day = (planted_day+17) * turns_per_day.
    assert mls == (planted_day + 17) * turns_per_day, (
        f"claim 7: max_lifespan_step not set as (next_day+1)*turns_per_day (got {mls})"
    )

    assert _player_tile(env, mls)["yield_units"] == 4, (
        "claim 7: yield decayed before max_lifespan_step"
    )
    assert _player_tile(env, mls + 1)["yield_units"] == 3, (
        "claim 7: first decay decrement did not land at max_lifespan_step"
    )
    assert _player_tile(env, mls + 3)["yield_units"] == 2, (
        "claim 7: second decay decrement cadence wrong"
    )
    assert _player_tile(env, mls + 5)["yield_units"] == 1, (
        "claim 7: third decay decrement cadence wrong"
    )
    assert _player_tile(env, mls + 7) == {"kind": "WEED"}, (
        "claim 7: tile never decayed to WEED after 4 decrements"
    )


def test_claim8_harvest_credits_unit_inventory_and_only_clears_non_ongoing_tiles() -> None:
    """Claim 8: HARVEST adds yield_units to the acting unit's own inventory
    (private["inventories"][idx]), never directly to the shed, and clears
    the tile back to None only for a non-ongoing crop -- an ongoing crop's
    tile survives harvest (yield_units resets to 0, but kind/crop/
    planted_day are untouched, so it keeps producing on its own calendar).

    Fails if harvested units ever land in the shed directly, or if the
    ongoing/non-ongoing tile-clearing branches swapped.
    """
    # Non-ongoing: CARROT -- HARVEST must clear the tile to None.
    tpd = 3
    script_carrot: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "CARROT", 1]]},
        1 * tpd: {"farmer": ["PLANT", "CARROT"], "hands": [], "market": []},
        1 * tpd + 1: {"farmer": ["WATER"], "hands": [], "market": []},
        2 * tpd: {"farmer": ["WATER"], "hands": [], "market": []},
        3 * tpd: {"farmer": ["HARVEST"], "hands": [], "market": []},
    }
    env_carrot = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 20,
            "seed": 15001,
            "weedSpawnChance": 0.0,
            "turnsPerDay": tpd,
        },
    )
    env_carrot.run([_scripted_agent(script_carrot), _idle_agent])
    after = env_carrot.steps[3 * tpd + 1][0].observation
    assert after.farms[0]["tiles"][4][4] is None, (
        "claim 8: non-ongoing tile (CARROT) was not cleared by HARVEST"
    )
    assert after.private["inventories"][0].get("CARROT", 0) >= 1, (
        "claim 8: harvested CARROT did not land in the unit's inventory"
    )
    assert after.private["shed"]["CARROT"] == 0, (
        "claim 8: HARVEST put units directly in the shed instead of the unit's inventory"
    )

    # Ongoing: TOMATO -- HARVEST must NOT clear the tile.
    script_tomato: dict[int, Action] = {
        0: {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "TOMATO", 1]]},
        1 * tpd: {"farmer": ["PLANT", "TOMATO"], "hands": [], "market": []},
        1 * tpd + 1: {"farmer": ["WATER"], "hands": [], "market": []},
    }
    for day in range(2, 9):
        script_tomato[day * tpd] = {"farmer": ["WATER"], "hands": [], "market": []}
    script_tomato[9 * tpd] = {"farmer": ["HARVEST"], "hands": [], "market": []}
    env_tomato = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 40,
            "seed": 15002,
            "weedSpawnChance": 0.0,
            "turnsPerDay": tpd,
        },
    )
    env_tomato.run([_scripted_agent(script_tomato), _idle_agent])
    after_t = env_tomato.steps[9 * tpd + 1][0].observation
    tile_t = after_t.farms[0]["tiles"][4][4]
    assert (
        isinstance(tile_t, dict)
        and tile_t.get("kind") == "PLANT"
        and tile_t.get("crop") == "TOMATO"
    ), f"claim 8 REFUTED: ongoing tile (TOMATO) was cleared/changed by HARVEST (tile={tile_t})"
    assert tile_t["yield_units"] == 0, (
        "claim 8: ongoing tile's yield_units did not reset to 0 after HARVEST"
    )
    assert after_t.private["inventories"][0].get("TOMATO", 0) >= 1, (
        "claim 8: harvested TOMATO did not land in the unit's inventory"
    )
    assert after_t.private["shed"]["TOMATO"] == 0, (
        "claim 8: HARVEST put ongoing-crop units directly in the shed, not the unit's inventory"
    )


def test_claim9_town_shops_drain_market_inventory_on_controlled_schedule() -> None:
    """Claim 9: every townShopSellInterval steps (default 4), each entry in
    town["unlocked_shops"] decrements market inventory for each product it
    sells -- multiplier 2 for a single-product shop, 1 for a multi-product
    shop. The town center separately pulls 1 of every non-FERTILIZER product
    every townCenterSellInterval steps (default 24); both ticks land on step
    0, so the very first tick sees combined shop+center drain.

    Sets town["unlocked_shops"] directly via env.state, using
    kaggle_environments' own Environment.reset()/step() API -- the same
    direct-state-mutation pattern already used by this repo's
    tools/recon-scripts/order_position_test.py -- since no player action can
    populate this list on a controlled schedule. Fails if the per-shop
    multiplier, the interval, or the step-0 shop+center overlap changed.
    """
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 20, "seed": 12001, "weedSpawnChance": 0.0},
    )
    env.reset(num_agents=2)
    obs0 = env.state[0].observation
    # YARN_STORE sells only WOOL (single-product -> multiplier 2).
    # BAKERY sells EGG + WHEAT (multi-product -> multiplier 1 each).
    obs0.town["unlocked_shops"] = ["YARN_STORE", "BAKERY"]
    start = dict(obs0.market["inventory"])
    actions = [_pass_action(), _pass_action()]

    env.step(actions)  # processes step 0: shop tick (0 % 4) AND center tick (0 % 24) both fire.
    inv = env.state[0].observation.market["inventory"]
    assert inv["WOOL"] == start["WOOL"] - 3, (
        "claim 9: step-0 WOOL drain wrong (want shop x2 + center x1 = 3)"
    )
    assert inv["EGG"] == start["EGG"] - 2, (
        "claim 9: step-0 EGG drain wrong (want shop x1 + center x1 = 2)"
    )
    assert inv["WHEAT"] == start["WHEAT"] - 2, (
        "claim 9: step-0 WHEAT drain wrong (want shop x1 + center x1 = 2)"
    )
    assert inv["MELON"] == start["MELON"] - 1, (
        "claim 9: step-0 MELON drain wrong (no unlocked shop sells it; center-only = 1)"
    )

    for _ in range(4):
        env.step(actions)  # processes steps 1-4; step 4 fires a second shop-only tick (no center).
    inv = env.state[0].observation.market["inventory"]
    assert inv["WOOL"] == start["WOOL"] - 5, (
        "claim 9: cumulative WOOL drain after the step-4 shop tick wrong"
    )
    assert inv["EGG"] == start["EGG"] - 3, (
        "claim 9: cumulative EGG drain after the step-4 shop tick wrong"
    )
    assert inv["WHEAT"] == start["WHEAT"] - 3, (
        "claim 9: cumulative WHEAT drain after the step-4 shop tick wrong"
    )
    assert inv["MELON"] == start["MELON"] - 1, (
        "claim 9: MELON drained by a shop tick that shouldn't touch it"
    )


def test_claim10_fertilizer_has_zero_town_demand() -> None:
    """Claim 10: FERTILIZER is absent from TOWN_CENTER_PRODUCTS and from
    every SHOPS entry, so town consumption (_town_consume) never touches
    market["inventory"]["FERTILIZER"] -- it can only move via player
    BUY_PRODUCT/SELL orders.

    Structural check against the engine's own tables, plus a behavioral
    check: unlock every shop (several times over, so every product any shop
    sells gets pulled repeatedly) and run 60 ticks with two idle players --
    FERTILIZER inventory must not move at all. Fails if a future engine
    version added FERTILIZER to any shop or to the town center.
    """
    assert "FERTILIZER" not in kagg.TOWN_CENTER_PRODUCTS, (
        "claim 10: FERTILIZER now in TOWN_CENTER_PRODUCTS"
    )
    for shop_name, products in kagg.SHOPS.items():
        assert "FERTILIZER" not in products, f"claim 10: {shop_name} now sells FERTILIZER"

    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 100, "seed": 12101, "weedSpawnChance": 0.0},
    )
    env.reset(num_agents=2)
    obs0 = env.state[0].observation
    obs0.town["unlocked_shops"] = sorted(kagg.SHOPS) * 3
    start_fertilizer = obs0.market["inventory"]["FERTILIZER"]
    actions = [_pass_action(), _pass_action()]
    for _ in range(60):
        env.step(actions)
    end_fertilizer = env.state[0].observation.market["inventory"]["FERTILIZER"]
    assert end_fertilizer == start_fertilizer, (
        f"claim 10 REFUTED: FERTILIZER market inventory moved from town consumption alone "
        f"({start_fertilizer} -> {end_fertilizer}) with no player orders"
    )


def test_claim11_shops_unlock_every_interval_days_capped_at_max_instances() -> None:
    """Claim 11: shops unlock every townShopUnlockInterval days (default 3),
    drawn with replacement from SHOPS, up to MAX_SHOP_INSTANCES (8) total
    instances -- after which unlocking stops even though days keep passing.

    Runs two idle players for 26 days at turnsPerDay=4 and checks the
    unlocked_shops count at every day boundary: it must grow by exactly 1 on
    days that are multiples of 3 (starting day 3) while the count is still
    below the cap, stay flat otherwise, and never exceed 8. Fails if the
    interval, the replacement-draw pool, or the instance cap changed.
    """
    turns_per_day = 4
    num_days = 26
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": (num_days + 1) * turns_per_day,
            "seed": 13001,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_idle_agent, _idle_agent])

    counts = []
    for day in range(num_days):
        obs = env.steps[day * turns_per_day][0].observation
        shops = obs.town["unlocked_shops"]
        for shop_name in shops:
            assert shop_name in kagg.SHOPS, f"claim 11: unlocked an unknown shop {shop_name!r}"
        counts.append(len(shops))

    for day in range(1, num_days):
        grew = counts[day] - counts[day - 1]
        if day % 3 == 0 and counts[day - 1] < 8:
            assert grew == 1, (
                f"claim 11: no unlock on day {day} (multiple of 3, count still below cap)"
            )
        else:
            assert grew == 0, f"claim 11: unexpected unlock on day {day} (not a multiple of 3)"
    assert counts[-1] == 8, (
        f"claim 11: count did not reach the cap of 8 by day {num_days - 1} (got {counts[-1]})"
    )
    assert max(counts) <= 8, "claim 11: instance count exceeded MAX_SHOP_INSTANCES (8)"


def test_claim12_one_fertilizer_per_animal_per_day() -> None:
    """Claim 12: fertilizer_available is set True unconditionally for every
    surviving animal tile in the end-of-day tick (_daily_refresh_animals),
    and COLLECT_FERTILIZER takes exactly 1 unit and clears the flag for the
    rest of that day -- a second COLLECT_FERTILIZER the same day is a silent
    no-op, and the flag comes back True again the following day.

    Fails if collection stopped being capped at 1/day, or if the daily reset
    stopped firing for a surviving (fed) animal.
    """
    turns_per_day = 8
    script: dict[int, Action] = {
        0: {
            "farmer": ["BUILD_COOP"],
            "hands": [],
            "market": [["BUY_ANIMAL", "GOOSE", 1], ["BUY_PRODUCT", "WHEAT", 3]],
        },
        1: {"farmer": ["PICKUP", "GOOSE", 1], "hands": [], "market": []},
        2: {"farmer": ["PLACE", "GOOSE"], "hands": [], "market": []},
        1 * turns_per_day: {"farmer": ["PICKUP", "WHEAT", 1], "hands": [], "market": []},
        1 * turns_per_day + 1: {"farmer": ["FEED"], "hands": [], "market": []},
        1 * turns_per_day + 2: {"farmer": ["COLLECT_FERTILIZER"], "hands": [], "market": []},
        1 * turns_per_day + 3: {"farmer": ["COLLECT_FERTILIZER"], "hands": [], "market": []},
    }
    env = make(
        "kaggriculture",
        configuration={
            "episodeSteps": 40,
            "seed": 14001,
            "weedSpawnChance": 0.0,
            "turnsPerDay": turns_per_day,
        },
    )
    env.run([_scripted_agent(script), _idle_agent])

    after_first_collect = env.steps[1 * turns_per_day + 3][0].observation
    assert after_first_collect.private["inventories"][0].get("FERTILIZER", 0) == 1, (
        "claim 12: first COLLECT_FERTILIZER did not add exactly 1 to the unit's inventory"
    )
    assert after_first_collect.farms[0]["tiles"][4][4]["fertilizer_available"] is False, (
        "claim 12: fertilizer_available did not clear after collection"
    )

    after_second_collect = env.steps[1 * turns_per_day + 4][0].observation
    assert after_second_collect.private["inventories"][0].get("FERTILIZER", 0) == 1, (
        "claim 12: a second same-day COLLECT_FERTILIZER granted more than 1/day"
    )

    day2_start = env.steps[2 * turns_per_day][0].observation
    day2_tile = day2_start.farms[0]["tiles"][4][4]
    assert day2_tile.get("animal") == "GOOSE", (
        "test setup: goose escaped (unfed) before claim 12 could be checked"
    )
    assert day2_tile["fertilizer_available"] is True, (
        "claim 12: fertilizer_available did not reset True the following day"
    )
