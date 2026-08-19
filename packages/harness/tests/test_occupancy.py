"""Tests for the standing-crop occupancy census.

The census exists because no instrument in the repo could read the thing four
sessions of notes were arguing about. `strawberry_labor.py`'s `alive_by_day`
counts `tile["crop"] == "STRAWBERRY"` only, and the shipped champion sets
`strawberry_tile_target = 0` -- so at the shipped config it is identically
zero on all thirty days and cannot see the wheat oscillation at all.

The failure mode these tests are shaped against is NOT "the arithmetic is
wrong". It is "the census silently reads the wrong seat". `private` is
per-player and is not broadcast onto `farms[seat]`, so a census wired to the
wrong field returns a clean, plausible, entirely fictional series -- which is
exactly how this project has shipped false [verified] claims before. Hence
`test_seat_is_honoured`: it asserts an ASYMMETRY that only a correctly-seated
census can produce.
"""

import pytest
from harness.episodes import resolve_agent
from harness.occupancy import census

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def episode():
    """One champion-vs-pass episode, shared across the tests in this module.

    `zoo:pass` is the point: it never plants anything, so seat 1's standing
    count is known a priori to be zero on every day. That known-zero is the
    fixed point the seat test hangs on.
    """
    from kaggle_environments import make

    env = make("kaggriculture", configuration={"seed": 661000})
    env.run([resolve_agent("champion"), resolve_agent("zoo:pass")])
    return env


def test_seat_is_honoured(episode):
    """A census read off the wrong seat -- or off a broadcast field -- cannot
    produce this asymmetry.

    Seat 1 is `zoo:pass`, which submits PASS every turn and therefore never
    plants. Seat 0 is the champion, which plants tens of wheat tiles. If the
    census reads `farms[seat]` for a per-player field, or ignores `seat`
    entirely, both seats come back identical and this goes red.
    """
    seat0 = census(episode, seat=0)
    seat1 = census(episode, seat=1)

    assert all(day.standing == 0 for day in seat1.values()), (
        "zoo:pass never plants, so seat 1 must be empty on every day; "
        "a non-zero count here means the census is reading seat 0's board"
    )
    assert max(day.standing for day in seat0.values()) > 20, (
        "the champion runs a wheat rush and peaks well above 20 standing "
        "tiles; a zero or near-zero peak means the census found nothing"
    )


def test_seed_stock_is_read_per_seat(episode):
    """Seeds live in ``private``, which is NOT broadcast between seats.

    This is the read that gives ``_seat_observation`` its teeth: ``farms`` is
    broadcast, so indexing it by seat is enough there, but ``private`` only
    ever appears on its owner's observation. A census that reads seat 1's
    private state off seat 0's observation gets seat 0's seed pool -- a clean,
    plausible, wrong number. ``zoo:pass`` never buys a seed, so seat 1's pool
    is known-zero for the whole episode and pins that mistake.
    """
    seat0 = census(episode, seat=0)
    seat1 = census(episode, seat=1)

    assert all(day.seeds == {} for day in seat1.values()), (
        "zoo:pass never issues BUY_SEED, so seat 1 holds no seeds on any day; "
        "a non-empty pool here means private state was read off the wrong seat"
    )
    assert any(day.seeds.get("WHEAT", 0) > 0 for day in seat0.values()), (
        "the champion buys wheat seed every day it can afford to"
    )


def test_bare_ground_and_ages_are_internally_consistent(episode):
    """The two fields the replant question actually turns on.

    ``bare`` is the ground a PLANT task could be emitted for; ``ages`` is the
    age histogram whose shape separates a synchronized cohort (peaked, and the
    peak walks one bin per day) from a steady state (flat across bins). Both
    are meaningless if they disagree with ``standing``, so pin that first.
    """
    days = census(episode, seat=0)

    for day in days.values():
        assert sum(day.ages.values()) == day.standing, (
            f"day {day.day}: age histogram sums to {sum(day.ages.values())} "
            f"but standing is {day.standing}"
        )
        assert day.bare >= 0

    # A 10x10 board cannot hold more than 100 tiles of anything.
    assert all(day.standing + day.bare <= 100 for day in days.values())
