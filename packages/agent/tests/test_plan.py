"""Daily-planner behavior: the Plan A opening, land expansion, and hand-count
scaling, plus their respective cutoffs.

The planner is pure and per-turn idempotent: every quantity is derived from
current observable state (seeds bought on turn t are visible at t+1, hires_today
is in the shared farm dict), so re-running it never double-buys.
"""

from __future__ import annotations

from agent.plan import (
    ANIMAL_BUY_ORDER,
    GOOSE_MIN_DAY,
    LAND_UNLOCK_HAND_BURST,
    MAX_HIRES_PER_TURN,
    MELON_SEED_PRICE,
    NE_LAND_MIN_DAY,
    SEED_PRICE,
    STRAWBERRY_SEED_PRICE,
    DayPlan,
    plan_day,
)


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


def test_goose_min_day_default_is_zero_so_shipped_behavior_is_unchanged() -> None:
    # DEFAULT-NEUTRAL by construction: the goose branch never had an
    # earliest-day gate before this knob existed (it buys the instant cash
    # allows, including turn 0), so 0 reproduces that exactly -- day >= 0 is
    # always true. Pinned against the module constant so an edit can never
    # drift silently out of sync with plan_day's own default. Mirrors
    # test_ne_land_min_day_default_is_zero_so_shipped_behavior_is_unchanged.
    assert GOOSE_MIN_DAY == 0


def test_goose_waits_for_goose_min_day_then_buys_on_time() -> None:
    # Mirrors test_ne_land_waits_for_ne_land_min_day_then_buys_on_time: the
    # same day >= *_min_day mechanism, gating the goose purchase instead of
    # NE land. Ample cash throughout so the gate under test is the day
    # check, not affordability.
    kwargs = dict(
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=False,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
        goose_min_day=6,
    )
    for day in (0, 3, 5):
        too_early = plan_day(day=day, **kwargs)  # type: ignore[arg-type]
        assert ["BUY_ANIMAL", "GOOSE", 1] not in too_early.buys, day

    on_time = plan_day(day=6, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_ANIMAL", "GOOSE", 1] in on_time.buys


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


def test_ne_land_min_day_default_is_zero_so_shipped_behavior_is_unchanged() -> None:
    # DEFAULT-NEUTRAL by construction: the NE branch never had an
    # earliest-day gate before this knob existed (it buys the instant cash
    # allows, including turn 0), so 0 reproduces that exactly -- day >= 0 is
    # always true. Pinned against the module constant so an edit can never
    # drift silently out of sync with plan_day's own default.
    assert NE_LAND_MIN_DAY == 0


def test_ne_land_waits_for_ne_land_min_day_then_buys_on_time() -> None:
    # Mirrors test_se_land_not_bought_before_day_twelve_even_with_ample_budget:
    # SE already has an earliest-day gate (SE_LAND_MIN_DAY); this is the same
    # mechanism for NE, which never had one. Ample cash throughout so the
    # gate under test is the day check, not affordability.
    kwargs = dict(
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
        ne_land_min_day=6,
    )
    for day in (0, 3, 5):
        too_early = plan_day(day=day, **kwargs)  # type: ignore[arg-type]
        assert ["BUY_LAND"] not in too_early.buys, day

    on_time = plan_day(day=6, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] in on_time.buys


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
    """SE's own gates, exercised with the quadrant cap lifted.

    The shipped default is max_owned_quadrants=3 (gated, PR #81), so the
    SE branch is unreachable in normal play. These gates still exist and
    still have to work, so the tests opt in explicitly rather than being
    deleted -- otherwise raising the cap later would silently ship
    untested land logic.
    """
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
        max_owned_quadrants=4,
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
        max_owned_quadrants=4,
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


def test_max_hires_per_turn_default_and_override() -> None:
    # Diagnosis: the morning crew rebuilds over 3 hours (units on the farm at
    # hours 0/1/2/3: 1/5/9/11) because MAX_HIRES_PER_TURN=4 caps every day's
    # ramp-up, regardless of how large the actual shortfall is. active_tiles=80
    # makes hands_target = round(80/8) == 10 exactly, so hires_today=0 is a
    # clean "need 10 hires" scenario: the default constant clamps it to 4, and
    # an explicit override recovers the full 10.
    kwargs = dict(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=80,
    )
    default_plan = plan_day(**kwargs)
    assert default_plan.hire_count == 4
    assert default_plan.hire_count == MAX_HIRES_PER_TURN

    overridden_plan = plan_day(**kwargs, max_hires_per_turn=10)
    assert overridden_plan.hire_count == 10


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


# --- Animals (M2a) -----------------------------------------------------
#
# Cows before sheep, at most ANIMAL_BUY_CAP_PER_TURN (2) total per turn,
# never more than the observed empty-built-pasture count (trap: a bought
# animal that can't be placed just sits in the shed, dead capital), and only
# inside each species' own breakeven purchase window.


def test_animals_buy_cows_before_sheep_until_targets() -> None:
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=15,
    )
    animal_buys = [b for b in plan.buys if b[0] == "BUY_ANIMAL"]
    # The shared 2/turn cap is exhausted by cows before sheep gets a look-in.
    assert animal_buys == [["BUY_ANIMAL", "COW", 2]]


def test_animal_buy_order_default_is_cows_before_sheep() -> None:
    # Pinned against the module constant, the same pattern as
    # test_ne_land_min_day_default_is_zero_so_shipped_behavior_is_unchanged --
    # test_animals_buy_cows_before_sheep_until_targets above already proves
    # this behaviorally; this pins the literal default value itself.
    assert ANIMAL_BUY_ORDER == ("COW", "SHEEP")


