"""How many of an episode's shop draws an occupancy-moving arm can disturb.

Why this exists: kaggriculture#82. The engine's ``_end_of_day`` seeds one rng
per day, runs both players' ``_spawn_weeds`` -- which calls ``rng.random()``
**only for ``None`` (bare) tiles** -- and then draws the day's shop with
``rng.choice(sorted(SHOPS))`` **from that same stream**. So the number of
draws consumed before the shop draw is a function of each player's bare-tile
count, and the town roster is downstream of our own occupancy. Any arm that
changes how much bare ground we leave reshuffles which shops unlock, which
moves realized prices for BOTH seats on identical sale volumes.

The issue states that as a blanket "every gate in ``eval/gates/`` is
affected." That is an overstatement, and this module computes the real bound:

- The draw fires only when ``next_day % townShopUnlockInterval == 0`` AND
  ``len(unlocked_shops) < MAX_SHOP_INSTANCES``, from an empty start. In a
  default 30-day game that is **exactly 8 draws**, decided at end-of-day
  2/5/8/11/14/17/20/23, and **none after end-of-day 23**.
- The rng is rebuilt every day (``random.Random((seed * 1_000_003) ^ day)``),
  so the coupling is **within-day, not cumulative**: a draw depends only on
  that day's combined bare-tile count, never on history.

Therefore affectedness is per-arm and measurable. An arm whose combined
bare-tile count first differs on draw-day D can disturb only the draws from D
onward -- and an arm that changes occupancy only after end-of-day 23 has ZERO
roster coupling and is genuinely paired.

SAMPLING HAZARD: this censuses the LAST turn of each draw-day, not the first.
``harness.occupancy.census`` deliberately samples each day's first turn (a
mid-day board is churning), but the rng is consumed during end-of-day
processing, so an hour-0 read measures a board that is one full day of
planting and harvesting away from the one ``_spawn_weeds`` actually saw.

WHAT THIS CANNOT DO: it cannot be used to "recover" pairing by comparing only
the seeds whose rosters matched. The roster is a **mediator** -- it is caused
by the treatment -- so conditioning on it selects the seeds where the arm
happened not to express its occupancy effect, which selects against the
treatment. The effect can only be averaged over. ``roster_identical`` is
reported for description, never as a filter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_UNLOCK_INTERVAL = 3  # engine: townShopUnlockInterval
DEFAULT_MAX_INSTANCES = 8  # engine: MAX_SHOP_INSTANCES
DEFAULT_DAYS = 30
TURNS_PER_DAY = 24


@dataclass(frozen=True)
class CouplingProfile:
    """One arm's end-of-day bare-tile census plus its final shop roster."""

    # draw-day -> COMBINED bare tiles across both farms. Combined, because
    # _spawn_weeds runs for both players off the one rng before the shop draw,
    # so it is the sum that positions the cursor -- an arm can desync the
    # stream through the opponent's board as well as its own.
    bare_by_day: dict[int, int]
    roster: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CouplingResult:
    """The per-arm bound for one seed."""

    first_divergent_day: int | None
    coupled_draws: int
    total_draws: int
    roster_identical: bool


def draw_days(
    n_days: int = DEFAULT_DAYS,
    unlock_interval: int = DEFAULT_UNLOCK_INTERVAL,
    max_instances: int = DEFAULT_MAX_INSTANCES,
) -> list[int]:
    """End-of-day indices on which the engine draws a shop.

    Mirrors ``_end_of_day``: ``next_day = day + 1``, draw when
    ``next_day % unlock_interval == 0`` and the roster is still under
    ``max_instances``. Returned values are the day whose END-OF-DAY
    processing makes the draw -- the new shop is visible from ``day + 1``.

    The engine clamps the interval with ``max(1, ...)``; this raises instead,
    because silently clamping would hide a caller that computed one wrongly.
    """
    if unlock_interval < 1:
        raise ValueError(f"unlock_interval must be >= 1, got {unlock_interval}")

    days: list[int] = []
    roster = 0
    for day in range(n_days):
        if roster >= max_instances:
            break
        if (day + 1) % unlock_interval == 0:
            days.append(day)
            roster += 1
    return days


def _combined_bare(step: Any) -> int:
    """Bare (``None``) tiles summed over both farms at one step.

    ``None`` is exactly ``_spawn_weeds``'s predicate. A ``WEED`` tile is a
    dict and a ``LOCKED`` tile is a bare string, so neither is counted --
    matching the engine, which draws for neither.
    """
    observation = step[0]["observation"] if isinstance(step[0], dict) else step[0].observation
    farms = observation["farms"] if isinstance(observation, dict) else observation.farms
    return sum(
        1
        for farm in farms
        for column in (farm.get("tiles") or [])
        for tile in column
        if tile is None
    )


def profile(
    env: Any,
    unlock_interval: int = DEFAULT_UNLOCK_INTERVAL,
    max_instances: int = DEFAULT_MAX_INSTANCES,
    turns_per_day: int = TURNS_PER_DAY,
) -> CouplingProfile:
    """Census a finished episode at the last turn of every draw-day."""
    n_days = max(1, len(env.steps) // turns_per_day)
    days = draw_days(n_days, unlock_interval, max_instances)

    bare_by_day: dict[int, int] = {}
    for day in days:
        index = min((day + 1) * turns_per_day - 1, len(env.steps) - 1)
        bare_by_day[day] = _combined_bare(env.steps[index])

    final = env.steps[-1][0]
    observation = final["observation"] if isinstance(final, dict) else final.observation
    town = (observation["town"] if isinstance(observation, dict) else observation.town) or {}
    return CouplingProfile(bare_by_day=bare_by_day, roster=list(town.get("unlocked_shops", [])))


def compare_profiles(a: CouplingProfile, b: CouplingProfile) -> CouplingResult:
    """Bound how many draws two arms' streams could have disagreed on.

    Counts every draw from the first divergence onward, including any that
    coincidentally re-match: once the two streams have consumed a different
    number of ``random()`` calls on a day, that day's cursor differs, and a
    later day agreeing on bare-tile count does not undo an earlier day's
    different draw. The count is a bound on disturbed draws, not an estimate
    of how many actually changed value -- with 8 shop types drawn with
    replacement, a desynced draw still lands on the same shop about 1 time in 8.
    """
    if sorted(a.bare_by_day) != sorted(b.bare_by_day):
        raise ValueError(
            "profiles were sampled on different draw-day schedules: "
            f"{sorted(a.bare_by_day)} vs {sorted(b.bare_by_day)}"
        )

    days = sorted(a.bare_by_day)
    first = next((d for d in days if a.bare_by_day[d] != b.bare_by_day[d]), None)
    coupled = 0 if first is None else len(days) - days.index(first)

    return CouplingResult(
        first_divergent_day=first,
        coupled_draws=coupled,
        total_draws=len(days),
        # Descriptive only -- never a filter. See the module docstring.
        roster_identical=sorted(a.roster) == sorted(b.roster),
    )
