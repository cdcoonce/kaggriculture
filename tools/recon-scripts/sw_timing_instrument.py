"""SW-purchase timing instrument: which precondition -- "animals done" or cash
-- is later-binding, per day, per arm/seed.

Wraps the REAL agent.policy.plan_day (behavior unchanged -- the traced call
just forwards to the original and returns its real result) and records every
call's real keyword arguments plus its real DayPlan.buys. From that real
trace it derives, per day:
  - end-of-day money (read the same way tools/recon-scripts/early_cash_ledger.py
    does: parse_obs on the env's own recorded observation at hour 23);
  - strawberry-seed spend and land spend that day (summed from the REAL
    buys returned each hour -- not re-derived from a heuristic);
  - "animals_done" and the SW-check's "budget" value, replicated using the
    same module constants and the same private helpers (_next_quadrant,
    plant_quota) plan.py itself calls, so the replication cannot silently
    drift from the source it mirrors. This one number (the budget the SW
    conditional actually compares against LAND_PRICES["SW"] + LAND_RESERVE)
    is not part of plan_day's return value, so it cannot be read any other
    way without editing plan.py.

Cross-checked at the end of each game: the shadow's own "day SW would fire"
must agree with the day SW actually shows up in view.unlocked_quadrants, and
a mismatch is printed loudly rather than silently trusted.

Recon only; requires engine 1.32.7. Run from the repository (or worktree)
root, so the agent under test is the one `uv run` imports there.

Usage:
    uv run python instrument_sw_timing.py \
        --arms '{"A_shipped": {}, "LTS": {...}}' \
        --seeds 779000,779001,779002,779003 --out instrument.json
"""