def test_animal_buy_order_reorders_sheep_before_cows() -> None:
    # Same scenario as test_animals_buy_cows_before_sheep_until_targets --
    # the shared 2/turn cap is the binding constraint -- just with
    # animal_buy_order flipped, so sheep claims the cap before cow gets a
    # look-in. Every guard/cap/target math is untouched; only the order the
    # loop visits the two species changes.
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=15,
        animal_buy_order=("SHEEP", "COW"),
    )
    animal_buys = [b for b in plan.buys if b[0] == "BUY_ANIMAL"]
    assert animal_buys == [["BUY_ANIMAL", "SHEEP", 2]]


def test_animals_buy_sheep_once_cow_target_is_met() -> None:
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=6,
        sheep_owned=0,
        empty_pastures=15,
    )
    animal_buys = [b for b in plan.buys if b[0] == "BUY_ANIMAL"]
    assert animal_buys == [["BUY_ANIMAL", "SHEEP", 2]]


def test_no_animal_buy_when_no_empty_pastures() -> None:
    # Trap: never BUY_ANIMAL without an already-built empty pasture to place
    # it on -- a bought-but-unplaceable animal is pure dead capital.
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=0,
    )
    assert not any(b[0] == "BUY_ANIMAL" for b in plan.buys)


def test_animal_buy_limited_by_empty_pasture_count() -> None:
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=1,
    )
    animal_buys = [b for b in plan.buys if b[0] == "BUY_ANIMAL"]
    assert animal_buys == [["BUY_ANIMAL", "COW", 1]]


def test_animal_purchase_nets_out_already_owned_toward_target() -> None:
    plan = plan_day(
        day=3,
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=5,
        sheep_owned=9,  # already at target: contributes nothing
        empty_pastures=15,
    )
    animal_buys = [b for b in plan.buys if b[0] == "BUY_ANIMAL"]
    assert animal_buys == [["BUY_ANIMAL", "COW", 1]]  # only 1 needed to reach target 6


def test_cow_purchase_window_closes_after_day_nine() -> None:
    kwargs = dict(
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=0,
        sheep_owned=9,
        empty_pastures=15,
    )
    on_time = plan_day(day=9, **kwargs)  # type: ignore[arg-type]
    assert any(b[0] == "BUY_ANIMAL" and b[1] == "COW" for b in on_time.buys)

    late = plan_day(day=10, **kwargs)  # type: ignore[arg-type]
    assert not any(b[0] == "BUY_ANIMAL" and b[1] == "COW" for b in late.buys)


def test_sheep_purchase_window_closes_after_day_eleven() -> None:
    kwargs = dict(
        money=10000.0,
        wheat_seeds=50,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        cows_owned=6,
        sheep_owned=0,
        empty_pastures=15,
    )
    on_time = plan_day(day=11, **kwargs)  # type: ignore[arg-type]
    assert any(b[0] == "BUY_ANIMAL" and b[1] == "SHEEP" for b in on_time.buys)

    late = plan_day(day=12, **kwargs)  # type: ignore[arg-type]
    assert not any(b[0] == "BUY_ANIMAL" and b[1] == "SHEEP" for b in late.buys)


def test_day_zero_sequence_includes_animals_between_melon_and_wheat() -> None:
    plan = plan_day(
        day=0,
        money=5000.0,
        wheat_seeds=0,
        plantable_target_tiles=24,
        melon_seeds=0,
        empty_melon_tiles=8,
        wheat_on_hand=0,
        goose_owned=False,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=2,
    )
    op_order = [b[0] for b in plan.buys]
    assert op_order == [
        "BUY_ANIMAL",  # goose
        "BUY_LAND",  # NE
        "BUY_SEED",  # melon
        "BUY_ANIMAL",  # cow
        "BUY_SEED",  # wheat
        "BUY_PRODUCT",  # feed top-up
    ]
    assert plan.buys[3] == ["BUY_ANIMAL", "COW", 2]


# --- SW/SE reorder around animals (M2a) -------------------------------------


def test_sw_land_waits_while_animal_windows_are_open_and_targets_unmet() -> None:
    waiting = plan_day(
        day=5,  # cow window (<=9) still open, target unmet
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=0,  # can't buy animals this turn either -- still must wait
    )
    assert ["BUY_LAND"] not in waiting.buys

    unblocked = plan_day(
        day=12,  # both windows closed (cow <=9, sheep <=11)
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
        cows_owned=0,
        sheep_owned=0,
        empty_pastures=0,
    )
    assert ["BUY_LAND"] in unblocked.buys


def test_sw_land_proceeds_once_animal_targets_are_met_even_within_windows() -> None:
    plan = plan_day(
        day=5,  # well within both purchase windows
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
        cows_owned=6,
        sheep_owned=9,  # both targets already met
        empty_pastures=0,
    )
    assert ["BUY_LAND"] in plan.buys


def test_se_land_not_bought_before_day_twelve_even_with_ample_budget() -> None:
    """SE's own gates, exercised with the quadrant cap lifted.

    The shipped default is max_owned_quadrants=3 (gated, PR #81), so the
    SE branch is unreachable in normal play. These gates still exist and
    still have to work, so the tests opt in explicitly rather than being
    deleted -- otherwise raising the cap later would silently ship
    untested land logic.
    """
    kwargs = dict(
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
        cows_owned=6,
        sheep_owned=9,  # targets met so the animals-done gate isn't the blocker here
        empty_pastures=0,
        max_owned_quadrants=4,
    )
    too_early = plan_day(day=11, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] not in too_early.buys

    on_time = plan_day(day=12, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] in on_time.buys


