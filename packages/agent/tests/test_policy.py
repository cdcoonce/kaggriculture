"""Policy wiring behavior: opening orders, watchdog fallback, process reuse,
and the market-list ordering law (sells, then buys, then hires)."""

from __future__ import annotations

from typing import Any

import pytest
from agent import dispatch, plan, policy
from agent.constants import (
    LAND_ORDER,
    PASTURE_REFERENCE_QUADRANTS,
    QUADRANTS,
    STRAWBERRY_REFERENCE_QUADRANTS,
    melon_tiles,
    pasture_tiles,
    strawberry_tiles,
    target_tiles,
)
from agent.policy import PolicyConfig, make_policy
from agent.shell import pass_action
from viewfactory import built_pasture, make_view, plant
from viewfactory import pasture as animal_tile


def _quadrant_of(x: int, y: int) -> str:
    return ("N" if y < 5 else "S") + ("W" if x < 5 else "E")


def _board(unlocked: tuple[str, ...]) -> list[list[Any]]:
    unlocked_set = set(unlocked)
    return [
        [None if _quadrant_of(x, y) in unlocked_set else "LOCKED" for x in range(10)]
        for y in range(10)
    ]


def raw_obs(
    *, step: int = 0, money: float = 3000.0, unlocked_quadrants: tuple[str, ...] = ("NW",)
) -> dict[str, Any]:
    """A minimal engine-shaped observation for player 0 on a fresh farm."""
    tiles = _board(unlocked_quadrants)
    farm = {
        "money": money,
        "tiles": tiles,
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": list(unlocked_quadrants),
        "hires_today": 0,
    }
    other = {
        "money": money,
        "tiles": [row[:] for row in tiles],
        "farmer": [4, 4],
        "hands": [],
        "unlocked_quadrants": list(unlocked_quadrants),
        "hires_today": 0,
    }
    return {
        "step": step,
        "player": 0,
        "farms": [farm, other],
        "private": {"seeds": {"WHEAT": 0}, "shed": {}, "inventories": [{}]},
        "market": {
            "prices": {"WHEAT": 25.0, "EGG": 50.0, "FERTILIZER": 100.0},
            "inventory": {"WHEAT": 10000, "EGG": 10000, "FERTILIZER": 10000},
        },
        "town": {"unlocked_shops": []},
        "day": step // 24,
        "hour": step % 24,
        "remainingOverageTime": 60,
    }


