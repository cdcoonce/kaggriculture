"""Board geometry and role constants the chassis relies on.

Engine-verified (kaggle_environments 1.32.4): board 10x10, tiles[y][x], NW
quadrant x<5,y<5 always unlocked; shed-access tiles are the four center tiles,
of which only (4,4) is unlocked without land purchases; farmer respawns at
(4,4) and hands are evicted at every day boundary. BUY_LAND unlocks NE, SW,
SE in that fixed order at 1000/2000/4000, each purchase opening its own
shed-access corner alongside its quadrant.
"""

from __future__ import annotations

from functools import cache

BOARD_SIZE = 10
SHED_TILE = (4, 4)  # the only unlocked shed-access tile pre-NE
COOP_TILE = (3, 4)  # adjacent to the shed corner; reserved for the goose

#: Quadrant name -> (x tiles, y tiles); matches the engine's NWSE layout.
QUADRANTS: dict[str, tuple[range, range]] = {
    "NW": (range(0, 5), range(0, 5)),
    "NE": (range(5, BOARD_SIZE), range(0, 5)),
    "SW": (range(0, 5), range(5, BOARD_SIZE)),
    "SE": (range(5, BOARD_SIZE), range(5, BOARD_SIZE)),
}

#: Shed-access tile -> the quadrant that must be unlocked to stand on it.
SHED_ACCESS: dict[tuple[int, int], str] = {
    (4, 4): "NW",
    (5, 4): "NE",
    (4, 5): "SW",
    (5, 5): "SE",
}

#: Fixed BUY_LAND unlock order and per-quadrant price (engine LAND_ORDER/LAND_PRICES).
LAND_ORDER: tuple[str, ...] = ("NE", "SW", "SE")
LAND_PRICES: dict[str, int] = {"NE": 1000, "SW": 2000, "SE": 4000}


@cache
def target_tiles(unlocked: tuple[str, ...]) -> list[tuple[int, int]]:
    """Wheat tiles across every unlocked quadrant, nearest-open-shed first.

    Sorted by (distance to the nearest unlocked shed-access tile, y, x), so a
    freshly-bought quadrant's tiles interleave with the rest by true walking
    distance instead of being appended as a separate block. For ``("NW",)``
    alone this is exactly the legacy single-quadrant ordering. Memoized:
    ``unlocked`` only changes on a BUY_LAND purchase (at most three times a
    game), so re-sorting the up-to-99-tile universe every turn is wasted work.
    """
    unlocked_set = set(unlocked)
    access_tiles = [tile for tile, quadrant in SHED_ACCESS.items() if quadrant in unlocked_set]

    tiles: list[tuple[int, int]] = []
    for quadrant, (x_range, y_range) in QUADRANTS.items():
        if quadrant not in unlocked_set:
            continue
        for y in y_range:
            for x in x_range:
                if (x, y) != COOP_TILE:
                    tiles.append((x, y))

    def sort_key(tile: tuple[int, int]) -> tuple[int, int, int]:
        dist = min(abs(tile[0] - ax) + abs(tile[1] - ay) for ax, ay in access_tiles)
        return (dist, tile[1], tile[0])

    tiles.sort(key=sort_key)
    return tiles


MELON_TILE_TARGET = 8  # size of the melon zone carved out of the target-tile universe


@cache
def melon_tiles(unlocked: tuple[str, ...]) -> list[tuple[int, int]]:
    """The melon zone: the first ``MELON_TILE_TARGET`` tiles of ``target_tiles``.

    Melon is the premium crop (seed $80 vs wheat's $10, ten days to first
    yield instead of two) so it claims the shortest hauls -- the tiles
    nearest whichever shed-access corner is closest, exactly like
    ``target_tiles``' own ordering. The remaining tiles (``target_tiles``
    minus this prefix) stay wheat's. Memoized for the same reason as
    ``target_tiles``: ``unlocked`` only changes on a BUY_LAND purchase.
    """
    return target_tiles(unlocked)[:MELON_TILE_TARGET]


def nearest_shed_access(pos: tuple[int, int], unlocked: tuple[str, ...]) -> tuple[int, int]:
    """The closest shed-access tile among the currently-unlocked quadrants."""
    unlocked_set = set(unlocked)
    access_tiles = [tile for tile, quadrant in SHED_ACCESS.items() if quadrant in unlocked_set]

    def sort_key(tile: tuple[int, int]) -> tuple[int, int, int]:
        return (abs(tile[0] - pos[0]) + abs(tile[1] - pos[1]), tile[1], tile[0])

    return min(access_tiles, key=sort_key)
