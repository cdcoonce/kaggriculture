"""Crop x quadrant x day census, read off a finished episode.

Why this exists: ``harness.occupancy`` can say how many wheat tiles were
standing on day 17, but not WHERE. ``occupancy._board`` iterates the tiles and
counts crops, and it discards the (x, y) before anything reaches ``DayCensus``
-- so no instrument in this repo could answer "which quadrant is each crop
growing in", and none recorded when each quadrant was actually bought. A prior
investigation produced per-quadrant figures that could not be reproduced,
because nothing committed computed them. This module computes them.

Like ``occupancy``, the census samples the board at each day's FIRST turn, and
for the same reason: mid-day the board is churning (a tile harvested at hour 9
and replanted at hour 11 is bare in between), so an hour-0 snapshot is the only
sample point at which "standing" is a stable daily quantity comparable across
days and across agents.

ORIENTATION HAZARD: the engine board is ``tiles[y][x]`` -- the OUTER index is
y (``agent.constants``' module docstring, engine-verified). ``occupancy._board``
calls its outer loop variable ``column``, which is misleading, but it only ever
counts, so orientation could not change its answer. Here it changes every
answer: NW and NE differ only in x, NW and SW differ only in y, so reading the
outer index as x SWAPS NE with SW and returns a table that still sums correctly
and still names real quadrants. See ``_board`` below.

SEAT HAZARD: ``farms`` is broadcast onto both seats' observations, so the
``farms[seat]`` index is the only thing selecting whose board is measured. A
census wired to the wrong index reports the opponent's farm as though it were
yours -- clean, plausible, fictional. Every read here goes through
``_seat_observation`` for the same reason ``occupancy`` does.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from agent.constants import LAND_ORDER, QUADRANTS

from harness.occupancy import TURNS_PER_DAY, _get, _seat_observation

#: Canonical quadrant order: NW (always owned) first, then the engine's fixed
#: BUY_LAND unlock sequence. Reporting order everywhere in this module, so a
#: series reads in the order the quadrants are actually acquired rather than
#: alphabetically or in whatever order a set happened to iterate.
QUADRANT_ORDER: tuple[str, ...] = ("NW", *LAND_ORDER)

#: (x, y) -> quadrant name, precomputed from ``agent.constants.QUADRANTS``.
#: Built from the constants rather than from an ``x < 5`` literal so a board
#: geometry change lands here automatically instead of silently disagreeing.
_QUADRANT_OF: dict[tuple[int, int], str] = {
    (x, y): name for name, (x_range, y_range) in QUADRANTS.items() for x in x_range for y in y_range
}


@dataclass(frozen=True)
class DayQuadrantCensus:
    """One day's board for one seat, bucketed by quadrant, at the day's first turn."""

    day: int
    # Quadrants this seat OWNS at this sample, in ``QUADRANT_ORDER``. Derived
    # from the tiles themselves (a ``'LOCKED'`` tile is unowned ground) rather
    # than from ``farm["unlocked_quadrants"]``, so the unlock series and the
    # crop series are read off the same array and cannot disagree.
    unlocked: tuple[str, ...] = ()
    # crop name -> quadrant -> standing tiles. Sparse: a crop that is nowhere
    # is absent, and a quadrant holding none of that crop is absent from its
    # inner dict.
    by_crop_quadrant: dict[str, dict[str, int]] = field(default_factory=dict)
    # quadrant -> tiles a PLANT could legally target: empty ground, no weed,
    # no structure. NOT sparse -- every unlocked quadrant gets an entry, zero
    # included. This is the denominator of the per-quadrant replant fill rate,
    # and a denominator that vanishes when it hits zero is a division trap;
    # "owned and full" and "not owned" must not collapse to the same absence.
    bare_by_quadrant: dict[str, int] = field(default_factory=dict)


def _board(farm: Any) -> tuple[dict[str, dict[str, int]], dict[str, int], tuple[str, ...]]:
    """(crop -> quadrant -> standing, quadrant -> bare, unlocked quadrants).

    ORIENTATION -- the load-bearing detail of this module. The engine stores
    the board as ``tiles[y][x]``: the OUTER index is y, the inner is x. Hence
    ``for y, row`` then ``for x, tile``, and NOT the reverse. NW and NE differ
    only in x and NW and SW differ only in y, so walking the outer index as x
    swaps NE with SW while leaving NW and SE where they are -- the totals still
    add up, every quadrant name is still spelled correctly, and nothing
    downstream can tell. ``TestOrientation`` in the test module pins a tile
    that lands in NE upright and in SW transposed.

    The tile rules are ``occupancy._board``'s, unchanged. A tile carries a
    ``crop`` key only while a plant is alive on it: the engine writes it in
    ``_new_plant`` and replaces the whole tile with ``None`` (non-ongoing crop,
    on harvest) or ``{"kind": "WEED"}`` (death by thirst or decay) otherwise.
    So "has a crop key" is exactly "is standing", and a ``None`` tile is
    exactly the plantable ground -- a WEED is NOT plantable, it needs a DIG
    first, which is why it is excluded from bare rather than folded in as
    empty. What is new here is the third return value: ``'LOCKED'`` is the
    engine's sentinel for ground this seat has not bought, so any tile that is
    NOT that sentinel proves the quadrant is owned.
    """
    by_crop: dict[str, dict[str, int]] = {}
    bare: dict[str, int] = {}
    unlocked: set[str] = set()

    for y, row in enumerate(_get(farm, "tiles") or []):
        for x, tile in enumerate(row):
            quadrant = _QUADRANT_OF.get((x, y))
            if quadrant is None:
                continue  # off-board: a ragged or resized board, not ours to attribute
            if tile is not None and not isinstance(tile, dict):
                continue  # 'LOCKED' -- unowned ground, neither standing nor bare
            # A None or dict tile is ground this seat owns: the engine only
            # leaves the 'LOCKED' sentinel there while the quadrant is unbought.
            unlocked.add(quadrant)
            bare.setdefault(quadrant, 0)
            if tile is None:
                bare[quadrant] += 1
                continue
            crop = tile.get("crop")
            if crop is None:
                continue  # WEED / PASTURE / COOP: owned and occupied, not a standing crop
            counts = by_crop.setdefault(crop, {})
            counts[quadrant] = counts.get(quadrant, 0) + 1

    return by_crop, bare, tuple(q for q in QUADRANT_ORDER if q in unlocked)


def census(
    env_steps: Any, seat: int, turns_per_day: int = TURNS_PER_DAY
) -> list[DayQuadrantCensus]:
    """Per-day crop x quadrant census for ``seat``, in ascending day order.

    Takes the steps list itself (``env.steps``) rather than the env, so a
    replay loaded from JSON can be censused without reconstructing an
    environment. Days whose observation is missing or whose ``farms`` does not
    reach ``seat`` are skipped rather than faked, so a truncated episode
    shortens the series instead of inventing empty boards in it.
    """
    out: list[DayQuadrantCensus] = []
    for i, step in enumerate(env_steps):
        if i % turns_per_day:
            continue
        obs = _seat_observation(step, seat)
        if obs is None:
            continue
        farms = _get(obs, "farms")
        if not farms or seat >= len(farms):
            continue
        # `farms` is broadcast onto both seats' observations, so this index --
        # not the observation it was read from -- is what selects the seat.
        by_crop_quadrant, bare_by_quadrant, unlocked = _board(farms[seat])
        out.append(
            DayQuadrantCensus(
                day=i // turns_per_day,
                unlocked=unlocked,
                by_crop_quadrant=by_crop_quadrant,
                bare_by_quadrant=bare_by_quadrant,
            )
        )
    return out


def unlock_days(censuses: Iterable[DayQuadrantCensus]) -> dict[str, int]:
    """Quadrant -> the first day at which it reads as unlocked, in QUADRANT_ORDER.

    A quadrant never bought is ABSENT from the result, not mapped to a
    sentinel: there is no first day, and a ``-1`` or ``None`` in this dict
    would sort and arithmetic like a real day. Sorted by day rather than
    trusting input order, so a concatenated or re-ordered series still dates
    each purchase correctly.
    """
    first: dict[str, int] = {}
    for day_census in sorted(censuses, key=lambda c: c.day):
        for quadrant in day_census.unlocked:
            first.setdefault(quadrant, day_census.day)
    return {q: first[q] for q in QUADRANT_ORDER if q in first}


def crop_quadrant_tile_days(
    censuses: Iterable[DayQuadrantCensus], day_from: int = 10, day_to: int = 28
) -> dict[str, dict[str, int]]:
    """Crop -> quadrant -> tile-days summed over the INCLUSIVE window.

    One tile standing for one day is one tile-day, so this is the area under
    the per-quadrant occupancy curve: it separates "a lot of tiles briefly"
    from "a few tiles all season", which a peak or a mean cannot.

    The default window is days 10-28, matching ``occupancy.report``'s summary
    window, so a per-quadrant figure and a whole-farm figure quoted together
    cover the same days. Both ends are inclusive, as they are there: day 10 is
    past the opening ramp, and day 28 stops short of the final-day sell-off.
    """
    out: dict[str, dict[str, int]] = {}
    for day_census in censuses:
        if not day_from <= day_census.day <= day_to:
            continue
        for crop, per_quadrant in day_census.by_crop_quadrant.items():
            totals = out.setdefault(crop, {})
            for quadrant, standing in per_quadrant.items():
                totals[quadrant] = totals.get(quadrant, 0) + standing
    return out
