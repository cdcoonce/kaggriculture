"""Board-geometry behavior: the target-tile universe and shed-access routing
as land unlocks widen the farmable board.
"""

from __future__ import annotations

from agent.constants import (
    COOP_TILE,
    COW_TARGET,
    MELON_TILE_TARGET,
    PASTURE_TILE_TARGET,
    SHEEP_TARGET,
    melon_tiles,
    nearest_shed_access,
    pasture_tiles,
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
# (6 + 9 = 15) exactly fill the reserved zone: one animal per pasture tile.


def test_pasture_targets_sum_to_the_pasture_tile_target() -> None:
    assert COW_TARGET + SHEEP_TARGET == PASTURE_TILE_TARGET
    assert PASTURE_TILE_TARGET == 15


def test_pasture_tiles_are_the_fifteen_after_melons_prefix() -> None:
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
