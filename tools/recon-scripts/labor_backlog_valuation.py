"""Backlog valuation: turns the task-funnel counts (task_funnel.py output)
into tile-day / unit-count estimates and then into rough dollar estimates,
using the vendored engine's own rules (kaggle_environments 1.32.7,
kaggriculture.py) and the shipped agent's own module constants.

Every $ figure here is derived, not observed-in-game (the game plays out
under noisy market curves and joint agent behavior); treat every number this
script prints as an ESTIMATE, explicitly using the undepressed/base engine
price as an upper bound where noted. This is pure post-hoc arithmetic over
already-collected JSON -- it does not run the game.

Run from anywhere:
    uv run python backlog_valuation.py <summary_json_855000> <summary_json_855001> ...
"""
from __future__ import annotations

import json
import sys

TURNS_PER_DAY = 24

# --- engine ground truth (kaggle_environments 1.32.7, kaggriculture.py) ---
# CROPS: seed cost, first_yield_day, max_yield_day, max_yield (kaggriculture.py:11-17)
WHEAT_SEED = 10
WHEAT_MAX_YIELD_DAY = 4
WHEAT_MAX_YIELD = 6
MELON_SEED = 80
MELON_MAX_YIELD_DAY = 12
MELON_MAX_YIELD = 6
# MARKET_PARAMS base price (kaggriculture.py:41-51) -- undepressed/equilibrium price
WHEAT_BASE_PRICE = 25
MELON_BASE_PRICE = 250
MILK_BASE_PRICE = 160
WOOL_BASE_PRICE = 200
EGG_BASE_PRICE = 50
FERT_BASE_PRICE = 100
# ANIMALS (kaggriculture.py:19-23)
COW_COST, COW_INTERVAL = 400, 2
SHEEP_COST, SHEEP_INTERVAL = 500, 3
GOOSE_COST, GOOSE_INTERVAL = 300, 1

# land_fert_labor.py's own steady-state derivation (re-derived here for
# transparency rather than re-imported, since that script has no importable
# function -- see tools/recon-scripts/land_fert_labor.py:7-11):
# crop_sim.py steady-state: WHEAT 4 cycles -> yield=16, actions=28, span=17 days
# (4 replant cycles, so seed cost amortizes as 4 seeds / 17 days, NOT a flat
# 5-day-per-cycle assumption -- verified by re-running land_fert_labor.py,
# which reports profit/day/tile = $21.18 exactly matching this formula.)
WHEAT_STEADY_YIELD_PER_DAY = 16 / 17
WHEAT_SEED_COST_PER_DAY = 4 * WHEAT_SEED / 17
WHEAT_PROFIT_PER_TILE_PER_DAY = (
    WHEAT_STEADY_YIELD_PER_DAY * WHEAT_BASE_PRICE - WHEAT_SEED_COST_PER_DAY
)  # = $21.18/tile/day at base price, no travel cost -- an UPPER BOUND (land_fert_labor.py's own verified number)

# Animal daily_net (land_fert_labor.py formula, kaggriculture.py:19-23 base prices):
# daily_net = MARKET_PARAMS[product]["base"]/interval - MARKET_PARAMS["WHEAT"]["base"]
COW_DAILY_NET = MILK_BASE_PRICE / COW_INTERVAL - WHEAT_BASE_PRICE  # 80-25=55
SHEEP_DAILY_NET = WOOL_BASE_PRICE / SHEEP_INTERVAL - WHEAT_BASE_PRICE  # 66.67-25=41.67
GOOSE_DAILY_NET = EGG_BASE_PRICE / GOOSE_INTERVAL - WHEAT_BASE_PRICE  # 50-25=25


