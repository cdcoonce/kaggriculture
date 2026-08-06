"""Daily-planner behavior: the Plan A opening, land expansion, and hand-count
scaling, plus their respective cutoffs.

The planner is pure and per-turn idempotent: every quantity is derived from
current observable state (seeds bought on turn t are visible at t+1, hires_today
is in the shared farm dict), so re-running it never double-buys.
"""

from __future__ import annotations

from agent.plan import plan_day


def test_day_zero_opening_buys_seeds_goose_feed_and_hires() -> None:
    plan = plan_day(
        day=0,
        money=3000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=False,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert plan.hire_count == 3
    assert ["BUY_ANIMAL", "GOOSE", 1] in plan.buys
    assert ["BUY_SEED", "WHEAT", 24] in plan.buys
    assert ["BUY_PRODUCT", "WHEAT", 3] in plan.buys


def test_phase_cutoffs_stop_seed_and_goose_purchases() -> None:
    late = plan_day(
        day=26,
        money=5000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert not any(b[0] == "BUY_SEED" for b in late.buys)

    past_payback = plan_day(
        day=15,
        money=5000.0,
        wheat_seeds=5,
        plantable_target_tiles=5,
        wheat_on_hand=3,
        goose_owned=False,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert not any(b[0] == "BUY_ANIMAL" for b in past_payback.buys)


def test_idempotent_against_observed_state() -> None:
    plan = plan_day(
        day=3,
        money=2000.0,
        wheat_seeds=10,
        plantable_target_tiles=10,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=2,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert plan.hire_count == 1
    assert not any(b[0] == "BUY_SEED" for b in plan.buys)  # seeds already cover tiles
    assert not any(b[0] == "BUY_PRODUCT" for b in plan.buys)  # feed reserve already met
    assert not any(b[0] == "BUY_ANIMAL" for b in plan.buys)


def test_cash_poor_day_clamps_seed_buys() -> None:
    plan = plan_day(
        day=2,
        money=100.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=3,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert ["BUY_SEED", "WHEAT", 10] in plan.buys


def test_land_buy_fires_at_reserve_boundary() -> None:
    # NE costs 1000 and LAND_RESERVE is 500, so 1500 is the affordability
    # line; goose already owned keeps that purchase out of the budget math.
    too_poor = plan_day(
        day=0,
        money=1499.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert ["BUY_LAND"] not in too_poor.buys

    affordable = plan_day(
        day=0,
        money=1500.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert ["BUY_LAND"] in affordable.buys


def test_land_order_uses_next_missing_quadrants_cutoff_not_an_earlier_one() -> None:
    # NE is already owned, so the pending purchase is SW — it must be judged
    # against SW's cutoff (day 23), not NE's (24) or SE's (20).
    within_sw_cutoff = plan_day(
        day=23,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=49,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
    )
    assert ["BUY_LAND"] in within_sw_cutoff.buys

    past_sw_cutoff = plan_day(
        day=24,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=49,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
    )
    assert ["BUY_LAND"] not in past_sw_cutoff.buys


def test_no_land_buy_when_all_quadrants_owned() -> None:
    plan = plan_day(
        day=0,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=99,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert not any(b == ["BUY_LAND"] for b in plan.buys)


def test_se_land_cutoff_day_boundary() -> None:
    on_cutoff = plan_day(
        day=20,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
    )
    assert ["BUY_LAND"] in on_cutoff.buys

    past_cutoff = plan_day(
        day=21,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
    )
    assert not any(b == ["BUY_LAND"] for b in past_cutoff.buys)


def test_hand_target_scales_with_active_tile_universe() -> None:
    # hands_target = max(HANDS_MIN, round(active_tiles / HANDS_PER_TILES)).
    # hires_today is pinned one below each expected target so the uncapped
    # hire_count (1) reveals the target exactly instead of saturating at
    # MAX_HIRES_PER_TURN.
    for active_tiles, expected_target in [(24, 3), (49, 6), (74, 9), (99, 12)]:
        plan = plan_day(
            day=0,
            money=0.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=0,
            goose_owned=True,
            hires_today=expected_target - 1,
            unlocked_quadrants=("NW", "NE", "SW", "SE"),
            active_tiles=active_tiles,
        )
        assert plan.hire_count == 1, f"active_tiles={active_tiles}"


def test_hire_count_capped_at_max_hires_per_turn() -> None:
    plan = plan_day(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert plan.hire_count == 4  # hands_target is 12; MAX_HIRES_PER_TURN clamps it


def test_hire_count_floors_at_zero_when_hires_today_exceeds_target() -> None:
    plan = plan_day(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=5,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert plan.hire_count == 0


def test_day_zero_composite_sequences_goose_then_land_then_seeds_then_feed() -> None:
    # goose 300 -> NE land 1000 (leaves 1700, still above the reserve floor)
    # -> 24 seeds at 10 each -> feed top-up, in that exact order.
    plan = plan_day(
        day=0,
        money=3000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=False,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    assert plan.buys == [
        ["BUY_ANIMAL", "GOOSE", 1],
        ["BUY_LAND"],
        ["BUY_SEED", "WHEAT", 24],
        ["BUY_PRODUCT", "WHEAT", 3],
    ]


def test_melon_seed_buy_targets_two_days_of_stagger() -> None:
    # MELON_PLANT_DAILY_CAP (2) * 2 days = 4; 5 empty melon tiles don't raise it.
    # All quadrants already owned and the goose already bought, so land/goose
    # purchases don't interfere with the budget math under test.
    plan = plan_day(
        day=3,
        money=2000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        melon_seeds=0,
        empty_melon_tiles=5,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert ["BUY_SEED", "MELON", 4] in plan.buys


def test_melon_seed_buy_clamped_by_empty_tiles_below_the_stagger_target() -> None:
    plan = plan_day(
        day=3,
        money=2000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        melon_seeds=0,
        empty_melon_tiles=1,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert ["BUY_SEED", "MELON", 1] in plan.buys


def test_melon_seed_buy_nets_out_seeds_already_on_hand() -> None:
    plan = plan_day(
        day=3,
        money=2000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        melon_seeds=3,
        empty_melon_tiles=8,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert ["BUY_SEED", "MELON", 1] in plan.buys  # target 4, 3 already on hand


def test_melon_seed_buy_stops_after_cutoff_day() -> None:
    plan = plan_day(
        day=20,
        money=2000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        melon_seeds=0,
        empty_melon_tiles=8,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert not any(b[0] == "BUY_SEED" and b[1] == "MELON" for b in plan.buys)


def test_melon_seed_buy_precedes_wheat_seed_buy_in_the_budget_sequence() -> None:
    plan = plan_day(
        day=3,
        money=2000.0,
        wheat_seeds=0,
        plantable_target_tiles=40,
        melon_seeds=0,
        empty_melon_tiles=8,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    seed_buys = [b for b in plan.buys if b[0] == "BUY_SEED"]
    assert [b[1] for b in seed_buys] == ["MELON", "WHEAT"]


def test_melon_seed_buy_clamped_by_available_budget() -> None:
    plan = plan_day(
        day=3,
        money=150.0,  # 150 // 80 == 1, below the stagger target of 4
        wheat_seeds=0,
        plantable_target_tiles=0,
        melon_seeds=0,
        empty_melon_tiles=8,
        wheat_on_hand=3,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
    )
    assert ["BUY_SEED", "MELON", 1] in plan.buys