def test_se_land_requires_larger_reserve_than_other_quadrants() -> None:
    """SE's own gates, exercised with the quadrant cap lifted.

    The shipped default is max_owned_quadrants=3 (gated, PR #81), so the
    SE branch is unreachable in normal play. These gates still exist and
    still have to work, so the tests opt in explicitly rather than being
    deleted -- otherwise raising the cap later would silently ship
    untested land logic.
    """
    # price(4000) + 2000 = 6000 is the affordability line, not the usual
    # price + LAND_RESERVE(500) -- SE is demoted relative to NE/SW.
    kwargs = dict(
        day=15,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
        cows_owned=6,
        sheep_owned=9,
        empty_pastures=0,
        max_owned_quadrants=4,
    )
    too_poor = plan_day(money=5999.0, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] not in too_poor.buys

    affordable = plan_day(money=6000.0, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] in affordable.buys


# --- Hands + feed reserve scale with husbandry (M2a) ------------------------


def test_hands_target_gets_a_husbandry_hand_at_eight_placed_animals() -> None:
    # active_tiles=99 -> base target round(99/8)=12; +1 husbandry hand once
    # animals_placed >= 8 -> target 13. hires_today pinned one below the
    # target so the uncapped hire_count (1) reveals it exactly, mirroring
    # the existing tile-scaling isolation pattern.
    plan = plan_day(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=12,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        animals_placed=8,
    )
    assert plan.hire_count == 1


def test_hands_target_unaffected_below_eight_placed_animals() -> None:
    plan = plan_day(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=11,
        unlocked_quadrants=("NW", "NE", "SW", "SE"),
        active_tiles=99,
        animals_placed=7,
    )
    assert plan.hire_count == 1  # target stays 12 (round(99/8)); no husbandry bonus yet


# --- extra_hands: labor SUPPLY knob (kaggriculture diagnosis, 2026-09-11 --
# continuation of the three labor knobs in test_policy.py) --------------------


def test_extra_hands_raises_the_hands_target_by_exactly_two() -> None:
    # extra_hands (PolicyConfig field, default 0) is added to hands_target
    # AFTER the existing max(HANDS_MIN, round(active_tiles/HANDS_PER_TILES) +
    # husbandry_hand) computation, so it never interacts with the HANDS_MIN
    # floor or the husbandry bonus -- it is a flat add-on.
    #
    # active_tiles=24 -> base target 3 (HANDS_MIN; round(24/8) == 3 exactly,
    # so the floor isn't even doing anything here). hires_today is pinned one
    # below that base target so the uncapped hire_count (1) reveals the
    # target exactly, mirroring test_hand_target_scales_with_active_tile_
    # universe's isolation technique. Same kwargs both calls -- only
    # extra_hands differs -- so any change in hire_count is attributable to
    # it alone.
    kwargs = dict(
        day=0,
        money=0.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=2,
        unlocked_quadrants=("NW",),
        active_tiles=24,
    )
    default_plan = plan_day(**kwargs)
    assert default_plan.hire_count == 1  # hands_target 3 (HANDS_MIN), hires_today 2

    with_extra_hands = plan_day(**kwargs, extra_hands=2)
    assert with_extra_hands.hire_count == default_plan.hire_count + 2
    assert with_extra_hands.hire_count == 3  # hands_target 3+2=5, hires_today 2


# --- land_unlock_hand_burst: a ONE-TURN crew burst on the turn that buys new
# land (kaggriculture, 2026-09-12) --------------------------------------------


def test_land_unlock_hand_burst_raises_the_hands_target_on_the_sw_purchase_turn() -> None:
    # The turn under test submits the SW ["BUY_LAND"] (NW+NE owned, both
    # animal windows closed at day 12, ample cash), so the burst fires. Same
    # isolation technique as test_extra_hands_raises_the_hands_target_by_
    # exactly_two above: hires_today is pinned one below the base target so
    # the uncapped hire_count reveals the target exactly, and the same kwargs
    # feed both calls so any change is attributable to the knob alone.
    #
    # active_tiles=48 (NW+NE) -> base target 6 (round(48/8); no husbandry
    # bonus at animals_placed=0), hires_today=5 -> base hire_count 1. A burst
    # of 2 lifts the target to 8, so 3 hires -- still under
    # MAX_HIRES_PER_TURN's 4, which the clamp test below covers separately.
    kwargs = dict(
        day=12,
        money=20000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=5,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=48,
    )
    default_plan = plan_day(**kwargs)
    assert ["BUY_LAND"] in default_plan.buys  # the trigger turn is real
    assert default_plan.hire_count == 1  # hands_target 6, hires_today 5

    burst_plan = plan_day(**kwargs, land_unlock_hand_burst=2)
    assert burst_plan.hire_count == default_plan.hire_count + 2
    assert burst_plan.hire_count == 3  # hands_target 6+2=8, hires_today 5


def test_land_unlock_hand_burst_default_is_zero_so_shipped_behavior_is_unchanged() -> None:
    # DEFAULT-NEUTRAL by construction: there was never an implicit "burst"
    # term before this knob existed, so 0 adds exactly nothing to
    # hands_target on every turn, land-buying or not. Pinned against the
    # module constant so an edit can never drift silently out of sync with
    # plan_day's own default -- the same pin
    # test_ne_land_min_day_default_is_zero_so_shipped_behavior_is_unchanged
    # and test_goose_min_day_default_is_zero_so_shipped_behavior_is_unchanged
    # put on their constants.
    assert LAND_UNLOCK_HAND_BURST == 0


