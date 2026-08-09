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
def melon_tiles(
    unlocked: tuple[str, ...], target: int = MELON_TILE_TARGET
) -> list[tuple[int, int]]:
    """The melon zone: the first ``target`` tiles of ``target_tiles``.

    Melon is the premium crop (seed $80 vs wheat's $10, ten days to first
    yield instead of two) so it claims the shortest hauls -- the tiles
    nearest whichever shed-access corner is closest, exactly like
    ``target_tiles``' own ordering. The remaining tiles (``target_tiles``
    minus this prefix) stay wheat's. Memoized for the same reason as
    ``target_tiles``: ``unlocked`` only changes on a BUY_LAND purchase.
    ``target`` defaults to ``MELON_TILE_TARGET`` so existing callers are
    unaffected; a policy-config override passes a different size explicitly.
    """
    return target_tiles(unlocked)[:target]


# M2a: cow + sheep targets sum to exactly the pasture zone size -- one
# animal per pasture tile (BUILD_PASTURE, then PLACE, is a one-animal-per-
# tile pipeline; there's no reason to reserve more tiles than animals we
# ever intend to buy).
COW_TARGET = 6
SHEEP_TARGET = 9
PASTURE_TILE_TARGET = COW_TARGET + SHEEP_TARGET  # 15

# Pastures are anchored to this FIXED reference frame forever, never the
# live/current ``unlocked_quadrants`` -- unlike melon_tiles (whose zone is
# deliberately allowed to grow/shift towards whatever corner is newly
# closest), a pasture position must stay stable for the entire game. Once an
# animal is PLACEd there, ``dispatch`` only recognizes it as pasture-zone by
# position membership; if a later SW/SE land purchase reshuffled
# target_tiles' nearest-shed-first ordering (it does -- a new shed-access
# corner changes every tile's "nearest open access" distance, including
# already-unlocked NW/NE tiles), any pasture tile that fell out of a
# recomputed window would silently stop receiving FEED/HARVEST/CARE forever:
# a placed animal starves and escapes with no signal at all, and a built
# empty pasture just becomes dead, permanently-invisible board space. Cow/
# sheep purchase windows (day 9/11) both close well before SW ever unlocks
# under the M2a budget order anyway, so pastures never needed to extend past
# NW+NE in the first place. (Found via the M2a solo probe: cows silently
# dropping from 4 to 2 mid-game, animals stranded unplaced in the shed at
# day 29 -- see packages/agent/tests/test_policy.py's regression test.)
PASTURE_REFERENCE_QUADRANTS: tuple[str, ...] = ("NW", "NE")


@cache
def pasture_tiles(
    unlocked: tuple[str, ...], target: int = PASTURE_TILE_TARGET
) -> list[tuple[int, int]]:
    """The pasture zone: the ``target`` tiles right after melon's.

    Same nearest-shed-first ordering as ``target_tiles``/``melon_tiles``, just
    the next window instead of the prefix -- pastures claim the second-
    shortest hauls (after melon's), well ahead of wheat's much larger, lower-
    value-per-tile share of the universe. A slice of the same list as
    ``melon_tiles`` when both are evaluated against the *same* ``unlocked``
    argument (disjoint by construction in that case); callers deriving a
    wheat-tile set should subtract both this and ``melon_tiles``. Memoized
    for the same reason as ``target_tiles``: ``unlocked`` only changes on a
    BUY_LAND purchase.

    Caveat: because live callers must pin this to ``PASTURE_REFERENCE_
    QUADRANTS`` while ``melon_tiles`` keeps tracking the *live*
    ``unlocked_quadrants`` (see that constant's docstring), the two zones can
    briefly overlap by a handful of tiles before NE actually unlocks (melon's
    NW-only-basis "8 nearest" and pasture's NW+NE-basis window are different
    orderings over the same small board). ``dispatch`` resolves any such
    overlap deterministically -- pasture wins ties in the per-tile branch --
    and the window closes the instant NE unlocks (turn 0 in every observed
    game), so this costs at most a few of melon's day-0 planting slots.

    Generic in ``unlocked`` (like ``melon_tiles``) so it stays directly
    testable against every unlock state, but callers threading this into the
    live dispatch loop MUST pass ``PASTURE_REFERENCE_QUADRANTS`` -- a fixed
    frame -- not the game's current ``unlocked_quadrants`` (see that
    constant's docstring for why passing a live value orphans tiles).
    ``target`` defaults to ``PASTURE_TILE_TARGET`` so existing callers are
    unaffected; a policy-config override passes a different size explicitly.
    """
    return target_tiles(unlocked)[MELON_TILE_TARGET : MELON_TILE_TARGET + target]


def nearest_shed_access(pos: tuple[int, int], unlocked: tuple[str, ...]) -> tuple[int, int]:
    """The closest shed-access tile among the currently-unlocked quadrants."""
    unlocked_set = set(unlocked)
    access_tiles = [tile for tile, quadrant in SHED_ACCESS.items() if quadrant in unlocked_set]

    def sort_key(tile: tuple[int, int]) -> tuple[int, int, int]:
        return (abs(tile[0] - pos[0]) + abs(tile[1] - pos[1]), tile[1], tile[0])

    return min(access_tiles, key=sort_key)
