"""Tests for the crop x quadrant x day census.

The census exists because nothing in the repo could answer "which quadrant is
this crop growing in". ``harness.occupancy._board`` iterates tiles and counts
crops, but it throws the (x, y) away before anything reaches ``DayCensus`` --
so a prior investigation's per-quadrant figures could not be reproduced,
because no committed instrument computed them.

The failure mode these tests are shaped against is NOT "the arithmetic is
wrong". It is the pair of silent mis-wirings that both return a clean,
plausible, entirely fictional table:

* TRANSPOSITION. The engine board is ``tiles[y][x]``. NW and NE differ only in
  x; NW and SW differ only in y. So reading the outer index as x swaps NE with
  SW and changes nothing else -- the totals still add up, every quadrant name
  is still spelled right. ``TestOrientation`` pins a tile that lands in NE
  under the engine's layout and in SW under a transposed read.
* SEAT. ``farms`` is broadcast onto both seats' observations, so the ONLY
  thing selecting a seat's board out of it is the ``farms[seat]`` index.
  ``TestSeat`` builds two seats whose boards disagree on crop, on quadrant and
  on unlock state, so no wrong-seat wiring can survive it.

Both fakes are hand-built: these are unit tests over a known board, not an
episode run, so they stay in the fast set.
"""

from __future__ import annotations

from typing import Any

import pytest
from agent.constants import QUADRANTS
from harness.crop_quadrant import census, crop_quadrant_tile_days, unlock_days

TURNS_PER_DAY = 24

Tile = Any


def _quadrant_of(x: int, y: int) -> str:
    for name, (x_range, y_range) in QUADRANTS.items():
        if x in x_range and y in y_range:
            return name
    raise ValueError(f"tile ({x}, {y}) is outside every quadrant")


def _plant(crop: str, planted_day: int = 0) -> dict[str, Any]:
    """A tile as the engine's ``_new_plant`` leaves it: it carries ``crop``."""
    return {"kind": "PLANT", "crop": crop, "planted_day": planted_day}


def _weed() -> dict[str, Any]:
    """A dead tile. Owned ground, but not plantable -- it needs a DIG first."""
    return {"kind": "WEED"}


def _board(
    unlocked: tuple[str, ...] = ("NW",),
    crops: dict[tuple[int, int], dict[str, Any]] | None = None,
    weeds: tuple[tuple[int, int], ...] = (),
) -> list[list[Tile]]:
    """A 10x10 board stored the way the engine stores it: ``tiles[y][x]``.

    ``crops`` and ``weeds`` are keyed by (x, y) in the engine's own coordinate
    order, and the two ``tiles[y][x]`` assignments below are the only place
    that translates to storage order. ``TestOrientation`` asserts on the raw
    structure this returns before it asserts on any census output, so a
    transposed builder cannot quietly make a transposed census look right.
    """
    open_quadrants = set(unlocked)
    tiles: list[list[Tile]] = [
        [None if _quadrant_of(x, y) in open_quadrants else "LOCKED" for x in range(10)]
        for y in range(10)
    ]
    for (x, y), tile in (crops or {}).items():
        tiles[y][x] = tile
    for x, y in weeds:
        tiles[y][x] = _weed()
    return tiles


def _episode(day_boards: list[list[list[list[Tile]]]], seats: int = 2) -> list[Any]:
    """A steps list where ``day_boards[day][seat]`` is that seat's hour-0 board.

    Every other hour of the day carries a fully locked board, so a census that
    samples any turn but the day's first reads an empty, unowned farm instead.
    That is ``harness.occupancy``'s first-turn convention and its justification:
    mid-day the board churns, and hour 0 is the only sample point at which
    "standing" is a stable daily quantity.

    ``farms`` is BROADCAST -- both seats' observations carry the identical
    list, exactly as the engine emits it -- so the ``farms[seat]`` index is the
    only thing that can pick the right board out of it.
    """
    midday = [_board(unlocked=()) for _ in range(seats)]
    steps: list[Any] = []
    for boards in day_boards:
        for hour in range(TURNS_PER_DAY):
            active = boards if hour == 0 else midday
            obs = {"farms": [{"tiles": tiles} for tiles in active]}
            steps.append([{"observation": obs} for _ in range(seats)])
    return steps


def _wheat_in_nw(n: int) -> dict[tuple[int, int], dict[str, Any]]:
    """``n`` wheat tiles in NW, in reading order."""
    coords = [(x, y) for y in range(5) for x in range(5)][:n]
    return {coord: _plant("WHEAT") for coord in coords}


@pytest.fixture
def mixed_board_steps() -> list[Any]:
    """One day, all four quadrants owned, six known crops at known coordinates."""
    board = _board(
        unlocked=("NW", "NE", "SW", "SE"),
        crops={
            (1, 1): _plant("WHEAT"),
            (2, 3): _plant("WHEAT"),
            (6, 1): _plant("WHEAT"),
            (7, 4): _plant("MELON"),
            (1, 7): _plant("MELON"),
            (8, 8): _plant("STRAWBERRY"),
        },
    )
    return _episode([[board, _board(unlocked=())]])


