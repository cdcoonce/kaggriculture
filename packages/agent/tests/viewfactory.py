"""Synthetic FarmView builder for dispatcher/policy tests."""

from __future__ import annotations

from typing import Any

from agent.view import FarmView

Tile = Any


def empty_tiles() -> list[list[Tile]]:
    """10x10 board: NW quadrant open, everything else locked (fresh farm)."""
    return [
        [None if x < 5 and y < 5 else "LOCKED" for x in range(10)]  # noqa: B023
        for y in range(10)
    ]


def make_view(
    *,
    step: int = 30,
    farmer: tuple[int, int] = (4, 4),
    hands: list[tuple[int, int]] | None = None,
    tiles: list[list[Tile]] | None = None,
    seeds: int = 0,
    shed: dict[str, int] | None = None,
    inventories: list[dict[str, int]] | None = None,
    prices: dict[str, float] | None = None,
    money: float = 3000.0,
    hires_today: int = 0,
) -> FarmView:
    hands = hands or []
    n_units = 1 + len(hands)
    inv = inventories or [{} for _ in range(n_units)]
    while len(inv) < n_units:
        inv.append({})
    return FarmView(
        step=step,
        day=step // 24,
        hour=step % 24,
        money=money,
        tiles=tiles if tiles is not None else empty_tiles(),
        farmer=farmer,
        hands=hands,
        seeds={"WHEAT": seeds},
        shed=shed or {},
        inventories=inv,
        prices=prices or {"WHEAT": 25.0, "EGG": 50.0, "FERTILIZER": 100.0},
        hires_today=hires_today,
    )


def plant(
    *,
    crop: str = "WHEAT",
    planted_day: int = 0,
    watered_today: bool = False,
    yield_units: int = 1,
) -> dict[str, Any]:
    return {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": planted_day,
        "watered_today": watered_today,
        "consecutive_unwatered": 1,
        "yield_units": yield_units,
        "fertilized_until_day": -1,
    }


def goose_tile(
    *,
    fed_today: bool = False,
    cared_today: bool = False,
    yield_units: int = 0,
    fertilizer_available: bool = False,
) -> dict[str, Any]:
    return {
        "kind": "COOP",
        "animal": "GOOSE",
        "placed_day": 0,
        "yield_units": yield_units,
        "consecutive_unfed": 0,
        "fed_today": fed_today,
        "cared_today": cared_today,
        "fertilizer_available": fertilizer_available,
        "pending_care_bonus": 0,
    }
