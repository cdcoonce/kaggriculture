"""Typed parse of the raw observation — the only place obs keys are spelled.

The runner delivers a Struct supporting dict access; everything downstream
(planner, dispatcher, market) works from this frozen view, so their logic is
pure and unit-testable against synthetic views.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Tile = Any  # None | "LOCKED" | dict — engine tile cell


@dataclass(frozen=True)
class FarmView:
    step: int
    day: int
    hour: int
    money: float
    tiles: list[list[Tile]]
    farmer: tuple[int, int]
    hands: list[tuple[int, int]]
    seeds: dict[str, int]
    shed: dict[str, int]
    inventories: list[dict[str, int]]
    prices: dict[str, float]
    hires_today: int


def parse_obs(obs: dict[str, Any]) -> FarmView:
    step = int(obs.get("step", 0))
    me = int(obs.get("player", 0))
    farms = obs["farms"]
    farm = farms[me]
    private = obs.get("private", {}) or {}
    market = obs.get("market", {}) or {}
    farmer = farm.get("farmer", [4, 4])
    return FarmView(
        step=step,
        day=step // 24,
        hour=step % 24,
        money=float(farm.get("money", 0.0)),
        tiles=farm["tiles"],
        farmer=(int(farmer[0]), int(farmer[1])),
        hands=[(int(h[0]), int(h[1])) for h in farm.get("hands", [])],
        seeds=dict(private.get("seeds", {}) or {}),
        shed=dict(private.get("shed", {}) or {}),
        inventories=[dict(i) for i in private.get("inventories", [{}]) or [{}]],
        prices={k: float(v) for k, v in (market.get("prices", {}) or {}).items()},
        hires_today=int(farm.get("hires_today", 0)),
    )
