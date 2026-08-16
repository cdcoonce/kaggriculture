"""Dispatcher behavior: field tasks, atomic-plant budget, movement legality,
and how both widen once land purchases unlock more quadrants."""

from __future__ import annotations

from agent.constants import PASTURE_TILE_TARGET, target_tiles
from agent.dispatch import STRAWBERRY_PLANT_DAILY_CAP, dispatch
from viewfactory import built_pasture, make_view, pasture, plant, strawberry

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


# --- Pasture husbandry (M2a) -------------------------------------------
#
# Pasture tiles are identified purely by position (membership in the
# caller-supplied ``pasture_tiles`` frozenset), independent of
# constants.pasture_tiles, exactly like the melon satellite above. Priority
# numbers match the field-task classes: P0 FEED (escape + banked-care-bonus
# risk), P1 HARVEST (amortize trips) / PLACE a bought animal, P2 CARE /
# COLLECT_FERTILIZER, P3 BUILD_PASTURE, P4 DIG (shared with wheat/melon).


def test_unfed_pasture_animal_gets_fed_when_carrying_wheat() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=False)
    view = make_view(hands=[(2, 2)], tiles=tiles, inventories=[{}, {"WHEAT": 2}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["FEED"]


def test_unfed_pasture_animal_without_wheat_walks_to_shed_first() -> None:
    # Mirrors the goose steward's fetch-before-carry pattern: no wheat in
    # inventory but the shed has some, so the unit heads for shed access
    # (EAST from (0, 0) toward (4, 4)) instead of straight for the pasture
    # tile (which would be SOUTH from here).
    # Farmer carries WHEAT so it's mule-bound (out of the field-task race) --
    # otherwise the farmer, also fielded and idle, would win the sole P0 task
    # via the greedy per-unit-index assignment before the hand gets a look.
    tiles = make_view().tiles
    tiles[3][0] = pasture(fed_today=False)  # (0, 3)
    view = make_view(hands=[(0, 0)], tiles=tiles, shed={"WHEAT": 5}, inventories=[{"WHEAT": 1}, {}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(0, 3)}))
    assert actions.hands[0] == ["EAST"]


def test_unfed_pasture_animal_picks_up_wheat_at_shed_access() -> None:
    tiles = make_view().tiles
    tiles[3][0] = pasture(fed_today=False)
    view = make_view(hands=[(4, 4)], tiles=tiles, shed={"WHEAT": 5}, inventories=[{"WHEAT": 1}, {}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(0, 3)}))
    assert actions.hands[0] == ["PICKUP", "WHEAT", 1]


def test_unfed_pasture_animal_with_no_wheat_anywhere_walks_toward_tile() -> None:
    # Best-effort fallback when the feed-reserve top-up hasn't caught up yet:
    # walk toward the animal rather than stall at the shed forever. FEED
    # issued with an empty inventory is a harmless engine no-op.
    tiles = make_view().tiles
    tiles[3][0] = pasture(fed_today=False)
    view = make_view(hands=[(0, 0)], tiles=tiles, shed={}, inventories=[{"WHEAT": 1}, {}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(0, 3)}))
    assert actions.hands[0] == ["SOUTH"]


def test_pasture_harvest_at_two_or_more_yield_units() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, yield_units=2)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["HARVEST"]


def test_pasture_no_harvest_below_two_yield_before_day_twenty_seven() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, yield_units=1, cared_today=True)
    view = make_view(step=10 * 24, hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PASS"]  # fed, cared, yield 1 (< 2 amortize threshold), day 10


def test_pasture_harvest_at_one_yield_unit_on_or_after_day_twenty_seven() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, yield_units=1, cared_today=True)
    view = make_view(step=27 * 24, hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["HARVEST"]


def test_pasture_care_when_not_cared_today() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, yield_units=0, cared_today=False)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["CARE"]


def test_pasture_collect_fertilizer_when_cared_and_available() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, cared_today=True, fertilizer_available=True)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["COLLECT_FERTILIZER"]


def test_pasture_idle_when_fed_cared_and_no_fertilizer_or_yield() -> None:
    tiles = make_view().tiles
    tiles[2][2] = pasture(fed_today=True, cared_today=True, fertilizer_available=False)
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PASS"]


def test_empty_pasture_zone_tile_gets_build_pasture_task() -> None:
    view = make_view(hands=[(2, 2)])  # tile is None by default
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["BUILD_PASTURE"]


