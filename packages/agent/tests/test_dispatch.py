"""Dispatcher behavior: field tasks, atomic-plant budget, movement legality,
and how both widen once land purchases unlock more quadrants."""

from __future__ import annotations

from agent.constants import target_tiles
from agent.dispatch import dispatch
from viewfactory import make_view, plant

NW_TILES = target_tiles(("NW",))


def test_hand_standing_on_unwatered_plant_waters_it() -> None:
    # planted_day matches the view's day (1) so this is age 0 (fresh
    # planting) rather than the default age-1 skip-day.
    tiles = make_view().tiles
    tiles[2][2] = plant(planted_day=1, watered_today=False)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["WATER"]


def test_plant_orders_never_exceed_seed_count() -> None:
    # Two hands, two empty target tiles, ONE seed: the engine's atomic pre-pass
    # would void BOTH plants if we issued two — the dispatcher must issue one.
    view = make_view(hands=[(1, 1), (2, 2)], seeds=1)
    actions = dispatch(view, NW_TILES)
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
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["HARVEST"]
    assert actions.hands[1] == ["WATER"]
    assert actions.hands[2] == ["DIG"]


def test_heavy_hand_routes_to_shed_and_drops() -> None:
    tiles = make_view().tiles
    walking = make_view(hands=[(2, 4)], tiles=tiles, inventories=[{}, {"WHEAT": 9}], seeds=5)
    assert dispatch(walking, NW_TILES).hands[0] == ["EAST"]

    at_shed = make_view(hands=[(4, 4)], inventories=[{}, {"WHEAT": 9}], seeds=5)
    assert dispatch(at_shed, NW_TILES).hands[0] == ["DROP"]


def test_field_task_exists_on_unlocked_ne_tile() -> None:
    # Day 0 is quota-exempt (plant_quota returns the whole board), so the
    # newly-unlocked NE tile the hand stands on is guaranteed a task instead
    # of possibly falling outside a day>0 quota's nearest-shed-first prefix.
    unlocked = ("NW", "NE")
    view = make_view(step=0, hands=[(7, 2)], unlocked_quadrants=unlocked, seeds=5)
    actions = dispatch(view, target_tiles(unlocked))
    assert actions.hands[0] == ["PLANT", "WHEAT"]


def test_heavy_hand_mules_to_nearest_unlocked_shed_access() -> None:
    # With every quadrant unlocked, (5, 5) is the closer shed-access corner
    # for a hand deep in the SE quadrant, so a hand already standing there
    # drops rather than walking all the way to (4, 4).
    all_open = ("NW", "NE", "SW", "SE")
    at_se_shed = make_view(
        hands=[(5, 5)], unlocked_quadrants=all_open, inventories=[{}, {"WHEAT": 6}], seeds=0
    )
    assert dispatch(at_se_shed, target_tiles(all_open)).hands[0] == ["DROP"]

    # The same tile is still LOCKED with only NW unlocked, so the mule keeps
    # walking toward the one open corner, (4, 4), instead of dropping.
    nw_only = ("NW",)
    still_locked = make_view(
        hands=[(5, 5)], unlocked_quadrants=nw_only, inventories=[{}, {"WHEAT": 6}], seeds=0
    )
    assert dispatch(still_locked, NW_TILES).hands[0] == ["WEST"]


def test_fresh_planting_outranks_nearer_in_window_water() -> None:
    # A same-day planting must be watered today or it becomes a WEED
    # overnight; an in-window water a turn from now is safe to defer. The
    # hand should take the farther, more urgent tile over the nearer one.
    tiles = make_view().tiles
    tiles[0][3] = plant(planted_day=5, watered_today=False)  # (3, 0): fresh, far
    tiles[1][0] = plant(planted_day=2, watered_today=False)  # (0, 1): in-window, near
    view = make_view(
        step=5 * 24,
        hands=[(0, 0)],
        tiles=tiles,
        inventories=[{"WHEAT": 1}, {}],  # farmer already loaded: out of the field race
    )
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["EAST"]  # toward (3, 0), not south toward (0, 1)


def test_ripe_harvest_outranks_nearer_in_window_water() -> None:
    # A ripe, already-watered tile just needs picking up; it should not lose
    # its unit to a nearer tile that only needs an in-window water.
    tiles = make_view().tiles
    tiles[0][3] = plant(planted_day=2, watered_today=True, yield_units=2)  # (3, 0): ripe, far
    tiles[1][0] = plant(planted_day=3, watered_today=False, yield_units=0)  # (0, 1): in-window
    view = make_view(
        step=6 * 24,
        hands=[(0, 0)],
        tiles=tiles,
        inventories=[{"WHEAT": 1}, {}],
    )
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["EAST"]  # toward (3, 0), not south toward (0, 1)


def test_age_one_plant_generates_no_task() -> None:
    # One unwatered day is safe (weed conversion needs two consecutive
    # misses) and age 1 is outside the yield window, so watering it would be
    # wasted labor. A hand standing right on it should still end up idle.
    tiles = make_view().tiles
    tiles[2][2] = plant(planted_day=4, watered_today=False)  # day 5 - 4 = age 1
    view = make_view(step=5 * 24, hands=[(2, 2)], tiles=tiles, seeds=0)
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["PASS"]


