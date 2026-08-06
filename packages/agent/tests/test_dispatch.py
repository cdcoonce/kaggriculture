"""Dispatcher behavior: field tasks, atomic-plant budget, movement legality."""

from __future__ import annotations

from agent.dispatch import dispatch
from viewfactory import make_view, plant


def test_hand_standing_on_unwatered_plant_waters_it() -> None:
    tiles = make_view().tiles
    tiles[2][2] = plant(watered_today=False)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view)
    assert actions.hands[0] == ["WATER"]


def test_plant_orders_never_exceed_seed_count() -> None:
    # Two hands, two empty target tiles, ONE seed: the engine's atomic pre-pass
    # would void BOTH plants if we issued two — the dispatcher must issue one.
    view = make_view(hands=[(1, 1), (2, 2)], seeds=1)
    actions = dispatch(view)
    plants = [a for a in [actions.farmer, *actions.hands] if a and a[0] == "PLANT"]
    assert len(plants) == 1


def test_ripe_tile_watered_before_harvest_and_weed_dug() -> None:
    # Watering at age 4 is still inside the yield window (+1); harvest follows
    # the water. A ripe-but-unwatered tile therefore gets WATER, a ripe-and-
    # watered tile gets HARVEST, and weeds get DIG.
    tiles = make_view().tiles
    tiles[1][1] = plant(planted_day=0, watered_today=True, yield_units=4)
    tiles[1][2] = plant(planted_day=0, watered_today=False, yield_units=3)
    tiles[3][3] = {"kind": "WEED"}
    view = make_view(step=4 * 24 + 2, hands=[(1, 1), (2, 1), (3, 3)], tiles=tiles)
    actions = dispatch(view)
    assert actions.hands[0] == ["HARVEST"]
    assert actions.hands[1] == ["WATER"]
    assert actions.hands[2] == ["DIG"]


def test_heavy_hand_routes_to_shed_and_drops() -> None:
    tiles = make_view().tiles
    walking = make_view(hands=[(2, 4)], tiles=tiles, inventories=[{}, {"WHEAT": 6}], seeds=5)
    assert dispatch(walking).hands[0] == ["EAST"]

    at_shed = make_view(hands=[(4, 4)], inventories=[{}, {"WHEAT": 6}], seeds=5)
    assert dispatch(at_shed).hands[0] == ["DROP"]
