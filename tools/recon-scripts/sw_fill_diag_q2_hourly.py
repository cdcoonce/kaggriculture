"""Q2 follow-up: hourly money/fert trace on day 9 for the 4 seeds where the
shipped agent buys SW that day, sw25 vs shipped, to pin down whether the
withheld fertilizer cash is what keeps sw25 under the $2500 (price+reserve)
threshold at the hour shipped crosses it.
"""
from __future__ import annotations

import kaggle_environments as k

assert k.__version__ == "1.32.7"

from agent.view import parse_obs  # noqa: E402
from harness.episodes import resolve_agent  # noqa: E402
from kaggle_environments import make  # noqa: E402

SW25 = {
    "strawberry_frame_quadrants": ["SW"],
    "strawberry_tile_target": 25,
    "strawberry_plant_daily_cap": 10,
    "strawberry_start_day": 9,
}
SHIPPED = {}

SEEDS_SHIPPED_BUYS_DAY9 = [855000, 855003, 855006, 855007]


def fert_sell_qty(action):
    for o in (action or {}).get("market", []) or []:
        if o and o[0] == "SELL" and len(o) > 2 and o[1] == "FERTILIZER":
            return o[2] if isinstance(o[2], (int, float)) else 0
    return 0


def land_buy(action):
    return any(o and o[0] == "BUY_LAND" for o in (action or {}).get("market", []) or [])


def strawberry_seed_buy_qty(action):
    for o in (action or {}).get("market", []) or []:
        if o and o[0] == "BUY_SEED" and len(o) > 2 and o[1] == "STRAWBERRY":
            return o[2] if isinstance(o[2], (int, float)) else 0
    return 0


def run(seed, cfg):
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent("champion", cfg), resolve_agent("public:sokolovsky-v12")])
    return env


for seed in SEEDS_SHIPPED_BUYS_DAY9:
    env_sw25 = run(seed, SW25)
    env_shipped = run(seed, SHIPPED)
    print(f"\n===== seed {seed}: day-9 hourly money (sw25 vs shipped) =====")
    print(f"{'hr':>3} {'sw25_$':>9} {'sw25_fertsold':>13} {'sw25_strawseed':>14} {'shipped_$':>10} {'shipped_fertsold':>16} {'shipped_LAND':>13}")
    cum_fert_withheld = 0
    shipped_buy_hour = None
    for hour in range(24):
        step = 9 * 24 + hour
        v_sw25 = parse_obs(env_sw25.steps[step][0]["observation"])
        v_shipped = parse_obs(env_shipped.steps[step][0]["observation"])
        a_sw25 = env_sw25.steps[step][0].get("action")
        a_shipped = env_shipped.steps[step][0].get("action")
        fert_sw25 = fert_sell_qty(a_sw25)
        fert_shipped = fert_sell_qty(a_shipped)
        straw_seed = strawberry_seed_buy_qty(a_sw25)
        bought_land = land_buy(a_shipped)
        if bought_land and shipped_buy_hour is None:
            shipped_buy_hour = hour
        marker = "  <== shipped BUYS SW" if bought_land else ""
        print(
            f"{hour:>3} {v_sw25.money:>9,.0f} {fert_sw25:>13} {straw_seed:>14} "
            f"{v_shipped.money:>10,.0f} {fert_shipped:>16} {str(bought_land):>13}{marker}"
        )
    if shipped_buy_hour is not None:
        v_sw25_at_buy = parse_obs(env_sw25.steps[9 * 24 + shipped_buy_hour][0]["observation"])
        print(
            f"  -> shipped buys SW at hour {shipped_buy_hour} (needs >= $2500). "
            f"sw25's money at that SAME hour: ${v_sw25_at_buy.money:,.0f} "
            f"(short by ${2500 - v_sw25_at_buy.money:,.0f})" if v_sw25_at_buy.money < 2500 else
            f"  -> shipped buys SW at hour {shipped_buy_hour}; sw25 ALREADY had ${v_sw25_at_buy.money:,.0f} >= 2500 then too (didn't buy for a different reason)"
        )