def test_clone_front_run_advances_a_pressured_melon_sale() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    own_tiles = obs["farms"][0]["tiles"]
    opponent_tiles = obs["farms"][1]["tiles"]
    own_tiles[0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": 0,
        "planted_day": 0,
    }
    opponent_tiles[0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": 6,
        "planted_day": 0,
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert ["SELL", "MELON", 2] in action["market"]


def test_clone_front_run_malformed_opponent_tiles_fail_closed() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["tiles"] = [7]
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


def test_clone_front_run_malformed_opponent_yield_fails_closed() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": "not-public-yield",
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


def test_clone_front_run_boolean_opponent_yield_fails_closed() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": True,
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


def test_clone_front_run_malformed_opponent_quadrants_fail_closed() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["unlocked_quadrants"] = [7]
    obs["farms"][1]["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": 6,
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


def test_clone_front_run_is_active_when_policy_config_is_omitted() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": 6,
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy()(obs)

    assert ["SELL", "MELON", 2] in action["market"]


def test_clone_front_run_rejects_dissimilar_opponent() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    for x in range(5):
        obs["farms"][1]["tiles"][0][x] = {
            "kind": "PLANT",
            "crop": "MELON" if x == 0 else "WHEAT",
            "yield_units": 6 if x == 0 else 0,
        }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


def test_clone_front_run_requires_public_yield_for_matching_product() -> None:
    obs = raw_obs(step=6, unlocked_quadrants=("NW",))
    obs["farms"][1]["tiles"][0][0] = {
        "kind": "PLANT",
        "crop": "MELON",
        "yield_units": 0,
    }
    obs["farms"][1]["tiles"][0][1] = {
        "kind": "PLANT",
        "crop": "WHEAT",
        "yield_units": 4,
    }
    obs["private"]["shed"] = {"MELON": 12}
    obs["market"]["prices"]["MELON"] = 100.0

    action = make_policy(policy_config=PolicyConfig(clone_front_run=True))(obs)

    assert not any(order[:2] == ["SELL", "MELON"] for order in action["market"])


# --- Shipped defaults must match the gated ranch reshape (kaggriculture#59) -


def test_default_valve_thresholds_are_the_gated_pair() -> None:
    """The two-tier shed valve's thresholds are gated numbers, and until now
    nothing pinned them -- unlike the herd and the wheat cap.

    valve_soft_threshold was moved 55 -> 35 on head-to-head evidence: 0.690 at
    n=100 (band 838000) and 349-151 = 0.698, Wilson ci_lower 0.6564, at n=250
    (band 839000) against frozen:m3c_hml20_96d8b41. The knob is steep AND
    signed, not a plateau -- the same screen's opposite arm
    (valve_soft_threshold=70) scored 0.130 -- so drifting this value is not a
    small mistake in either direction.

    The ordering assertion is the load-bearing one. _valve_tier tests
    `>= hard` before `>= soft`, so any config with soft >= hard collapses the
    tier-1 band to empty and silently makes valve_soft_cap a no-op. That is a
    configuration that still runs, still passes every other test, and quietly
    disables a whole tier of the M2c valve.
    """
    config = PolicyConfig()
    assert config.valve_soft_threshold == 35
    assert config.valve_hard_threshold == 85
    assert config.valve_soft_threshold == policy.VALVE_SOFT_THRESHOLD
    assert config.valve_hard_threshold == policy.VALVE_HARD_THRESHOLD
    # Tier 1 must be reachable at all: soft strictly below hard.
    assert config.valve_soft_threshold < config.valve_hard_threshold


def test_default_policy_config_matches_the_gated_ranch_reshape() -> None:
    """PolicyConfig()'s defaults ARE the shipped ranch, gated against the
    full opponent roster on identical seeds (~24,000 games): 6 cow / 4 sheep
    beat the shipped 6 cow / 9 sheep in all 11 roster matchups on median
    money, with the best worst-case win rate (0.205 vs meta-clone, where 6/9
    scores 0.000). These four numbers are that gated configuration -- if
    someone edits a herd constant (COW_TARGET/SHEEP_TARGET) without
    re-gating, this test must fail, not a live match.

    wheat_rush_tiles is the one that silently follows: policy.
    _WHEAT_RUSH_TILES_DEFAULT is computed ONCE AT IMPORT TIME as
    BOARD_SIZE**2 - 1 - MELON_TILE_TARGET - (COW_TARGET + SHEEP_TARGET), so a
    herd-constant edit reshapes the wheat zone too even though nothing here
    references sheep/cow by name: 100 - 1 - 8 - 10 = 81, and 81 is the value
    that was actually gated alongside 6/4.
    """
    config = PolicyConfig()
    assert config.cow_target == 6
    assert config.sheep_target == 4
    assert config.pasture_tile_target == 10
    assert config.wheat_rush_tiles == 81
    assert config.wheat_rush_tiles == policy._WHEAT_RUSH_TILES_DEFAULT


def test_day_zero_opening_orders() -> None:
    # NW-only is 24 target tiles. Pastures are pinned to a fixed NW+NE
    # reference frame (constants.PASTURE_REFERENCE_QUADRANTS), so only the 5
    # of its 10 tiles that happen to fall inside NW are actually reachable
    # (and excluded from wheat) yet; melon's own 8 nearest (computed against
    # the live NW-only state) overlap 4 of those 5. Wheat's day-0 plantable
    # count is therefore 24 - |melon ∪ reachable-pasture| = 24 - 9 = 15.
    # This is a turn-0-only shape: NE unlocks this same turn (below) and the
    # active universe is 49 tiles from the next observation on.
    action = make_policy()(raw_obs(), None)
    market = action["market"]
    assert ["BUY_ANIMAL", "GOOSE", 1] in market
    assert ["BUY_SEED", "MELON", 4] in market
    assert ["BUY_SEED", "WHEAT", 15] in market
    assert market.count(["HIRE"]) == 3
    assert len(market) <= 10


def test_day_zero_flow_emits_exactly_one_buy_land() -> None:
    action = make_policy()(raw_obs(money=3000.0), None)
    assert action["market"].count(["BUY_LAND"]) == 1


def test_watchdog_returns_pass_when_budget_exhausted() -> None:
    ticks = iter([0.0, 100.0])
    policy = make_policy(clock=lambda: next(ticks))
    assert policy(raw_obs(), None) == pass_action()


def test_policy_config_override_shrinks_soft_budget_and_truncates_actions() -> None:
    # An overridden PolicyConfig actually reaches decide(): a zeroed soft
    # budget trips the watchdog on the very first tick, where the default
    # config's much larger budget lets the same observation produce a full
    # opening turn.
    obs = raw_obs()
    default_action = make_policy()(obs, None)
    assert len(default_action["market"]) > 0

    ticks = iter([0.0, 0.1])
    overridden_policy = make_policy(
        clock=lambda: next(ticks), policy_config=PolicyConfig(soft_budget_seconds=0.0)
    )
    assert overridden_policy(obs, None) == pass_action()


def test_step_zero_resets_for_process_reuse() -> None:
    policy = make_policy()
    policy(raw_obs(step=500), None)  # a prior episode's late turn
    fresh = policy(raw_obs(step=0), None)  # runner reused the process
    assert ["BUY_ANIMAL", "GOOSE", 1] in fresh["market"]
    assert fresh["market"].count(["HIRE"]) == 3


def test_market_orders_sells_then_buys_then_hires_teeth_check() -> None:
    """Hires sit last in the market list, so the 10-slot cap always drops
    trailing hires (which self-heal next turn) rather than a sell or buy.
    This scenario overflows the cap (melon's own seed line adds a buy ahead
    of wheat's): if hires were ever placed ahead of buys, the feed buy would
    be one of the ones truncated away instead — this exact-list assertion
    catches that directly, with no monkeypatching of plan_day or dispatch.

    NW + NE is 49 target tiles; 8 of those are the melon zone, so wheat's
    plantable count is 41 -- still above the quota-doubled cap of 20 at day
    3 (plant_quota(3, 49) = 10), so the wheat seed buy is quota-bound either
    way. Melon's own target is min(2 * MELON_PLANT_DAILY_CAP, empty melon
    tiles) = min(4, 8) = 4.

    No BUY_LAND here (M2a reorder): NE is already unlocked so the NE-land
    step no-ops, and SW is deliberately gated behind the animal-purchase
    windows (still open at day 3, both targets unmet with no cows/sheep
    owned) -- proven separately in test_plan.py. One extra HIRE therefore
    survives the cap in its place.
    """
    obs = raw_obs(step=3 * 24, money=6000.0, unlocked_quadrants=("NW", "NE"))
    obs["private"]["shed"] = {"FERTILIZER": 3, "EGG": 2, "WHEAT": 2}
    action = make_policy()(obs, None)
    market = action["market"]

    assert market == [
        ["SELL", "FERTILIZER", 3],  # below the 4/turn cap: exact count, not the SELL_ALL sentinel
        ["SELL", "EGG", 99999],
        ["SELL", "WHEAT", 2],
        ["BUY_ANIMAL", "GOOSE", 1],
        ["BUY_SEED", "MELON", 4],
        ["BUY_SEED", "WHEAT", 20],
        ["BUY_PRODUCT", "WHEAT", 1],
        ["HIRE"],
        ["HIRE"],
        ["HIRE"],
    ]


# --- Animal husbandry wiring (M2a) ------------------------------------------
#
# plan.py/dispatch.py's animal parameters are unit-tested against hand-built
# values directly; these tests instead exercise the glue in policy.py that
# *computes* those values (cows/sheep owned, empty-built-pasture count,
# placed-animal count) from a raw engine-shaped observation.


def test_animal_buy_is_gated_by_real_empty_pasture_count_on_the_board() -> None:
    unlocked = ("NW", "NE")
    obs = raw_obs(step=5 * 24, money=10000.0, unlocked_quadrants=unlocked)
    zone = pasture_tiles(unlocked)
    px, py = zone[0]
    obs["farms"][0]["tiles"][py][px] = built_pasture()  # exactly one empty built pasture
    action = make_policy()(obs, None)
    animal_buys = [o for o in action["market"] if o[0] == "BUY_ANIMAL" and o[1] in ("COW", "SHEEP")]
    total_bought = sum(o[2] for o in animal_buys)
    # Capped by the single empty pasture, even though both the 2/turn cap and
    # the $10k budget would otherwise allow more.
    assert total_bought == 1


def test_eight_placed_animals_add_a_husbandry_hand() -> None:
    unlocked = ("NW", "NE", "SW", "SE")
    obs = raw_obs(step=10 * 24, money=0.0, unlocked_quadrants=unlocked)
    obs["farms"][0]["hires_today"] = 12  # base target for 99 tiles is round(99/8) == 12
    zone = pasture_tiles(unlocked)
    for x, y in zone[:8]:
        obs["farms"][0]["tiles"][y][x] = animal_tile(fed_today=True, cared_today=True)
    action = make_policy()(obs, None)
    # target 13 (12 base + 1 husbandry hand); hires_today already at 12
    assert action["market"].count(["HIRE"]) == 1


def test_unfed_placed_animal_gets_fed_via_the_full_policy() -> None:
    unlocked = ("NW",)
    obs = raw_obs(step=5 * 24, money=3000.0, unlocked_quadrants=unlocked)
    px, py = pasture_tiles(unlocked)[0]
    obs["farms"][0]["tiles"][py][px] = animal_tile(fed_today=False)
    obs["farms"][0]["hands"] = [[px, py]]
    obs["private"]["inventories"] = [{}, {"WHEAT": 2}]
    action = make_policy()(obs, None)
    assert action["hands"][0] == ["FEED"]


def test_placed_animal_keeps_receiving_tasks_after_more_land_unlocks() -> None:
    # Regression (found via the solo probe -- cows dropping 4 -> 2 mid-game,
    # animals stranded unplaced in the shed at day 29): the pasture zone must
    # NOT reshuffle as SW/SE unlock later, or an animal placed earlier (while
    # only NW+NE were open) silently stops receiving FEED/HARVEST/CARE the
    # instant a later land purchase reorders target_tiles' nearest-shed-first
    # universe -- it starves and escapes with no signal at all.
    # Index 3, not 0: the nearest-of-all tile happens to survive every
    # reshuffle by coincidence (it's close to *every* shed-access corner);
    # picking one further into the zone actually exercises the reorder.
    early_zone = pasture_tiles(("NW", "NE"))
    px, py = early_zone[3]

    for unlocked in [("NW", "NE"), ("NW", "NE", "SW", "SE")]:
        obs = raw_obs(step=15 * 24, money=3000.0, unlocked_quadrants=unlocked)
        obs["farms"][0]["tiles"][py][px] = animal_tile(fed_today=False)
        obs["farms"][0]["hands"] = [[px, py]]
        obs["private"]["inventories"] = [{}, {"WHEAT": 2}]
        action = make_policy()(obs, None)
        assert action["hands"][0] == ["FEED"], f"unlocked={unlocked}"


def test_wheat_rush_tiles_caps_the_wheat_planting_zone() -> None:
    # wheat_rush_tiles=0 shrinks the wheat zone to nothing, so day-zero's
    # otherwise-guaranteed wheat seed buy (see test_day_zero_opening_orders)
    # never fires -- proof the field actually gates plan_day's wheat line.
    action = make_policy(policy_config=PolicyConfig(wheat_rush_tiles=0))(raw_obs(), None)
    assert not any(order[:2] == ["BUY_SEED", "WHEAT"] for order in action["market"])


# --- M2c: two-tier shed valve + regime-conditional floors (kaggriculture#59) -
#
# The fix for #59: a floor that never yields against a floor-free ranch
# dumper holds a crashed product's backlog forever, backing the shared
# 100-unit shed up to full -- and the engine SILENTLY DESTROYS anything
# DROPped (including the automatic end-of-day sweep) once the shed is full,
# so healthy wheat/egg income evaporates right along with the crashed
# backlog. policy.decide computes a shed-fill valve tier from view.shed each
# turn and owns a pair of WOOL/MILK crash latches (agent.state.
# ProductCrashLatch) that permanently waive the regime floor once a crash
# has run long enough.


def _sells(action: dict[str, object]) -> dict[str, int]:
    market = action["market"]
    assert isinstance(market, list)
    return {o[1]: o[2] for o in market if o[0] == "SELL"}


def test_config_none_and_shed_capacity_100_produce_the_same_valve_tier() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"WOOL": 60}
    obs["market"]["prices"]["WOOL"] = 1.0
    action_none = make_policy()(obs, None)
    action_100 = make_policy()(obs, {"shedCapacity": 100})
    assert _sells(action_none).get("WOOL") == _sells(action_100).get("WOOL")


def test_shed_capacity_scales_the_valve_thresholds() -> None:
    # 30 units in a default 100-unit shed sits below the 55-unit soft
    # threshold (tier 0, floor still applies) -- but the same 30 units in a
    # config-reported 50-unit shed is 60% full, above the scaled 27-unit
    # soft threshold (tier 1, floor waived).
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"WOOL": 30}
    obs["market"]["prices"]["WOOL"] = 1.0  # far under the $200 floor, unlatched

    default_action = make_policy()(obs, None)
    assert "WOOL" not in _sells(default_action)

    scaled_action = make_policy()(obs, {"shedCapacity": 50})
    assert "WOOL" in _sells(scaled_action)


def test_valve_soft_cap_config_reaches_build_orders() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"WOOL": 20}
    obs["market"]["prices"]["WOOL"] = 1.0
    config = PolicyConfig(valve_soft_threshold=10, valve_hard_threshold=999_999, valve_soft_cap=3)
    action = make_policy(policy_config=config)(obs, None)
    assert _sells(action).get("WOOL") == 3


def test_wool_floor_config_reaches_build_orders() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"WOOL": 4}
    obs["market"]["prices"]["WOOL"] = 90.0  # below the $150 default, above an $80 override
    action = make_policy(policy_config=PolicyConfig(wool_floor=80.0))(obs, None)
    assert "WOOL" in _sells(action)


def test_milk_floor_config_reaches_build_orders() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"MILK": 4}
    obs["market"]["prices"]["MILK"] = 50.0  # below the $120 default, above a $40 override
    action = make_policy(policy_config=PolicyConfig(milk_floor=40.0))(obs, None)
    assert "MILK" in _sells(action)


def test_fert_floor_config_reaches_build_orders() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"FERTILIZER": 4}
    obs["market"]["prices"]["FERTILIZER"] = 10.0  # below the $15 default, above a $5 override
    action = make_policy(policy_config=PolicyConfig(fert_floor=5.0))(obs, None)
    assert "FERTILIZER" in _sells(action)


def test_wool_milk_sell_cap_config_reaches_build_orders() -> None:
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"MILK": 20}
    obs["market"]["prices"]["MILK"] = 200.0  # above the floor, unlatched -- normal cap applies
    action = make_policy(policy_config=PolicyConfig(wool_milk_sell_cap=7))(obs, None)
    assert _sells(action).get("MILK") == 7