def test_build_pasture_stops_once_every_zone_tile_is_built() -> None:
    """The negative case: occupancy, not a counter, is what stops building.

    Deleting the old ``built_count`` ceiling (it was stale AND provably
    unable to fire) removed the cap test's negative half, so pin what
    actually bounds this now: the ``tile is None`` check. A zone whose tiles
    are ALL already built must emit no further BUILD_PASTURE — issuing one
    on an occupied tile would burn a unit-action every turn for the rest of
    the game.
    """
    tiles = make_view().tiles
    zone = NW_TILES[:6]
    for x, y in zone:
        tiles[y][x] = built_pasture()
    # The hand stands on a built zone tile; nothing in the zone is empty.
    view = make_view(hands=[zone[-1]], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset(zone))
    assert not any(a and a[0] == "BUILD_PASTURE" for a in [actions.farmer, *actions.hands])


def test_build_pasture_continues_past_the_module_target_when_the_zone_is_larger() -> None:
    # Zone size, not any module constant, is what bounds building. Here the
    # zone is exactly one tile larger than PASTURE_TILE_TARGET (the whole
    # target-sized prefix already built, plus one more designated-but-empty
    # tile): that extra tile must still get BUILD_PASTURE. Under the removed
    # `built_count < PASTURE_TILE_TARGET` ceiling it was silently skipped
    # forever. Guards against re-introducing any module-constant cap (see
    # test_pasture_build_ceiling_follows_the_configured_zone_size_not_the_
    # module_constant below for the sharper, larger-zone version).
    tiles = make_view().tiles
    built_positions = [(x, y) for y in range(3) for x in range(5)][:PASTURE_TILE_TARGET]
    assert len(built_positions) == PASTURE_TILE_TARGET
    for x, y in built_positions:
        tiles[y][x] = built_pasture()
    extra_empty = (0, 3)  # one more designated pasture position, still empty
    pasture_zone = frozenset(built_positions) | frozenset({extra_empty})
    view = make_view(hands=[extra_empty], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), pasture_zone)
    assert actions.hands[0] == ["BUILD_PASTURE"]


def test_pasture_build_ceiling_follows_the_configured_zone_size_not_the_module_constant() -> None:
    """Regression for the M2a stranding bug this ranch-reshape PR fixes:
    BUILD_PASTURE must be bounded by the zone the caller actually passed in,
    never by the module-level ``PASTURE_TILE_TARGET``.
    A ``PolicyConfig`` override of cow_target/sheep_target resizes the zone
    ``policy.py`` hands to ``dispatch`` without touching that module
    constant, so a ceiling pinned to it would silently stop emitting
    BUILD_PASTURE partway through a larger zone -- any tile past the cutoff
    never gets built, so an animal bought for it can never be PLACEd and
    sits in the shed, unplaced, for the rest of the game. That's the exact
    M2a failure mode the surrounding dispatch.py comments warn about.

    This zone has 17 tiles -- comfortably past PASTURE_TILE_TARGET (10) --
    all left unbuilt. Against the old ``built_count < PASTURE_TILE_TARGET``
    code, the loop stopped issuing BUILD_PASTURE after the 10th zone tile it
    visits (in the same nearest-shed-first order as ``tiles``), so no
    BUILD_PASTURE task was ever generated for the 17th -- the hand standing
    there fell back on whatever unrelated task was nearest instead. With the
    ceiling removed, every empty zone tile -- including the 17th -- gets its
    own BUILD_PASTURE.
    """
    zone = NW_TILES[:17]  # nearest-shed-first order, same as dispatch's own tile loop
    assert len(zone) == 17
    assert len(zone) > PASTURE_TILE_TARGET
    pasture_zone = frozenset(zone)
    last = zone[-1]  # 17th in loop order -- stranded under the old module-constant ceiling
    view = make_view(hands=[last])  # tile is None by default: an unbuilt pasture position
    actions = dispatch(view, NW_TILES, frozenset(), pasture_zone)
    assert actions.hands[0] == ["BUILD_PASTURE"]