def test_stale_ripe_plant_without_final_water_still_harvests() -> None:
    # Age 5+ with yield means the final in-window water was missed; convert
    # to HARVEST anyway instead of issuing a now-pointless WATER.
    tiles = make_view().tiles
    tiles[2][2] = plant(planted_day=0, watered_today=False, yield_units=3)  # age 5
    view = make_view(step=5 * 24, hands=[(2, 2)], tiles=tiles, seeds=0)
    actions = dispatch(view, NW_TILES)
    assert actions.hands[0] == ["HARVEST"]


def test_plant_suppressed_after_hour_twenty() -> None:
    # A plant issued at hour 21+ cannot reliably get its own same-day water,
    # so PLANT orders stop even with seeds in hand and an empty tile underfoot.
    # Day 0 keeps this quota-exempt so the hand's own tile is guaranteed a
    # task at hour 20, isolating the hour cutoff as the only variable.
    hour_20 = make_view(step=20, hands=[(2, 2)], seeds=5)
    assert dispatch(hour_20, NW_TILES).hands[0] == ["PLANT", "WHEAT"]

    hour_21 = make_view(step=21, hands=[(2, 2)], seeds=5)
    assert dispatch(hour_21, NW_TILES).hands[0] == ["PASS"]


def test_priority_classes_starve_lower_priority_once_units_exhausted() -> None:
    # Two units, three candidate tasks spanning three priority classes: the
    # nearest task (P3, an empty-tile plant) goes unclaimed because both
    # units are already spoken for by the higher-priority P0 and P2 work,
    # even though P3 is physically closest to both of them.
    tiles = make_view().tiles
    tiles[0][4] = plant(planted_day=5, watered_today=False)  # (4, 0): P0, far
    tiles[2][2] = plant(planted_day=2, watered_today=False)  # (2, 2): P2, near
    # (1, 0) stays empty -> P3, nearest to both units, seeds available.
    view = make_view(step=5 * 24, farmer=(4, 4), hands=[(0, 0)], tiles=tiles, seeds=5)
    actions = dispatch(view, NW_TILES)
    assert actions.farmer == ["NORTH"]  # farmer -> (4, 0), the P0 task
    assert actions.hands[0] == ["EAST"]  # hand -> (2, 2), the P2 task


# --- Melon satellite -------------------------------------------------------
#
# Melon tiles are identified purely by position (membership in the caller-
# supplied ``melon_tiles`` frozenset), independent of constants.melon_tiles,
# so these tests pin arbitrary coordinates as "the melon zone" directly.


def test_fresh_melon_planting_unwatered_gets_priority_zero_water() -> None:
    # Same reasoning as wheat: skip today's water and it's a WEED overnight.
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=1, watered_today=False)
    view = make_view(step=24, hands=[(2, 2)], tiles=tiles)  # day 1, age 0
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["WATER"]


def test_melon_window_water_between_age_six_and_twelve() -> None:
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=False, yield_units=3)
    view = make_view(step=9 * 24, hands=[(2, 2)], tiles=tiles)  # age 9, mid-window
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["WATER"]


def test_melon_maintenance_waters_only_even_ages_in_the_dead_zone() -> None:
    # Ages 1-5 sit between the forced planting-day water and the yield
    # window (age 6): only ages 2 and 4 get a maintenance water (every other
    # day is enough to stay under the 2-consecutive-unwatered weed trap).
    expected = {1: ["PASS"], 2: ["WATER"], 3: ["PASS"], 4: ["WATER"], 5: ["PASS"]}
    for age, want in expected.items():
        tiles = make_view().tiles
        tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=False, yield_units=1)
        view = make_view(step=age * 24, hands=[(2, 2)], tiles=tiles)
        actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
        assert actions.hands[0] == want, f"age={age}"


def test_melon_ripe_via_max_yield_even_before_ripe_age() -> None:
    # yield_units hitting the cap is its own ripeness signal, independent of
    # age -- no reason to make a maxed-out melon wait until age 12.
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=False, yield_units=6)
    view = make_view(step=8 * 24, hands=[(2, 2)], tiles=tiles)  # age 8
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["HARVEST"]


def test_melon_ripe_at_max_yield_day_when_watered() -> None:
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=True, yield_units=5)
    view = make_view(step=12 * 24, hands=[(2, 2)], tiles=tiles)  # age 12, watered
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["HARVEST"]


def test_melon_still_waterable_on_the_last_window_day_if_missed() -> None:
    # Age 12, unwatered: still inside the window, so it gets one more WATER
    # rather than being force-harvested a day early.
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=False, yield_units=5)
    view = make_view(step=12 * 24, hands=[(2, 2)], tiles=tiles)  # age 12, unwatered
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["WATER"]


