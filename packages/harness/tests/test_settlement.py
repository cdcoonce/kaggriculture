"""Teeth for the settlement recorder.

Each test targets a way this instrument could return clean, plausible,
fictional numbers rather than failing loudly.
"""

from __future__ import annotations

import pytest
from harness.settlement import HIRE_KEY, LAND_KEY, Settlement, _Recorder


def _recorder_with_farms() -> tuple[_Recorder, dict, dict]:
    farm0: dict = {"money": 0.0}
    farm1: dict = {"money": 0.0}
    rec = _Recorder()
    rec.farms = [farm0, farm1]
    return rec, farm0, farm1


def test_a_rejected_commit_is_not_booked_as_a_sale() -> None:
    """The engine returns False and mutates nothing on an unfillable order.
    Recording on the CALL instead of the RETURN books rejects as revenue --
    measured at 26 of 80 EGG SELL calls worth a fictional $1,201 on one seed.
    """
    rec, farm0, _ = _recorder_with_farms()
    rec.record(True, "SELL", "WHEAT", 25.0, farm0)
    rec.record(False, "SELL", "EGG", 50.0, farm0)

    assert rec.revenue[0]["WHEAT"] == 25.0
    assert "EGG" not in rec.revenue[0]
    assert rec.units[0]["WHEAT"] == 1
    assert rec.calls == 2
    assert rec.filled == 1
    assert rec.rejected == 1


def test_rejects_would_change_the_total_if_they_were_counted() -> None:
    """Teeth on the test above: prove the reject actually carries value, so
    excluding it is a real decision and not a no-op that would pass either
    way."""
    rec, farm0, _ = _recorder_with_farms()
    rec.record(False, "SELL", "EGG", 50.0, farm0)
    assert sum(rec.revenue[0].values()) == 0.0

    counted = _Recorder()
    counted.farms = rec.farms
    counted.record(True, "SELL", "EGG", 50.0, farm0)
    assert sum(counted.revenue[0].values()) == 50.0


def test_seat_comes_from_object_identity_not_equality() -> None:
    """Two farms with identical contents must not collapse to one seat.
    Equality would silently attribute both players' sales to seat 0."""
    rec, farm0, farm1 = _recorder_with_farms()
    assert farm0 == farm1  # identical contents
    assert farm0 is not farm1

    rec.record(True, "SELL", "WHEAT", 25.0, farm0)
    rec.record(True, "SELL", "WHEAT", 30.0, farm1)

    assert rec.revenue[0]["WHEAT"] == 25.0
    assert rec.revenue[1]["WHEAT"] == 30.0


def test_an_unknown_farm_raises_rather_than_guessing() -> None:
    rec, _, _ = _recorder_with_farms()
    with pytest.raises(AssertionError, match="refusing to attribute"):
        rec.record(True, "SELL", "WHEAT", 25.0, {"money": 0.0})


def test_a_commit_before_the_market_sets_farms_raises() -> None:
    """Ordering teeth: if the _process_market wrap ever stops firing, the
    recorder must fail loudly instead of attributing to a stale list."""
    rec = _Recorder()
    assert rec.farms is None
    with pytest.raises(AssertionError, match="before _process_market"):
        rec.record(True, "SELL", "WHEAT", 25.0, {"money": 0.0})


def test_buys_land_in_spend_not_revenue() -> None:
    rec, farm0, _ = _recorder_with_farms()
    rec.record(True, "BUY_SEED", "WHEAT", 10.0, farm0)
    rec.record(True, "BUY_ANIMAL", "COW", 400.0, farm0)
    rec.record(True, "BUY_PRODUCT", "WHEAT", 26.0, farm0)

    assert rec.revenue[0] == {}
    assert rec.spend[0]["BUY_SEED:WHEAT"] == 10.0
    assert rec.spend[0]["BUY_ANIMAL:COW"] == 400.0
    assert rec.spend[0]["BUY_PRODUCT:WHEAT"] == 26.0


def test_settlement_totals_sum_the_per_item_maps() -> None:
    s = Settlement(
        seed=1,
        final_money=[100.0, 200.0],
        units={0: {"WHEAT": 2}, 1: {}},
        revenue={0: {"WHEAT": 50.0, "EGG": 25.0}, 1: {"MILK": 10.0}},
        spend={0: {"BUY_SEED:WHEAT": 20.0}, 1: {}},
    )
    assert s.revenue_total(0) == 75.0
    assert s.revenue_total(1) == 10.0
    assert s.spend_total(0) == 20.0
    # cost_side is the residual used pairwise between arms
    assert s.cost_side(0) == 100.0 - 75.0