def test_empty_built_pasture_gets_place_cow_when_carrying_one() -> None:
    tiles = make_view().tiles
    tiles[2][2] = built_pasture()
    view = make_view(hands=[(2, 2)], tiles=tiles, shed={"COW": 1}, inventories=[{}, {"COW": 1}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLACE", "COW"]


def test_empty_built_pasture_gets_place_sheep_when_no_cow_available() -> None:
    tiles = make_view().tiles
    tiles[2][2] = built_pasture()
    view = make_view(hands=[(2, 2)], tiles=tiles, shed={"SHEEP": 1}, inventories=[{}, {"SHEEP": 1}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLACE", "SHEEP"]


def test_place_task_prefers_cow_over_sheep_when_both_available_in_shed() -> None:
    tiles = make_view().tiles
    tiles[2][2] = built_pasture()
    view = make_view(
        hands=[(2, 2)],
        tiles=tiles,
        shed={"COW": 1, "SHEEP": 1},
        inventories=[{}, {"COW": 1, "SHEEP": 1}],
    )
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLACE", "COW"]


def test_place_cow_task_fetches_from_shed_first_when_not_carrying() -> None:
    # Farmer sidelined (mule-bound) so the hand is the one competing for --
    # and fetching for -- the sole PLACE task; see the FEED fetch tests above.
    tiles = make_view().tiles
    tiles[3][0] = built_pasture()  # (0, 3), far from shed
    view = make_view(hands=[(0, 0)], tiles=tiles, shed={"COW": 1}, inventories=[{"WHEAT": 1}, {}])
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(0, 3)}))
    assert actions.hands[0] == ["EAST"]  # toward shed (4,4) to PICKUP COW, not south to the pasture


def test_weed_on_pasture_zone_tile_still_gets_dig() -> None:
    tiles = make_view().tiles
    tiles[2][2] = {"kind": "WEED"}
    view = make_view(hands=[(2, 2)], tiles=tiles)
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["DIG"]


def test_teeth_check_unfed_animal_feed_outranks_nearer_field_task() -> None:
    # (0, 4) [FEED, P0] is farther from the hand (dist 4) than (3, 0) [an
    # in-window water, P2] (dist 3); the P0 task must still win the unit.
    tiles = make_view().tiles
    tiles[4][0] = pasture(fed_today=False)  # (0, 4)
    tiles[0][3] = plant(planted_day=2, watered_today=False)  # (3, 0): age 3, in-window water
    view = make_view(
        step=5 * 24,
        farmer=(4, 4),
        hands=[(0, 0)],
        tiles=tiles,
        inventories=[{"WHEAT": 1}, {"WHEAT": 1}],  # farmer loaded (mule-bound, out of the race)
    )
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(0, 4)}))
    assert actions.hands[0] == ["SOUTH"]  # toward (0, 4) [FEED], not (3, 0) [water]


def test_carrying_unit_keeps_place_task_after_shed_count_drops_to_zero() -> None:
    # Regression: once a unit PICKUPs the last cow in the shed, the shed's
    # own COW count drops to 0. If PLACE-task generation depended only on
    # the shed count (not on what units are already carrying), the carrying
    # unit would lose its task the very next turn -- nothing left to
    # "budget" against -- fall through to the idle-cleanup path, get
    # misclassified as carrying produce, and mule the cow straight back into
    # the shed instead of finishing the walk to the empty pasture: a
    # pickup-then-drop cycle that never actually places the animal.
    tiles = make_view().tiles
    tiles[2][2] = built_pasture()
    view = make_view(
        hands=[(2, 2)],
        tiles=tiles,
        shed={},  # the cow already left the shed -- it's in the hand's inventory now
        inventories=[{}, {"COW": 1}],
    )
    actions = dispatch(view, NW_TILES, frozenset(), frozenset({(2, 2)}))
    assert actions.hands[0] == ["PLACE", "COW"]


# --- Strawberry (ongoing crop) -------------------------------------------
#
# The engine facts these pin are verified in tests/test_invariants.py claims
# 1-8 and by a full 720-step planting-window probe. What is checked here is
# that the DISPATCHER acts on them, since every one of these rules fails
# silently in the engine: a missed water weeds the tile, a lazy harvest halves
# the fertilizer bonus, and a wasted FERTILIZE just consumes the unit.

SB = (2, 2)
SB_ZONE = frozenset({SB})


def _sb_view(
    tile: dict[str, object],
    *,
    day: int,
    hands: list[tuple[int, int]] | None = None,
    inventories: list[dict[str, int]] | None = None,
    shed: dict[str, int] | None = None,
) -> object:
    tiles = make_view().tiles
    tiles[SB[1]][SB[0]] = tile
    return make_view(
        step=day * 24,
        hands=hands if hands is not None else [SB],
        tiles=tiles,
        inventories=inventories,
        shed=shed,
    )


def _sb_action(tile: dict[str, object], *, day: int, **kwargs: object) -> list[object]:
    view = _sb_view(tile, day=day, **kwargs)  # type: ignore[arg-type]
    return dispatch(view, NW_TILES, frozenset(), frozenset(), SB_ZONE).hands[0]