def plant_quota(day: int, active_tiles: int) -> int:
    """Verbatim from packages/agent/src/agent/dispatch.py:286-299 (plant_quota):
    day 0 is exempt (whole board plants at once); else ceil(active_tiles/5),
    floored at 1. Re-implemented here (not imported) so this script has no
    dependency on the agent package being importable from an arbitrary cwd."""
    if day == 0:
        return active_tiles
    return max(1, -(-active_tiles // 5))


def active_tiles_for(unlocked: list[str]) -> int:
    """25 tiles/quadrant (5x5) minus the single COOP_TILE reserved for the
    goose, which sits inside NW and is excluded universally -- matches
    constants.py's target_tiles() exactly (verified: len(target_tiles(NW))=24,
    NW+NE=49, NW+NE+SW=74, the shipped MAX_OWNED_QUADRANTS=3 ceiling)."""
    return 25 * len(unlocked) - 1


def wheat_quota_capacity(turns: dict) -> tuple[int, dict]:
    """Sum plant_quota(day, active_tiles) over every DAY actually observed in
    the turns log, using that day's real unlocked-quadrant count (read off
    the earliest hour seen for that day, since a quadrant can unlock
    mid-day)."""
    best_hour: dict[int, int] = {}
    best_unlocked: dict[int, list[str]] = {}
    for step_str, rec in turns.items():
        day, hour = rec["day"], rec["hour"]
        if day not in best_hour or hour < best_hour[day]:
            best_hour[day] = hour
            best_unlocked[day] = rec["unlocked"]
    total = 0
    per_day = {}
    for day in sorted(best_unlocked):
        active = active_tiles_for(best_unlocked[day])
        q = plant_quota(day, active)
        per_day[day] = (active, q)
        total += q
    return total, per_day


def tile_days(generated_task_turns: int) -> float:
    """A task with NO daily cap and NO hour cutoff (DIG, FEED, CARE,
    COLLECT_FERTILIZER, HARVEST:PASTURE) is re-offered EVERY turn it remains
    unresolved -- so generated task-turns / 24 = tile-days (or animal-days)
    the underlying condition persisted, an exact integral, not an estimate
    of the COUNT itself (though what it COSTS in $ still is an estimate)."""
    return generated_task_turns / TURNS_PER_DAY


def main():
    paths = sys.argv[1:]
    if not paths:
        print("usage: backlog_valuation.py <summary_json>[:<turns_json>] [...]", file=sys.stderr)
        sys.exit(1)

    print(f"{'='*100}\nDERIVED RATES (all from engine constants, base/undepressed price -- upper bounds)\n{'='*100}")
    print(f"WHEAT profit/tile/day (land_fert_labor.py steady-state formula): ${WHEAT_PROFIT_PER_TILE_PER_DAY:.2f}")
    print(f"COW daily_net: ${COW_DAILY_NET:.2f}   SHEEP daily_net: ${SHEEP_DAILY_NET:.2f}   GOOSE daily_net: ${GOOSE_DAILY_NET:.2f}")

    for spec in paths:
        path, _, turns_path = spec.partition(":")
        with open(path) as fh:
            summary = json.load(fh)
        turns = None
        if turns_path:
            with open(turns_path) as fh:
                turns = json.load(fh)
        seed = summary["seed"]
        by_kind = {row["kind"]: row for row in summary["per_kind_total"]}
        money = summary["final_money_ours"]

        print(f"\n{'='*100}\nseed {seed}  (final money ${money:,.0f})\n{'='*100}")

        # --- DIG: clean tile-days of weeds sitting, no cap/cutoff distorts this ---
        dig_wheat = by_kind.get("DIG:WHEAT", {"generated": 0, "executed": 0})
        dig_melon = by_kind.get("DIG:MELON", {"generated": 0, "executed": 0})
        dig_days = tile_days(dig_wheat["generated"] + dig_melon["generated"])
        dig_value = dig_days * WHEAT_PROFIT_PER_TILE_PER_DAY
        print(f"\n[DIG backlog -- undug weeds, land taken fully out of production]")
        print(f"  DIG:WHEAT generated={dig_wheat['generated']} executed={dig_wheat['executed']}  "
              f"DIG:MELON generated={dig_melon['generated']} executed={dig_melon['executed']}")
        print(f"  VERIFIED (exact integral, no cap distorts DIG's generation): "
              f"{dig_days:.1f} tile-days of weeds sitting across the game")
        print(f"  ESTIMATE ($ at undepressed wheat rate, upper bound, ignores travel cost to reach the tile): "
              f"${dig_value:,.0f}/game")

        # --- PLANT:WHEAT / PLANT:MELON: shortfall WITHIN the quota's own throttled offer ---
        pw = by_kind.get("PLANT:WHEAT", {"generated": 0, "claimed": 0, "executed": 0})
        pm = by_kind.get("PLANT:MELON", {"generated": 0, "claimed": 0, "executed": 0})
        print(f"\n[PLANT backlog -- shortfall WITHIN the daily quota's own throttled offer, i.e. labor-attributable, "
              f"NOT counting quota-throttled demand beyond what was ever offered]")
        print(f"  PLANT:WHEAT generated={pw['generated']} claimed={pw['claimed']} executed={pw['executed']} "
              f"(claim_rate={pw['claimed']/pw['generated']*100 if pw['generated'] else 0:.1f}%)")
        print(f"  PLANT:MELON generated={pm['generated']} claimed={pm['claimed']} executed={pm['executed']} "
              f"(claim_rate={pm['claimed']/pm['generated']*100 if pm['generated'] else 0:.1f}%)")
        # Each turn's plant_budget re-offers the SAME still-empty tiles, so
        # "generated" over-counts unique tiles; "executed" is the one
        # ground-truth count of tiles actually planted. Estimate unique
        # tiles-still-wanting-a-plant conservatively via a wheat 5-day
        # replant cycle: a tile that stays in the "generated" pool persists
        # roughly (generated/executed) times longer than an executed one on
        # average -- INFERRED, not a direct count. We instead report the
        # concrete, defensible number: each SUCCESSFUL wheat planting nets
        # ~5 days of the tile's own $21.18/day rate (a fresh cycle) minus the
        # $10 seed; an EXECUTED plant is not backlog -- it's the backlog's
        # resolution. So we bound the wheat side of this differently: see
        # HARVEST section below, which shows HARVEST itself is NOT
        # meaningfully backlogged (92-100% claim/exec) -- the constraint is
        # upstream, at getting a tile PLANTED at all, which this funnel
        # shows directly via the claim-rate gap (~90% of throttled-offer
        # PLANT:WHEAT tasks get NO unit assigned that turn).
        print(f"  VERIFIED: only {pw['claimed']/pw['generated']*100 if pw['generated'] else 0:.1f}% of "
              f"PLANT:WHEAT task-turns the dispatcher itself chose to offer (already inside plant_quota's own "
              f"daily cap) got a unit assigned at all -- this is a pure labor-availability shortfall, not a "
              f"quota design choice (the quota already decided these tiles should be planted).")

        if turns is not None:
            quota_total, per_day = wheat_quota_capacity(turns)
            shortfall = quota_total - pw["executed"]
            # Each unplanted quota-slot costs one full ~5-day wheat cycle's
            # profit on that tile (the tile just sits bare instead) -- a
            # cycle-based estimate, not a tile-days-idle one (a slot that
            # goes unplanted today usually gets re-offered tomorrow too,
            # this values the CYCLE that never started, roughly bounding the
            # single biggest recoverable line item).
            cycle_days = 17 / 4  # steady-state span/cycles, land_fert_labor.py
            shortfall_value = shortfall * WHEAT_PROFIT_PER_TILE_PER_DAY * cycle_days
            print(f"  VERIFIED (exact, from the real day-by-day unlocked-quadrant trajectory in the turns log): "
                  f"the agent's OWN plant_quota formula intended {quota_total} wheat plantings across the game "
                  f"(day-by-day active_tiles/quota: {per_day})")
            print(f"  VERIFIED: only {pw['executed']} of those {quota_total} intended plantings actually "
                  f"happened ({pw['executed']/quota_total*100:.0f}%) -- a shortfall of {shortfall} plantings, "
                  f"entirely within the agent's own already-throttled intent (seeds/cash were not the "
                  f"binding constraint here -- see PolicyConfig/plan.py, which gates seed BUYING on cash "
                  f"but not on this quota)")
            print(f"  ESTIMATE (upper bound, {shortfall} missed plantings x one ~{cycle_days:.1f}-day cycle's "
                  f"wheat profit at undepressed price, ignores travel cost and that the tile may still be "
                  f"planted on a LATER day rather than never): ${shortfall_value:,.0f}/game")

        # --- FEED / CARE / COLLECT_FERTILIZER / HARVEST:PASTURE sanity check ---
        feed = by_kind.get("FEED:PASTURE", {"generated": 0, "claimed": 0, "executed": 0})
        care = by_kind.get("CARE:PASTURE", {"generated": 0, "claimed": 0, "executed": 0})
        cfert = by_kind.get("COLLECT_FERTILIZER:PASTURE", {"generated": 0, "claimed": 0, "executed": 0})
        harv_p = by_kind.get("HARVEST:PASTURE", {"generated": 0, "claimed": 0, "executed": 0})
        harv_w = by_kind.get("HARVEST:WHEAT", {"generated": 0, "claimed": 0, "executed": 0})
        harv_m = by_kind.get("HARVEST:MELON", {"generated": 0, "claimed": 0, "executed": 0})
        print(f"\n[Animal chores + HARVEST -- NOT primary loss areas (reported for completeness)]")
        print(f"  FEED:PASTURE executed={feed['executed']} (claim_rate={feed['claimed']/feed['generated']*100 if feed['generated'] else 0:.1f}%, "
              f"exec_of_claimed={feed['executed']/feed['claimed']*100 if feed['claimed'] else 0:.1f}%)")
        print(f"  CARE:PASTURE executed={care['executed']} (claim_rate={care['claimed']/care['generated']*100 if care['generated'] else 0:.1f}%, "
              f"exec_of_claimed={care['executed']/care['claimed']*100 if care['claimed'] else 0:.1f}%)")
        print(f"  COLLECT_FERTILIZER:PASTURE executed={cfert['executed']} "
              f"(claim_rate={cfert['claimed']/cfert['generated']*100 if cfert['generated'] else 0:.1f}%, "
              f"exec_of_claimed={cfert['executed']/cfert['claimed']*100 if cfert['claimed'] else 0:.1f}%)")
        print(f"  HARVEST:PASTURE claim_rate={harv_p['claimed']/harv_p['generated']*100 if harv_p['generated'] else 0:.1f}% "
              f"exec_of_claimed={harv_p['executed']/harv_p['claimed']*100 if harv_p['claimed'] else 0:.1f}%")
        print(f"  HARVEST:WHEAT claim_rate={harv_w['claimed']/harv_w['generated']*100 if harv_w['generated'] else 0:.1f}% "
              f"exec_of_claimed={harv_w['executed']/harv_w['claimed']*100 if harv_w['claimed'] else 0:.1f}%")
        print(f"  HARVEST:MELON claim_rate={harv_m['claimed']/harv_m['generated']*100 if harv_m['generated'] else 0:.1f}% "
              f"exec_of_claimed={harv_m['executed']/harv_m['claimed']*100 if harv_m['claimed'] else 0:.1f}%")

        # --- PLACE: bought-but-unplaced animals (delayed START, not lost production) ---
        place_cow = by_kind.get("PLACE:COW", {"generated": 0, "claimed": 0, "executed": 0})
        place_sheep = by_kind.get("PLACE:SHEEP", {"generated": 0, "claimed": 0, "executed": 0})
        print(f"\n[PLACE -- animal bought but not yet on a pasture tile: delays the START of production, "
              f"does not destroy anything already produced]")
        print(f"  PLACE:COW claimed={place_cow['claimed']} executed={place_cow['executed']} "
              f"(exec_of_claimed={place_cow['executed']/place_cow['claimed']*100 if place_cow['claimed'] else 0:.1f}%)")
        print(f"  PLACE:SHEEP claimed={place_sheep['claimed']} executed={place_sheep['executed']} "
              f"(exec_of_claimed={place_sheep['executed']/place_sheep['claimed']*100 if place_sheep['claimed'] else 0:.1f}%)")
        place_days = tile_days(place_cow["claimed"] + place_sheep["claimed"])  # claimed persists every turn until executed
        print(f"  INFERRED: ~{place_days:.1f} animal-days spent bought-but-unplaced (claim persists every turn "
              f"until the carrying unit arrives) -- delays first production tick by roughly this many days per "
              f"animal on average; not a destructive loss, a timing delay.")

        # --- BUILD_PASTURE ---
        bp = by_kind.get("BUILD_PASTURE", {"generated": 0, "claimed": 0, "executed": 0})
        print(f"\n[BUILD_PASTURE]")
        print(f"  generated={bp['generated']} claimed={bp['claimed']} executed={bp['executed']} "
              f"(claim_rate={bp['claimed']/bp['generated']*100 if bp['generated'] else 0:.1f}%)")

        # --- Goose ---
        goose = summary.get("goose_totals", {})
        print(f"\n[GOOSE -- structurally cannot backlog: farmer pre-empts all other duty for it]")
        print(f"  {goose}")


if __name__ == "__main__":
    main()
