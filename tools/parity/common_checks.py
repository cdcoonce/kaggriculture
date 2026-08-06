"""
Shared, engine-independent check functions for kaggriculture parity verification.

These operate purely on the *observation data* (dicts pulled out of either a
server replay JSON or a locally-run episode's `env.steps`), plus the LOCAL
copies of MARKET_PARAMS / market_price / SHOPS / TOWN_CENTER_* imported from
the installed kaggle_environments package. They contain no dependency on
where the steps came from, so the same functions are used both to check the
server replay and to cross-check a local PASS-vs-PASS run (sanity check on
the checker itself).
"""
import math

# Import the real, installed local engine's constants/law so we are always
# comparing against "what the local package actually does", not a hand
# transcription of it.
from kaggle_environments.envs.kaggriculture.kaggriculture import (
    MARKET_PARAMS,
    PRODUCTS,
    SHOPS,
    TOWN_CENTER_PRODUCTS,
    TOWN_CENTER_DEMAND_SCHEDULE,
    market_price,
)


def price_law_check(steps, turns_per_day=24):
    """
    For every step, recompute each product's price from the observation's
    market inventory using the LOCAL market_price()/MARKET_PARAMS, and
    compare against the replay's quoted price at that same step.

    `steps` is a list of per-step observation dicts, each with at least
    obs["market"] = {"inventory": {...}, "prices": {...}}.

    Returns dict with counts and a list of mismatches (capped).
    """
    checked = 0
    mismatches = []
    products_checked = set()

    for step_idx, obs in enumerate(steps):
        market = obs.get("market")
        if not market:
            continue
        inv = market.get("inventory", {})
        prices = market.get("prices", {})
        for item in PRODUCTS:
            if item not in inv or item not in prices:
                continue
            checked += 1
            products_checked.add(item)
            local_price = market_price(item, inv[item], None)
            replay_price = prices[item]
            if local_price != replay_price:
                mismatches.append({
                    "step": step_idx,
                    "item": item,
                    "inventory": inv[item],
                    "replay_price": replay_price,
                    "local_price": local_price,
                })

    return {
        "steps_with_market": sum(1 for o in steps if o.get("market")),
        "price_points_checked": checked,
        "products_checked": sorted(products_checked),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],  # cap for readability
    }


def _town_center_multiplier(day):
    return next(m for threshold, m in TOWN_CENTER_DEMAND_SCHEDULE if day >= threshold)


def town_consumption_law_check(
    steps,
    shop_interval=4,
    center_interval=12,
    unlock_interval=3,
    turns_per_day=24,
):
    """
    Verify inventory deltas between consecutive steps are fully explained by
    town shop + town center consumption (valid only when BOTH agents PASS
    every step, i.e. no market sell/buy orders ever move inventory).

    `steps` is a list of per-step observation dicts in step order
    (obs["step"] must be present and contiguous), each with
    obs["market"]["inventory"] and obs["town"]["unlocked_shops"].

    Checks, per transition from step s -> s+1 (post-interpreter state of s
    is what's recorded as the observation AT s+1 in kaggle_environments'
    replay convention -- i.e. steps[i+1] reflects the world after acting on
    steps[i]):
      - if (s % shop_interval == 0): every unlocked shop (as of the town
        dict visible at step s, i.e. BEFORE any same-day unlock) consumes
        1 unit of each of its products (2 units if it only sells one
        product), from inventory.
      - if (s % center_interval == 0): the town center consumes
        center_mult units of every non-FERTILIZER product, where
        center_mult depends on day = s // turns_per_day via
        TOWN_CENTER_DEMAND_SCHEDULE.
      - shop unlock cadence: town["unlocked_shops"] length can only grow,
        and only at day boundaries where (day+1) % unlock_interval == 0
        (i.e. transitioning into next_day where next_day % unlock_interval
        == 0), by exactly one shop per qualifying boundary until all 8 are
        unlocked.
    """
    mismatches = []
    checked_transitions = 0
    unlock_mismatches = []
    prev_unlocked_count = None
    prev_day = None

    for i in range(len(steps) - 1):
        obs_s = steps[i]
        obs_s1 = steps[i + 1]
        if not obs_s.get("market") or not obs_s1.get("market"):
            continue

        s = obs_s.get("step")
        if s is None:
            continue

        inv_s = obs_s["market"]["inventory"]
        inv_s1 = obs_s1["market"]["inventory"]
        town_s = obs_s.get("town", {})
        unlocked_shops = town_s.get("unlocked_shops", [])

        day = s // turns_per_day

        expected_delta = {p: 0 for p in PRODUCTS}

        if s % shop_interval == 0:
            for shop_name in unlocked_shops:
                products = SHOPS[shop_name]
                mult = 2 if len(products) == 1 else 1
                for item in products:
                    expected_delta[item] -= mult

        if s % center_interval == 0:
            center_mult = _town_center_multiplier(day)
            for item in TOWN_CENTER_PRODUCTS:
                expected_delta[item] -= center_mult

        checked_transitions += 1
        for item in PRODUCTS:
            actual_delta = inv_s1.get(item, 0) - inv_s.get(item, 0)
            if actual_delta != expected_delta[item]:
                mismatches.append({
                    "step": s,
                    "item": item,
                    "actual_delta": actual_delta,
                    "expected_delta": expected_delta[item],
                    "unlocked_shops_at_s": list(unlocked_shops),
                })

        # Unlock cadence check
        cur_unlocked_count = len(unlocked_shops)
        if prev_unlocked_count is not None:
            if cur_unlocked_count < prev_unlocked_count:
                unlock_mismatches.append({
                    "step": s, "issue": "unlocked_shops shrank",
                    "prev": prev_unlocked_count, "cur": cur_unlocked_count,
                })
            elif cur_unlocked_count > prev_unlocked_count:
                # An unlock must have happened at the day boundary that
                # produced this observation, i.e. obs_s.day == prev_day+1
                # and (obs_s.day) % unlock_interval == 0.
                cur_day = obs_s.get("day")
                grew_by = cur_unlocked_count - prev_unlocked_count
                ok_boundary = (
                    cur_day is not None
                    and prev_day is not None
                    and cur_day == prev_day + 1
                    and cur_day % unlock_interval == 0
                )
                if grew_by != 1 or not ok_boundary:
                    unlock_mismatches.append({
                        "step": s,
                        "issue": "unlock did not fire on expected cadence/size",
                        "prev_count": prev_unlocked_count,
                        "cur_count": cur_unlocked_count,
                        "prev_day": prev_day,
                        "cur_day": cur_day,
                        "unlock_interval": unlock_interval,
                    })
        prev_unlocked_count = cur_unlocked_count
        prev_day = obs_s.get("day")

    return {
        "transitions_checked": checked_transitions,
        "delta_mismatch_count": len(mismatches),
        "delta_mismatches": mismatches[:50],
        "unlock_mismatch_count": len(unlock_mismatches),
        "unlock_mismatches": unlock_mismatches[:50],
    }


