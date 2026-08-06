"""Daily-planner behavior: the Plan A opening and its cutoffs.

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
    )
    assert ["BUY_SEED", "WHEAT", 10] in plan.buys
