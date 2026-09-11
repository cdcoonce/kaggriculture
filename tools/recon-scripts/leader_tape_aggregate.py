"""Aggregate raw_records.json across the 8 seeds per label. Recon only, read-only.

Writes summary.json (machine-readable) and prints human-readable tables/evidence
blocks straight to stdout for the write-up.
"""

import json
import statistics as stats
import sys

IN = sys.argv[1]  # raw_records.json from leader_recon.py --out
OUT = sys.argv[2]  # the summary JSON to write

# Any submitted qty at or above this is not a literal quantity -- it's a "sell
# everything in the shed" sentinel idiom (confirmed empirically: our own champion
# submits ["SELL","EGG",99999] every turn once geese lay -- see agent/market.py's
# SELL_ALL constant, packages/agent/src/agent/market.py:419). Real observed
# per-game quantities everywhere else top out in the hundreds, so anything >=
# SENTINEL is excluded from sums (which it would otherwise dominate/corrupt) and
# tracked separately as a standing-order behavior instead.
SENTINEL = 9999

d = json.load(open(IN))
results = d["results"]
labels = list(results.keys())
seeds = [str(s) for s in d["identity"]["seeds"]]


def mv(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"mean": None, "min": None, "max": None, "sd": None, "n": 0}
    return {
        "mean": round(sum(xs) / len(xs), 1),
        "min": round(min(xs), 1),
        "max": round(max(xs), 1),
        "sd": round(stats.pstdev(xs), 1) if len(xs) > 1 else 0.0,
        "n": len(xs),
    }


