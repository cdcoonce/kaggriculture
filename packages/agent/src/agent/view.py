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
    unlocked_quadrants: tuple[str, ...]
    farmer: tuple[int, int]
    hands: list[tuple[int, int]]
    seeds: dict[str, int]
    shed: dict[str, int]
    inventories: list[dict[str, int]]
    prices: dict[str, float]
    hires_today: int
    opponent_tiles: list[list[Tile]] | None = None
    opponent_unlocked_quadrants: tuple[str, ...] | None = None


_PRESSURE_PRODUCT = {
    ("crop", "MELON"): "MELON",
    ("crop", "STRAWBERRY"): "STRAWBERRY",
    ("animal", "COW"): "MILK",
    ("animal", "SHEEP"): "WOOL",
}
_PUBLIC_QUADRANTS = frozenset({"NW", "NE", "SW", "SE"})


def clone_pressure_products(view: FarmView) -> frozenset[str]:
    """Premium goods with harvestable public yield on a near-clone opponent."""
    opponent_tiles = view.opponent_tiles
    opponent_quadrants = view.opponent_unlocked_quadrants
    if opponent_tiles is None or opponent_quadrants is None:
        return frozenset()
    if not all(isinstance(row, list) for row in opponent_tiles):
        return frozenset()
    if (
        not all(isinstance(quadrant, str) for quadrant in opponent_quadrants)
        or not set(opponent_quadrants) <= _PUBLIC_QUADRANTS
        or len(set(opponent_quadrants)) != len(opponent_quadrants)
    ):
        return frozenset()
    if len(view.unlocked_quadrants) != len(opponent_quadrants):
        return frozenset()

    categories = (
        ("crop", "WHEAT"),
        ("crop", "MELON"),
        ("crop", "STRAWBERRY"),
        ("animal", "COW"),
        ("animal", "SHEEP"),
    )

    def counts(tiles: list[list[Tile]]) -> dict[tuple[str, str], int]:
        return {
            category: sum(
                1
                for row in tiles
                for tile in row
                if isinstance(tile, dict) and tile.get(category[0]) == category[1]
            )
            for category in categories
        }

    ours = counts(view.tiles)
    theirs = counts(opponent_tiles)
    if sum(abs(ours[category] - theirs[category]) for category in categories) > 4:
        return frozenset()

    pressured: set[str] = set()
    for row in opponent_tiles:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            raw_yield = tile.get("yield_units", 0)
            if isinstance(raw_yield, bool) or not isinstance(raw_yield, (int, float)):
                return frozenset()
            if raw_yield <= 0:
                continue
            for key in ("crop", "animal"):
                value = tile.get(key)
                if not isinstance(value, str):
                    continue
                product = _PRESSURE_PRODUCT.get((key, value))
                if product is not None:
                    pressured.add(product)
    return frozenset(pressured)


def parse_obs(obs: dict[str, Any]) -> FarmView:
    step = int(obs.get("step", 0))
    me = int(obs.get("player", 0))
    farms = obs["farms"]
    farm = farms[me]
    opponent = farms[1 - me] if len(farms) == 2 and isinstance(farms[1 - me], dict) else None
    private = obs.get("private", {}) or {}
    market = obs.get("market", {}) or {}
    farmer = farm.get("farmer", [4, 4])
    return FarmView(
        step=step,
        day=step // 24,
        hour=step % 24,
        money=float(farm.get("money", 0.0)),
        tiles=farm["tiles"],
        unlocked_quadrants=tuple(farm.get("unlocked_quadrants", ("NW",))),
        farmer=(int(farmer[0]), int(farmer[1])),
        hands=[(int(h[0]), int(h[1])) for h in farm.get("hands", [])],
        seeds=dict(private.get("seeds", {}) or {}),
        shed=dict(private.get("shed", {}) or {}),
        inventories=[dict(i) for i in private.get("inventories", [{}]) or [{}]],
        prices={k: float(v) for k, v in (market.get("prices", {}) or {}).items()},
        hires_today=int(farm.get("hires_today", 0)),
        opponent_tiles=(opponent.get("tiles") if opponent is not None else None),
        opponent_unlocked_quadrants=(
            tuple(opponent.get("unlocked_quadrants", ()))
            if opponent is not None
            and isinstance(opponent.get("tiles"), list)
            and isinstance(opponent.get("unlocked_quadrants"), (list, tuple))
            else None
        ),
    )