def test_direct_paths_record_a_measured_money_decrease() -> None:
    """_do_hire and _do_buy_land bypass _commit_unit and write farm["money"]
    directly, so they are captured by differencing money across the call."""
    rec, farm0, farm1 = _recorder_with_farms()
    rec.record_direct(HIRE_KEY, farm0, 8.0)
    rec.record_direct(HIRE_KEY, farm0, 13.0)
    rec.record_direct(LAND_KEY, farm0, 4000.0)
    rec.record_direct(HIRE_KEY, farm1, 5.0)

    assert rec.spend[0][HIRE_KEY] == 21.0
    assert rec.spend[0][LAND_KEY] == 4000.0
    assert rec.hires[0] == 2
    assert rec.spend[1][HIRE_KEY] == 5.0
    assert rec.hires[1] == 1
    assert rec.revenue[0] == {}


def test_a_no_op_direct_call_records_nothing() -> None:
    """Neither engine function reports success in its return value: both
    return None whether or not they acted. A hire the farm could not afford,
    or a land buy with every quadrant owned, must not be booked."""
    rec, farm0, _ = _recorder_with_farms()
    rec.record_direct(HIRE_KEY, farm0, 0.0)
    rec.record_direct(LAND_KEY, farm0, 0.0)

    assert rec.spend[0] == {}
    assert rec.hires[0] == 0


def test_sell_is_the_only_money_inflow_in_the_engine() -> None:
    """cost_side treats its residual as pure outflow. That is only true while
    _commit_unit's SELL branch is the engine's ONLY money inflow.

    Pinned against the engine source rather than asserted in a docstring: an
    engine bump adding a subsidy, prize or interest would otherwise turn
    cost_side from a cost measure into a mixed residual with a green suite.
    """
    import inspect
    import re

    from kaggle_environments.envs.kaggriculture import kaggriculture as engine

    source = inspect.getsource(engine)
    # Every statement that increases a farm's money.
    increases = re.findall(r'\["money"\]\s*\+=\s*(\S+)', source)
    assert increases == ["price"], (
        f"engine gained a money inflow this instrument does not model: {increases}. "
        "Settlement.cost_side assumes SELL is the only inflow."
    )


def test_settlement_exposes_hire_and_land_spend() -> None:
    s = Settlement(
        seed=1,
        final_money=[100.0, 200.0],
        spend={0: {HIRE_KEY: 11501.0, LAND_KEY: 7000.0, "BUY_SEED:WHEAT": 20.0}, 1: {}},
    )
    assert s.hire_spend(0) == 11501.0
    assert s.land_spend(0) == 7000.0
    assert s.hire_spend(1) == 0.0


def test_a_real_episode_books_hire_and_land_spend_to_the_right_seat() -> None:
    """The engine wiring itself, not a hand-built recorder.

    Everything above drives ``_Recorder`` directly with fabricated farms, so
    ``play_with_settlement`` -- the spies, the seat capture and the restore --
    had no coverage at all. That is the half that produced the $8,388/season
    land attribution, and its money-differencing path is the fragile one:
    ``_do_hire`` and ``_do_buy_land`` bypass ``_commit_unit``, so spend is
    recovered as ``before - farm["money"]``. Flip that subtraction and every
    ``spent`` goes negative, ``record_direct``'s ``if spent <= 0: return``
    swallows all of them, and ``hire_spend`` reads a clean, plausible 0.0 with
    the rest of this file still green.

    Seat resolution is pinned by the opponent choice: ``zoo:pass`` never hires
    and never buys land, so seat 1 MUST be empty. If the recorder resolved
    seats by index instead of by farm object identity, the two seats would
    swap and the seat-1 assertions would fail.
    """
    from harness.settlement import play_with_settlement

    s = play_with_settlement(
        seed=663300,
        candidate="champion",
        opponent="zoo:pass",
    )

    # The candidate hires daily (hands are re-rented every morning) and buys
    # NE + SW. Both paths must book POSITIVE spend, not a swallowed negative.
    assert s.hire_spend(0) > 0.0, "hire spend swallowed -- check the sign of `before - money`"
    assert s.land_spend(0) > 0.0, "land spend swallowed -- check the sign of `before - money`"
    assert s.hires.get(0, 0) > 0

    # max_owned_quadrants=3 ships, so NE ($1,000) + SW ($2,000) and never SE.
    assert s.land_spend(0) == 3000.0

    # A passing opponent spends nothing on either path.
    assert s.hire_spend(1) == 0.0
    assert s.land_spend(1) == 0.0

    # The engine's functions must be put back, or every later test in the
    # process inherits the spies.
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine

    assert engine._do_hire.__name__ != "hire_spy"
    assert engine._commit_unit.__name__ != "cu_spy"