import argparse
import json
import subprocess


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True, help="JSON {name: config}")
    ap.add_argument("--seeds", default="779000")
    ap.add_argument("--opponent", default="public:sokolovsky-v12")
    ap.add_argument("--max-day", type=int, default=14)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    arms = json.loads(a.arms)
    seeds = [int(s) for s in a.seeds.split(",")]

    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"

    import agent
    import agent.plan as planmod
    import agent.policy as pol
    from agent.dispatch import MELON_PLANT_CUTOFF_DAY, MELON_PLANT_DAILY_CAP, plant_quota
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    orig_plan_day = pol.plan_day
    _next_quadrant = planmod._next_quadrant

    calls: list[dict] = []

    def traced_plan_day(**kw):
        result = orig_plan_day(**kw)
        rec = dict(kw)
        rec["_buys"] = [list(b) for b in result.buys]
        calls.append(rec)
        return result

    # Patch the name policy.decide() actually looks up (its own module
    # globals -- policy.py does `from agent.plan import (..., plan_day, ...)`,
    # so agent.plan.plan_day and agent.policy.plan_day are two names for the
    # same object until this line rebinds the SECOND one).
    pol.plan_day = traced_plan_day

    def shadow_budget_before_sw(kw: dict) -> tuple[float, bool, bool]:
        """Replays plan_day's own budget bookkeeping through the strawberry
        seed line (everything queued before the SW conditional), using the
        real constants/helpers plan.py itself uses. Returns (budget just
        before the SW check, animals_done, sw_next)."""
        day = kw["day"]
        budget = kw["money"]

        if (
            not kw["goose_owned"]
            and day >= kw.get("goose_min_day", planmod.GOOSE_MIN_DAY)
            and day <= planmod.GOOSE_LAST_BUY_DAY
            and budget >= planmod.GOOSE_COST
        ):
            budget -= planmod.GOOSE_COST

        unlocked = kw["unlocked_quadrants"]
        max_owned = kw.get("max_owned_quadrants", planmod.MAX_OWNED_QUADRANTS)
        ne_min_day = kw.get("ne_land_min_day", planmod.NE_LAND_MIN_DAY)
        if (
            _next_quadrant(unlocked, max_owned) == "NE"
            and day >= ne_min_day
            and day <= planmod.LAND_LAST_BUY_DAY["NE"]
        ):
            price = planmod.LAND_PRICES["NE"]
            if budget >= price + planmod.LAND_RESERVE:
                budget -= price

        if day <= MELON_PLANT_CUTOFF_DAY:
            target = min(2 * MELON_PLANT_DAILY_CAP, kw.get("empty_melon_tiles", 0))
            need = target - kw.get("melon_seeds", 0)
            n = min(need, int(budget // planmod.MELON_SEED_PRICE))
            if n > 0:
                budget -= n * planmod.MELON_SEED_PRICE

        animal_room = kw.get("empty_pastures", 0)
        turn_cap_left = planmod.ANIMAL_BUY_CAP_PER_TURN
        animal_buy_order = kw.get("animal_buy_order", planmod.ANIMAL_BUY_ORDER)
        cow_target = kw.get("cow_target", planmod.COW_TARGET)
        sheep_target = kw.get("sheep_target", planmod.SHEEP_TARGET)
        animal_target = {"COW": cow_target, "SHEEP": sheep_target}
        animal_owned = {"COW": kw.get("cows_owned", 0), "SHEEP": kw.get("sheep_owned", 0)}
        for species in animal_buy_order:
            if day <= planmod._ANIMAL_LAST_BUY_DAY[species]:
                need = max(0, animal_target[species] - animal_owned[species])
                n = min(
                    need,
                    animal_room,
                    turn_cap_left,
                    int(budget // planmod._ANIMAL_PRICE[species]),
                )
                if n > 0:
                    budget -= n * planmod._ANIMAL_PRICE[species]
                    animal_room -= n
                    turn_cap_left -= n

        if day <= planmod.PLANT_CUTOFF_DAY:
            quota = plant_quota(day, kw["active_tiles"])
            target = min(kw["plantable_target_tiles"], 2 * quota)
            need = target - kw["wheat_seeds"]
            n = min(need, int(budget // planmod.SEED_PRICE))
            if n > 0:
                budget -= n * planmod.SEED_PRICE

        if day <= planmod.STRAWBERRY_PLANT_CUTOFF_DAY:
            cap = kw.get("strawberry_plant_daily_cap", planmod.STRAWBERRY_PLANT_DAILY_CAP)
            share = kw.get("strawberry_seed_budget_share", planmod.STRAWBERRY_SEED_BUDGET_SHARE)
            target = min(2 * cap, kw.get("empty_strawberry_tiles", 0))
            need = target - kw.get("strawberry_seeds", 0)
            n = min(need, int((budget * share) // planmod.STRAWBERRY_SEED_PRICE))
            if n > 0:
                budget -= n * planmod.STRAWBERRY_SEED_PRICE

        # feed top-up is a no-op on budget in the real function too (no
        # `budget -=` line accompanies its BUY_PRODUCT append) -- mirrored
        # here by doing nothing, on purpose.

        animals_done = (
            animal_owned["COW"] >= cow_target or day > planmod.COW_LAST_BUY_DAY
        ) and (animal_owned["SHEEP"] >= sheep_target or day > planmod.SHEEP_LAST_BUY_DAY)
        sw_next = _next_quadrant(unlocked, max_owned) == "SW"
        return budget, animals_done, sw_next

    identity = {
        "script": "instrument_sw_timing.py",
        "git_sha": git("rev-parse", "HEAD"),
        "packages_dirty": bool(git("status", "--porcelain", "--", "packages")),
        "agent_imported_from": agent.__file__,
        "engine": k.__version__,
        "opponent": a.opponent,
        "seeds": seeds,
        "arms": arms,
    }
    print("identity:", json.dumps(identity))

    games: dict = {}
    for arm, cfg in arms.items():
        for seed in seeds:
            start_idx = len(calls)
            env = make("kaggriculture", configuration={"seed": seed})
            env.run([resolve_agent("champion", cfg), resolve_agent(a.opponent)])
            game_calls = calls[start_idx:]

            by_day: dict[int, list[dict]] = {}
            for rec in game_calls:
                by_day.setdefault(rec["day"], []).append(rec)

            max_day = max(a.max_day, max(by_day))
            day_rows = []
            cum_strawberry_spend = 0
            cum_land_spend = 0
            animals_done_day = None
            cash_ok_day = None
            sw_bought_day_shadow = None
            for day in range(0, max_day + 1):
                recs = by_day.get(day, [])
                strawberry_spend_today = 0
                land_spend_today = 0
                land_bought_today = []
                animals_done_today = False
                cash_ok_today = False
                shadow_budget_last = None
                for rec in recs:
                    for b in rec["_buys"]:
                        if b[0] == "BUY_SEED" and b[1] == "STRAWBERRY":
                            strawberry_spend_today += b[2] * planmod.STRAWBERRY_SEED_PRICE
                        elif b[0] == "BUY_LAND":
                            which = "NE" if "NE" not in rec["unlocked_quadrants"] else "SW"
                            land_spend_today += planmod.LAND_PRICES[which]
                            land_bought_today.append(which)
                            if which == "SW" and sw_bought_day_shadow is None:
                                sw_bought_day_shadow = day
                    budget, a_done, sw_next = shadow_budget_before_sw(rec)
                    shadow_budget_last = budget
                    if a_done:
                        animals_done_today = True
                    if sw_next and budget >= planmod.LAND_PRICES["SW"] + planmod.LAND_RESERVE:
                        cash_ok_today = True
                cum_strawberry_spend += strawberry_spend_today
                cum_land_spend += land_spend_today
                if animals_done_today and animals_done_day is None:
                    animals_done_day = day
                if cash_ok_today and cash_ok_day is None:
                    cash_ok_day = day

                t_end = day * 24 + 23
                eod_money = None
                if t_end < len(env.steps):
                    eod_money = parse_obs(env.steps[t_end][0]["observation"]).money

                day_rows.append(
                    {
                        "day": day,
                        "eod_money": eod_money,
                        "n_plan_day_calls": len(recs),
                        "strawberry_spend_today": strawberry_spend_today,
                        "land_spend_today": land_spend_today,
                        "land_bought_today": land_bought_today,
                        "cum_strawberry_spend": cum_strawberry_spend,
                        "cum_land_spend": cum_land_spend,
                        "animals_done_today": animals_done_today,
                        "cash_ok_today": cash_ok_today,
                        "shadow_budget_before_sw_last_call": shadow_budget_last,
                    }
                )

            # Ground-truth SW day: first day SW appears in the unlocked
            # quadrants at end-of-day observation (same convention
            # early_cash_ledger.py uses).
            sw_bought_day = None
            for day in range(0, 30):
                t_end = day * 24 + 23
                if t_end >= len(env.steps):
                    break
                v = parse_obs(env.steps[t_end][0]["observation"])
                if "SW" in v.unlocked_quadrants:
                    sw_bought_day = day
                    break

            mismatch = sw_bought_day_shadow != sw_bought_day
            final_money = parse_obs(env.steps[-1][0]["observation"]).money

            games.setdefault(str(seed), {})[arm] = {
                "rows": day_rows,
                "animals_done_day": animals_done_day,
                "cash_ok_day": cash_ok_day,
                "sw_bought_day": sw_bought_day,
                "sw_bought_day_shadow": sw_bought_day_shadow,
                "shadow_matches_ground_truth": not mismatch,
                "final_money": final_money,
                "later_binding": (
                    None
                    if animals_done_day is None or cash_ok_day is None
                    else ("cash" if cash_ok_day > animals_done_day else (
                        "animals_done" if animals_done_day > cash_ok_day else "tie"
                    ))
                ),
            }
            g = games[str(seed)][arm]
            print(
                f"{arm} seed={seed}: animals_done day {g['animals_done_day']}, "
                f"cash_ok day {g['cash_ok_day']}, SW bought day {g['sw_bought_day']} "
                f"(shadow {g['sw_bought_day_shadow']}, match={g['shadow_matches_ground_truth']}), "
                f"later-binding={g['later_binding']}, final ${g['final_money']:,.0f}"
            )
            if mismatch:
                print(f"  *** MISMATCH: shadow says SW day {sw_bought_day_shadow}, ground truth {sw_bought_day}")

    with open(a.out, "w") as fh:
        json.dump({"identity": identity, "games": games}, fh, indent=1, default=str)
    print("\nwrote", a.out)


if __name__ == "__main__":
    main()