def test_strawberry_is_watered_on_its_planting_day() -> None:
    # Not optional: the engine seeds a fresh plant with
    # consecutive_unwatered = 1, so an unwatered planting day is already one
    # of the two consecutive misses that turn the tile into a WEED overnight
    # -- losing the $100 seed and all four ticks before any of them fire.
    assert _sb_action(strawberry(planted_day=5), day=5) == ["WATER"]


def test_strawberry_waters_on_every_tick_age() -> None:
    # The engine computes `fertilized = was_watered and covered`, so an
    # unwatered tick day pays no fertilizer bonus no matter how well the tile
    # is fertilized. Each of these four ages is a refresh that credits yield.
    for age in (9, 11, 13, 15):
        tile = strawberry(planted_day=0, watered_today=False)
        assert _sb_action(tile, day=age) == ["WATER"], f"no water on tick age {age}"


def test_strawberry_maintenance_water_runs_every_other_day_before_the_ticks() -> None:
    # Two consecutive unwatered days weed the tile, so the ten-day dead zone
    # between planting and the first tick still needs an alternating cadence.
    # Odd ages are deliberately left alone -- a single dry day is safe, and
    # watering one would be pure wasted labor.
    for age in (2, 4, 6, 8):
        assert _sb_action(strawberry(planted_day=0), day=age) == ["WATER"], (
            f"no maintenance water at age {age}"
        )
    for age in (1, 3, 5, 7):
        assert _sb_action(strawberry(planted_day=0), day=age) == ["PASS"], (
            f"wasted a turn watering age {age}, which is safe to skip"
        )


def test_strawberry_harvests_on_the_yield_cap_not_on_an_age() -> None:
    # The engine clamps with min(max_yield, yield + bonus), so a fertilized
    # tile fills to 4 in two ticks and every later tick adds nothing until
    # it is drained. Harvesting on the cap is what makes fertilizer worth 8
    # units a cycle instead of 4; waiting for a fixed age silently halves it.
    capped = strawberry(planted_day=0, yield_units=4, watered_today=True)
    assert _sb_action(capped, day=12) == ["HARVEST"]

    # Below the cap mid-cycle there is nothing to do but keep the cadence --
    # harvesting 2 units here would cost a trip and bank the same total.
    partial = strawberry(planted_day=0, yield_units=2, watered_today=True)
    assert _sb_action(partial, day=10) == ["PASS"]


def test_strawberry_sweeps_a_sub_cap_tile_at_the_final_age() -> None:
    # The unfertilized path accrues +1 per tick and so only ever reaches 4 on
    # the last one. Without this sweep an unfertilized tile would never clear
    # the cap rule and would never be harvested at all.
    tile = strawberry(planted_day=0, yield_units=3, watered_today=True)
    assert _sb_action(tile, day=16) == ["HARVEST"]


def test_strawberry_fertilizes_only_at_ages_nine_and_thirteen() -> None:
    # Coverage is day..day+2 inclusive and is read on the refresh day, so age
    # 9 covers the age-9 and age-11 ticks and age 13 covers 13 and 15. Two
    # units buy the bonus on all four ticks; fertilizing at 11 or 15 would
    # buy nothing and still consume the unit.
    for age in (9, 13):
        tile = strawberry(planted_day=0, watered_today=True)
        assert _sb_action(tile, day=age, inventories=[{}, {"FERTILIZER": 1}]) == ["FERTILIZE"], (
            f"no fertilize at age {age}"
        )
    # Asserted as an absence rather than as PASS: the hand stands ON the tile
    # holding a unit, so a wrongly-emitted FERTILIZE would be dispatched
    # verbatim with no walking leg to mask it -- but a unit holding sellable
    # goods with nothing to do correctly walks them home instead of idling,
    # so PASS is not the right negative.
    for age in (11, 15):
        tile = strawberry(planted_day=0, watered_today=True)
        assert _sb_action(tile, day=age, inventories=[{}, {"FERTILIZER": 1}]) != ["FERTILIZE"], (
            f"wasted a FERTILIZER unit at age {age}, which age 9/13 coverage already spans"
        )


def test_strawberry_never_refertilizes_a_covered_tile() -> None:
    # The engine takes the FERTILIZER unit BEFORE the max() that may not move
    # fertilized_until_day at all, so re-applying to a covered tile is a
    # silent, uncompensated loss of the unit.
    covered = strawberry(planted_day=0, watered_today=True, fertilized_until_day=13)
    assert _sb_action(covered, day=13, inventories=[{}, {"FERTILIZER": 1}]) != ["FERTILIZE"]

    lapsed = strawberry(planted_day=0, watered_today=True, fertilized_until_day=12)
    assert _sb_action(lapsed, day=13, inventories=[{}, {"FERTILIZER": 1}]) == ["FERTILIZE"]