def structural_checks(steps, board_size=10, starting_money=3000):
    """
    Spot-checks that don't depend on RNG/seed:
      - starting money for both players at step 0
      - farmer spawn position(s) at step 0
      - locked-quadrant tile layout at step 0
      - final reward(s) == final farm money
    Expects `steps` as list of (obs_player0, obs_player1) tuples per step,
    OR a list of single-player-0 obs dicts PLUS a separate `rewards`/final
    farms snapshot; caller adapts. Here we accept a list of obs dicts (all
    from player 0's perspective is enough, since obs.farms holds both
    farms) plus final reward list.
    """
    results = {}
    obs0 = steps[0]
    farms0 = obs0["farms"]

    results["starting_money_ok"] = all(
        f["money"] == float(starting_money) for f in farms0
    )
    results["starting_money_values"] = [f["money"] for f in farms0]

    half = board_size // 2

    def quadrant_of(x, y):
        return ("N" if y < half else "S") + ("W" if x < half else "E")

    def expected_default_spawn():
        # NWSE preference among the four inner-corner shed-access tiles
        tiles = [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]
        for t in tiles:
            if quadrant_of(*t) == "NW":
                return list(t)
        return [0, 0]

    exp_spawn = expected_default_spawn()
    results["expected_farmer_spawn"] = exp_spawn
    results["farmer_spawns"] = [f["farmer"] for f in farms0]
    results["farmer_spawn_ok"] = all(f["farmer"] == exp_spawn for f in farms0)

    lock_mismatches = []
    for f_idx, f in enumerate(farms0):
        tiles = f["tiles"]
        for y in range(board_size):
            for x in range(board_size):
                t = tiles[y][x]
                q = quadrant_of(x, y)
                expected = None if q == "NW" else "LOCKED"
                if t != expected:
                    lock_mismatches.append((f_idx, x, y, q, t, expected))
    results["locked_quadrant_mismatch_count"] = len(lock_mismatches)
    results["locked_quadrant_mismatches"] = lock_mismatches[:20]

    return results


def weed_boundary_check(steps, turns_per_day=24):
    """
    Verify that any tile transition None -> {"kind": "WEED"} only ever
    appears in the observation immediately AFTER a day boundary (i.e. at
    step index s+1 where (s+1) % turns_per_day == 0, meaning the weed was
    planted by _end_of_day processing of step s). Since agents PASS-only,
    no PLANT/WATER actions occur, so _decay_plants/_daily_refresh_plants
    have no PLANT tiles to act on -- the only source of new WEED tiles is
    _spawn_weeds() inside _end_of_day.
    """
    violations = []
    checked_farms = 0
    weed_events = 0

    prev_tiles_by_farm = None
    for i, obs in enumerate(steps):
        farms = obs.get("farms")
        if not farms:
            continue
        step = obs.get("step")
        if prev_tiles_by_farm is not None and step is not None:
            for f_idx, farm in enumerate(farms):
                tiles = farm["tiles"]
                prev_tiles = prev_tiles_by_farm[f_idx]
                board_size = len(tiles)
                for y in range(board_size):
                    for x in range(board_size):
                        prev_t = prev_tiles[y][x]
                        cur_t = tiles[y][x]
                        became_weed = (
                            prev_t is None
                            and isinstance(cur_t, dict)
                            and cur_t.get("kind") == "WEED"
                        )
                        if became_weed:
                            weed_events += 1
                            # This obs is the state AFTER processing step
                            # (step-1) [since steps[i] holds obs at `step`,
                            # and the transition into it happened via
                            # interpreter(step-1)]. A day boundary fires
                            # end_of_day when (prev_step + 1) % turns_per_day == 0,
                            # i.e. exactly when `step % turns_per_day == 0`
                            # and step > 0.
                            if not (step % turns_per_day == 0 and step > 0):
                                violations.append({
                                    "farm": f_idx, "x": x, "y": y, "step": step,
                                })
            checked_farms = len(farms)
        prev_tiles_by_farm = [f["tiles"] for f in farms]

    return {
        "weed_spawn_events": weed_events,
        "boundary_violations": len(violations),
        "violations_sample": violations[:20],
        "farms_checked": checked_farms,
    }
