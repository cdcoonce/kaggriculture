"""Policy wiring behavior: opening orders, watchdog fallback, process reuse,
and the market-list ordering law (sells, then buys, then hires)."""

from __future__ import annotations

from typing import Any

from agent.constants import pasture_tiles
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


def test_day_zero_opening_orders() -> None:
    # NW-only is 24 target tiles. Pastures are pinned to a fixed NW+NE
    # reference frame (constants.PASTURE_REFERENCE_QUADRANTS), so only the 7
    # of its 15 tiles that happen to fall inside NW are actually reachable
    # (and excluded from wheat) yet; melon's own 8 nearest (computed against
    # the live NW-only state) overlap 4 of those 7. Wheat's day-0 plantable
    # count is therefore 24 - |melon ∪ reachable-pasture| = 24 - 11 = 13.
    # This is a turn-0-only shape: NE unlocks this same turn (below) and the
    # active universe is 49 tiles from the next observation on.
    action = make_policy()(raw_obs(), None)
    market = action["market"]
    assert ["BUY_ANIMAL", "GOOSE", 1] in market
    assert ["BUY_SEED", "MELON", 4] in market
    assert ["BUY_SEED", "WHEAT", 13] in market
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
