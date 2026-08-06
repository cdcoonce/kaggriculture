"""Obs-parsing behavior: the FarmView field mapping and its optional-key defaults."""

from __future__ import annotations

from typing import Any

from agent.view import parse_obs


def _obs(*, unlocked_quadrants: list[str] | None = None) -> dict[str, Any]:
    tiles = [[None if x < 5 and y < 5 else "LOCKED" for x in range(10)] for y in range(10)]
    farm: dict[str, Any] = {
        "money": 100.0,
        "tiles": tiles,
        "farmer": [4, 4],
        "hands": [],
        "hires_today": 0,
    }
    if unlocked_quadrants is not None:
        farm["unlocked_quadrants"] = unlocked_quadrants
    return {"step": 0, "player": 0, "farms": [farm], "private": {}, "market": {}}


def test_unlocked_quadrants_parsed_from_obs() -> None:
    view = parse_obs(_obs(unlocked_quadrants=["NW", "NE"]))
    assert view.unlocked_quadrants == ("NW", "NE")


def test_unlocked_quadrants_defaults_to_nw_when_key_missing() -> None:
    view = parse_obs(_obs(unlocked_quadrants=None))
    assert view.unlocked_quadrants == ("NW",)