def test_melon_stale_harvest_ignores_watered_today() -> None:
    # Age 13+, past the window: harvest regardless of watered_today, exactly
    # like wheat's age >= 5 fallback (a missed final water can't be undone).
    tiles = make_view().tiles
    tiles[2][2] = plant(crop="MELON", planted_day=0, watered_today=False, yield_units=4)
    view = make_view(step=13 * 24, hands=[(2, 2)], tiles=tiles)  # age 13
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["HARVEST"]


def test_empty_melon_tile_gets_plant_melon_task() -> None:
    view = make_view(step=0, hands=[(2, 2)], melon_seeds=5)
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLANT", "MELON"]


def test_melon_plant_suppressed_after_cutoff_day() -> None:
    # Day 19 is the last profitable melon plant day (10-day runway, game
    # ends day 29); day 20 stops issuing PLANT MELON even with seeds ready.
    view = make_view(step=20 * 24, hands=[(2, 2)], melon_seeds=5)
    actions = dispatch(view, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["PASS"]


def test_melon_plant_stagger_caps_at_two_per_day() -> None:
    # Two melon tiles already planted today exhausts melon's own 2/day cap;
    # a third empty melon tile goes unclaimed even with seeds in hand.
    tiles = make_view().tiles
    tiles[1][1] = plant(crop="MELON", planted_day=0, watered_today=True)
    tiles[1][2] = plant(crop="MELON", planted_day=0, watered_today=True)
    melon_zone = frozenset({(1, 1), (2, 1), (3, 3)})
    view = make_view(step=0, hands=[(3, 3)], tiles=tiles, melon_seeds=5)
    actions = dispatch(view, NW_TILES, melon_zone)
    assert actions.hands[0] == ["PASS"]


def test_melon_seed_budget_is_independent_of_wheat_seed_budget() -> None:
    # A shared seed counter (reading only view.seeds["WHEAT"]) would block
    # melon planting whenever wheat seeds run out, and vice versa. Each pool
    # must gate only its own crop's PLANT task.
    wheat_exhausted = make_view(step=0, hands=[(2, 2)], seeds=0, melon_seeds=1)
    actions = dispatch(wheat_exhausted, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLANT", "MELON"]

    # seeds=2: the farmer is idle (no goose, nothing carried) and also stands
    # on an empty wheat tile at the default (4, 4), so it legitimately claims
    # the first wheat seed in unit-index order — 1 seed would starve the hand
    # via that incidental competition rather than via the bug under test.
    melon_exhausted = make_view(step=0, hands=[(1, 1)], seeds=2, melon_seeds=0)
    actions = dispatch(melon_exhausted, NW_TILES, frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLANT", "WHEAT"]


def test_endgame_suppresses_harvest_tasks_after_hour_twenty() -> None:
    # Day 29 is the last game day; goods harvested past hour 20 can't reach
    # the shed before the market closes (it reads shed contents pre-drop),
    # so no P1 task -- wheat or melon -- is ever emitted that late.
    tiles = make_view().tiles
    tiles[2][2] = plant(planted_day=0, watered_today=True, yield_units=4)  # wheat, ripe
    tiles[3][3] = plant(crop="MELON", planted_day=0, watered_today=True, yield_units=6)  # ripe
    melon_zone = frozenset({(3, 3)})

    at_hour_twenty = make_view(step=29 * 24 + 20, hands=[(2, 2), (3, 3)], tiles=tiles)
    actions = dispatch(at_hour_twenty, NW_TILES, melon_zone)
    assert actions.hands[0] == ["HARVEST"]
    assert actions.hands[1] == ["HARVEST"]

    at_hour_twenty_one = make_view(step=29 * 24 + 21, hands=[(2, 2), (3, 3)], tiles=tiles)
    actions = dispatch(at_hour_twenty_one, NW_TILES, melon_zone)
    assert actions.hands[0] == ["PASS"]
    assert actions.hands[1] == ["PASS"]


def test_endgame_mule_threshold_drops_to_one_carried_unit() -> None:
    # Off day 29, a hand carrying just 1 unit keeps farming (HAND_MULE_LOAD
    # is 9) and takes the ripe tile it's standing on.
    tiles = make_view().tiles
    tiles[2][2] = plant(planted_day=0, watered_today=False, yield_units=3)  # age 5, ripe
    normal_day = make_view(step=5 * 24, hands=[(2, 2)], tiles=tiles, inventories=[{}, {"WHEAT": 1}])
    assert dispatch(normal_day, NW_TILES).hands[0] == ["HARVEST"]

    # On day 29 at hour <= 20 (harvest not yet hour-suppressed), that same
    # 1-unit carry is mule-worthy on its own: the hand heads for the shed
    # (EAST, the first step from (2, 2) toward (4, 4)) instead of taking the
    # harvest, since goods harvested this late can't reach the shed in time.
    endgame = make_view(step=29 * 24, hands=[(2, 2)], tiles=tiles, inventories=[{}, {"WHEAT": 1}])
    assert dispatch(endgame, NW_TILES).hands[0] == ["EAST"]