def test_strawberry_water_outranks_fertilize_on_the_same_tile() -> None:
    # Both are due on a tick day, but only one task per tile is emitted per
    # turn. Water has to win: `fertilized = was_watered and covered` means an
    # unwatered tick day pays no bonus however well fertilized it is, so
    # fertilizing first would risk spending the unit on a dry tick.
    tile = strawberry(planted_day=0, watered_today=False)
    assert _sb_action(tile, day=9, inventories=[{}, {"FERTILIZER": 1}]) == ["WATER"]


def test_strawberry_fetches_fertilizer_from_the_shed_before_applying_it() -> None:
    # FERTILIZE draws from the acting unit's own inventory, so a hand with an
    # empty inventory has to make the shed trip first -- the same carry leg
    # FEED and PLACE already use.
    tile = strawberry(planted_day=0, watered_today=True)
    action = _sb_action(tile, day=9, hands=[(2, 2)], inventories=[{}, {}], shed={"FERTILIZER": 2})
    assert action in (["EAST"], ["SOUTH"]), f"expected a walk toward the shed, got {action}"


def test_strawberry_zone_falls_through_to_wheat_once_its_window_closes() -> None:
    # The reservation trap. Melon reserves its whole zone all game against a
    # flat 2/day cap, stranding roughly 110 tile-days at melon 20 -- that idle
    # ground is what makes melon 22/24 gate WORSE than 16-20. Strawberry's
    # window closes at day 12, and a tile whose cycle finished and was dug
    # re-enters as empty ground well after that, so a zone that kept claiming
    # its tiles would hold prime near-shed ground doing nothing for the whole
    # back half of the game.
    #
    # This is a silent failure with no in-game signal, and it survived a
    # deliberate deletion of the fall-through branch with the entire suite
    # still green -- so it is pinned here explicitly.
    # Every other target tile is filled with an age-1 wheat plant, which the
    # dispatcher deliberately gives no task at all (one dry day is safe, and
    # age 1 is outside the yield window). That leaves the tile under test as
    # the only one on the board that can generate work, so the assertion is
    # about the branch rather than about who won the nearest-tile race or
    # what was left of wheat's daily quota.
    def _isolated(day: int) -> list[list[object]]:
        tiles = make_view().tiles
        for x, y in NW_TILES:
            if (x, y) != SB:
                tiles[y][x] = plant(planted_day=day - 1, watered_today=False)
        return tiles

    inside = make_view(step=12 * 24, hands=[SB], tiles=_isolated(12), seeds=5, strawberry_seeds=5)
    assert dispatch(inside, NW_TILES, frozenset(), frozenset(), SB_ZONE).hands[0] == [
        "PLANT",
        "STRAWBERRY",
    ]

    closed = make_view(step=13 * 24, hands=[SB], tiles=_isolated(13), seeds=5)
    assert dispatch(closed, NW_TILES, frozenset(), frozenset(), SB_ZONE).hands[0] == [
        "PLANT",
        "WHEAT",
    ], "an empty strawberry tile past the cutoff was reserved instead of falling through to wheat"


def test_strawberry_zone_falls_through_to_wheat_once_the_daily_cap_is_spent() -> None:
    # Same trap, the other trigger: inside the window but with today's
    # stagger already spent, the remaining zone tiles must not idle until
    # tomorrow -- wheat's own quota can still use them today.
    day = 5
    zone = [(x, 0) for x in range(5)] + [(0, 1), (1, 1)]
    planted, spare = zone[:STRAWBERRY_PLANT_DAILY_CAP], zone[STRAWBERRY_PLANT_DAILY_CAP]

    tiles = make_view().tiles
    for x, y in NW_TILES:
        if (x, y) != spare:
            # planted_day == day for the zone tiles, so they count against
            # today's stagger; age-1 wheat everywhere else emits no task.
            tiles[y][x] = (
                strawberry(planted_day=day, watered_today=True)
                if (x, y) in planted
                else plant(planted_day=day - 1, watered_today=False)
            )

    view = make_view(step=day * 24, hands=[spare], tiles=tiles, seeds=5, strawberry_seeds=5)
    action = dispatch(view, NW_TILES, frozenset(), frozenset(), frozenset(zone)).hands[0]
    assert action == ["PLANT", "WHEAT"], (
        f"cap-spent strawberry tile idled instead of falling through to wheat (got {action})"
    )
