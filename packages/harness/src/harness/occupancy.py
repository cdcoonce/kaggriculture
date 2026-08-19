"""Standing-crop occupancy census, read off a finished episode.

Why this exists: no instrument in the repo could measure standing crops.
``tools/recon-scripts/strawberry_labor.py``'s ``alive_by_day`` filters
``tile["crop"] == "STRAWBERRY"``, and the shipped champion sets
``strawberry_tile_target = 0`` -- so on the shipped agent it reports zero on
every day of every episode. Four sessions of notes reasoned about a
whole-farm occupancy series that nothing in the tree computed.

The census samples the board at each day's FIRST turn. That choice matters
and is not arbitrary: mid-day the board is churning (a tile harvested at hour
9 and replanted at hour 11 is bare in between), so an hour-0 snapshot is the
only sample point at which "standing" is a stable daily quantity comparable
across days and across agents.

SEAT HAZARD: ``farms`` is broadcast onto both seats' observations, but
per-player state (``private``: seeds, shed, inventories) is NOT. A census
wired to the wrong field returns a clean and entirely fictional series. Every
read here goes through ``_seat_observation`` for that reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TURNS_PER_DAY = 24


@dataclass(frozen=True)
class DayCensus:
    """One day's board state for one seat, sampled at the day's first turn."""

    day: int
    standing: int
    by_crop: dict[str, int] = field(default_factory=dict)
    # Tiles a PLANT task could legally target: empty ground, no weed, no
    # structure. The denominator of the replant fill rate -- without it a low
    # planting count cannot be told from a board with nowhere left to plant.
    bare: int = 0
    # Standing tiles bucketed by ``day - planted_day``. The shape is the
    # discriminator: a synchronized cohort is PEAKED with the peak walking one
    # bin per day, a true steady state is FLAT across bins. Occupancy that
    # oscillates under a peaked histogram is the cohort ripening together, not
    # a replant that arrived late.
    ages: dict[int, int] = field(default_factory=dict)
    # Per-seat seed pools, read from ``private``. Distinguishes "did not
    # replant" from "could not replant".
    seeds: dict[str, int] = field(default_factory=dict)


def _get(obj: Any, key: str) -> Any:
    """Read a field off either a dict or an attribute-style object.

    ``env.steps`` entries are dicts under kaggle_environments but attribute
    objects under some replay paths, and this module is used against both.
    """
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _seat_observation(step: Any, seat: int) -> Any:
    """The observation as THIS seat saw it."""
    if seat >= len(step):
        return None
    return _get(step[seat], "observation")


def _board(farm: Any, day: int) -> tuple[dict[str, int], int, dict[int, int]]:
    """(standing crops by name, bare tiles, age histogram) for one farm.

    A tile carries a ``crop`` key only while a plant is alive on it: the
    engine writes it in ``_new_plant`` and replaces the whole tile with
    ``None`` (non-ongoing crop, on harvest) or ``{"kind": "WEED"}`` (death by
    thirst or decay) otherwise. So "has a crop key" is exactly "is standing",
    and a ``None`` tile is exactly the plantable ground -- a WEED is NOT
    plantable, it needs a DIG first, which is why it is excluded from ``bare``
    rather than folded in as empty.
    """
    counts: dict[str, int] = {}
    ages: dict[int, int] = {}
    bare = 0
    for column in farm.get("tiles") or []:
        for tile in column:
            if tile is None:
                bare += 1
                continue
            if not isinstance(tile, dict):
                continue  # 'LOCKED' -- unowned ground, neither standing nor bare
            crop = tile.get("crop")
            if crop is None:
                continue
            counts[crop] = counts.get(crop, 0) + 1
            planted = tile.get("planted_day")
            if planted is not None:
                age = day - int(planted)
                ages[age] = ages.get(age, 0) + 1
    return counts, bare, ages


def census(env: Any, seat: int, turns_per_day: int = TURNS_PER_DAY) -> dict[int, DayCensus]:
    """Per-day standing-crop census for ``seat`` over a finished episode."""
    out: dict[int, DayCensus] = {}
    for i, step in enumerate(env.steps):
        if i % turns_per_day:
            continue
        obs = _seat_observation(step, seat)
        if obs is None:
            continue
        farms = _get(obs, "farms")
        if not farms or seat >= len(farms):
            continue
        day = i // turns_per_day
        by_crop, bare, ages = _board(farms[seat], day)
        # `private` is the seat's own; reading it off another seat's
        # observation silently yields that seat's pools instead.
        private = _get(obs, "private") or {}
        seeds = {k: int(v or 0) for k, v in (private.get("seeds") or {}).items() if v}
        out[day] = DayCensus(
            day=day,
            standing=sum(by_crop.values()),
            by_crop=by_crop,
            bare=bare,
            ages=ages,
            seeds=seeds,
        )
    return out
