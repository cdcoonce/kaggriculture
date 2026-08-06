"""Farmer goose-stewardship behavior: coop pipeline, feed logistics, chores."""

from __future__ import annotations

from agent.dispatch import dispatch
from viewfactory import goose_tile, make_view


def _with_goose(**goose_kwargs: object) -> list[list[object]]:
    tiles = make_view().tiles
    tiles[4][3] = goose_tile(**goose_kwargs)  # type: ignore[arg-type]
    return tiles


def test_coop_pipeline_pickup_carry_build_place() -> None:
    # Goose bought (in shed), farmer at the shed corner, nothing carried.
    at_shed = make_view(shed={"GOOSE": 1, "WHEAT": 3})
    assert dispatch(at_shed).farmer == ["PICKUP", "GOOSE", 1]

    carrying = make_view(shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(carrying).farmer == ["WEST"]  # toward the coop tile (3,4)

    at_site = make_view(farmer=(3, 4), shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(at_site).farmer == ["BUILD_COOP"]

    tiles = make_view().tiles
    tiles[4][3] = {"kind": "COOP"}
    built = make_view(farmer=(3, 4), tiles=tiles, shed={"WHEAT": 3}, inventories=[{"GOOSE": 1}])
    assert dispatch(built).farmer == ["PLACE", "GOOSE"]


def test_chore_order_feed_harvest_care_collect() -> None:
    unfed = make_view(
        farmer=(3, 4), tiles=_with_goose(), shed={"WHEAT": 2}, inventories=[{"WHEAT": 1}]
    )
    assert dispatch(unfed).farmer == ["FEED"]

    eggs_waiting = make_view(
        farmer=(3, 4), tiles=_with_goose(fed_today=True, yield_units=2), shed={"WHEAT": 2}
    )
    assert dispatch(eggs_waiting).farmer == ["HARVEST"]

    uncared = make_view(farmer=(3, 4), tiles=_with_goose(fed_today=True), shed={"WHEAT": 2})
    assert dispatch(uncared).farmer == ["CARE"]

    fert_ready = make_view(
        farmer=(3, 4),
        tiles=_with_goose(fed_today=True, cared_today=True, fertilizer_available=True),
        shed={"WHEAT": 2},
    )
    assert dispatch(fert_ready).farmer == ["COLLECT_FERTILIZER"]


def test_feed_logistics_fetch_wheat_then_walk_back() -> None:
    # Goose unfed, farmer empty-handed at the shed corner with feed in shed.
    fetch = make_view(farmer=(4, 4), tiles=_with_goose(), shed={"WHEAT": 3})
    assert dispatch(fetch).farmer == ["PICKUP", "WHEAT", 1]

    walk = make_view(
        farmer=(4, 4), tiles=_with_goose(), shed={"WHEAT": 2}, inventories=[{"WHEAT": 1}]
    )
    assert dispatch(walk).farmer == ["WEST"]


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
    assert dispatch(away).farmer == ["EAST"]

    home = make_view(
        farmer=(4, 4),
        tiles=tiles,
        shed={"WHEAT": 2},
        inventories=[{"EGG": 2, "FERTILIZER": 1}],
    )
    assert dispatch(home).farmer == ["DROP"]


def test_hand_spawned_on_locked_tile_walks_out() -> None:
    tiles = make_view().tiles
    tiles[1][1] = {"kind": "WEED"}
    view = make_view(hands=[(5, 4)], tiles=tiles, seeds=0)
    action = dispatch(view).hands[0]
    assert action == ["WEST"]  # x-first step off the locked spawn toward work