class TestCensus:
    def test_crops_are_bucketed_by_quadrant(self, mixed_board_steps):
        """Two wheat in NW, one in NE; melon split NE/SW; one strawberry in SE."""
        days = census(mixed_board_steps, seat=0)

        assert len(days) == 1
        assert days[0].day == 0
        assert days[0].by_crop_quadrant == {
            "WHEAT": {"NW": 2, "NE": 1},
            "MELON": {"NE": 1, "SW": 1},
            "STRAWBERRY": {"SE": 1},
        }

    def test_unlocked_is_nw_first_then_land_order(self, mixed_board_steps):
        """Not alphabetical and not set order: NW, then the BUY_LAND sequence."""
        days = census(mixed_board_steps, seat=0)

        assert days[0].unlocked == ("NW", "NE", "SW", "SE")

    def test_bare_counts_the_ground_a_plant_could_target(self, mixed_board_steps):
        """25 tiles a quadrant, minus whatever is standing on them."""
        days = census(mixed_board_steps, seat=0)

        assert days[0].bare_by_quadrant == {"NW": 23, "NE": 23, "SW": 24, "SE": 24}

    def test_weeds_are_not_bare_and_locked_ground_is_neither(self):
        """``occupancy``'s rule, unchanged, now per quadrant.

        A ``None`` tile is plantable ground. A WEED is NOT -- it needs a DIG
        first, so folding it in as empty would inflate the replant denominator.
        A ``'LOCKED'`` tile is not this seat's ground at all: neither standing
        nor bare.
        """
        board = _board(
            unlocked=("NW", "NE"),
            crops={(2, 2): _plant("WHEAT")},
            weeds=((0, 0), (1, 0), (5, 0)),
        )
        days = census(_episode([[board, _board(unlocked=())]]), seat=0)

        assert days[0].bare_by_quadrant == {"NW": 22, "NE": 24}
        assert days[0].by_crop_quadrant == {"WHEAT": {"NW": 1}}

    def test_samples_the_first_turn_of_each_day(self):
        """Hours 1-23 of every day are a locked, empty board in this fixture.

        A census that read any other turn would report an unowned farm on
        every day, so this pins the sampling convention rather than assuming it.
        """
        day0 = _board(unlocked=("NW",), crops=_wheat_in_nw(3))
        day1 = _board(unlocked=("NW",), crops=_wheat_in_nw(5))
        days = census(_episode([[day0, day0], [day1, day1]]), seat=0)

        assert [d.day for d in days] == [0, 1]
        assert [d.by_crop_quadrant["WHEAT"]["NW"] for d in days] == [3, 5]

    def test_a_seat_beyond_the_board_yields_no_days(self, mixed_board_steps):
        """Guard, mirroring ``occupancy``: a two-farm game has no seat 2."""
        assert census(mixed_board_steps, seat=2) == []


class TestOrientation:
    """TEETH: a transposed read swaps NE with SW and nothing else.

    ``agent.constants``' module docstring records the engine-verified layout:
    ``tiles[y][x]``, outer index y. A census that walks the outer index as x
    still produces a table that sums correctly and names real quadrants -- it
    just puts every NE crop in SW and every SW crop in NE. Nothing downstream
    could detect that, which is why it is pinned here.
    """

    COORD = (7, 2)  # x >= 5, y < 5 -> NE upright; (2, 7) -> SW transposed

    def test_fixture_stores_the_tile_at_tiles_y_x(self):
        """Pin the BUILDER first, so the assertion below cannot go vacuous.

        If ``_board`` itself transposed, a transposed census would agree with
        it and the teeth check below would pass while measuring nothing.
        """
        x, y = self.COORD
        tiles = _board(unlocked=("NW", "NE"), crops={self.COORD: _plant("WHEAT")})

        assert tiles[y][x] == _plant("WHEAT"), "the builder must store tiles[y][x]"
        assert tiles[x][y] == "LOCKED", "the transposed slot is unowned SW ground"

    def test_crop_at_x7_y2_is_attributed_to_ne_not_sw(self):
        """The whole point of the module. Fails loudly on a transposed read."""
        board = _board(unlocked=("NW", "NE"), crops={self.COORD: _plant("WHEAT")})
        days = census(_episode([[board, _board(unlocked=())]]), seat=0)

        assert days[0].by_crop_quadrant == {"WHEAT": {"NE": 1}}, (
            "(x=7, y=2) is NE under the engine's tiles[y][x] layout; an 'SW' "
            "here means the census read the outer index as x"
        )

    def test_unlock_state_is_not_transposed_either(self):
        """NE owned, SW locked -- a transposed read reports exactly the opposite."""
        board = _board(unlocked=("NW", "NE"))
        days = census(_episode([[board, _board(unlocked=())]]), seat=0)

        assert days[0].unlocked == ("NW", "NE")
        assert "SW" not in days[0].bare_by_quadrant


