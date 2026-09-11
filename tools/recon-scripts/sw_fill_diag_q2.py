"""Q2: why is SW bought on day 10 in all 8 SW25 games instead of day 9 (as the
shipped agent does in 4/8)? Tests the fert_reserve = strawberry_tile_target
hypothesis: from strawberry_start_day (9) on, build_orders withholds
`fert_reserve` units of FERTILIZER from sale (market.py, fert_held_back),
which could delay cash reaching the SW BUY_LAND threshold by a day.

No monkeypatching needed here -- everything is read straight off env.steps
(observations + submitted actions), exactly like
tools/recon-scripts/early_cash_ledger.py's own pattern. Read-only recon.
"""
from __future__ import annotations

import sys

import json

import kaggle_environments as k

assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"

import agent  # noqa: E402
from agent.view import parse_obs  # noqa: E402
from harness.episodes import resolve_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

SEEDS = list(range(855000, 855008))

SW25 = {
    "strawberry_frame_quadrants": ["SW"],
    "strawberry_tile_target": 25,
    "strawberry_plant_daily_cap": 10,
    "strawberry_start_day": 9,
}
SHIPPED = {}  # PolicyConfig() defaults: strawberry_tile_target=0 always -> fert_reserve=0 always


def fert_sell_qty(action):
    for o in (action or {}).get("market", []) or []:
        if o and o[0] == "SELL" and len(o) > 2 and o[1] == "FERTILIZER":
            return o[2] if isinstance(o[2], (int, float)) else 0
    return 0


def land_buy_count(action):
    return sum(1 for o in (action or {}).get("market", []) or [] if o and o[0] == "BUY_LAND")


def play_and_trace(seed, cfg, opponent="public:sokolovsky-v12"):
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])

    rows = []
    sw_day = None
    for day in range(0, 14):
        t_end = day * 24 + 23
        if t_end >= len(env.steps):
            break
        v = parse_obs(env.steps[t_end][0]["observation"])
        fert_shed = v.shed.get("FERTILIZER", 0)
        day_fert_sold = 0
        day_land_buys = 0
        for t in range(day * 24, t_end + 1):
            act = env.steps[t][0].get("action")
            day_fert_sold += fert_sell_qty(act)
            day_land_buys += land_buy_count(act)
        if sw_day is None and "SW" in v.unlocked_quadrants:
            sw_day = day
        rows.append(
            {
                "day": day,
                "money": v.money,
                "fert_shed_eod": fert_shed,
                "fert_sold_this_day": day_fert_sold,
                "land_buys_this_day": day_land_buys,
                "unlocked": "".join(v.unlocked_quadrants),
            }
        )
    return rows, sw_day


def main():
    results = {}
    print(f"{'seed':>8} | {'arm':>8} | {'d9$':>8} {'d9fert_sold':>11} {'d9fert_eod':>10} | {'SW day':>6}")
    for seed in SEEDS:
        for arm_name, cfg in (("sw25", SW25), ("shipped", SHIPPED)):
            rows, sw_day = play_and_trace(seed, cfg)
            results.setdefault(seed, {})[arm_name] = {"rows": rows, "sw_day": sw_day}
            d9 = next((r for r in rows if r["day"] == 9), None)
            d8 = next((r for r in rows if r["day"] == 8), None)
            print(
                f"{seed:>8} | {arm_name:>8} | {d9['money']:>8,.0f} {d9['fert_sold_this_day']:>11} "
                f"{d9['fert_shed_eod']:>10} | {str(sw_day):>6}"
                f"   (day8 money={d8['money']:,.0f})"
            )

    print("\n--- per-day detail, seed 855000, both arms, days 7-11 ---")
    for arm_name in ("sw25", "shipped"):
        print(f"\n{arm_name}:")
        for r in results[855000][arm_name]["rows"]:
            if 7 <= r["day"] <= 11:
                print(
                    f"  day {r['day']:>2}  money={r['money']:>8,.0f}  "
                    f"fert_sold_today={r['fert_sold_this_day']:>3}  fert_shed_eod={r['fert_shed_eod']:>3}  "
                    f"land_buys_today={r['land_buys_this_day']}  unlocked={r['unlocked']}"
                )

    n_sw9_sw25 = sum(1 for s in SEEDS if results[s]["sw25"]["sw_day"] == 9)
    n_sw9_shipped = sum(1 for s in SEEDS if results[s]["shipped"]["sw_day"] == 9)
    n_sw10_sw25 = sum(1 for s in SEEDS if results[s]["sw25"]["sw_day"] == 10)
    n_sw10_shipped = sum(1 for s in SEEDS if results[s]["shipped"]["sw_day"] == 10)
    print(f"\nSW bought on day 9:  sw25={n_sw9_sw25}/8   shipped={n_sw9_shipped}/8")
    print(f"SW bought on day 10: sw25={n_sw10_sw25}/8   shipped={n_sw10_shipped}/8")

    # cumulative fertilizer sold through day 9, and day-9 money delta
    print("\n--- cumulative FERTILIZER sold through day 9, and day-9 cash, both arms ---")
    for seed in SEEDS:
        cum_sw25 = sum(r["fert_sold_this_day"] for r in results[seed]["sw25"]["rows"] if r["day"] <= 9)
        cum_shipped = sum(r["fert_sold_this_day"] for r in results[seed]["shipped"]["rows"] if r["day"] <= 9)
        d9_sw25 = next(r for r in results[seed]["sw25"]["rows"] if r["day"] == 9)["money"]
        d9_shipped = next(r for r in results[seed]["shipped"]["rows"] if r["day"] == 9)["money"]
        print(
            f"  seed {seed}: fert_sold[0..9] sw25={cum_sw25:>3} shipped={cum_shipped:>3}  |  "
            f"day9 money sw25={d9_sw25:>8,.0f} shipped={d9_shipped:>8,.0f}  delta={d9_sw25-d9_shipped:>+8,.0f}  |  "
            f"SW day sw25={results[seed]['sw25']['sw_day']} shipped={results[seed]['shipped']['sw_day']}"
        )

    out_path = (sys.argv[1] if len(sys.argv) > 1 else "q2_results.json")
    with open(out_path, "w") as fh:
        json.dump(results, fh, default=str)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
