"""Leader opening recon: per-day behavioral instrumentation for public leader agents.

Plays each requested (seat0, seat1) pairing across a set of seeds and records, for
SEAT 0 ONLY (its own observation + its own submitted actions -- per-player fields are
not broadcast, so seat 1's observation is a different, private view and is never read
here), a rich per-day trace: money, tile census by crop/weed/empty, animals owned
(placed on tiles) and pending-in-shed, unlocked quadrants and the day each was bought,
units on the farm by hour, hires (submitted vs confirmed), plantings (confirmed via
tile-diff, and attempted via PLANT-verb count), strawberry plantings by quadrant,
harvest/fertilize/collect_fertilizer verb counts (+ best-effort crop attribution for
harvests via acting-unit position), and market orders per day by verb:item with
quantities (all verbs, including SELL, with the quoted price at submission).

Recon only; no game/package code is modified. Requires engine 1.32.7. Run from the
repository root so `uv run` imports the checked-out agent/harness packages.

Usage:
    uv run python leader_recon.py \
        --games '[{"label":"sokolovsky-v12","seat0":"public:sokolovsky-v12","seat1":"champion"}]' \
        --seeds 855000-855007 --out records.json
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
import time
from typing import Any

ANIMAL_KINDS = ("COW", "SHEEP", "GOOSE")
# Verbs worth a dedicated per-day count (task-named ones first, then the rest of the
# observed unit-action vocabulary so nothing silently falls through uncounted).
TRACKED_VERBS = (
    "HARVEST", "FERTILIZE", "COLLECT_FERTILIZER", "PLANT", "WATER", "CARE", "FEED",
    "PLACE", "PICKUP", "DROP", "BUILD_PASTURE", "BUILD_COOP", "PASS",
    "NORTH", "SOUTH", "EAST", "WEST",
)


def _seeds(spec: str) -> list[int]:
    if "-" in spec and "," not in spec:
        lo, hi = (int(x) for x in spec.split("-"))
        return list(range(lo, hi + 1))
    return [int(s) for s in spec.split(",")]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def _rows(tiles):
    for row in tiles:
        yield row if isinstance(row, (list, tuple)) else [row]


def quadrant_of(x: int, y: int, quadrants: dict) -> str:
    return next((n for n, (xr, yr) in quadrants.items() if x in xr and y in yr), "?")


def tile_crop(t: Any) -> str | None:
    """Crop name if t is a live PLANT tile, else None. Matches labor_probe.py's
    _is_wheat gate (kind == PLANT), generalized to any crop name."""
    if isinstance(t, dict) and t.get("kind") == "PLANT":
        crop = t.get("crop")
        return str(crop).upper() if crop else None
    return None


def tile_animal(t: Any) -> str | None:
    """Animal kind if t is an occupied COOP/PASTURE tile, else None."""
    if isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE") and "animal" in t:
        a = t.get("animal")
        return str(a).upper() if a else None
    return None


def board_census(tiles) -> collections.Counter:
    """Tile census: empty, LOCKED, weed, structure_empty (COOP/PASTURE w/ no animal),
    crop counts by name (generic -- whatever crop appears), animal counts (a_<kind>)."""
    c: collections.Counter = collections.Counter()
    for row in _rows(tiles):
        for t in row:
            if t is None:
                c["empty"] += 1
            elif t == "LOCKED":
                c["locked"] += 1
            elif isinstance(t, dict):
                if t.get("kind") == "WEED":
                    c["weed"] += 1
                    continue
                crop = tile_crop(t)
                if crop:
                    c[crop.lower()] += 1
                    continue
                animal = tile_animal(t)
                if animal:
                    c["a_" + animal.lower()] += 1
                    continue
                if t.get("kind") in ("COOP", "PASTURE"):
                    c["structure_empty"] += 1
                else:
                    c["other"] += 1
            else:
                c["other"] += 1
    return c


def market_orders(action) -> list[tuple[str, str | None, Any]]:
    """[(verb, item_or_None, qty_or_None), ...] for every SUBMITTED order this turn,
    ALL verbs including SELL (unlike early_cash_ledger.py's non-SELL-only orders())."""
    out = []
    mk = (action or {}).get("market", []) if isinstance(action, dict) else []
    for o in mk or []:
        if not o:
            continue
        verb = o[0]
        item = o[1] if len(o) > 1 and isinstance(o[1], str) else None
        qty = o[2] if len(o) > 2 and isinstance(o[2], (int, float)) and not isinstance(o[2], bool) else None
        out.append((verb, item, qty))
    return out


def unit_commands(action) -> list[tuple[str, list]]:
    """[("farmer", cmd), ("hand0", cmd), ("hand1", cmd), ...] in the SAME index order
    as the observation's farmer/hands position fields (engine-confirmed: action["hands"]
    is index-aligned with the hand-position list, no explicit hand id in the command)."""
    out = []
    if not isinstance(action, dict):
        return out
    f = action.get("farmer")
    if isinstance(f, list) and f:
        out.append(("farmer", f))
    for i, h in enumerate(action.get("hands", []) or []):
        if isinstance(h, list) and h:
            out.append((f"hand{i}", h))
    return out


def play(label: str, seat0: str, seat1: str, seed: int, quadrants: dict) -> dict:
    from agent.view import parse_obs
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    cfg0 = {} if seat0 == "champion" else None
    cfg1 = {} if seat1 == "champion" else None
    env = make("kaggriculture", configuration={"seed": seed})
    env.run([resolve_agent(seat0, cfg0), resolve_agent(seat1, cfg1)])
    steps = env.steps
    n = len(steps)

    quad_bought_day: dict[str, int] = {}
    animal_first_seen_day: dict[str, int] = {}
    strawberry_plantings_detail: list[dict] = []
    all_planting_events: list[dict] = []  # every crop, full detail
    days: list[dict] = []

    prev_v = None
    for day in range(30):
        t_start = day * 24
        if t_start >= n:
            break
        t_end = min(day * 24 + 23, n - 1)

        units_by_hour: dict[int, int] = {}
        hire_qty_submitted = 0
        plant_verb_attempts: collections.Counter = collections.Counter()
        planted_confirmed: collections.Counter = collections.Counter()
        verb_counts: collections.Counter = collections.Counter()
        harvest_by_crop_inferred: collections.Counter = collections.Counter()
        orders_submitted: collections.Counter = collections.Counter()
        sell_events: list[dict] = []
        v_eod = None

        for t in range(t_start, t_end + 1):
            obs0 = steps[t][0]["observation"]
            v = parse_obs(obs0)
            act0 = steps[t][0].get("action")
            v_eod = v

            units_by_hour[v.hour] = 1 + len(v.hands or [])

            for q in v.unlocked_quadrants:
                if q not in quad_bought_day:
                    quad_bought_day[q] = day

            # confirmed plantings: tile transitions INTO a crop vs the prior turn
            if prev_v is not None:
                for y, row in enumerate(v.tiles):
                    prev_row = prev_v.tiles[y] if y < len(prev_v.tiles) else []
                    cells = row if isinstance(row, (list, tuple)) else [row]
                    for x, t_now in enumerate(cells):
                        t_prev = prev_row[x] if x < len(prev_row) else None
                        crop_now = tile_crop(t_now)
                        crop_prev = tile_crop(t_prev)
                        if crop_now and crop_now != crop_prev:
                            planted_confirmed[crop_now] += 1
                            ev = {
                                "day": prev_v.day, "hour": prev_v.hour, "x": x, "y": y,
                                "crop": crop_now, "quadrant": quadrant_of(x, y, quadrants),
                            }
                            all_planting_events.append(ev)
                            if crop_now == "STRAWBERRY":
                                strawberry_plantings_detail.append(ev)

            # market orders (submitted; ALL verbs incl SELL)
            for verb, item, qty in market_orders(act0):
                key = f"{verb}:{item}" if item else verb
                orders_submitted[key] += qty if qty is not None else 1
                if verb == "HIRE":
                    hire_qty_submitted += qty if qty is not None else 1
                if verb == "SELL":
                    sell_events.append({
                        "hour": v.hour, "item": item, "qty": qty,
                        "quoted_price": v.prices.get(item) if item else None,
                    })

            # unit (farmer/hand) verb counts + PLANT attempts + best-effort harvest attribution
            positions = {"farmer": v.farmer}
            for i, pos in enumerate(v.hands or []):
                positions[f"hand{i}"] = pos
            for who, cmd in unit_commands(act0):
                verb = cmd[0]
                verb_counts[verb] += 1
                if verb == "PLANT" and len(cmd) > 1:
                    plant_verb_attempts[str(cmd[1]).upper()] += 1
                elif verb == "HARVEST":
                    pos = positions.get(who)
                    if pos is not None:
                        px, py = pos
                        row = v.tiles[py] if 0 <= py < len(v.tiles) else []
                        tile = row[px] if 0 <= px < len(row) else None
                        crop = tile_crop(tile)
                        animal = tile_animal(tile)
                        harvest_by_crop_inferred[crop or (f"animal:{animal}" if animal else "?")] += 1

            prev_v = v

        b = board_census(v_eod.tiles)
        hours0_4 = [units_by_hour.get(h, 0) for h in range(5)]
        h4_20 = [units_by_hour[h] for h in range(4, 21) if h in units_by_hour]
        for a in ANIMAL_KINDS:
            if b.get("a_" + a.lower(), 0) > 0 and a not in animal_first_seen_day:
                animal_first_seen_day[a] = day

        days.append({
            "day": day,
            "obs_day": v_eod.day,
            "money": v_eod.money,
            "tiles": dict(sorted(b.items())),
            "unlocked_quadrants": list(v_eod.unlocked_quadrants),
            "hands_eod": len(v_eod.hands or []),
            "units_hours_0_4": hours0_4,
            "units_mean_4_20": (sum(h4_20) / len(h4_20)) if h4_20 else None,
            "hires_submitted": hire_qty_submitted,
            "hires_confirmed_eod": v_eod.hires_today,
            "shed_pending_animals": {a: v_eod.shed.get(a, 0) for a in ANIMAL_KINDS},
            "shed": dict(v_eod.shed),
            "seeds_on_hand": dict(v_eod.seeds),
            "plantings_confirmed": dict(planted_confirmed),
            "plantings_attempted": dict(plant_verb_attempts),
            "verb_counts": dict(verb_counts),
            "harvest_by_crop_inferred": dict(harvest_by_crop_inferred),
            "orders_submitted": dict(sorted(orders_submitted.items())),
            "sell_events": sell_events,
        })

    final_money = {
        "seat0": parse_obs_money(steps[-1][0]["observation"]),
        "seat1": parse_obs_money(steps[-1][1]["observation"]),
    }

    return {
        "label": label, "seat0": seat0, "seat1": seat1, "seed": seed,
        "n_steps": n,
        "quad_bought_day": quad_bought_day,
        "animal_first_seen_day": animal_first_seen_day,
        "final_money": final_money,
        "days": days,
        "strawberry_plantings_detail": strawberry_plantings_detail,
        "planting_events": all_planting_events,
    }


def parse_obs_money(obs) -> float:
    from agent.view import parse_obs
    return parse_obs(obs).money


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", required=True, help='JSON list of {"label","seat0","seat1"}')
    ap.add_argument("--seeds", default="855000-855007")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    games_spec = json.loads(a.games)
    seeds = _seeds(a.seeds)

    import kaggle_environments as k

    assert k.__version__ == "1.32.7", f"ABORT: engine {k.__version__}; requires 1.32.7"
    import agent  # noqa: F401
    from agent.constants import QUADRANTS

    identity = {
        "script": "leader_recon.py",
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "agent_imported_from": agent.__file__,
        "engine": k.__version__,
        "seeds": seeds,
        "games": games_spec,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    print("identity:", json.dumps(identity))

    results: dict[str, dict[str, dict]] = {}
    t0 = time.time()
    n_games = len(games_spec) * len(seeds)
    done = 0
    for g in games_spec:
        label, seat0, seat1 = g["label"], g["seat0"], g["seat1"]
        results[label] = {}
        for seed in seeds:
            tg0 = time.time()
            rec = play(label, seat0, seat1, seed, QUADRANTS)
            done += 1
            print(
                f"[{done}/{n_games}] {label} seed={seed} "
                f"final=${rec['final_money']['seat0']:,.0f} vs ${rec['final_money']['seat1']:,.0f} "
                f"({time.time() - tg0:.1f}s)"
            )
            results[label][str(seed)] = rec

    with open(a.out, "w") as fh:
        json.dump({"identity": identity, "results": results}, fh, indent=1, default=str)
    print(f"\nwrote {a.out} in {time.time() - t0:.1f}s total")


if __name__ == "__main__":
    main()
