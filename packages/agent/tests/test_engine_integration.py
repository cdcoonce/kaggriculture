"""Chassis v1 (M1 + melon satellite) against the real engine: structural
floors at day 6, compounding by day 12, egg pipeline, full-game liquidation.

Bars are behavioral floors, not tuned snapshots: day 6 checks structure (land
unlocked, crew hired, crop on the ground) rather than a cash amount, since
M1's land purchases and melon's seed line put day 6 mid-J-curve, cash-poor by
design (the old day-6 cash bar assumed a pre-M1 pace that no longer holds).
Day 12 and the full game check compounding cash instead, each calibrated to
~70% of a real observed run so the bar is a genuine regression floor without
being a brittle exact-match snapshot.
"""

from __future__ import annotations

from typing import Any

from agent.main import agent
from kaggle_environments import make


def _run(steps: int, seed: int, opponent: str = "pass") -> Any:
    env = make("kaggriculture", configuration={"seed": seed, "episodeSteps": steps})
    env.run([agent, opponent])
    return env


def _money(env: Any, player: int = 0) -> float:
    return float(env.steps[-1][0].observation["farms"][player]["money"])


def _planted_counts(env: Any, player: int = 0) -> tuple[int, int]:
    """(wheat tiles standing, melon tiles standing) in the final observation."""
    tiles = env.steps[-1][0].observation["farms"][player]["tiles"]
    wheat = sum(
        1
        for row in tiles
        for t in row
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "WHEAT"
    )
    melon = sum(
        1
        for row in tiles
        for t in row
        if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "MELON"
    )
    return wheat, melon


def test_day_six_structure() -> None:
    """Land unlocked, crew hired, crop actually on the ground -- not a cash
    snapshot (see module docstring for why day 6 is a cash trough by design).

    Observed on seed 41 at day 6 (144 steps): 3 quadrants unlocked, 9 hands,
    14 wheat + 7 melon tiles standing. Wheat's standing count is volatile
    turn to turn -- the day-0 rush cohort (~40 tiles by day 3-4) matures and
    gets harvested around day 4-5 (max_yield_day 4), so the snapshot dips
    hard right before day 6 even though the pipeline is healthy (a cumulative
    count of PLANT actions issued over the same window is 62). The floors
    below sit with margin under the post-harvest dip, not the pre-harvest
    peak. Melon can't be harvested before day 10 (first_yield_day), so its
    standing count is monotonic through day 6 and is the cleaner signal that
    the satellite crop is actually landing plants, not just buying seed.
    """
    env = _run(steps=144, seed=41)
    obs = env.steps[-1][0].observation
    farm = obs["farms"][0]

    assert len(farm.get("unlocked_quadrants", ["NW"])) >= 3
    assert len(farm.get("hands", [])) >= 6
    assert [s.status for s in env.steps[-1]] == ["DONE", "DONE"]

    wheat, melon = _planted_counts(env)
    assert wheat + melon >= 15  # observed 21 (14 wheat + 7 melon); ~70% floor
    assert melon >= 5  # observed 7; proves the melon satellite is landing plants, not just buying


def test_day_twelve_compounds() -> None:
    # Observed on seed 41 at day 12 (288 steps): money = 5169.0. Chassis-v1
    # (pre-M1) pace was ~6.3k here, but M1's land purchases and melon's $80
    # seed line both draw down cash earlier in exchange for a bigger payoff
    # later (see test_full_game_beats_pass_and_liquidates) -- floor at ~70%
    # of the observed number rather than the old pre-M1 pace.
    env = _run(steps=288, seed=41)
    assert _money(env) > 3600.0


def test_goose_eggs_are_sold_within_eleven_days() -> None:
    env = _run(steps=264, seed=42)
    sold_egg = any(
        any(o[0] == "SELL" and o[1] == "EGG" for o in (step[0].action or {}).get("market", []))
        for step in env.steps[1:]
    )
    assert sold_egg


def test_full_game_beats_pass_and_liquidates() -> None:
    # Observed on seed 43 at game end (720 steps): money = 36100.0, well
    # above the ~25k expected-with-melon mark -- melon is converting, not
    # just eating budget. Floor at ~70% of the observed number.
    env = _run(steps=720, seed=43)
    assert [s.status for s in env.steps[-1]] == ["DONE", "DONE"]
    assert _money(env) > 25000.0

    shed = env.steps[-1][0].observation["private"]["shed"]
    residue = sum(n for item, n in shed.items() if item in ("WHEAT", "EGG", "FERTILIZER", "MELON"))
    assert residue <= 4  # feed reserve at most; unsold produce is $0 at game end
