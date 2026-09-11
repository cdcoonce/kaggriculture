"""Board-geometry behavior: the target-tile universe and shed-access routing
as land unlocks widen the farmable board.
"""

from __future__ import annotations

from agent.constants import (
    COOP_TILE,
    COW_TARGET,
    MELON_TILE_TARGET,
    PASTURE_REFERENCE_QUADRANTS,
    PASTURE_TILE_TARGET,
    SHEEP_TARGET,
    STRAWBERRY_REFERENCE_QUADRANTS,
    melon_tiles,
    nearest_shed_access,
    pasture_tiles,
    strawberry_tiles,
    strawberry_tiles_for_frame,
    target_tiles,
)


def test_nw_only_matches_legacy_single_quadrant_ordering() -> None:
    # Independently re-derive the pre-M1a ordering (distance to (4, 4), then
    # y, then x) rather than importing it, so this actually proves the new
    # generalized sort collapses to the old one instead of testing itself.
    coop = (3, 4)
    shed = (4, 4)
    expected = [(x, y) for x in range(5) for y in range(5) if (x, y) != coop]
    expected.sort(key=lambda t: (abs(t[0] - shed[0]) + abs(t[1] - shed[1]), t[1], t[0]))
    assert target_tiles(("NW",)) == expected


def test_nw_ne_unlocked_has_49_tiles_sorted_by_nearest_of_two_access_points() -> None:
    tiles = target_tiles(("NW", "NE"))
    assert len(tiles) == 49
    assert COOP_TILE not in tiles

    access = [(4, 4), (5, 4)]
    expected = sorted(
        tiles,
        key=lambda t: (
            min(abs(t[0] - ax) + abs(t[1] - ay) for ax, ay in access),
            t[1],
            t[0],
        ),
    )
    assert tiles == expected


def test_all_quadrants_unlocked_has_99_tiles_coop_excluded() -> None:
    tiles = target_tiles(("NW", "NE", "SW", "SE"))
    assert len(tiles) == 99
    assert len(set(tiles)) == 99  # no duplicates across quadrant boundaries
    assert COOP_TILE not in tiles


def test_nearest_shed_access_prefers_the_closer_unlocked_corner() -> None:
    far_se = (8, 8)
    assert nearest_shed_access(far_se, ("NW", "NE", "SW", "SE")) == (5, 5)
    assert nearest_shed_access(far_se, ("NW",)) == (4, 4)


def test_nearest_shed_access_tie_break_prefers_lower_y_then_lower_x() -> None:
    # (5, 5) is equidistant (1) from (5, 4) and (4, 5); the spec's y-then-x
    # tie-break must prefer (5, 4) (y=4) over (4, 5) (y=5).
    assert nearest_shed_access((5, 5), ("NW", "NE", "SW")) == (5, 4)


def test_melon_tiles_are_the_first_eight_of_the_target_universe() -> None:
    unlocked = ("NW",)
    assert melon_tiles(unlocked) == target_tiles(unlocked)[:MELON_TILE_TARGET]
    assert len(melon_tiles(unlocked)) == MELON_TILE_TARGET


def test_melon_tiles_are_nearest_shed_first_across_multiple_quadrants() -> None:
    # Same nearest-shed-first ordering as target_tiles, just truncated: the
    # melon zone widens toward whichever new corner is closest as land opens.
    unlocked = ("NW", "NE")
    assert melon_tiles(unlocked) == target_tiles(unlocked)[:MELON_TILE_TARGET]


def test_melon_tiles_disjoint_from_the_rest_of_the_target_universe() -> None:
    unlocked = ("NW", "NE", "SW", "SE")
    tiles = target_tiles(unlocked)
    melons = set(melon_tiles(unlocked))
    assert len(melons) == MELON_TILE_TARGET
    assert melons <= set(tiles)
    # Every melon tile is a prefix element; nothing from the tail leaks in.
    assert melons == set(tiles[:MELON_TILE_TARGET])