def test_crash_trigger_config_reaches_the_latch_over_consecutive_turns() -> None:
    # crash_trigger_ticks=2 with a well-under-trigger price latches on the
    # second consecutive turn -- proof wool_crash_trigger/crash_trigger_ticks
    # both reach the ProductCrashLatch instance policy.py owns, not just
    # PolicyConfig's own dataclass fields.
    config = PolicyConfig(wool_crash_trigger=50.0, crash_trigger_ticks=2)
    policy = make_policy(policy_config=config)
    action: dict[str, object] = {}
    for step in (6 * 24, 6 * 24 + 1):
        obs = raw_obs(step=step)
        obs["private"]["shed"] = {"WOOL": 4}
        obs["market"]["prices"]["WOOL"] = 10.0  # below both the trigger and the $200 floor
        action = policy(obs, None)
    assert _sells(action).get("WOOL") == 4


def test_shed_crisis_teeth_check_emergency_valve_forces_wool_milk_sells() -> None:
    """kaggriculture#59's actual defect, reproduced directly: with only a
    static floor, a crashed WOOL/MILK price (here $5, far under either
    floor) holds the backlog forever while the shared 100-unit shed keeps
    filling -- the engine silently destroys anything DROPped at a full shed
    (including the automatic end-of-day sweep), so the farm's other income
    evaporates right along with it. The valve exists to force a sale anyway
    once the shed is dangerously full, regardless of price.

    Reverting the valve (e.g. deleting the ``valve_tier >= 2`` branches in
    ``market.py``) turns the first assertion red: the pre-valve agent held
    WOOL/MILK at any price below their floor, full stop, no matter how full
    the shed got.
    """
    obs = raw_obs(step=6 * 24)
    obs["private"]["shed"] = {"WOOL": 45, "MILK": 45}  # 90 total: past the 85-unit hard threshold
    obs["market"]["prices"]["WOOL"] = 5.0
    obs["market"]["prices"]["MILK"] = 5.0

    action = make_policy()(obs, None)
    sells = _sells(action)
    assert "WOOL" in sells
    assert "MILK" in sells

    # Discrimination: with the valve thresholds pushed out of reach and the
    # crash latches disabled (a $0 trigger price -- a real market price is
    # never below it), the exact same scenario reproduces the pre-fix bug --
    # proof this test is actually exercising the new machinery, not passing
    # regardless of whether the valve/latch exist at all.
    disabled_config = PolicyConfig(
        valve_soft_threshold=999_999,
        valve_hard_threshold=999_999,
        wool_crash_trigger=0.0,
        milk_crash_trigger=0.0,
        crash_trigger_ticks=999_999,
    )
    disabled_action = make_policy(policy_config=disabled_config)(obs, None)
    disabled_sells = _sells(disabled_action)
    assert "WOOL" not in disabled_sells
    assert "MILK" not in disabled_sells


# --- Strawberry zone ------------------------------------------------------


def test_default_config_leaves_the_strawberry_zone_empty() -> None:
    # The whole mechanic ships dormant. Every strawberry code path is
    # unreachable at a zero-tile zone, which is what lets the no-op paired
    # gate below be a real check on the shared dispatch path rather than a
    # check on freshly-added dead code.
    config = PolicyConfig()
    assert config.strawberry_tile_target == 0
    assert strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=0) == []


def test_strawberry_zone_does_not_move_melon_or_pasture() -> None:
    # The zone is offset by the module-level MELON/PASTURE targets, so
    # introducing it (or resizing it) must not slide either existing zone.
    melon_before = melon_tiles(("NW", "NE"))
    pasture_before = pasture_tiles(PASTURE_REFERENCE_QUADRANTS)
    for target in (0, 8, 25):
        zone = strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=target)
        assert len(zone) == target
        assert melon_tiles(("NW", "NE")) == melon_before
        assert pasture_tiles(PASTURE_REFERENCE_QUADRANTS) == pasture_before
        assert not set(zone) & set(pasture_before)


def test_strawberry_zone_is_pinned_to_a_fixed_reference_frame() -> None:
    # A strawberry tile is occupied for seventeen days, so it is mid-cycle
    # across essentially any BUY_LAND. If the zone tracked the live
    # unlocked_quadrants the way melon's does, a land purchase would
    # re-sort target_tiles' nearest-shed-first ordering, drop occupied tiles
    # out of the zone, and they would stop being watered -- two days later
    # the engine turns them into WEEDs, losing the seed and every tick not
    # yet produced, with no signal at all.
    #
    # Assert the drift is REAL before asserting the pin holds: comparing the
    # pinned frame against itself would pass however decide() was wired,
    # which is exactly the tautology this failure mode hides behind.
    fixed = strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=12)
    drifting = strawberry_tiles(("NW", "NE", "SW", "SE"), target=12)
    assert drifting != fixed, (
        "test setup: the zone no longer moves with the unlock state, so this "
        "test can no longer detect decide() passing a live frame"
    )

    # ... and that decide() really passes the fixed frame, which is the
    # wiring the drift above makes load-bearing.
    seen: list[tuple[str, ...]] = []
    real = policy.strawberry_tiles

    def spy(unlocked: tuple[str, ...], target: int = 0) -> list[tuple[int, int]]:
        seen.append(unlocked)
        return real(unlocked, target)

    policy.strawberry_tiles = spy  # type: ignore[assignment]
    try:
        make_policy(policy_config=PolicyConfig(strawberry_tile_target=12))(
            raw_obs(unlocked_quadrants=("NW", "NE", "SW", "SE")), None
        )
    finally:
        policy.strawberry_tiles = real  # type: ignore[assignment]

    assert seen == [STRAWBERRY_REFERENCE_QUADRANTS], (
        f"decide() sized the strawberry zone against {seen}, not the fixed frame"
    )


def _zone_built_by_decide(
    *,
    unlocked: tuple[str, ...],
    target: int = 12,
    frame_live: bool | None = None,
    frame_quadrants: tuple[str, ...] | None = None,
) -> list[tuple[int, int]]:
    """The strawberry zone ``decide()`` actually built, read off its call site.

    ``frame_live=None`` leaves the field off the PolicyConfig entirely, so the
    SHIPPED default is what gets exercised rather than a value the test handed
    back to itself. ``frame_quadrants=None`` does the same for
    ``strawberry_frame_quadrants``.

    Spies on BOTH ``policy.strawberry_tiles`` (the fixed-offset formula,
    used only for the default frame) and ``policy.strawberry_tiles_for_
    frame`` (the melon/pasture-aware formula used for any other frame) --
    decide() calls exactly one of the two, so exactly one spy should ever
    fire.
    """
    overrides: dict[str, Any] = {"strawberry_tile_target": target}
    if frame_live is not None:
        overrides["strawberry_frame_live"] = frame_live
    if frame_quadrants is not None:
        overrides["strawberry_frame_quadrants"] = frame_quadrants

    seen: list[list[tuple[int, int]]] = []
    real_fixed = policy.strawberry_tiles
    real_for_frame = policy.strawberry_tiles_for_frame

    def spy_fixed(unlocked_arg: tuple[str, ...], target: int = 0) -> list[tuple[int, int]]:
        zone = real_fixed(unlocked_arg, target)
        seen.append(zone)
        return zone

    def spy_for_frame(
        frame_arg: tuple[str, ...],
        target_arg: int,
        melon_set: frozenset[tuple[int, int]],
        pasture_set: frozenset[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        zone = real_for_frame(frame_arg, target_arg, melon_set, pasture_set)
        seen.append(zone)
        return zone

    policy.strawberry_tiles = spy_fixed  # type: ignore[assignment]
    policy.strawberry_tiles_for_frame = spy_for_frame  # type: ignore[assignment]
    try:
        make_policy(policy_config=PolicyConfig(**overrides))(
            raw_obs(unlocked_quadrants=unlocked), None
        )
    finally:
        policy.strawberry_tiles = real_fixed  # type: ignore[assignment]
        policy.strawberry_tiles_for_frame = real_for_frame  # type: ignore[assignment]

    assert len(seen) == 1, f"decide() sized the strawberry zone {len(seen)}x, expected once"
    return seen[0]


def _sw_tiles(zone: list[tuple[int, int]]) -> list[tuple[int, int]]:
    sw_x, sw_y = QUADRANTS["SW"]
    return [(x, y) for x, y in zone if x in sw_x and y in sw_y]


def test_strawberry_frame_live_defaults_off_and_leaves_the_shipped_zone_alone() -> None:
    # strawberry_frame_live is a MEASURING INSTRUMENT -- it exists so an A/B
    # can find out whether a live frame changes behavior at all, not because
    # a live frame is wanted. So the only thing standing between it and a
    # silent change to the shipped agent is this default, and the default is
    # asserted against the resulting TILES, not just the flag's value: a
    # flipped default and a mis-wired call site both land here.
    assert PolicyConfig().strawberry_frame_live is False
    zone = _zone_built_by_decide(unlocked=("NW", "NE", "SW", "SE"))
    assert zone == strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=12), (
        "the shipped default moved the strawberry zone off its fixed frame"
    )


def test_strawberry_frame_live_follows_the_unlock_state_once_sw_is_bought() -> None:
    # The other half of the guard: the flag has to actually DO something, or
    # the A/B it was built for measures nothing and reports a clean null.
    # With SW unlocked the live frame re-sorts target_tiles' nearest-shed
    # ordering and pulls SW ground into the zone; the fixed frame never can.
    zone = _zone_built_by_decide(unlocked=("NW", "NE", "SW"), frame_live=True)
    assert _sw_tiles(zone), f"the live frame never reached SW: {zone}"
    assert zone != strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=12)


