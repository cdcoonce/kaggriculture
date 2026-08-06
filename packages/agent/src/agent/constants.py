"""Board geometry and role constants the chassis relies on.

Engine-verified (kaggle_environments 1.32.4): board 10x10, tiles[y][x], NW
quadrant x<5,y<5 always unlocked; shed-access tiles are the four center tiles,
of which only (4,4) is unlocked without land purchases; farmer respawns at
(4,4) and hands are evicted at every day boundary.
"""

from __future__ import annotations

BOARD_SIZE = 10
SHED_TILE = (4, 4)  # the only unlocked shed-access tile pre-NE
COOP_TILE = (3, 4)  # adjacent to the shed corner; reserved for the goose


def _target_order() -> list[tuple[int, int]]:
    tiles = [(x, y) for x in range(5) for y in range(5) if (x, y) != COOP_TILE]
    tiles.sort(key=lambda t: (abs(t[0] - SHED_TILE[0]) + abs(t[1] - SHED_TILE[1]), t[1], t[0]))
    return tiles


#: Wheat tiles in deterministic work-priority order (nearest the shed first).
TARGET_TILES: list[tuple[int, int]] = _target_order()