# Every row is a (label, kwargs, hire_count, buys) tuple whose expected values
# are pinned to the PRE-knob formula -- hands_target = max(HANDS_MIN,
# round(active_tiles / HANDS_PER_TILES) + husbandry_hand) + extra_hands, then
# hire_count = min(max(0, hands_target - hires_today), max_hires_per_turn).
# Recomputing them by hand here (rather than diffing two plan_day calls) is
# what makes this a no-op proof rather than a self-consistency check: a burst
# that fired at the default would have to change one of these literals.
_BURST_NO_OP_MATRIX: list[tuple[str, dict[str, object], int, list[list[object]]]] = [
    (
        # NE purchase turn at the shipped ne_land_min_day of 0: day 0, the
        # 24-tile NW-only board, opening cash. base target 3 (HANDS_MIN and
        # round(24/8) agree), hires_today 0.
        "ne purchase, day 0, opening board",
        dict(
            day=0,
            money=3000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=("NW",),
            active_tiles=24,
        ),
        3,
        [["BUY_LAND"]],
    ),
    (
        # No land left to buy (three quadrants owned, the shipped
        # max_owned_quadrants cap) -- the burst has nothing to fire on.
        "no purchase, three quadrants owned",
        dict(
            day=20,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=("NW", "NE", "SW"),
            active_tiles=72,
        ),
        4,
        [],
    ),
    (
        # SW purchase turn, mid-ramp: base target 6, hires_today one below it.
        "sw purchase, hires_today one below target",
        dict(
            day=12,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=5,
            unlocked_quadrants=("NW", "NE"),
            active_tiles=48,
        ),
        1,
        [["BUY_LAND"]],
    ),
    (
        # BEFORE the animal gate: SW is next and affordable, but neither
        # species' window has closed and neither target is met, so
        # animals_done is False and no BUY_LAND is submitted.
        "sw next but animals_done False",
        dict(
            day=5,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=("NW", "NE"),
            active_tiles=48,
        ),
        4,
        [],
    ),
    (
        # SW purchase turn at hires_today 0 -- already pinned to
        # max_hires_per_turn before any burst is applied.
        "sw purchase, already cap-bound at hires_today 0",
        dict(
            day=12,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=("NW", "NE"),
            active_tiles=48,
        ),
        4,
        [["BUY_LAND"]],
    ),
    (
        # SW purchase turn with extra_hands raised and the per-turn cap
        # lifted, so neither of those knobs masks a stray burst.
        "sw purchase, extra_hands=3 and max_hires_per_turn=10",
        dict(
            day=12,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=8,
            unlocked_quadrants=("NW", "NE"),
            active_tiles=48,
            extra_hands=3,
            max_hires_per_turn=10,
        ),
        1,
        [["BUY_LAND"]],
    ),
    (
        # The SE rung, reachable only through max_owned_quadrants=4 (the
        # value the pre-cap eval arms use) -- it appends ["BUY_LAND"] too.
        "se purchase, max_owned_quadrants=4",
        dict(
            day=15,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=50,
            goose_owned=True,
            hires_today=8,
            unlocked_quadrants=("NW", "NE", "SW"),
            active_tiles=72,
            max_owned_quadrants=4,
        ),
        1,
        [["BUY_LAND"]],
    ),
    (
        # A land-buying turn that also carries a non-land order and the
        # husbandry bonus: base target 6 + 1 = 7. Pins that the burst leaves
        # the feed line's quantity and its position before ["BUY_LAND"] alone.
        "sw purchase alongside a feed order and the husbandry hand",
        dict(
            day=12,
            money=20000.0,
            wheat_seeds=0,
            plantable_target_tiles=0,
            wheat_on_hand=0,
            goose_owned=True,
            hires_today=5,
            unlocked_quadrants=("NW", "NE"),
            active_tiles=48,
            animals_placed=9,
        ),
        2,
        [["BUY_PRODUCT", "WHEAT", 12], ["BUY_LAND"]],
    ),
]


def test_land_unlock_hand_burst_at_the_default_changes_nothing_anywhere() -> None:
    # The property that matters most: at the default the shipped agent is
    # provably unchanged. Asserts the WHOLE DayPlan (hire_count AND buys)
    # against hand-computed pre-knob values across land-buying and
    # non-land-buying turns, NE/SW/SE purchases, before and after the animal
    # gate, and varying hires_today, active_tiles, extra_hands and
    # max_hires_per_turn.
    for label, kwargs, hire_count, buys in _BURST_NO_OP_MATRIX:
        expected = DayPlan(hire_count=hire_count, buys=buys)
        assert plan_day(**kwargs) == expected, label  # type: ignore[arg-type]
        # ...and passing the default explicitly is the same thing again, so
        # plan_day's own default can never diverge from LAND_UNLOCK_HAND_BURST.
        explicit = plan_day(**kwargs, land_unlock_hand_burst=LAND_UNLOCK_HAND_BURST)  # type: ignore[arg-type]
        assert explicit == expected, label