def test_strawberry_frame_live_is_a_no_op_before_sw_is_bought() -> None:
    # The central finding this instrument is expected to report, pinned so a
    # future reader cannot mistake a null result for a broken flag: while the
    # unlock state IS the reference frame, on and off are the same zone. Any
    # measured difference between the arms therefore has to come from a turn
    # after SW is bought -- there is nowhere else for it to come from.
    live = _zone_built_by_decide(unlocked=("NW", "NE"), frame_live=True)
    fixed = _zone_built_by_decide(unlocked=("NW", "NE"))
    assert live == fixed == strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=12)
    assert not _sw_tiles(live)


# --- strawberry_frame_quadrants: an arbitrary (non-live) frame, e.g. SW ---
#
# strawberry_frame_live answers "does a LIVE frame change behavior"; this
# knob answers a different question -- "what if the (still fixed) frame were
# somewhere other than NW+NE". Measured: a zone in NW+NE displaces $7-10k of
# wheat revenue per game, while SW (bought day 9-10) sits mostly idle
# (20-38 empty tiles on days 10-16). See constants.strawberry_tiles_for_
# frame for the formula this uses once the frame isn't the default.


def test_strawberry_frame_quadrants_default_is_pinned_to_nw_ne() -> None:
    # The only thing standing between this knob and a silent change to the
    # shipped agent is this default -- every existing PolicyConfig() must
    # keep resolving to exactly today's frame.
    assert PolicyConfig().strawberry_frame_quadrants == STRAWBERRY_REFERENCE_QUADRANTS
    assert PolicyConfig().strawberry_frame_quadrants == ("NW", "NE")


def test_strawberry_frame_sw_is_a_full_wheat_noop_before_sw_is_unlocked() -> None:
    # The whole point of relocating the zone: target_tiles(("SW",)) can never
    # overlap NW/NE (the four quadrants partition the board), so -- unlike
    # the default NW+NE frame, which always carves its target out of wheat's
    # own tiles -- a zone parked on SW cannot displace a single wheat tile
    # while SW isn't owned yet. And a "LOCKED" tile (raw_obs'/viewfactory's
    # stand-in for ground outside unlocked_quadrants) is neither None nor a
    # WEED, so _plantable_targets counts none of it either -- no seed gets
    # bought for ground the farmer cannot reach.
    # Direct, literal tile-set proof (not just a downstream count proxy): the
    # raw zone itself must not contain a single NW/NE tile, which is what
    # makes wheat_tiles' "t not in strawberry_set" filter a no-op for every
    # tile in target_tiles(("NW", "NE")) -- the exact mechanism, not just its
    # observable effect on the seed line below.
    zone = _zone_built_by_decide(unlocked=("NW", "NE"), target=25, frame_quadrants=("SW",))
    assert set(zone).isdisjoint(target_tiles(("NW", "NE"))), (
        f"the SW-framed zone overlapped NW/NE tiles: {zone}"
    )

    shipped = make_policy()(raw_obs(unlocked_quadrants=("NW", "NE"), money=5000.0), None)
    sw_frame = make_policy(
        policy_config=PolicyConfig(strawberry_frame_quadrants=("SW",), strawberry_tile_target=25)
    )(raw_obs(unlocked_quadrants=("NW", "NE"), money=5000.0), None)

    assert not any(o[:2] == ["BUY_SEED", "STRAWBERRY"] for o in sw_frame["market"]), (
        f"bought strawberry seed for an unreachable SW zone: {sw_frame['market']}"
    )
    assert _wheat_seed_qty(sw_frame["market"]) == _wheat_seed_qty(shipped["market"]), (
        "an unreachable SW zone still displaced wheat's NW+NE seed line"
    )


def test_strawberry_frame_sw_stays_inside_sw_once_sw_is_unlocked() -> None:
    zone = _zone_built_by_decide(unlocked=("NW", "NE", "SW"), target=20, frame_quadrants=("SW",))
    assert zone, "expected a non-empty zone once SW is unlocked"
    assert _sw_tiles(zone) == zone, f"the SW-framed zone reached outside SW: {zone}"


def test_strawberry_frame_sw_buys_seed_once_sw_is_unlocked() -> None:
    obs = raw_obs(step=10 * 24, unlocked_quadrants=("NW", "NE", "SW"), money=50000.0)
    action = make_policy(
        policy_config=PolicyConfig(strawberry_frame_quadrants=("SW",), strawberry_tile_target=20)
    )(obs, None)
    bought = next((o for o in action["market"] if o[:2] == ["BUY_SEED", "STRAWBERRY"]), None)
    assert bought is not None and bought[2] > 0, (
        f"expected a STRAWBERRY seed buy once SW is unlocked, got {action['market']}"
    )


def test_default_frame_zone_matches_todays_formula_at_every_target_and_unlock_state() -> None:
    """Step-2 equivalence proof for the DEFAULT frame: decide() must keep
    routing STRAWBERRY_REFERENCE_QUADRANTS to the untouched, fixed-offset
    ``strawberry_tiles`` -- never to the new melon/pasture-aware
    ``strawberry_tiles_for_frame`` -- at every target 0..31, under every
    unlocked-quadrant state the agent can reach.

    Not the same claim as "the two formulas agree" --
    test_constants.py's test_the_general_formula_disagrees_with_the_
    default_frame_formula_once_sw_unlocks proves they do NOT, across most of
    this same grid. What must stay true is narrower: which function
    decide() calls for this one frame.
    """
    states = [
        ("NW",),
        ("NW", "NE"),
        ("NW", "NE", "SW"),
        ("NW", "NE", "SE"),
        ("NW", "NE", "SW", "SE"),
    ]
    for unlocked in states:
        for target in range(32):
            actual = _zone_built_by_decide(unlocked=unlocked, target=target)
            expected = strawberry_tiles(STRAWBERRY_REFERENCE_QUADRANTS, target=target)
            assert actual == expected, (
                f"unlocked={unlocked} target={target}: decide() built {actual}, "
                f"expected today's shipped zone {expected}"
            )


def test_frame_live_keeps_todays_live_formula_at_every_target_and_unlock_state() -> None:
    """``strawberry_frame_live=True`` predates ``strawberry_frame_quadrants`` and
    must keep origin/main's behavior: the fixed-offset ``strawberry_tiles``
    over the LIVE unlocked quadrants, in every live state -- never the
    melon/pasture-aware ``strawberry_tiles_for_frame`` that the new knob
    introduced for non-default frames. Keying decide()'s branch on the
    frame's VALUE would route every live state other than exactly NW+NE to
    the new formula and silently change this instrument knob.
    """
    states = [
        ("NW",),
        ("NW", "NE"),
        ("NW", "NE", "SW"),
        ("NW", "NE", "SE"),
        ("NW", "NE", "SW", "SE"),
    ]
    for unlocked in states:
        for target in range(32):
            actual = _zone_built_by_decide(unlocked=unlocked, target=target, frame_live=True)
            expected = strawberry_tiles(unlocked, target=target)
            assert actual == expected, (
                f"frame_live unlocked={unlocked} target={target}: decide() built {actual}, "
                f"expected origin/main's live-frame zone {expected}"
            )


def test_strawberry_tiles_are_carved_out_of_the_wheat_zone() -> None:
    # Both zones claiming the same ground would have wheat's seed line buying
    # seed for tiles strawberry is about to occupy, and the dispatcher
    # charging strawberry plantings against wheat's own daily quota.
    def wheat_qty(market: list[list[Any]]) -> int:
        return next((int(o[2]) for o in market if o[:2] == ["BUY_SEED", "WHEAT"]), 0)

    baseline = make_policy()(raw_obs(), None)["market"]
    with_berry = make_policy(policy_config=PolicyConfig(strawberry_tile_target=6))(raw_obs(), None)[
        "market"
    ]

    assert wheat_qty(with_berry) < wheat_qty(baseline), (
        "wheat still claims every tile it did before the strawberry zone existed"
    )


def test_max_owned_quadrants_threads_from_policy_config_to_the_land_order() -> None:
    """The knob has to reach the emitted market orders, not just plan_day.

    A PolicyConfig field that nothing downstream reads is the classic
    silently-inert knob, so this asserts on the ACTION the engine would see.
    The shipped default (3) refuses SE; lifting the cap to 4 buys it, and
    changes nothing else about the turn.
    """
    obs = raw_obs(step=12 * 24, money=10000.0, unlocked_quadrants=("NW", "NE", "SW"))

    default_action = make_policy()(obs, None)
    assert ["BUY_LAND"] not in default_action["market"]

    uncapped_action = make_policy(policy_config=PolicyConfig(max_owned_quadrants=4))(obs, None)
    assert ["BUY_LAND"] in uncapped_action["market"]
    assert default_action["market"] == [o for o in uncapped_action["market"] if o != ["BUY_LAND"]]


def test_shipped_max_owned_quadrants_is_the_gated_value() -> None:
    """3 is a gated result, not a guess.

    Confirmed at n=64 against all four tapes: money ci_lower +7,233 / +5,991 /
    +7,558 / +7,780, margin ci_lower +5,898 / +7,140 / +7,687 / +5,044, every
    opponent_mean_delta inside +/-3,000, vetoes empty
    (eval/gates/2026-08-23T21-*). Editing this constant without re-gating must
    fail here rather than on the ladder.

    It is strictly less than the board's quadrant count -- the cap really
    binds, and is not a no-op standing in for "buy everything".
    """
    assert PolicyConfig().max_owned_quadrants == 3
    assert PolicyConfig().max_owned_quadrants < len(("NW", *LAND_ORDER))


def _wheat_seed_qty(market: list[Any]) -> int:
    return next((int(o[2]) for o in market if o[:2] == ["BUY_SEED", "WHEAT"]), 0)


