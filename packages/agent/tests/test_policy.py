"""Policy wiring behavior: opening orders, watchdog fallback, process reuse,
and the market-list ordering law (sells, then buys, then hires)."""

from __future__ import annotations

from typing import Any

from agent import policy
from agent.constants import (
    LAND_ORDER,
    PASTURE_REFERENCE_QUADRANTS,
    STRAWBERRY_REFERENCE_QUADRANTS,
    melon_tiles,
    pasture_tiles,
    strawberry_tiles,
)
from agent.policy import PolicyConfig, make_policy
from agent.shell import pass_action
from viewfactory import built_pasture
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