summary = {}
for label in labels:
    seed_recs = results[label]
    games = [seed_recs[s] for s in seeds]

    # ---- per-day aggregates (0-29) ----
    day_agg = []
    max_days = max(len(g["days"]) for g in games)
    for day_idx in range(max_days):
        rows = [g["days"][day_idx] for g in games if day_idx < len(g["days"])]
        if not rows:
            continue

        def field(key, default=0):
            return [r["tiles"].get(key, default) for r in rows]

        day_agg.append({
            "day": day_idx,
            "money": mv([r["money"] for r in rows]),
            "wheat": mv(field("wheat")),
            "strawberry": mv(field("strawberry")),
            "melon": mv(field("melon")),
            "weed": mv(field("weed")),
            "empty": mv(field("empty")),
            "cow": mv(field("a_cow")),
            "sheep": mv(field("a_sheep")),
            "goose": mv(field("a_goose")),
            "quads_n": mv([len(r["unlocked_quadrants"]) for r in rows]),
            "quads_mode": max(set(tuple(sorted(r["unlocked_quadrants"])) for r in rows),
                               key=lambda q: sum(1 for r in rows if tuple(sorted(r["unlocked_quadrants"])) == q)),
            "hands_eod": mv([r["hands_eod"] for r in rows]),
            "units_mean_4_20": mv([r["units_mean_4_20"] for r in rows]),
            "hires_submitted": mv([r["hires_submitted"] for r in rows]),
            "hires_confirmed": mv([r["hires_confirmed_eod"] for r in rows]),
            "fertilize": mv([r["verb_counts"].get("FERTILIZE", 0) for r in rows]),
            "collect_fertilizer": mv([r["verb_counts"].get("COLLECT_FERTILIZER", 0) for r in rows]),
            "harvest": mv([r["verb_counts"].get("HARVEST", 0) for r in rows]),
            "plant_confirmed_total": mv([sum(r["plantings_confirmed"].values()) for r in rows]),
            "sell_fertilizer_qty": mv([sum(q for v_, it, q in
                                            [(o.split(":")[0], o.split(":")[1] if ":" in o else None, r["orders_submitted"][o])
                                             for o in r["orders_submitted"]] if v_ == "SELL" and it == "FERTILIZER")
                                       for r in rows]),
        })

    # ---- quadrant purchase day distribution ----
    quad_days = {}
    for q in ("NW", "NE", "SW", "SE"):
        vals = [g["quad_bought_day"].get(q) for g in games]
        quad_days[q] = {"days": vals, **mv([v for v in vals if v is not None]),
                         "n_bought": sum(1 for v in vals if v is not None)}

    # money at END of day (purchase_day - 1) for each quadrant, i.e. cash on hand
    # the morning of the day the quadrant shows up unlocked (evidence for "buys
    # when money >= X"; LAND_PRICES are NE=1000/SW=2000/SE=4000 per agent/constants.py).
    quad_money_before = {}
    for q in ("NW", "NE", "SW", "SE"):
        vals = []
        for g in games:
            pd = g["quad_bought_day"].get(q)
            if pd is not None and pd > 0:
                prev_day_row = next((r for r in g["days"] if r["day"] == pd - 1), None)
                if prev_day_row is not None:
                    vals.append(prev_day_row["money"])
        quad_money_before[q] = mv(vals)

    # ---- animal purchase day distribution ----
    animal_days = {}
    for a in ("COW", "SHEEP", "GOOSE"):
        vals = [g["animal_first_seen_day"].get(a) for g in games]
        animal_days[a] = {"days": vals, **mv([v for v in vals if v is not None]),
                           "n_bought": sum(1 for v in vals if v is not None)}

    # ---- strawberry planting histogram by day (aggregate counts across all seeds) ----
    straw_hist = {}
    straw_quad_hist = {}
    for g in games:
        for ev in g["strawberry_plantings_detail"]:
            straw_hist[ev["day"]] = straw_hist.get(ev["day"], 0) + 1
            key = (ev["day"], ev["quadrant"])
            straw_quad_hist[key] = straw_quad_hist.get(key, 0) + 1
    straw_total_per_seed = mv([len(g["strawberry_plantings_detail"]) for g in games])

    # ---- money level in the hour just before each strawberry planting BURST START ----
    # a "burst start" = a planting on a day where the PRIOR day had 0 strawberry plantings.
    straw_burst_money = []
    for g in games:
        by_day = {}
        for ev in g["strawberry_plantings_detail"]:
            by_day.setdefault(ev["day"], []).append(ev)
        for day, evs in by_day.items():
            if by_day.get(day - 1) is None:  # burst start
                dayrow = next((r for r in g["days"] if r["day"] == day - 1), None)
                if dayrow is not None:
                    straw_burst_money.append(dayrow["money"])
    straw_burst_money_stat = mv(straw_burst_money)

    # ---- cumulative fertilizer balance through day 15 and day 29 ----
    def cum_through(g, day_limit, key):
        return sum(r["verb_counts"].get(key, 0) for r in g["days"] if r["day"] <= day_limit)

    def cum_sell_fert(g, day_limit):
        tot = 0
        for r in g["days"]:
            if r["day"] > day_limit:
                continue
            for o, qty in r["orders_submitted"].items():
                if o == "SELL:FERTILIZER":
                    tot += qty
        return tot

    fert_balance = {
        "collect_through_d15": mv([cum_through(g, 15, "COLLECT_FERTILIZER") for g in games]),
        "fertilize_through_d15": mv([cum_through(g, 15, "FERTILIZE") for g in games]),
        "sell_fertilizer_through_d15": mv([cum_sell_fert(g, 15) for g in games]),
        "collect_through_d29": mv([cum_through(g, 29, "COLLECT_FERTILIZER") for g in games]),
        "fertilize_through_d29": mv([cum_through(g, 29, "FERTILIZE") for g in games]),
        "sell_fertilizer_through_d29": mv([cum_sell_fert(g, 29) for g in games]),
    }

    # ---- order totals (all days) by verb:item, summed qty across seeds then averaged.
    # Sentinel ("sell all") orders are excluded from the sum and tracked separately
    # as a standing-order behavior (turns/days it was submitted on), per game.
    order_totals: dict[str, list] = {}
    sentinel_orders: dict[str, list] = {}
    for g in games:
        per_game_totals: dict[str, float] = {}
        per_game_sentinel_turns: dict[str, int] = {}
        for r in g["days"]:
            for k, v in r["orders_submitted"].items():
                if v >= SENTINEL:
                    per_game_sentinel_turns[k] = per_game_sentinel_turns.get(k, 0) + 1
                else:
                    per_game_totals[k] = per_game_totals.get(k, 0) + v
        for k, v in per_game_totals.items():
            order_totals.setdefault(k, []).append(v)
        for k, v in per_game_sentinel_turns.items():
            sentinel_orders.setdefault(k, []).append(v)
    order_totals_mv = {k: mv(v) for k, v in sorted(order_totals.items())}
    sentinel_orders_mv = {k: mv(v) for k, v in sorted(sentinel_orders.items())}

    # ---- final money ----
    final_seat0 = mv([g["final_money"]["seat0"] for g in games])
    final_seat1 = mv([g["final_money"]["seat1"] for g in games])

    # ---- sell events: revenue proxy (qty * quoted_price) by item, through d15 / all ----
    def sell_revenue(g, day_limit=None):
        rev: dict[str, float] = {}
        for r in g["days"]:
            if day_limit is not None and r["day"] > day_limit:
                continue
            for ev in r["sell_events"]:
                if ev["item"] and ev["qty"] and ev["quoted_price"] and ev["qty"] < SENTINEL:
                    rev[ev["item"]] = rev.get(ev["item"], 0) + ev["qty"] * ev["quoted_price"]
        return rev

    sell_rev_items = set()
    for g in games:
        sell_rev_items |= set(sell_revenue(g).keys())
    sell_revenue_mv = {
        item: mv([sell_revenue(g).get(item, 0) for g in games]) for item in sorted(sell_rev_items)
    }

    summary[label] = {
        "seat0": games[0]["seat0"], "seat1": games[0]["seat1"],
        "final_money_seat0": final_seat0, "final_money_seat1": final_seat1,
        "day_agg": day_agg,
        "quad_bought_day": quad_days,
        "quad_money_before_purchase_day": quad_money_before,
        "animal_first_seen_day": animal_days,
        "strawberry_planting_hist_by_day": {str(k): v for k, v in sorted(straw_hist.items())},
        "strawberry_planting_hist_by_day_quadrant": {f"{k[0]}:{k[1]}": v for k, v in sorted(straw_quad_hist.items())},
        "strawberry_total_per_seed": straw_total_per_seed,
        "strawberry_burst_start_money_before": straw_burst_money_stat,
        "fertilizer_balance": fert_balance,
        "order_totals_per_game": order_totals_mv,
        "sentinel_sell_all_turns_per_game": sentinel_orders_mv,
        "sell_revenue_proxy_per_game": sell_revenue_mv,
    }