def test_wheat_seed_line_sees_the_zone_ground_the_dispatcher_falls_through() -> None:
    # The planner and the dispatcher disagreed about which tiles wheat may use
    # (prereg 2026-08-28). dispatch.py:497-513 already plants WHEAT on an empty
    # strawberry-zone tile once the daily strawberry cap is spent or the
    # planting window has shut -- its own comment calls that "the reservation
    # trap, fixed rather than inherited". But policy.py subtracted the whole
    # zone from wheat's tile set, so the seed line never bought for that ground
    # and the fall-through could not fire against an empty shed.
    #
    # Measured at strawberry_tile_target=31, seed 661200: wheat's
    # plantable_target_tiles sat at exactly 0 for thirteen days while 21 zone
    # tiles were empty, and the farm ran on $0-165 through day 12 because
    # nothing was producing.
    big_zone = make_policy(policy_config=PolicyConfig(strawberry_tile_target=31))(raw_obs(), None)
    assert _wheat_seed_qty(big_zone["market"]) > 0, (
        "a zone large enough to swallow the early board still leaves wheat a seed target of zero"
    )


def test_a_small_zone_leaves_the_wheat_seed_line_alone() -> None:
    # The registered control. The fall-through ground is only what strawberry's
    # own two-day planting horizon cannot reach, so a zone at or under that
    # horizon hands wheat nothing and the two lines stay disjoint by
    # construction -- no tile is counted by both. A small zone must therefore
    # still shrink wheat's claim, exactly as it did before this change.
    baseline = _wheat_seed_qty(make_policy()(raw_obs(), None)["market"])
    small = _wheat_seed_qty(
        make_policy(policy_config=PolicyConfig(strawberry_tile_target=6))(raw_obs(), None)["market"]
    )
    assert small < baseline


# --- _zone_fallthrough_tiles: how far beyond strawberry's own two-day seed
# horizon the wheat fall-through reaches into idle zone ground -------------
#
# _zone_fallthrough_tiles's own docstring: "the horizon here is strawberry's
# own, not the dispatcher's single-turn budget: plan.py sizes the strawberry
# seed line to TWO days of the planting stagger, so anything past 2 * cap is
# ground strawberry's own seed line is not asking for either." That
# arithmetic -- max(0, empty_zone - 2 * cap) -- had no test of its own
# anywhere in this file; test_wheat_seed_line_sees_the_zone_ground_the_
# dispatcher_falls_through above only pins "some ground comes back" (qty >
# 0), not the formula that decides how much. Diagnosis (kaggriculture,
# 2026-09-11): at a 36-tile zone, standing wheat collapses from day 6 (1-8
# tiles, against 8-23 for the shipped agent), starving the early cash that
# buys land and animals -- this pins the exact formula responsible before it
# gains a tuning knob.


def test_zone_fallthrough_tiles_formula_is_pinned_at_todays_multiplier() -> None:
    # 36 idle zone tiles (empty_tiles() leaves every unlocked tile None, so
    # slicing target_tiles gives an exact, controlled empty_zone count) and a
    # daily cap of 11 mirror the diagnosis's own worked example: fall-through
    # hands wheat exactly 36 - 2*11 = 14 tiles today. day=0 keeps this well
    # inside STRAWBERRY_PLANT_CUTOFF_DAY (12), the branch every eval config
    # actually runs under before the planting window shuts.
    zone = frozenset(target_tiles(("NW", "NE"))[:36])
    view = make_view(step=0, unlocked_quadrants=("NW", "NE"))
    config = PolicyConfig(strawberry_plant_daily_cap=11)
    assert policy._zone_fallthrough_tiles(view, config, zone) == 14


# --- zone_fallthrough_multiplier: how far beyond strawberry's own two-day
# seed horizon an eval run can reach into idle zone ground (kaggriculture,
# 2026-09-11) -------------------------------------------------------------
#
# DEFAULT-NEUTRAL: 2 reproduces the fixed boundary _zone_fallthrough_tiles
# has always used (pinned above), so nothing changes until an eval run
# lowers it. See PolicyConfig.zone_fallthrough_multiplier and
# ZONE_FALLTHROUGH_MULTIPLIER for the full diagnosis.


def test_zone_fallthrough_multiplier_default_pins_todays_behavior() -> None:
    # Compared against the module's OWN constant, the same pattern
    # test_goose_min_day_default_pins_todays_behavior above uses, so an edit
    # to ZONE_FALLTHROUGH_MULTIPLIER can never drift silently out of sync
    # with this default.
    config = PolicyConfig()
    assert config.zone_fallthrough_multiplier == 2
    assert config.zone_fallthrough_multiplier == policy.ZONE_FALLTHROUGH_MULTIPLIER


def test_zone_fallthrough_multiplier_lower_values_return_more_ground_to_wheat() -> None:
    # Same 36-tile zone, cap 11 as the pin above -- only the multiplier
    # changes. Lowering it narrows how much of that idle ground stays
    # reserved for strawberry's own two-day seed line and hands the rest to
    # wheat instead: 1 hands back 36 - 11 = 25 (more than the default's 14),
    # and 0 removes the reservation entirely -- every idle zone tile goes to
    # wheat, i.e. the result equals the zone's own size.
    zone = frozenset(target_tiles(("NW", "NE"))[:36])
    view = make_view(step=0, unlocked_quadrants=("NW", "NE"))

    at_default = policy._zone_fallthrough_tiles(
        view, PolicyConfig(strawberry_plant_daily_cap=11), zone
    )
    at_one = policy._zone_fallthrough_tiles(
        view,
        PolicyConfig(strawberry_plant_daily_cap=11, zone_fallthrough_multiplier=1),
        zone,
    )
    at_zero = policy._zone_fallthrough_tiles(
        view,
        PolicyConfig(strawberry_plant_daily_cap=11, zone_fallthrough_multiplier=0),
        zone,
    )

    assert at_default == 14
    assert at_one == 25
    assert at_one > at_default
    assert at_zero == 36
    assert at_zero == len(zone)  # 0 -> every idle zone tile, none held back


def test_zone_fallthrough_multiplier_rejects_out_of_range_values() -> None:
    # 0-10 -- see _MAX_ZONE_FALLTHROUGH_MULTIPLIER for why 10 is a
    # deliberately generous ceiling and 0 is the floor.
    with pytest.raises(ValueError, match="zone_fallthrough_multiplier"):
        PolicyConfig(zone_fallthrough_multiplier=-1)
    with pytest.raises(ValueError, match="zone_fallthrough_multiplier"):
        PolicyConfig(zone_fallthrough_multiplier=11)


def test_zone_fallthrough_multiplier_threads_from_policy_config_to_the_wheat_seed_line() -> None:
    """The knob has to reach plan_day's plantable_target_tiles through
    decide()'s own wheat_tiles + _zone_fallthrough_tiles sum, not just
    _zone_fallthrough_tiles in isolation (the unit tests above cover the
    formula itself) -- mirrors test_ne_land_min_day_threads_from_policy_
    config_and_delays_the_buy_land above.

    Money raised to 10000 (day 0, so plant_quota's 2x cap is
    2*active_tiles -- far above plantable_target_tiles either way -- and the
    seed buy is bounded only by the target and the budget) so the comparison
    isolates the knob rather than an affordability ceiling. Exact quantities
    empirically verified against this fixture before being pinned here.
    """
    obs = raw_obs(step=0, unlocked_quadrants=("NW", "NE"), money=10000.0)
    zone_kwargs: dict[str, Any] = {
        "strawberry_tile_target": 36,
        "strawberry_plant_daily_cap": 11,
    }

    default_qty = _wheat_seed_qty(
        make_policy(policy_config=PolicyConfig(**zone_kwargs))(obs, None)["market"]
    )
    assert default_qty == 9

    lower_qty = _wheat_seed_qty(
        make_policy(policy_config=PolicyConfig(**zone_kwargs, zone_fallthrough_multiplier=0))(
            obs, None
        )["market"]
    )
    assert lower_qty == 31
    assert lower_qty > default_qty


# --- strawberry_start_day: the WHOLE mechanic is off before it, not just the
# seed line (diagnosis 2026-09-10) ------------------------------------------
#
# An earlier version of this knob lived inside plan.py's plan_day, gating
# ONLY the BUY_SEED STRAWBERRY line. That left the zone's own land
# RESERVATION -- the strawberry_set carve-out in decide(), below, which
# removes those tiles from wheat_tiles before plan_day ever runs -- in place
# from day 0 regardless of the seed gate. Measured at strawberry_tile_target
# = 31 (8 seeds, band 855000, vs public:sokolovsky-v12, engine 1.32.7,
# turn-by-turn action diff against the shipped agent): wheat seed buys fell
# from 31 to 11 (at strawberry_plant_daily_cap=10) or 19 (at
# wheat_rush_tiles=21), ~17 zone tiles sat empty from day 0 through day 11,
# the day-0 BUY_ANIMAL:COW orders disappeared (2 -> 0), the herd was cut from
# 6 cows by day 5 to 2-3, and the day-8 milk/wool cash takeoff never
# happened. The fix moves the gate to decide()'s own effective-config
# derivation (STRAWBERRY_START_DAY / PolicyConfig.strawberry_start_day,
# above ``make_policy``), so strawberry_tile_target reads as 0 on EVERY
# downstream path before strawberry_start_day -- the zone, wheat_tiles,
# plan_day's own args, dispatch, and the market fertilizer reserve alike --
# not just the seed-buy line.