def test_land_unlock_hand_burst_does_not_fire_on_the_turns_around_the_purchase() -> None:
    # The burst is a ONE-TURN event keyed to the ["BUY_LAND"] order itself,
    # not to the day or to the board size. The turn before (SW affordable and
    # next, but animals_done still False at day 11 -- sheep's window closes
    # after day 11) and the turn after (SW now owned, so _next_quadrant is
    # None) must both get exactly the base target even at a large burst.
    common = dict(
        money=20000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
    )
    before = dict(common, day=11, hires_today=5, unlocked_quadrants=("NW", "NE"), active_tiles=48)
    purchase = dict(common, day=12, hires_today=5, unlocked_quadrants=("NW", "NE"), active_tiles=48)
    after = dict(
        common,
        day=12,
        hires_today=9,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=72,
    )

    assert ["BUY_LAND"] not in plan_day(**before).buys  # type: ignore[arg-type]
    assert ["BUY_LAND"] in plan_day(**purchase).buys  # type: ignore[arg-type]
    assert ["BUY_LAND"] not in plan_day(**after).buys  # type: ignore[arg-type]

    # Base target 6 against hires_today 5 before, and 9 against 9 after.
    assert plan_day(**before, land_unlock_hand_burst=8).hire_count == 1  # type: ignore[arg-type]
    assert plan_day(**after, land_unlock_hand_burst=8).hire_count == 0  # type: ignore[arg-type]
    # Unchanged from the no-burst call on both, and changed on the purchase
    # turn -- so the knob is keyed to the order, not to the surrounding state.
    assert plan_day(**before).hire_count == 1  # type: ignore[arg-type]
    assert plan_day(**after).hire_count == 0  # type: ignore[arg-type]
    assert plan_day(**purchase).hire_count == 1  # type: ignore[arg-type]
    assert plan_day(**purchase, land_unlock_hand_burst=8).hire_count == 4  # type: ignore[arg-type]


def test_land_unlock_hand_burst_is_clamped_by_max_hires_per_turn() -> None:
    # hire_count = min(hands_target - hires_today, max_hires_per_turn), so a
    # burst bigger than the per-turn cap cannot place more HIRE orders than
    # the cap allows on the one turn it fires. hires_today is pinned EXACTLY
    # at the base target (6) so the whole hire_count is the burst's doing and
    # the clamp is the only thing bounding it.
    kwargs = dict(
        day=12,
        money=20000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=6,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=48,
    )
    assert plan_day(**kwargs).hire_count == 0  # type: ignore[arg-type]
    assert plan_day(**kwargs, land_unlock_hand_burst=3).hire_count == 3  # type: ignore[arg-type]
    assert plan_day(**kwargs, land_unlock_hand_burst=4).hire_count == 4  # type: ignore[arg-type]
    # Past the cap the extra burst is simply unreachable on this turn.
    assert plan_day(**kwargs, land_unlock_hand_burst=8).hire_count == MAX_HIRES_PER_TURN  # type: ignore[arg-type]

    for burst in range(0, 9):
        for cap in (1, 2, 4, 10):
            plan = plan_day(**kwargs, land_unlock_hand_burst=burst, max_hires_per_turn=cap)  # type: ignore[arg-type]
            assert plan.hire_count <= cap, (burst, cap)
            assert plan.hire_count == min(burst, cap), (burst, cap)


def test_land_unlock_hand_burst_and_extra_hands_compose_additively() -> None:
    # extra_hands is a flat all-game add-on; the burst is a one-turn one. Both
    # land AFTER the max(HANDS_MIN, ...) floor, so on a land-buying turn they
    # simply sum. max_hires_per_turn=10 keeps the per-turn clamp out of the
    # way so the composed target is visible directly in hire_count.
    kwargs = dict(
        day=12,
        money=20000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=6,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=48,
        max_hires_per_turn=10,
    )
    assert plan_day(**kwargs).hire_count == 0  # type: ignore[arg-type]  # target 6, hires_today 6
    assert plan_day(**kwargs, extra_hands=2).hire_count == 2  # type: ignore[arg-type]  # target 8
    assert plan_day(**kwargs, land_unlock_hand_burst=3).hire_count == 3  # type: ignore[arg-type]  # target 9
    both = plan_day(**kwargs, extra_hands=2, land_unlock_hand_burst=3)  # type: ignore[arg-type]
    assert both.hire_count == 5  # target 6+2+3 = 11, hires_today 6


def test_land_unlock_hand_burst_is_applied_after_the_hands_min_floor() -> None:
    # A tiny board is the only place the HANDS_MIN floor actually binds:
    # active_tiles=8 gives round(8/8) == 1, which max(HANDS_MIN, ...) lifts
    # to 3. Folding the burst INSIDE that max would let the floor swallow it
    # (max(3, 1+2) is still 3); applied after, it adds. Same placement
    # extra_hands already has -- see
    # test_extra_hands_raises_the_hands_target_by_exactly_two above.
    kwargs = dict(
        day=12,
        money=20000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=3,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=8,
    )
    assert plan_day(**kwargs).hire_count == 0  # type: ignore[arg-type]  # target max(3, 1) == 3
    assert plan_day(**kwargs, land_unlock_hand_burst=2).hire_count == 2  # type: ignore[arg-type]