with open(OUT, "w") as fh:
    json.dump(summary, fh, indent=1, default=str)
print(f"wrote {OUT}\n")

# ---------------- human-readable printout ----------------
for label in labels:
    s = summary[label]
    print(f"\n{'=' * 90}\n{label}  (seat0={s['seat0']} vs seat1={s['seat1']})\n{'=' * 90}")
    print(f"final money seat0: mean={s['final_money_seat0']['mean']} range=[{s['final_money_seat0']['min']},{s['final_money_seat0']['max']}] sd={s['final_money_seat0']['sd']}")
    print(f"final money seat1: mean={s['final_money_seat1']['mean']} range=[{s['final_money_seat1']['min']},{s['final_money_seat1']['max']}] sd={s['final_money_seat1']['sd']}")
    print(f"quad_bought_day: {json.dumps(s['quad_bought_day'], default=str)}")
    print(f"quad_money_before_purchase_day: {json.dumps(s['quad_money_before_purchase_day'])}")
    print(f"animal_first_seen_day: {json.dumps(s['animal_first_seen_day'], default=str)}")
    print(f"strawberry_total_per_seed: {s['strawberry_total_per_seed']}")
    print(f"strawberry_burst_start_money_before: {s['strawberry_burst_start_money_before']}")
    print(f"strawberry_planting_hist_by_day: {s['strawberry_planting_hist_by_day']}")
    print(f"fertilizer_balance: {json.dumps(s['fertilizer_balance'])}")
    print("\nday-by-day (0-15): day money[range] wheat straw melon weed empty | quadsN cow sheep goose | hands u4-20 hiresC | fert collFert harvest plantConf")
    for row in s["day_agg"][:16]:
        m = row["money"]
        print(
            f"  d{row['day']:>2} ${m['mean']:>8,.0f}[{m['min']:>7,.0f},{m['max']:>8,.0f}]"
            f" w={row['wheat']['mean']:>4.1f} s={row['strawberry']['mean']:>4.1f} me={row['melon']['mean']:>4.1f}"
            f" wd={row['weed']['mean']:>3.1f} e={row['empty']['mean']:>4.1f}"
            f" | q={row['quads_n']['mean']:.1f}({''.join(row['quads_mode'])})"
            f" c={row['cow']['mean']:.1f} sh={row['sheep']['mean']:.1f} g={row['goose']['mean']:.1f}"
            f" | h={row['hands_eod']['mean']:>4.1f} u420={row['units_mean_4_20']['mean'] or 0:>4.1f} hC={row['hires_confirmed']['mean']:.1f}"
            f" | fert={row['fertilize']['mean']:.1f} cf={row['collect_fertilizer']['mean']:.1f} hv={row['harvest']['mean']:.1f} pc={row['plant_confirmed_total']['mean']:.1f}"
        )
    print("\nlate game snapshot (day 20, 25, 29):")
    for target_day in (20, 25, 29):
        row = next((r for r in s["day_agg"] if r["day"] == target_day), None)
        if row is None:
            continue
        m = row["money"]
        print(
            f"  d{target_day} ${m['mean']:>8,.0f}[{m['min']:>7,.0f},{m['max']:>8,.0f}]"
            f" w={row['wheat']['mean']:.1f} s={row['strawberry']['mean']:.1f} me={row['melon']['mean']:.1f}"
            f" q={row['quads_n']['mean']:.1f}({''.join(row['quads_mode'])}) h={row['hands_eod']['mean']:.1f}"
        )
    print("\norder totals per game (mean [range]), top by mean qty -- excludes sell-all sentinel orders (qty>=9999):")
    for k, v in sorted(s["order_totals_per_game"].items(), key=lambda kv: -(kv[1]["mean"] or 0))[:20]:
        print(f"  {k:<28} mean={v['mean']:>7} range=[{v['min']},{v['max']}] sd={v['sd']}")
    if s["sentinel_sell_all_turns_per_game"]:
        print("\nSELL-ALL SENTINEL standing orders (qty>=9999 = 'sell everything', not a literal quantity) -- turns/game submitted on:")
        for k, v in sorted(s["sentinel_sell_all_turns_per_game"].items(), key=lambda kv: -(kv[1]["mean"] or 0)):
            print(f"  {k:<28} mean_turns={v['mean']:>6} range=[{v['min']},{v['max']}] (out of up to 720 turns)")
    print("\nsell revenue proxy per game (qty*quoted_price summed), by item -- sentinel sell-all events excluded:")
    for k, v in sorted(s["sell_revenue_proxy_per_game"].items(), key=lambda kv: -(kv[1]["mean"] or 0)):
        print(f"  {k:<14} mean=${v['mean']:>9,.0f} range=[${v['min']:,.0f},${v['max']:,.0f}]")

sys.stdout.flush()
print("\n\nDONE", file=sys.stderr)