def _engine_reference_observations(seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Real day-0 and day-7 observations from an actual engine run of TODAY's
    shipped agent (strawberry off) against a "pass" opponent.

    Real, not hand-built: confirmed at seed 777201, the day-7 observation
    this returns has land bought, 17 tiles standing (wheat/melon), 10
    pastures built, and 6 units of FERTILIZER already sitting in the shed --
    so the no-op comparison below actually exercises the zone carve-out, the
    wheat fall-through, dispatch's per-tile task assignment, and the market
    fertilizer reserve, not just an empty board that would pass the
    invariant for uninteresting reasons.

    ``episodeSteps=169`` records steps 0..168 inclusive, so index 168 is the
    first turn of day 7 (168 // 24 == 7, hour 0) -- the same "day's first
    turn" convention ``harness.occupancy``'s census uses, and the freshest
    possible day-7 snapshot (hour 0, before this turn's own actions land).
    """
    from agent.main import agent as shipped_agent
    from kaggle_environments import make as make_env

    env = make_env("kaggriculture", configuration={"seed": seed, "episodeSteps": 169})
    env.run([shipped_agent, "pass"])
    day0 = env.steps[0][0].observation
    day7 = env.steps[168][0].observation
    assert (day0["step"], day0["day"]) == (0, 0)
    assert (day7["step"], day7["day"], day7["hour"]) == (168, 7, 0)
    return day0, day7


def test_strawberry_start_day_is_a_complete_action_noop_before_it() -> None:
    # The WHOLE action object -- farmer, hands, AND market -- not just the
    # seed-buy line, must match the strawberry-off arm at both day 0 and day
    # 7 (still < strawberry_start_day=8). Each comparison below builds a
    # FRESH policy instance per arm per observation (both start with
    # identical, just-initialized trackers/latches/claims), which isolates
    # the single-turn mechanism from any multi-turn trajectory question --
    # that question is what the measured no-op proof at the harness level
    # (money_gate, champion vs frozen pre-feature baseline) covers instead.
    day0_obs, day7_obs = _engine_reference_observations(seed=777201)
    gated_config = PolicyConfig(
        strawberry_tile_target=31, strawberry_plant_daily_cap=10, strawberry_start_day=8
    )
    off_config = PolicyConfig(strawberry_tile_target=0)

    for obs in (day0_obs, day7_obs):
        gated_action = make_policy(policy_config=gated_config)(obs, None)
        off_action = make_policy(policy_config=off_config)(obs, None)
        assert gated_action == off_action, (
            f"day {obs['day']}: gated action diverged from the off arm"
        )


def test_strawberry_activates_once_the_start_day_arrives() -> None:
    # The other half of the invariant: given cash and free land, the gate has
    # to actually open, or "off before start_day" would be trivially true of
    # a knob that never turns anything on.
    obs = raw_obs(step=8 * 24, money=100_000.0, unlocked_quadrants=("NW", "NE"))
    config = PolicyConfig(
        strawberry_tile_target=31, strawberry_plant_daily_cap=10, strawberry_start_day=8
    )
    action = make_policy(policy_config=config)(obs, None)
    assert any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in action["market"]), (
        "strawberry seed line stayed closed at day == strawberry_start_day"
    )


def test_one_policy_instance_activates_strawberry_crossing_the_start_day() -> None:
    # Catches frozen persistent state. Everything the zone/seed decision
    # depends on (strawberry_set, wheat_tiles, the fertilizer reserve, ...)
    # is recomputed fresh every turn straight off view.day, but the
    # trackers/latches and unit_claims closed over by ONE make_policy() call
    # are carried across turns -- if any of that cross-turn state had
    # memoized "the zone is empty" instead of re-deriving it every turn, a
    # policy built once and stepped across the boundary would stay off
    # forever, even though a freshly-built policy at day 8 (as in the test
    # above) would still pass.
    config = PolicyConfig(
        strawberry_tile_target=31, strawberry_plant_daily_cap=10, strawberry_start_day=8
    )
    decide = make_policy(policy_config=config)
    before = decide(raw_obs(step=7 * 24, money=100_000.0, unlocked_quadrants=("NW", "NE")), None)
    assert not any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in before["market"]), (
        "strawberry bought seed before its own start_day"
    )

    after = decide(raw_obs(step=8 * 24, money=100_000.0, unlocked_quadrants=("NW", "NE")), None)
    assert any(order[:2] == ["BUY_SEED", "STRAWBERRY"] for order in after["market"]), (
        "strawberry stayed off after the start-day boundary on a policy instance carried across it"
    )


def test_default_config_keeps_the_strawberry_start_day_at_zero() -> None:
    # Pinned default: strawberry_start_day=0 is "no gate" -- the mechanic
    # reads the configured strawberry_tile_target from turn one, exactly as
    # it did before this knob existed. The measured no-op proof (harness
    # money gate against a frozen pre-feature baseline, not a unit test) is
    # what actually holds the champion byte-identical at this default across
    # a full game; this pins the knob itself so a future edit cannot quietly
    # move it off zero without a fast test noticing first.
    config = PolicyConfig()
    assert config.strawberry_start_day == 0
    assert config.strawberry_start_day == policy.STRAWBERRY_START_DAY


# --- strawberry_plant_priority / strawberry_fert_reserve: fill the zone ---
#
# Diagnosis 2026-09-10 (SW-framed zone, target 25, strawberry_plant_daily_cap
# 10, start day 9; seeds 855000-855001 vs public:sokolovsky-v12): the zone
# plants only ~5 of its 25 tiles by the day-12 cutoff. Two independent
# causes. (1) dispatch.py's PLANT STRAWBERRY task shares PLANT WHEAT/MELON's
# priority tier, so for hours 2-15 of every day, 17-27 nearer NW/NE
# wheat/melon tasks in that same tier claim every idle unit first; the few
# strawberry claims that DO land arrive too late and are deleted by the
# hour-20 cutoff (funnel on days 10-12: 606 tasks generated, 61 claimed, 3
# executed). (2) policy.py sizes build_orders' fert_reserve off
# strawberry_tile_target from strawberry_start_day, withholding up to 25
# FERTILIZER units from sale before a single strawberry tile exists -- day-9
# FERTILIZER sales fall to 0 (shipped: 10-12 units), delaying the SW
# purchase a day past its $2,500 threshold. See test_dispatch.py's
# test_strawberry_plant_priority_is_tunable_not_just_the_module_constant for
# the dispatch-level half of (1).


def test_strawberry_plant_priority_default_is_dispatchs_own_constant() -> None:
    # The only thing standing between this knob and a silent change to the
    # shipped agent is this default -- every existing PolicyConfig() must
    # keep resolving to exactly today's tier. Compared against dispatch's OWN
    # constant, not a literal 3, so an edit to dispatch's hardcoded tier can
    # never drift silently out of sync with this default.
    assert PolicyConfig().strawberry_plant_priority == dispatch.STRAWBERRY_PLANT_PRIORITY


def test_default_config_keeps_the_strawberry_fert_reserve_at_target() -> None:
    assert PolicyConfig().strawberry_fert_reserve == "target"


def test_strawberry_plant_priority_rejects_a_value_outside_dispatchs_five_tiers() -> None:
    # dispatch()'s own priority-class dict is keyed 0..4
    # (tasks_by_priority = {p: [] for p in range(5)}); a priority outside
    # that range would KeyError deep inside a turn the moment a
    # strawberry-zone tile needed planting, instead of failing loudly here
    # at construction.
    with pytest.raises(ValueError, match="strawberry_plant_priority"):
        PolicyConfig(strawberry_plant_priority=5)
    with pytest.raises(ValueError, match="strawberry_plant_priority"):
        PolicyConfig(strawberry_plant_priority=-1)


def test_strawberry_fert_reserve_rejects_an_unknown_value() -> None:
    with pytest.raises(ValueError, match="strawberry_fert_reserve"):
        PolicyConfig(strawberry_fert_reserve="planted_tiles")


def _captured_fert_reserve(config: PolicyConfig, obs: dict[str, Any]) -> int:
    """The exact ``fert_reserve`` value ``decide()`` handed ``build_orders``
    this turn, read off a spy rather than inferred from a sell quantity --
    price/floor/valve-tier gating would otherwise confound the assertion."""
    captured: dict[str, object] = {}
    real = policy.build_orders

    def spy(**kwargs: object) -> list[list[object]]:
        captured["fert_reserve"] = kwargs["fert_reserve"]
        return real(**kwargs)  # type: ignore[arg-type]

    policy.build_orders = spy  # type: ignore[assignment]
    try:
        make_policy(policy_config=config)(obs, None)
    finally:
        policy.build_orders = real  # type: ignore[assignment]
    reserve = captured["fert_reserve"]
    assert isinstance(reserve, int)
    return reserve


def test_strawberry_fert_reserve_target_matches_todays_formula() -> None:
    # "target" is not a new behavior -- it IS today's formula, reserve =
    # strawberry_tile_target, unconditionally (even with zero tiles planted).
    obs = raw_obs(step=10 * 24, unlocked_quadrants=("NW", "NE"))
    config = PolicyConfig(strawberry_tile_target=25, strawberry_fert_reserve="target")
    assert _captured_fert_reserve(config, obs) == 25


def test_strawberry_fert_reserve_planted_counts_standing_strawberry_tiles() -> None:
    obs = raw_obs(step=10 * 24, unlocked_quadrants=("NW", "NE"))
    tiles = obs["farms"][0]["tiles"]
    for x, y in ((0, 0), (1, 0), (2, 0)):
        tiles[y][x] = {
            "kind": "PLANT",
            "crop": "STRAWBERRY",
            "planted_day": 0,
            "watered_today": True,
            "yield_units": 0,
            "fertilized_until_day": -1,
        }
    config = PolicyConfig(strawberry_tile_target=25, strawberry_fert_reserve="planted")
    assert _captured_fert_reserve(config, obs) == 3


def test_strawberry_fert_reserve_planted_sells_like_strawberry_off_before_anything_is_planted() -> (
    None
):
    # The behavioral claim, not just the internal number: a shed holding
    # fertilizer with zero standing strawberry plants must sell it exactly
    # like an agent with the mechanic off altogether -- "planted" only ever
    # withholds units a real tile can actually spend.
    obs = raw_obs(step=10 * 24, unlocked_quadrants=("NW", "NE"), money=50_000.0)
    obs["private"]["shed"] = {"FERTILIZER": 20}
    obs["market"]["prices"]["FERTILIZER"] = 150.0

    off = make_policy(policy_config=PolicyConfig(strawberry_tile_target=0))(obs, None)
    planted_mode = make_policy(
        policy_config=PolicyConfig(strawberry_tile_target=25, strawberry_fert_reserve="planted")
    )(obs, None)

    assert _sells(planted_mode).get("FERTILIZER") == _sells(off).get("FERTILIZER")


# --- Labor knobs (kaggriculture diagnosis, 2026-09-11) ----------------------
#
# SHIPPED agent, all-default PolicyConfig, seeds 855000-855001 vs
# public:sokolovsky-v12: only ~200 of the ~410 wheat plantings plant_quota
# intends actually execute per game. PLANT WHEAT tasks are generated ~7,800
# times, claimed ~740, executed ~200. Three causes, three knobs:
#   max_hires_per_turn   -- plan.MAX_HIRES_PER_TURN rebuilds the morning crew
#                            over 3 hours (units on the farm at hours 0/1/2/3:
#                            1/5/9/11), starving early-day field work.
#   wheat_plant_priority  -- dispatch._field_tasks hardcodes PLANT WHEAT at
#                            the same tier as melon/strawberry/pasture work,
#                            so nearer same-tier tasks starve it.
#   wheat_plant_hour_cutoff -- dispatch._field_tasks stops generating PLANT
#                            WHEAT tasks past hour 20, unconditionally.
#
# Follow-up (2026-09-11): even with the three knobs above tuned, the crew
# itself measures saturated (idle share ~4.7%) -- only ~200 of the ~410
# intended wheat plantings execute. Moving labor toward planting via a higher
# DISPATCH tier/cutoff instead starves watering and raises weeds 1.8-3.2x, so
# the next lever is labor SUPPLY, not dispatch priority: extra_hands (below)
# hires above plan.py's tile-based hands_target, unconditionally. It has no
# prior hardcoded behavior to reproduce (there was never an implicit "extra
# hands" term before this knob existed), so its default is a bare 0 rather
# than a module constant -- pinned below the same way.


def test_labor_knob_defaults_pin_todays_constants() -> None:
    # The only thing standing between these four knobs and a silent change to
    # the shipped agent is this test -- every existing PolicyConfig() must keep
    # resolving to exactly today's hardcoded behavior. Compared against the
    # modules' OWN constants, not bare literals, so an edit to either hardcoded
    # value can never drift silently out of sync with these defaults.
    config = PolicyConfig()
    assert config.max_hires_per_turn == 4
    assert config.max_hires_per_turn == plan.MAX_HIRES_PER_TURN
    assert config.wheat_plant_priority == 3
    assert config.wheat_plant_priority == dispatch.WHEAT_PLANT_PRIORITY
    assert config.wheat_plant_hour_cutoff == 20
    assert config.wheat_plant_hour_cutoff == dispatch.WHEAT_PLANT_HOUR_CUTOFF
    assert config.extra_hands == 0


def test_labor_knobs_reject_out_of_range_values() -> None:
    # max_hires_per_turn: 1..10 (0 disables hiring outright; above 10 can never
    # place more HIREs than market.MAX_ORDERS has slots for in a single turn,
    # so it can never mean anything beyond 10).
    with pytest.raises(ValueError, match="max_hires_per_turn"):
        PolicyConfig(max_hires_per_turn=0)
    with pytest.raises(ValueError, match="max_hires_per_turn"):
        PolicyConfig(max_hires_per_turn=11)

    # wheat_plant_priority: dispatch()'s own priority-class dict is keyed 0..4
    # (tasks_by_priority = {p: [] for p in range(5)}); a value outside that
    # range would KeyError deep inside a turn instead of failing here, at
    # construction -- the same reasoning strawberry_plant_priority already
    # uses.
    with pytest.raises(ValueError, match="wheat_plant_priority"):
        PolicyConfig(wheat_plant_priority=5)
    with pytest.raises(ValueError, match="wheat_plant_priority"):
        PolicyConfig(wheat_plant_priority=-1)

    # wheat_plant_hour_cutoff: 0..23, the valid range of view.hour.
    with pytest.raises(ValueError, match="wheat_plant_hour_cutoff"):
        PolicyConfig(wheat_plant_hour_cutoff=-1)
    with pytest.raises(ValueError, match="wheat_plant_hour_cutoff"):
        PolicyConfig(wheat_plant_hour_cutoff=24)


def test_max_hires_per_turn_threads_from_policy_config_to_the_market_list() -> None:
    """The knob has to reach the emitted market orders, not just plan_day.

    money=0.0 makes every OTHER buy line unaffordable (see plan.py: goose,
    land, seeds, and animals all gate on ``budget >= price``), so the market
    list is pure HIRE orders with nothing else competing for the 10-slot cap
    -- isolating the knob's effect from the truncation behavior documented on
    the field itself (see the next test).
    """
    obs = raw_obs(step=12 * 24, money=0.0, unlocked_quadrants=("NW", "NE", "SW", "SE"))

    default_action = make_policy()(obs, None)
    assert default_action["market"] == [["HIRE"]] * 4  # hands_target 12, MAX_HIRES_PER_TURN=4

    overridden_action = make_policy(policy_config=PolicyConfig(max_hires_per_turn=10))(obs, None)
    assert overridden_action["market"] == [["HIRE"]] * 10


def test_hires_beyond_the_market_order_cap_are_dropped_not_deferred() -> None:
    """market.MAX_ORDERS=10 caps the WHOLE per-turn list (sells, then buys,
    then HIRE last -- see policy.decide's "Buys first, hires last" comment),
    so a busy turn's sells/buys can crowd HIRE orders out of that same turn
    even with max_hires_per_turn=10 asking for all 10. They are silently
    DROPPED by ``orders[:MAX_ORDERS]``, not moved to a later slot -- and
    since plan_day recomputes ``hands_target - hires_today`` fresh every
    turn, the shortfall is simply asked for again next turn rather than
    queued anywhere.
    """
    obs = raw_obs(step=3 * 24, money=6000.0, unlocked_quadrants=("NW", "NE"))
    obs["private"]["shed"] = {"FERTILIZER": 3, "EGG": 2, "WHEAT": 2}

    action = make_policy(policy_config=PolicyConfig(max_hires_per_turn=10))(obs, None)
    market = action["market"]

    assert len(market) == 10
    hires = market.count(["HIRE"])
    assert 0 < hires < 10, (
        f"expected the busy turn's sells/buys to crowd out some of the 10 requested "
        f"hires, got {hires} HIRE orders in {market}"
    )


# --- extra_hands: labor SUPPLY knob (kaggriculture diagnosis, 2026-09-11 --
# continuation of the labor knobs above) --------------------------------------


def test_extra_hands_default_is_zero() -> None:
    # DEFAULT-NEUTRAL by construction: extra_hands has no prior hardcoded
    # behavior to reproduce, so 0 is a bare literal, not a module constant --
    # also pinned inside test_labor_knob_defaults_pin_todays_constants
    # alongside the other three labor knobs.
    assert PolicyConfig().extra_hands == 0


def test_extra_hands_rejects_out_of_range_values() -> None:
    # 0..5: the engine itself has no cap on hands (just a rising Fibonacci
    # hire cost within a day), so the ceiling here is a deliberately
    # conservative guard against a runaway CLI override, not a modeled market
    # limit -- the same reasoning as every other __post_init__ bound above.
    with pytest.raises(ValueError, match="extra_hands"):
        PolicyConfig(extra_hands=-1)
    with pytest.raises(ValueError, match="extra_hands"):
        PolicyConfig(extra_hands=6)


def test_extra_hands_threads_from_policy_config_to_the_market_list() -> None:
    """extra_hands has to reach the emitted market orders through decide()'s
    plan_day call, not just plan_day in isolation (test_plan.py's
    test_extra_hands_raises_the_hands_target_by_exactly_two covers the
    formula itself) -- mirrors test_max_hires_per_turn_threads_from_policy_
    config_to_the_market_list above.

    max_hires_per_turn=10 is set on BOTH arms so the comparison isolates
    extra_hands's own effect from that separate cap; money=0.0 makes every
    other buy line unaffordable (see that test's own docstring), so the
    market list is pure HIRE orders.
    """
    obs = raw_obs(step=0, money=0.0, unlocked_quadrants=("NW",))

    baseline_action = make_policy(policy_config=PolicyConfig(max_hires_per_turn=10))(obs, None)
    assert baseline_action["market"] == [["HIRE"]] * 3  # hands_target 3 (HANDS_MIN)

    overridden_action = make_policy(
        policy_config=PolicyConfig(max_hires_per_turn=10, extra_hands=2)
    )(obs, None)
    assert overridden_action["market"] == [["HIRE"]] * 5  # hands_target 3+2=5


# --- ne_land_min_day / animal_buy_order: opening knobs (kaggriculture,
# 2026-09-11) -----------------------------------------------------------------
#
# Observed strongest public bots (game replays): they own only NW until
# buying NE around day 6, buy about 4 sheep and 1 cow on day 0, and run only
# 0-4 hands early. Both knobs are DEFAULT-NEUTRAL -- plan.py's NE branch
# never had an earliest-day gate (SE already does: SE_LAND_MIN_DAY), and the
# cow-before-sheep order was a hardcoded sequence, not a parameter -- so an
# eval run opts into either arm explicitly.


def test_opening_knob_defaults_pin_todays_behavior() -> None:
    # Compared against the modules' OWN constants, the same pattern
    # test_labor_knob_defaults_pin_todays_constants uses above, so an edit to
    # either hardcoded value can never drift silently out of sync with these
    # defaults.
    config = PolicyConfig()
    assert config.ne_land_min_day == 0
    assert config.ne_land_min_day == plan.NE_LAND_MIN_DAY
    assert config.animal_buy_order == ("COW", "SHEEP")
    assert config.animal_buy_order == plan.ANIMAL_BUY_ORDER


def test_ne_land_min_day_rejects_out_of_range_values() -> None:
    # 0-29: the valid range of view.day across the 30-day game -- the same
    # "loud at construction, not a silent no-op or a crash deep inside a
    # turn" reasoning as every other bound in this class.
    with pytest.raises(ValueError, match="ne_land_min_day"):
        PolicyConfig(ne_land_min_day=-1)
    with pytest.raises(ValueError, match="ne_land_min_day"):
        PolicyConfig(ne_land_min_day=30)


def test_animal_buy_order_rejects_a_non_permutation() -> None:
    with pytest.raises(ValueError, match="animal_buy_order"):
        PolicyConfig(animal_buy_order=("COW", "COW"))
    with pytest.raises(ValueError, match="animal_buy_order"):
        PolicyConfig(animal_buy_order=("COW",))
    with pytest.raises(ValueError, match="animal_buy_order"):
        PolicyConfig(animal_buy_order=("COW", "GOAT"))


def test_animal_buy_order_coerces_a_json_list_to_a_tuple() -> None:
    # JSON has no tuple type, so a CLI --agent-config
    # '{"animal_buy_order": ["SHEEP", "COW"]}' arrives here as a Python list.
    # Mirrors test_agent_config_coerces_a_strawberry_frame_list_to_a_tuple in
    # test_episodes.py, but proved directly at the PolicyConfig constructor.
    config = PolicyConfig(animal_buy_order=["SHEEP", "COW"])  # type: ignore[arg-type]
    assert config.animal_buy_order == ("SHEEP", "COW")
    assert isinstance(config.animal_buy_order, tuple)
    hash(config)  # must not raise TypeError: unhashable type: 'list'


def test_ne_land_min_day_threads_from_policy_config_and_delays_the_buy_land() -> None:
    """The knob has to reach the emitted market orders, not just plan_day
    (test_plan.py's test_ne_land_waits_for_ne_land_min_day_then_buys_on_time
    covers the formula itself) -- mirrors test_max_owned_quadrants_threads_
    from_policy_config_to_the_land_order above.
    """
    obs = raw_obs(money=3000.0)  # day 0 by default (step=0)

    default_action = make_policy()(obs, None)
    assert default_action["market"].count(["BUY_LAND"]) == 1

    delayed_action = make_policy(policy_config=PolicyConfig(ne_land_min_day=6))(obs, None)
    assert ["BUY_LAND"] not in delayed_action["market"]

    on_time_obs = raw_obs(step=6 * 24, money=3000.0)
    on_time_action = make_policy(policy_config=PolicyConfig(ne_land_min_day=6))(on_time_obs, None)
    assert on_time_action["market"].count(["BUY_LAND"]) == 1


def test_animal_buy_order_threads_from_policy_config_to_the_market_list() -> None:
    """animal_buy_order has to reach the emitted market orders through
    decide()'s plan_day call, not just plan_day in isolation
    (test_plan.py's test_animal_buy_order_reorders_sheep_before_cows covers
    the formula itself) -- mirrors test_max_owned_quadrants_threads_from_
    policy_config_to_the_land_order above.
    """
    unlocked = ("NW", "NE")
    obs = raw_obs(step=3 * 24, money=10000.0, unlocked_quadrants=unlocked)
    zone = pasture_tiles(unlocked)
    for x, y in zone[:2]:  # 2 empty built pastures -- matches ANIMAL_BUY_CAP_PER_TURN
        obs["farms"][0]["tiles"][y][x] = built_pasture()

    default_action = make_policy()(obs, None)
    assert ["BUY_ANIMAL", "COW", 2] in default_action["market"]
    assert not any(o[:2] == ["BUY_ANIMAL", "SHEEP"] for o in default_action["market"])

    overridden_action = make_policy(policy_config=PolicyConfig(animal_buy_order=("SHEEP", "COW")))(
        obs, None
    )
    assert ["BUY_ANIMAL", "SHEEP", 2] in overridden_action["market"]
    assert not any(o[:2] == ["BUY_ANIMAL", "COW"] for o in overridden_action["market"])


# --- goose_min_day: defer the goose to keep the pre-NE pasture slots
# (kaggriculture, 2026-09-11) --------------------------------------------------
#
# Observed strongest public bots (game replays): they never buy a goose and
# keep the 5 NW pasture slots for 4 sheep + 1 cow before NE is bought -- our
# goose takes one of those slots, so a sheep-first opening stalls at 3 sheep.
# DEFAULT-NEUTRAL, the same reasoning as ne_land_min_day above: the goose
# branch never had an earliest-day gate before this knob existed (it buys the
# instant cash allows, including turn 0), so 0 reproduces that exactly. An
# eval run sets this to the NE day (e.g. 6) to defer the goose.


def test_goose_min_day_default_pins_todays_behavior() -> None:
    # Compared against plan.py's OWN constant, the same pattern
    # test_opening_knob_defaults_pin_todays_behavior above uses, so an edit to
    # the hardcoded value can never drift silently out of sync with this
    # default.
    config = PolicyConfig()
    assert config.goose_min_day == 0
    assert config.goose_min_day == plan.GOOSE_MIN_DAY


def test_goose_min_day_rejects_out_of_range_values() -> None:
    # 0-29: the valid range of view.day across the 30-day game -- the same
    # bound and "loud at construction" reasoning ne_land_min_day uses above.
    with pytest.raises(ValueError, match="goose_min_day"):
        PolicyConfig(goose_min_day=-1)
    with pytest.raises(ValueError, match="goose_min_day"):
        PolicyConfig(goose_min_day=30)


def test_goose_min_day_threads_from_policy_config_and_delays_the_buy_goose() -> None:
    """The knob has to reach the emitted market orders, not just plan_day
    (test_plan.py's test_goose_waits_for_goose_min_day_then_buys_on_time
    covers the formula itself) -- mirrors test_ne_land_min_day_threads_
    from_policy_config_and_delays_the_buy_land above.
    """
    obs = raw_obs(money=3000.0)  # day 0 by default (step=0)

    default_action = make_policy()(obs, None)
    assert default_action["market"].count(["BUY_ANIMAL", "GOOSE", 1]) == 1

    delayed_action = make_policy(policy_config=PolicyConfig(goose_min_day=6))(obs, None)
    assert ["BUY_ANIMAL", "GOOSE", 1] not in delayed_action["market"]

    on_time_obs = raw_obs(step=6 * 24, money=3000.0)
    on_time_action = make_policy(policy_config=PolicyConfig(goose_min_day=6))(on_time_obs, None)
    assert on_time_action["market"].count(["BUY_ANIMAL", "GOOSE", 1]) == 1


# --- rescue_water: water a plant the day before the engine kills it --------
#
# dispatch.py's own rescue_water tests (test_dispatch.py) cover the
# mechanism; these two prove the knob actually threads PolicyConfig ->
# make_policy -> dispatch(), the same "defaults pin the module constant" /
# "threading reaches the real action" pair every other knob above gets.


def test_rescue_water_default_pins_todays_behavior() -> None:
    # Compared against the module's OWN constant, the same pattern
    # test_opening_knob_defaults_pin_todays_behavior uses above, so an edit
    # to dispatch.RESCUE_WATER can never drift silently out of sync with
    # this default.
    config = PolicyConfig()
    assert config.rescue_water is False
    assert config.rescue_water == dispatch.RESCUE_WATER


def test_rescue_water_threads_from_policy_config_to_the_hands_action() -> None:
    """The knob has to reach the emitted hand actions through decide()'s
    dispatch() call, not just dispatch() in isolation (test_dispatch.py's
    rescue_water tests cover the mechanism itself) -- mirrors
    test_ne_land_min_day_threads_from_policy_config_and_delays_the_buy_land
    above.

    cow/sheep/melon targets zeroed so the only task on the whole board is
    the one on our tile: at their real defaults, most of target_tiles(("NW",))
    falls inside the melon/pasture zone, and an empty pasture tile emits an
    unconditional (no-seed) BUILD_PASTURE task -- a real P3 task elsewhere
    on the board that would pull an idle hand toward it and mask the PASS
    this test means to pin. Wheat's own PLANT tasks need no such zeroing:
    raw_obs's default 0 WHEAT seeds already blocks every one of them.

    Uses target_tiles(...)[1], not [0]: raw_obs's farmer always starts at
    (4, 4), which IS target_tiles(("NW",))[0] -- placing our tile and hand
    there too would let the farmer (checked first, at the same position)
    claim the rescue task ahead of the hand, since only one unit can claim
    a given tile.
    """
    unlocked = ("NW",)
    px, py = target_tiles(unlocked)[1]
    obs = raw_obs(step=5 * 24, money=3000.0, unlocked_quadrants=unlocked)
    # age 1: the calendar's own deliberate gap day, with one miss already
    # banked (consecutive_unwatered=1) -- the same fixture test_dispatch.py's
    # test_rescue_water_on_rescues_wheat_the_night_it_would_weed uses.
    obs["farms"][0]["tiles"][py][px] = plant(
        planted_day=4, watered_today=False, consecutive_unwatered=1
    )
    obs["farms"][0]["hands"] = [[px, py]]
    obs["private"]["inventories"] = [{}, {}]
    isolated = {"cow_target": 0, "sheep_target": 0, "melon_tile_target": 0}

    default_action = make_policy(policy_config=PolicyConfig(**isolated))(obs, None)
    assert default_action["hands"][0] == ["PASS"]

    overridden_action = make_policy(policy_config=PolicyConfig(**isolated, rescue_water=True))(
        obs, None
    )
    assert overridden_action["hands"][0] == ["WATER"]