def test_land_unlock_hand_burst_never_changes_what_the_turn_buys() -> None:
    # The knob is labor SUPPLY only. It must not buy land the turn would not
    # have bought, must not suppress one it would have, and must not shift a
    # single downstream quantity -- every buy line after the first reads the
    # running `budget`, so a burst that touched it would show up as a
    # different seed or feed count here.
    #
    # (Known limitation, deliberately NOT modeled: hire cost is paid by the
    # ENGINE, not out of plan_day's budget, and the engine's _do_hire
    # silently returns when the farm cannot afford the next rung of the
    # Fibonacci ladder. A burst asked for on a cash-poor turn is therefore a
    # silent partial no-op in the game -- see LAND_UNLOCK_HAND_BURST's own
    # comment in plan.py. plan_day cannot see engine cash at hire time, so
    # what is pinned here is that the PLAN is unchanged.)
    opening = dict(
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
    sw_affordable = dict(
        day=12,
        money=2500.0,  # exactly LAND_PRICES["SW"] + LAND_RESERVE
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=50,
        goose_owned=True,
        hires_today=5,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=48,
    )
    sw_one_dollar_short = dict(sw_affordable, money=2499.0)

    baseline_opening = plan_day(**opening).buys  # type: ignore[arg-type]
    # The shipped day-0 opening, unchanged -- goose, NE land, the wheat seed
    # line sized out of what those two left, then feed.
    assert baseline_opening == [
        ["BUY_ANIMAL", "GOOSE", 1],
        ["BUY_LAND"],
        ["BUY_SEED", "WHEAT", 24],
        ["BUY_PRODUCT", "WHEAT", 3],
    ]
    assert plan_day(**sw_affordable).buys == [["BUY_LAND"]]  # type: ignore[arg-type]
    assert plan_day(**sw_one_dollar_short).buys == []  # type: ignore[arg-type]

    for burst in range(0, 9):
        assert plan_day(**opening, land_unlock_hand_burst=burst).buys == baseline_opening, burst  # type: ignore[arg-type]
        # One dollar short stays one dollar short at every burst: the knob
        # can never conjure a purchase the turn could not afford.
        short = plan_day(**sw_one_dollar_short, land_unlock_hand_burst=burst)  # type: ignore[arg-type]
        assert short.buys == [], burst
        assert short.hire_count == 1, burst  # base target 6 - 5, no burst fired
        # ...and an affordable one stays affordable, with the burst applied.
        afford = plan_day(**sw_affordable, land_unlock_hand_burst=burst)  # type: ignore[arg-type]
        assert afford.buys == [["BUY_LAND"]], burst
        assert afford.hire_count == min(1 + burst, MAX_HIRES_PER_TURN), burst


def test_feed_reserve_scales_with_placed_animal_count() -> None:
    plan = plan_day(
        day=5,
        money=5000.0,
        wheat_seeds=0,
        plantable_target_tiles=0,
        wheat_on_hand=5,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW",),
        active_tiles=24,
        animals_placed=10,
    )
    assert ["BUY_PRODUCT", "WHEAT", 8] in plan.buys  # target 10+3=13, gap 13-5=8


# --- Strawberry seed line -------------------------------------------------


def _sb_plan(**overrides: object) -> object:
    base: dict[str, object] = {
        "day": 0,
        "money": 3000.0,
        "wheat_seeds": 0,
        "plantable_target_tiles": 24,
        "wheat_on_hand": 0,
        "goose_owned": True,
        "hires_today": 0,
        "unlocked_quadrants": ("NW",),
        "active_tiles": 24,
    }
    base.update(overrides)
    return plan_day(**base)  # type: ignore[arg-type]


def _sb_buy(plan: object) -> list[object] | None:
    return next((b for b in plan.buys if b[0] == "BUY_SEED" and b[1] == "STRAWBERRY"), None)  # type: ignore[attr-defined]


def test_no_strawberry_seed_is_bought_for_a_zero_tile_zone() -> None:
    # The shipped default. empty_strawberry_tiles is 0, so the line must emit
    # nothing at all -- this is what makes the whole mechanic a bit-exact
    # no-op against the pre-strawberry chassis.
    assert _sb_buy(_sb_plan()) is None


def test_strawberry_seed_buy_holds_two_days_of_the_planting_stagger() -> None:
    # Same "two days of headroom" sizing as the melon and wheat seed lines:
    # enough to keep the dispatcher's stagger fed without parking cash in
    # seed that could be buying land or animals.
    # Funded well past the budget share, which since the 2026-08-19 prereg is
    # the bound that binds first at the opening bankroll -- this test is about
    # the stagger, so the cash bound is deliberately taken out of the way.
    plan = _sb_plan(money=100_000.0, empty_strawberry_tiles=30, strawberry_plant_daily_cap=6)
    assert _sb_buy(plan) == ["BUY_SEED", "STRAWBERRY", 12]


def test_strawberry_seed_buy_is_capped_by_the_empty_zone() -> None:
    plan = _sb_plan(empty_strawberry_tiles=3, strawberry_plant_daily_cap=6)
    assert _sb_buy(plan) == ["BUY_SEED", "STRAWBERRY", 3]


def test_strawberry_seed_buy_nets_off_seed_already_held() -> None:
    # plan_day is re-run every turn and must stay idempotent: seed bought on
    # an earlier turn of the same day has to count against the target or the
    # line would re-buy the whole stagger every turn.
    plan = _sb_plan(empty_strawberry_tiles=30, strawberry_plant_daily_cap=6, strawberry_seeds=10)
    assert _sb_buy(plan) == ["BUY_SEED", "STRAWBERRY", 2]

    full = _sb_plan(empty_strawberry_tiles=30, strawberry_plant_daily_cap=6, strawberry_seeds=12)
    assert _sb_buy(full) is None


def test_strawberry_seed_buy_is_bounded_by_the_remaining_budget() -> None:
    # Seed is $100 -- by far the most expensive on the board -- so the budget
    # bound is the real throttle on how fast the zone fills, not the daily cap.
    #
    # Two isolations keep this about the raw budget: the wheat seed line now
    # runs first and would take $240 of the $350, and the share would then
    # halve what is left. Wheat's target is pre-met and the share is opened to
    # 1.0, so the only bound left standing is the one under test.
    plan = _sb_plan(
        money=350.0,
        empty_strawberry_tiles=30,
        strawberry_plant_daily_cap=6,
        strawberry_seed_budget_share=1.0,
        wheat_seeds=24,
    )
    assert _sb_buy(plan) == ["BUY_SEED", "STRAWBERRY", 3]


def test_strawberry_seed_buy_stops_after_the_last_fully_productive_planting_day() -> None:
    # Production ticks land at planted_day + 10/12/14/16 and the last
    # end-of-day refresh runs on day 28, so day 12 is the last planting that
    # banks all four ticks through the normal shed transfer. Buying seed past
    # it converts cash into tiles that cannot finish their cycle.
    assert _sb_buy(_sb_plan(day=12, empty_strawberry_tiles=30)) is not None
    assert _sb_buy(_sb_plan(day=13, empty_strawberry_tiles=30)) is None


def test_strawberry_never_outbids_the_animal_pipeline() -> None:
    # Deliberate ordering: the animal pipeline is measured and shipped, and
    # replay evidence puts 40-69% of the strongest opponents' revenue in
    # cow/sheep products. Strawberry draws on what animals leave, so a gate
    # on the strawberry knob prices strawberry rather than pricing a
    # strawberry-funded raid on the ranch.
    # $800 funds exactly two cows and nothing else. The cows must take it and
    # the strawberry line must come away empty -- with the ordering reversed,
    # eight $100 seeds would eat the same budget and starve the ranch.
    contested = _sb_plan(
        money=800.0,
        empty_strawberry_tiles=30,
        empty_pastures=2,
        cows_owned=0,
        sheep_owned=0,
        wheat_seeds=24,
        strawberry_seed_budget_share=1.0,
    )
    assert ["BUY_ANIMAL", "COW", 2] in contested.buys  # type: ignore[attr-defined]
    assert _sb_buy(contested) is None

    # It does still get the genuine remainder, so this is a priority rather
    # than a blockade.
    # wheat_seeds pre-met throughout: the wheat line also outranks strawberry
    # since the 2026-08-19 prereg, and letting it draw here would make this
    # test pass for the wrong reason.
    leftover = _sb_plan(
        money=1000.0,
        empty_strawberry_tiles=30,
        empty_pastures=2,
        cows_owned=0,
        sheep_owned=0,
        wheat_seeds=24,
        strawberry_seed_budget_share=1.0,
    )
    assert ["BUY_ANIMAL", "COW", 2] in leftover.buys  # type: ignore[attr-defined]
    assert _sb_buy(leftover) == ["BUY_SEED", "STRAWBERRY", 2]


def test_shipped_default_buys_ne_and_sw_but_refuses_se() -> None:
    """The promoted default (3) is the gated value, not a placeholder.

    max_owned_quadrants=3 confirmed at n=64 on all four tapes (money ci_lower
    +5,991 to +7,780, margin ci_lower +5,044 (mirror) to +7,687 (metac95),
    opponent_mean_delta
    inside +/-3,000 everywhere) -- see eval/prereg/2026-08-23-max-owned-quadrants.md
    and the eval/gates/2026-08-23T21-* ledgers. SE costs $4,000 up front plus a
    measured $8,388/season of re-rented crew, because hands are daily rentals
    and hands_target scales with active_tiles.

    If someone edits MAX_OWNED_QUADRANTS without re-gating, this test must
    fail, not a live match.
    """
    for unlocked in (("NW",), ("NW", "NE")):
        plan = plan_day(
            day=12,
            money=10000.0,
            wheat_seeds=0,
            plantable_target_tiles=24,
            wheat_on_hand=0,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=unlocked,
            active_tiles=24,
        )
        assert ["BUY_LAND"] in plan.buys, unlocked

    at_the_cap = plan_day(
        day=12,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
    )
    assert not any(b == ["BUY_LAND"] for b in at_the_cap.buys)


def test_max_owned_quadrants_three_refuses_the_se_purchase() -> None:
    """M3's arm: SE costs $4,000 up front and re-rents three extra hands
    every day (hands_target scales with active_tiles, and _end_of_day empties
    farm["hands"]), so the cap has to bite at the third quadrant."""
    plan = plan_day(
        day=12,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
        max_owned_quadrants=3,
    )
    assert not any(b == ["BUY_LAND"] for b in plan.buys)


def test_max_owned_quadrants_three_still_buys_ne_and_sw() -> None:
    """The cap refuses only the quadrant that would exceed it — it is not a
    blanket land freeze."""
    for unlocked in (("NW",), ("NW", "NE")):
        plan = plan_day(
            day=12,
            money=10000.0,
            wheat_seeds=0,
            plantable_target_tiles=24,
            wheat_on_hand=0,
            goose_owned=True,
            hires_today=0,
            unlocked_quadrants=unlocked,
            active_tiles=24,
            max_owned_quadrants=3,
        )
        assert ["BUY_LAND"] in plan.buys, unlocked


def test_max_owned_quadrants_two_refuses_the_sw_purchase() -> None:
    plan = plan_day(
        day=12,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=49,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE"),
        active_tiles=49,
        max_owned_quadrants=2,
    )
    assert not any(b == ["BUY_LAND"] for b in plan.buys)


def test_max_owned_quadrants_does_not_divert_the_refused_budget() -> None:
    """A refused land purchase must not silently reappear as extra seed or
    livestock spend — the whole point of the arm is that the money is NOT
    spent, and the crew that the land would have sized is never hired."""
    capped = plan_day(
        day=12,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
        max_owned_quadrants=3,
    )
    uncapped = plan_day(
        day=12,
        money=10000.0,
        wheat_seeds=0,
        plantable_target_tiles=74,
        wheat_on_hand=0,
        goose_owned=True,
        hires_today=0,
        unlocked_quadrants=("NW", "NE", "SW"),
        active_tiles=74,
        # Must be explicit. Omitting it falls back to MAX_OWNED_QUADRANTS,
        # which is the capped value -- the two arms would then be byte-identical
        # and both assertions below would reduce to `x == x`.
        max_owned_quadrants=4,
    )
    assert ["BUY_LAND"] in uncapped.buys, "uncapped arm must actually buy SE"
    non_land = [b for b in uncapped.buys if b != ["BUY_LAND"]]
    assert capped.buys == non_land
    assert capped.hire_count == uncapped.hire_count


# --- strawberry seed line: ordering and cash sizing (prereg 2026-08-19) -------


def _wheat_buy(plan: object) -> list[object] | None:
    return next((b for b in plan.buys if b[0] == "BUY_SEED" and b[1] == "WHEAT"), None)  # type: ignore[attr-defined]


def test_wheat_seed_is_funded_before_strawberry_seed() -> None:
    # The measured blocker (prereg 2026-08-19 + AMENDMENT 1): with strawberry
    # ahead of wheat, a $100 seed line placed before a $10 one consumed the
    # whole early budget and WHEAT did not appear on the board until day 14,
    # with the days 0-13 wheat seed pool sitting at exactly 0. Wheat is the
    # early cash engine and the cheapest ground-holder per dollar; strawberry
    # is a mid-game asset that has to draw on what wheat leaves.
    #
    # $260 funds 24 wheat seeds ($240) and nothing else meaningful. Wheat must
    # take it; with the ordering reversed two $100 strawberry seeds would eat
    # $200 of the same budget and leave wheat six seeds.
    contested = _sb_plan(
        money=260.0,
        empty_strawberry_tiles=30,
        plantable_target_tiles=24,
        wheat_seeds=0,
        active_tiles=24,
    )
    assert _wheat_buy(contested) == ["BUY_SEED", "WHEAT", 24]
    assert _sb_buy(contested) is None


def test_strawberry_seed_buy_is_capped_by_a_share_of_the_remaining_budget() -> None:
    # Ordering alone does not protect the lines that come AFTER strawberry --
    # the animal feed top-up and the SW land buy. An uncapped strawberry line
    # sized to the zone still places 12 x $100 = $1,200/day of demand ahead of
    # feed, and an unfed animal is dead capital. The share caps what the line
    # may take of whatever is left when it runs, so it self-scales with the
    # game phase instead of needing a schedule.
    plan = _sb_plan(
        money=1000.0,
        empty_strawberry_tiles=30,
        strawberry_plant_daily_cap=6,
        strawberry_seed_budget_share=0.5,
        wheat_seeds=24,
    )
    assert _sb_buy(plan) == ["BUY_SEED", "STRAWBERRY", 5]

    # A share of 1.0 is the uncapped behavior, so the knob can be swept back
    # to the pre-change sizing without editing code.
    uncapped = _sb_plan(
        money=1000.0,
        empty_strawberry_tiles=30,
        strawberry_plant_daily_cap=6,
        strawberry_seed_budget_share=1.0,
        wheat_seeds=24,
    )
    assert _sb_buy(uncapped) == ["BUY_SEED", "STRAWBERRY", 10]


def test_strawberry_seed_share_never_overrides_the_stagger_or_zone_bounds() -> None:
    # The share is a third bound, not a replacement: a generous share must not
    # let the line buy past two days of the dispatcher's stagger, nor past the
    # tiles that actually exist to plant into.
    stagger_bound = _sb_plan(
        money=100_000.0,
        empty_strawberry_tiles=30,
        strawberry_plant_daily_cap=6,
        strawberry_seed_budget_share=1.0,
    )
    assert _sb_buy(stagger_bound) == ["BUY_SEED", "STRAWBERRY", 12]

    zone_bound = _sb_plan(
        money=100_000.0,
        empty_strawberry_tiles=3,
        strawberry_plant_daily_cap=6,
        strawberry_seed_budget_share=1.0,
    )
    assert _sb_buy(zone_bound) == ["BUY_SEED", "STRAWBERRY", 3]


def test_strawberry_leaves_cash_on_the_table_for_the_feed_order_behind_it() -> None:
    # The regression the share exists to prevent, asserted end to end.
    #
    # Asserting merely that the feed order is EMITTED has no teeth: the feed
    # line appends unconditionally, with no budget check of its own, so it
    # survives any amount of upstream spending and the assertion can never
    # fail. What can fail -- and what actually costs money in an episode -- is
    # the feed order being emitted against cash that is already gone, because
    # an unfeedable animal is dead capital that can never be sold. So this
    # prices the plan: the spend committed AHEAD of feed must leave enough
    # behind to pay for it.
    plan = _sb_plan(
        money=1200.0,
        empty_strawberry_tiles=30,
        strawberry_plant_daily_cap=6,
        cows_owned=4,
        animals_placed=4,
        wheat_on_hand=0,
    )
    feed = next((b for b in plan.buys if b[0] == "BUY_PRODUCT"), None)  # type: ignore[attr-defined]
    assert feed is not None, "strawberry starved the feed line"

    # Wheat's base market price. This is a TEST threshold taken from
    # docs/recon/economy.md:49, which prices feed at $25/unit as an
    # opportunity-cost baseline -- the engine's own price is dynamic and there
    # is no constant to import. It is the right order of magnitude for
    # "did the seed lines leave enough to feed the herd", which is the whole
    # question here.
    wheat_product_price = 25.0
    prices = {"WHEAT": SEED_PRICE, "MELON": MELON_SEED_PRICE, "STRAWBERRY": STRAWBERRY_SEED_PRICE}
    committed = sum(
        prices[str(b[1])] * int(b[2])  # type: ignore[index]
        for b in plan.buys  # type: ignore[attr-defined]
        if b[0] == "BUY_SEED"
    )
    feed_cost = wheat_product_price * int(feed[2])  # type: ignore[index]
    assert committed + feed_cost <= 1200.0, (
        f"seed lines committed ${committed} of $1200 and left nothing for a ${feed_cost} feed order"
    )