class TestSeat:
    """TEETH: ``farms`` is broadcast, so ``farms[seat]`` is the only selector.

    Same hazard ``occupancy``'s SEAT HAZARD note describes: both seats see the
    identical broadcast list, so a census wired to the wrong index returns the
    other player's farm as though it were yours -- clean, plausible, fictional.
    The two boards here disagree on crop, on quadrant AND on unlock state, so
    no wrong-seat wiring produces either answer by accident.
    """

    @pytest.fixture
    def steps(self) -> list[Any]:
        seat0 = _board(unlocked=("NW",), crops=_wheat_in_nw(3))
        seat1 = _board(
            unlocked=("NW", "NE"),
            crops={(6, 1): _plant("MELON"), (7, 3): _plant("MELON")},
        )
        return _episode([[seat0, seat1]])

    def test_seat_one_gets_seat_ones_board(self, steps):
        days = census(steps, seat=1)

        assert days[0].by_crop_quadrant == {"MELON": {"NE": 2}}
        assert days[0].unlocked == ("NW", "NE")

    def test_seat_zero_gets_seat_zeros_board(self, steps):
        days = census(steps, seat=0)

        assert days[0].by_crop_quadrant == {"WHEAT": {"NW": 3}}
        assert days[0].unlocked == ("NW",)


class TestUnlockDays:
    @pytest.fixture
    def steps(self) -> list[Any]:
        """NW from the start, NE bought on day 1, SW on day 2, SE never."""
        locked = _board(unlocked=())
        return _episode(
            [
                [_board(unlocked=("NW",)), locked],
                [_board(unlocked=("NW", "NE")), locked],
                [_board(unlocked=("NW", "NE", "SW")), locked],
                [_board(unlocked=("NW", "NE", "SW")), locked],
            ]
        )

    def test_reports_the_first_day_each_quadrant_is_open(self, steps):
        assert unlock_days(census(steps, seat=0)) == {"NW": 0, "NE": 1, "SW": 2}

    def test_a_quadrant_never_bought_is_absent(self, steps):
        """Absent, not ``-1`` or ``None``: there is no first day."""
        assert "SE" not in unlock_days(census(steps, seat=0))

    def test_locked_string_tiles_are_not_unlocked(self):
        board = _board(unlocked=("NW",))
        days = census(_episode([[board, _board(unlocked=())]]), seat=0)

        assert days[0].unlocked == ("NW",)

    def test_weed_and_bare_tiles_both_count_as_unlocked(self):
        """Ownership is "not the ``'LOCKED'`` sentinel", not "has open ground".

        A quadrant whose every tile is a WEED is still bought and paid for; a
        census that inferred ownership from plantable ground would report it
        locked and mis-date the purchase.
        """
        all_of_ne = tuple((x, y) for x in range(5, 10) for y in range(5))
        board = _board(unlocked=("NW", "NE"), weeds=all_of_ne)
        days = census(_episode([[board, _board(unlocked=())]]), seat=0)

        assert days[0].unlocked == ("NW", "NE")
        assert days[0].bare_by_quadrant == {"NW": 25, "NE": 0}


class TestCropQuadrantTileDays:
    @pytest.fixture
    def censuses(self) -> list[Any]:
        """Five days: NW wheat grows 1, 2, 3, 4, 5; one NE melon on day 2."""
        locked = _board(unlocked=())
        boards = []
        for day in range(5):
            crops = _wheat_in_nw(day + 1)
            if day == 2:
                crops[(6, 1)] = _plant("MELON")
            boards.append([_board(unlocked=("NW", "NE"), crops=crops), locked])
        return census(_episode(boards), seat=0)

    def test_sums_only_days_inside_the_window(self, censuses):
        """Inclusive on both ends: days 1, 2, 3 -> 2 + 3 + 4."""
        assert crop_quadrant_tile_days(censuses, day_from=1, day_to=3) == {
            "WHEAT": {"NW": 9},
            "MELON": {"NE": 1},
        }

    def test_a_wider_window_picks_up_the_excluded_days(self, censuses):
        assert crop_quadrant_tile_days(censuses, day_from=0, day_to=4) == {
            "WHEAT": {"NW": 15},
            "MELON": {"NE": 1},
        }

    def test_a_window_past_the_episode_is_empty(self, censuses):
        assert crop_quadrant_tile_days(censuses, day_from=10, day_to=28) == {}

    def test_default_window_is_days_10_to_28_inclusive(self):
        """Matches ``occupancy.report``'s days 10-28 summary window.

        Thirty days, one wheat tile a day, so the sum IS the day count: 19
        days from 10 to 28 inclusive. An exclusive upper bound would read 18
        and an off-by-one lower bound 20.
        """
        locked = _board(unlocked=())
        boards = [[_board(unlocked=("NW",), crops=_wheat_in_nw(1)), locked] for _ in range(30)]

        assert crop_quadrant_tile_days(census(_episode(boards), seat=0)) == {"WHEAT": {"NW": 19}}
