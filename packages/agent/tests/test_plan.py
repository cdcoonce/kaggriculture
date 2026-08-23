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
    )
    too_early = plan_day(day=11, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] not in too_early.buys

    on_time = plan_day(day=12, **kwargs)  # type: ignore[arg-type]
    assert ["BUY_LAND"] in on_time.buys


def test_se_land_requires_larger_reserve_than_other_quadrants() -> None:
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
    plan = _sb_plan(empty_strawberry_tiles=30, strawberry_plant_daily_cap=6)
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
    plan = _sb_plan(money=350.0, empty_strawberry_tiles=30, strawberry_plant_daily_cap=6)
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
    )
    assert ["BUY_ANIMAL", "COW", 2] in contested.buys  # type: ignore[attr-defined]
    assert _sb_buy(contested) is None

    # It does still get the genuine remainder, so this is a priority rather
    # than a blockade.
    leftover = _sb_plan(
        money=1000.0,
        empty_strawberry_tiles=30,
        empty_pastures=2,
        cows_owned=0,
        sheep_owned=0,
    )
    assert ["BUY_ANIMAL", "COW", 2] in leftover.buys  # type: ignore[attr-defined]
    assert _sb_buy(leftover) == ["BUY_SEED", "STRAWBERRY", 2]


def test_max_owned_quadrants_default_still_buys_every_quadrant() -> None:
    """The default must reproduce today's behavior exactly: a cap of 4 can
    never bind on a 4-quadrant board, so each of NE/SW/SE still fires."""
    for unlocked, day in ((("NW",), 0), (("NW", "NE"), 12), (("NW", "NE", "SW"), 12)):
        plan = plan_day(
            day=day,
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
    )
    non_land = [b for b in uncapped.buys if b != ["BUY_LAND"]]
    assert capped.buys == non_land
    assert capped.hire_count == uncapped.hire_count