# --- Pasture zone ----------------------------------------------------------
#
# M2a: the pasture zone is the next-nearest ring after melon's prefix -- same
# nearest-shed-first universe, just a different slice. cow + sheep targets
# (6 + 4 = 10) exactly fill the reserved zone: one animal per pasture tile.


def test_pasture_targets_sum_to_the_pasture_tile_target() -> None:
    assert COW_TARGET + SHEEP_TARGET == PASTURE_TILE_TARGET
    assert PASTURE_TILE_TARGET == 10


def test_pasture_tiles_are_the_ten_after_melons_prefix() -> None:
    unlocked = ("NW", "NE")
    tiles = target_tiles(unlocked)
    expected = tiles[MELON_TILE_TARGET : MELON_TILE_TARGET + PASTURE_TILE_TARGET]
    assert pasture_tiles(unlocked) == expected
    assert len(pasture_tiles(unlocked)) == PASTURE_TILE_TARGET


def test_pasture_tiles_are_nearest_shed_first_across_multiple_quadrants() -> None:
    # Same nearest-shed-first ordering as target_tiles/melon_tiles, just a
    # different window: the pasture ring widens toward whichever new corner
    # is closest as land opens, exactly like melon's prefix does.
    unlocked = ("NW", "NE", "SW")
    assert (
        pasture_tiles(unlocked)
        == target_tiles(unlocked)[MELON_TILE_TARGET : MELON_TILE_TARGET + PASTURE_TILE_TARGET]
    )


def test_pasture_tiles_disjoint_from_melon_and_the_rest_of_the_universe() -> None:
    unlocked = ("NW", "NE", "SW", "SE")
    tiles = target_tiles(unlocked)
    melons = set(melon_tiles(unlocked))
    pastures = set(pasture_tiles(unlocked))
    assert len(pastures) == PASTURE_TILE_TARGET
    assert pastures <= set(tiles)
    assert pastures.isdisjoint(melons)
    # Every pasture tile is drawn from the prefix immediately after melon's;
    # nothing from further down the tail leaks in.
    assert pastures == set(tiles[MELON_TILE_TARGET : MELON_TILE_TARGET + PASTURE_TILE_TARGET])


def test_wheat_universe_excludes_both_melon_and_pasture_zones() -> None:
    # The wheat tiles a caller derives (target_tiles minus melon minus
    # pasture) must partition the full universe with no overlap and no gaps.
    unlocked = ("NW", "NE", "SW", "SE")
    tiles = target_tiles(unlocked)
    melons = set(melon_tiles(unlocked))
    pastures = set(pasture_tiles(unlocked))
    wheat = tiles[MELON_TILE_TARGET + PASTURE_TILE_TARGET :]
    assert set(wheat).isdisjoint(melons)
    assert set(wheat).isdisjoint(pastures)
    assert set(wheat) | melons | pastures == set(tiles)
    assert len(wheat) + len(melons) + len(pastures) == len(tiles)


# --- Strawberry zone: arbitrary frames (kaggriculture strawberry_frame_
# quadrants) -----------------------------------------------------------
#
# strawberry_tiles takes a FIXED positional slice (target_tiles(frame)
# [18:18+target]), assuming melon + pasture already fill exactly the frame's
# first 18 tiles. That assumption is specific to STRAWBERRY_REFERENCE_
# QUADRANTS: melon tracks the LIVE unlocked_quadrants, so for any other
# frame (e.g. a zone parked on SW, away from melon/pasture's NW+NE homes)
# there is no reason the frame's own first 18 tiles would be melon/pasture
# at all. strawberry_tiles_for_frame instead filters target_tiles(frame) by
# the ACTUAL melon_set/pasture_set and takes the first `target` survivors --
# correct for any frame, at the cost of needing those two sets as arguments.


def test_strawberry_tiles_for_frame_sw_target_25_is_all_of_sw_no_nw_ne_tile() -> None:
    zone = strawberry_tiles_for_frame(("SW",), 25, frozenset(), frozenset())
    assert set(zone) == set(target_tiles(("SW",)))
    assert len(zone) == 25
    assert not (set(zone) & set(target_tiles(("NW", "NE"))))


