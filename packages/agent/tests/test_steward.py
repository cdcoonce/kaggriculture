"""Farmer goose-stewardship behavior: coop pipeline, feed logistics, chores."""

from __future__ import annotations

from agent.constants import target_tiles
from agent.dispatch import dispatch
from viewfactory import goose_tile, make_view

NW_TILES = target_tiles(("NW",))


def _with_goose(**goose_kwargs: object) -> list[list[object]]:
    tiles = make_view().tiles
    tiles[4][3] = goose_tile(**goose_kwargs)  # type: ignore[arg-type]
    return tiles


def test_coop_pipeline_pickup_carry_build_place() -> None:
    # Goose bought (in shed), farmer at the shed corner, nothing carried.
    at_shed = make_view(shed={"GOOSE": 1, "WHEAT": 3})
    assert dispatch(at_shed, NW_TILES).farmer == ["PICKUP", "GOOSE", 1]

    carrying = make_view(shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(carrying, NW_TILES).farmer == ["WEST"]  # toward the coop tile (3,4)

    at_site = make_view(farmer=(3, 4), shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(at_site, NW_TILES).farmer == ["BUILD_COOP"]

    tiles = make_view().tiles
    tiles[4][3] = {"kind": "COOP"}
    built = make_view(farmer=(3, 4), tiles=tiles, shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(built, NW_TILES).farmer == ["PLACE", "GOOSE"]


def test_chore_order_feed_harvest_care_collect() -> None:
    unfed = make_view(
        farmer=(3, 4), tiles=_with_goose(), shed={"WHEAT": 2}, inventories=[{"WHEAT": 1}]
    )
    assert dispatch(unfed, NW_TILES).farmer == ["FEED"]

    eggs_waiting = make_view(
        farmer=(3, 4), tiles=_with_goose(fed_today=True, yield_units=2), shed={"WHEAT": 2}
    )
    assert dispatch(eggs_waiting, NW_TILES).farmer == ["HARVEST"]

    uncared = make_view(farmer=(3, 4), tiles=_with_goose(fed_today=True), shed={"WHEAT": 2})
    assert dispatch(uncared, NW_TILES).farmer == ["CARE"]

    fert_ready = make_view(
        farmer=(3, 4),
        tiles=_with_goose(fed_today=True, cared_today=True, fertilizer_available=True),
        shed={"WHEAT": 2},
    )
    assert dispatch(fert_ready, NW_TILES).farmer == ["COLLECT_FERTILIZER"]


def test_feed_logistics_fetch_wheat_then_walk_back() -> None:
    # Goose unfed, farmer empty-handed at the shed corner with feed in shed.
    fetch = make_view(farmer=(4, 4), tiles=_with_goose(), shed={"WHEAT": 3})
    assert dispatch(fetch, NW_TILES).farmer == ["PICKUP", "WHEAT", 1]

    walk = make_view(
        farmer=(4, 4), tiles=_with_goose(), shed={"WHEAT": 2}, inventories=[{"WHEAT": 1}]
    )
    assert dispatch(walk, NW_TILES).farmer == ["WEST"]


def test_farmer_mules_sellables_home_when_chores_done() -> None:
    done = goose_tile(fed_today=True, cared_today=True)
    tiles = make_view().tiles
    tiles[4][3] = done
    away = make_view(
        farmer=(3, 4),
        tiles=tiles,
        shed={"WHEAT": 2},
        inventories=[{"EGG": 2, "FERTILIZER": 1}],
    )
    assert dispatch(away, NW_TILES).farmer == ["EAST"]

    home = make_view(
        farmer=(4, 4),
        tiles=tiles,
        shed={"WHEAT": 2},
        inventories=[{"EGG": 2, "FERTILIZER": 1}],
    )
    assert dispatch(home, NW_TILES).farmer == ["DROP"]


def test_hand_spawned_on_locked_tile_walks_out() -> None:
    tiles = make_view().tiles
    tiles[1][1] = {"kind": "WEED"}
    view = make_view(hands=[(5, 4)], tiles=tiles, seeds=0)
    action = dispatch(view, NW_TILES).hands[0]
    assert action == ["WEST"]  # x-first step off the locked spawn toward work


def test_hand_spawned_on_locked_tile_walks_toward_nearest_unlocked_corner() -> None:
    # Generalization of the single-quadrant case above: with NW, NE and SW
    # unlocked but SE still LOCKED, a hand stranded at the SE shed-access
    # corner (5, 5) walks toward (5, 4) — the nearest OPEN corner (tied with
    # (4, 5) at distance 1, broken by lower y) — not blindly toward (4, 4).
    unlocked = ("NW", "NE", "SW")
    view = make_view(hands=[(5, 5)], unlocked_quadrants=unlocked, seeds=0)
    action = dispatch(view, target_tiles(unlocked)).hands[0]
    assert action == ["NORTH"]
