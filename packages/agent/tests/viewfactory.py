"""Synthetic FarmView builder for dispatcher/policy tests."""

from __future__ import annotations

from typing import Any

from agent.constants import QUADRANTS
from agent.view import FarmView

Tile = Any


def _quadrant_of(x: int, y: int) -> str:
    for name, (x_range, y_range) in QUADRANTS.items():
        if x in x_range and y in y_range:
            return name
    raise ValueError(f"tile ({x}, {y}) is outside every quadrant")


def empty_tiles(unlocked_quadrants: tuple[str, ...] = ("NW",)) -> list[list[Tile]]:
    """10x10 board: unlocked quadrants open, everything else locked."""
    unlocked = set(unlocked_quadrants)
    return [
        [None if _quadrant_of(x, y) in unlocked else "LOCKED" for x in range(10)]  # noqa: B023
        for y in range(10)
    ]


def make_view(
    *,
    step: int = 30,
    farmer: tuple[int, int] = (4, 4),
    hands: list[tuple[int, int]] | None = None,
    tiles: list[list[Tile]] | None = None,
    seeds: int = 0,
    melon_seeds: int = 0,
    strawberry_seeds: int = 0,
    shed: dict[str, int] | None = None,
    inventories: list[dict[str, int]] | None = None,
    prices: dict[str, float] | None = None,
    money: float = 3000.0,
    hires_today: int = 0,
    unlocked_quadrants: tuple[str, ...] = ("NW",),
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
        tiles=tiles if tiles is not None else empty_tiles(unlocked_quadrants),
        unlocked_quadrants=unlocked_quadrants,
        farmer=farmer,
        hands=hands,
        seeds={"WHEAT": seeds, "MELON": melon_seeds, "STRAWBERRY": strawberry_seeds},
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
    fertilized_until_day: int = -1,
    consecutive_unwatered: int = 1,
    max_lifespan_step: int = -1,
) -> dict[str, Any]:
    return {
        "kind": "PLANT",
        "crop": crop,
        "planted_day": planted_day,
        "watered_today": watered_today,
        "consecutive_unwatered": consecutive_unwatered,
        "yield_units": yield_units,
        "fertilized_until_day": fertilized_until_day,
        # -1 (the engine's own convention for "no cap yet" -- see
        # kaggriculture.py's _new_plant for ongoing crops) means the rescue
        # knob's lifespan skip never trips unless a test asks for it.
        "max_lifespan_step": max_lifespan_step,
    }


def strawberry(
    *,
    planted_day: int = 0,
    watered_today: bool = False,
    yield_units: int = 0,
    fertilized_until_day: int = -1,
    consecutive_unwatered: int = 1,
    max_lifespan_step: int = -1,
) -> dict[str, Any]:
    """A strawberry tile, shaped as the engine's ``_new_plant`` leaves an
    ongoing crop: ``yield_units`` starts at 0, not wheat's 1 -- the engine
    seeds that opening unit only for non-ongoing crops, and every strawberry
    unit arrives later from the end-of-day refresh."""
    return plant(
        crop="STRAWBERRY",
        planted_day=planted_day,
        watered_today=watered_today,
        yield_units=yield_units,
        fertilized_until_day=fertilized_until_day,
        consecutive_unwatered=consecutive_unwatered,
        max_lifespan_step=max_lifespan_step,
    )


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


def pasture(
    *,
    animal: str = "COW",
    fed_today: bool = False,
    cared_today: bool = False,
    yield_units: int = 0,
    fertilizer_available: bool = False,
) -> dict[str, Any]:
    """A built pasture with a placed cow/sheep -- same shape as ``goose_tile``
    (engine's ``_new_animal``), just ``kind: PASTURE`` and a caller-chosen
    species."""
    return {
        "kind": "PASTURE",
        "animal": animal,
        "placed_day": 0,
        "yield_units": yield_units,
        "consecutive_unfed": 0,
        "fed_today": fed_today,
        "cared_today": cared_today,
        "fertilizer_available": fertilizer_available,
        "pending_care_bonus": 0,
    }


def built_pasture() -> dict[str, Any]:
    """A built pasture with no animal placed yet."""
    return {"kind": "PASTURE"}