def test_strawberry_tiles_for_frame_sw_target_20_is_first_20_in_target_tiles_order() -> None:
    zone = strawberry_tiles_for_frame(("SW",), 20, frozenset(), frozenset())
    assert zone == target_tiles(("SW",))[:20]


def test_strawberry_tiles_for_frame_skips_melon_and_pasture_tiles() -> None:
    # The reason this function takes melon_set/pasture_set explicitly instead
    # of assuming a fixed offset: once SW unlocks, melon_tiles (live-tracked)
    # claims some of SW's own nearest tiles (SW's shed-access tile ties NW's
    # and NE's for "distance 0" the instant SW unlocks -- see the mechanism
    # in test_the_general_formula_disagrees_with_the_default_frame_formula_
    # once_sw_unlocks below). A frame that shares ground with melon/pasture
    # must not double-book it.
    frame = ("SW",)
    claimed = frozenset(target_tiles(frame)[:3])
    zone = strawberry_tiles_for_frame(frame, 5, claimed, frozenset())
    assert not (set(zone) & claimed)
    assert len(zone) == 5
    assert zone == [t for t in target_tiles(frame) if t not in claimed][:5]


# --- Strawberry zone: the default frame keeps its OWN formula --------------
#
# policy.decide special-cases STRAWBERRY_REFERENCE_QUADRANTS to keep calling
# strawberry_tiles (the fixed positional slice) rather than
# strawberry_tiles_for_frame, because the two formulas are NOT
# interchangeable at that frame -- proven below, not assumed.

_UNLOCK_STATES_THE_AGENT_CAN_REACH = [
    ("NW",),
    ("NW", "NE"),
    ("NW", "NE", "SW"),
    ("NW", "NE", "SE"),
    ("NW", "NE", "SW", "SE"),
]


def test_the_general_formula_disagrees_with_the_default_frame_formula_once_sw_unlocks() -> None:
    """melon_tiles tracks the LIVE unlocked_quadrants; STRAWBERRY_REFERENCE_
    QUADRANTS/PASTURE_REFERENCE_QUADRANTS are fixed at ("NW", "NE"). The two
    only coincide when live unlocked_quadrants is exactly ("NW", "NE") -- on
    turn 0 (only NW live) and on every turn from SW's purchase on, melon's
    zone stops being a clean prefix of the fixed frame's own ordering (SW's
    shed-access tile (4, 5) ties NW's/NE's for distance 0 in target_tiles the
    instant SW unlocks), and strawberry_tiles_for_frame's "first N
    non-melon/non-pasture tiles" then disagrees with strawberry_tiles'
    "tiles 18..18+N". This is the empirical answer to "does the new formula
    equal the old one for the default frame" -- no, not in general -- and it
    is why policy.decide keeps two code paths instead of one.
    """
    disagreements: list[tuple[tuple[str, ...], int]] = []
    for unlocked in _UNLOCK_STATES_THE_AGENT_CAN_REACH:
        melon_set = frozenset(melon_tiles(unlocked, target=MELON_TILE_TARGET))
        pasture_set = frozenset(
            pasture_tiles(PASTURE_REFERENCE_QUADRANTS, target=PASTURE_TILE_TARGET)
        )
        for target in range(32):
            old = (
                frozenset(strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=target))
                - melon_set
                - pasture_set
            )
            new = (
                frozenset(
                    strawberry_tiles_for_frame(
                        STRAWBERRY_REFERENCE_QUADRANTS, target, melon_set, pasture_set
                    )
                )
                - melon_set
                - pasture_set
            )
            if old != new:
                disagreements.append((unlocked, target))

    assert disagreements, (
        "expected the two formulas to disagree somewhere -- if this now holds "
        "everywhere, policy.decide no longer needs to special-case the default frame"
    )
    # The one state where they are provably forced to agree: live
    # unlocked_quadrants exactly matches the fixed frame the formulas share,
    # so melon's zone and the frame's own first 8 tiles coincide exactly.
    assert not [d for d in disagreements if d[0] == ("NW", "NE")], (
        "the two formulas diverged even though the live state matched the fixed "
        "frame -- that should be impossible"
    )
