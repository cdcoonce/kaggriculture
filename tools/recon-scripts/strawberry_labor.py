"""Where the unit-turns go, and why FERTILIZE misses.

Runs ONE instrumented game and accounts for every unit-turn the candidate
spent, so a strawberry knob result can be read as "the crop does not pay"
versus "the crop never got worked". The money gate structurally cannot tell
those apart -- it sees only the final bank.

The three questions it answers, in order of what actually blocks promotion:

  1. LABOR BUDGET. What fraction of unit-turns is movement rather than work,
     at this strawberry size AND at zero? A high walking share that is already
     there at target=0 is an agent-wide finding, not a strawberry one.
  2. FERTILIZE DEMAND vs FIRES. How many tile-days actually opened the age
     9/13 window uncovered, and how many FERTILIZE actions landed? A tile that
     misses its window silently yields 4 units instead of 8, with no error.
  3. WHY a miss happened. Split the misses into "shed was empty" (a supply or
     collection-labor problem) and "shed had stock but nobody came" (a
     dispatch or walking-distance problem). These have opposite fixes, and
     widening the age window only helps the second.

Usage:
    uv run python tools/recon-scripts/strawberry_labor.py --seed 510000 --tiles 16
    uv run python tools/recon-scripts/strawberry_labor.py --seed 510000 --tiles 0
    uv run python tools/recon-scripts/strawberry_labor.py --tiles 16 --json

Not a gate and not a test: prints a report, exits 0 unless the run itself
broke. Ledger the JSON alongside a gate ledger if a claim leans on it.
"""

import argparse
import json
from collections import Counter, defaultdict

MOVES = frozenset({"NORTH", "SOUTH", "EAST", "WEST"})
# PASS is the tell for a unit that was dispatched somewhere it could do
# nothing -- notably a FERTILIZE task claimed against an empty shed, where
# _carry_leg walks the unit to the tile and then has nothing to hand it.
IDLE = frozenset({"PASS"})
# Moving goods is overhead, not output: a PICKUP or DROP changes where a unit
# is holding something, never what exists on the farm. Folding them into
# "productive" (as `unit_turns - moves - idle` alone does) makes any change
# that trades field work for shed logistics look like a gain -- a batched
# fetch that fires 800 extra PICKUPs reads as +1.1pp productive while banking
# less money.
LOGISTICS = frozenset({"PICKUP", "DROP"})
OPPOSITE = {"NORTH": "SOUTH", "SOUTH": "NORTH", "EAST": "WEST", "WEST": "EAST"}


def _get(obs, key, default=None):
    """kaggle_environments observations are attribute- or key-addressable."""
    if hasattr(obs, key):
        return getattr(obs, key)
    try:
        return obs[key]
    except (KeyError, TypeError):
        return default


def _unit_actions(action):
    """Flatten one submitted action into the list of per-unit verbs."""
    if not action:
        return []
    units = []
    farmer = action.get("farmer")
    if farmer:
        units.append(farmer)
    for hand in action.get("hands") or []:
        if hand:
            units.append(hand)
    return units


def _indexed_unit_actions(action):
    """(slot, verb-list) pairs. Slot 0 is the farmer, slot n the nth hand.

    Slots are stable across turns because hands are only ever appended, which
    is what makes a per-slot movement history meaningful."""
    if not action:
        return []
    out = []
    farmer = action.get("farmer")
    if farmer:
        out.append((0, farmer))
    for n, hand in enumerate(action.get("hands") or []):
        if hand:
            out.append((n + 1, hand))
    return out


def _strawberry_tiles(farm):
    """Every occupied strawberry tile on this farm, as (x, y, tile)."""
    out = []
    tiles = farm.get("tiles") or []
    for xi, column in enumerate(tiles):
        for yi, tile in enumerate(column):
            if isinstance(tile, dict) and tile.get("crop") == "STRAWBERRY":
                out.append((xi, yi, tile))
    return out


def _shed_and_carried(obs, item):
    """(shed count, count in unit inventories) for ``item``, for THIS seat.

    ``private`` is per-player and is NOT broadcast onto the other seat's
    observation the way ``farms``/``market``/``town`` are, so it must be read
    off the seat's own state. Reading it from ``farms[seat]`` instead silently
    yields {} -- every count reads 0 and the whole supply story is fiction.
    """
    private = _get(obs, "private") or {}
    shed = int((private.get("shed") or {}).get(item, 0) or 0)
    carried = sum(int((inv or {}).get(item, 0) or 0) for inv in private.get("inventories") or [])
    return shed, carried


def analyze(env, seat, turns_per_day, fertilize_ages):
    steps = env.steps

    verbs = Counter()
    market_ops = Counter()
    unit_turns = 0

    collect_by_day = defaultdict(int)
    fert_fires_by_day = defaultdict(int)
    sells = Counter()
    alive_by_day = {}
    shed_fert_at_day_start = {}
    carried_fert_at_day_start = {}
    fert_peak_by_day = defaultdict(int)
    # A tile-day that opened the window uncovered: the demand FERTILIZE had to
    # meet. Keyed by day, valued by the (x, y) tiles that wanted it.
    demand_by_day = defaultdict(set)
    # Of those, the ones for which stock (shed OR already in a unit's hands)
    # existed at some point while the tile sat in the window that day. Those
    # misses had the material available and are dispatch/distance failures;
    # the remainder are genuine supply failures.
    stocked_demand_by_day = defaultdict(set)
    plantings_by_day = defaultdict(int)
    seen_planted = set()
    open_leg = defaultdict(list)
    leg_reversals = defaultdict(int)
    turns_by_slot = defaultdict(int)
    leg_lengths = []
    # Legs and their steps, keyed by the verb that closed the leg. See the
    # accounting loop for why that verb is the walk's purpose.
    legs_by_closer = Counter()
    leg_steps_by_closer = Counter()
    unterminated_legs = 0
    unterminated_steps = 0

    for i, step in enumerate(steps):
        day = i // turns_per_day
        state = step[seat]

        for slot, unit in _indexed_unit_actions(_get(state, "action")):
            unit_turns += 1
            turns_by_slot[slot] += 1
            verb = unit[0]
            verbs[verb] += 1
            if verb == "COLLECT_FERTILIZER":
                collect_by_day[day] += 1
            elif verb == "FERTILIZE":
                fert_fires_by_day[day] += 1

            # A "leg" is a maximal run of consecutive moves by one slot,
            # ended by any non-move action. A reversal inside a leg is a unit
            # that changed its mind mid-walk: targets are recomputed every
            # turn with no persistent assignment, so every step back down a
            # corridor it just walked up is pure waste.
            if verb in MOVES:
                if open_leg[slot] and open_leg[slot][-1] == OPPOSITE[verb]:
                    leg_reversals[slot] += 1
                open_leg[slot].append(verb)
            elif open_leg[slot]:
                leg_lengths.append(len(open_leg[slot]))
                # The verb that closes a leg is what the walk actually bought.
                # A leg is by construction a run of moves terminated by a
                # non-move, so the terminator is observable even though the
                # dispatcher's intent is not: DROP closes a mule trip to the
                # shed, PICKUP closes a fetch, a field verb closes a walk to
                # work, and PASS closes a walk that bought nothing. Realized
                # purpose, not intended -- which is the honest basis for
                # sizing a lever, since an abandoned intent never cost a step
                # it didn't take.
                legs_by_closer[verb] += 1
                leg_steps_by_closer[verb] += len(open_leg[slot])
                open_leg[slot] = []
        for order in (_get(state, "action") or {}).get("market") or []:
            if order:
                market_ops[order[0]] += 1
                if order[0] == "SELL" and len(order) > 1:
                    sells[order[1]] += 1

        obs = _get(state, "observation")
        if obs is None:
            continue
        farms = _get(obs, "farms")
        if not farms or seat >= len(farms):
            continue
        farm = farms[seat]
        shed_fert, carried_fert = _shed_and_carried(obs, "FERTILIZER")
        stock = shed_fert + carried_fert
        fert_peak_by_day[day] = max(fert_peak_by_day[day], stock)
        berries = _strawberry_tiles(farm)

        for x, y, tile in berries:
            planted = tile.get("planted_day")
            if planted is not None and (x, y, planted) not in seen_planted:
                seen_planted.add((x, y, planted))
                plantings_by_day[planted] += 1

        # Sample zone state once per day, at the day's first turn.
        if i % turns_per_day == 0:
            alive_by_day[day] = len(berries)
            shed_fert_at_day_start[day] = shed_fert
            carried_fert_at_day_start[day] = carried_fert

        # Demand is a tile-day property, so record it the first time we see
        # the tile in the window on that day -- but re-check stock every turn,
        # since a mid-day collection can rescue an otherwise-dry morning.
        for x, y, tile in berries:
            planted = tile.get("planted_day")
            if planted is None:
                continue
            age = day - int(planted)
            covered_through = int(tile.get("fertilized_until_day", -1) or -1)
            if age in fertilize_ages and covered_through < day:
                demand_by_day[day].add((x, y))
                if stock > 0:
                    stocked_demand_by_day[day].add((x, y))

    # Walks still in flight when the game ended bought nothing measurable, but
    # they did cost steps, so they are reported rather than dropped -- silently
    # discarding them would make the purpose buckets under-count `moves`.
    for slot, residue in open_leg.items():
        if residue:
            unterminated_legs += 1
            unterminated_steps += len(residue)

    moves = sum(v for k, v in verbs.items() if k in MOVES)
    idle = sum(v for k, v in verbs.items() if k in IDLE)
    logistics = sum(v for k, v in verbs.items() if k in LOGISTICS)
    productive = unit_turns - moves - idle - logistics

    # Roll the closing verbs up into the four purposes a walk can serve. The
    # buckets partition every closed leg, and steps across them plus the
    # unterminated residue must equal `moves` -- asserted in the payload as
    # `steps_accounted`, so a silent mis-bucketing is visible rather than
    # absorbed.
    def _purpose(closer):
        if closer == "DROP":
            return "shed_trip"
        if closer == "PICKUP":
            return "fetch"
        if closer in IDLE:
            return "wasted"
        return "field_work"

    purpose_legs = Counter()
    purpose_steps = Counter()
    for closer, n in legs_by_closer.items():
        purpose_legs[_purpose(closer)] += n
        purpose_steps[_purpose(closer)] += leg_steps_by_closer[closer]

    total_demand = sum(len(v) for v in demand_by_day.values())
    total_fires = sum(fert_fires_by_day.values())
    # A demand tile-day counts as "stocked" if a unit could in principle have
    # been supplied at any point while the tile sat in the window -- stock in
    # the shed OR already in a hand. The complement had no material available
    # all day and is a hard supply failure. Individual FERTILIZE actions are
    # not attributed to tiles, so this splits the DEMAND, not the misses:
    # unstocked is a lower bound on supply-caused misses, and misses beyond it
    # are dispatch or walking-distance failures.
    stocked = sum(len(stocked_demand_by_day[d] & demand_by_day[d]) for d in demand_by_day)
    unstocked = total_demand - stocked

    final_farms = _get(_get(steps[-1][seat], "observation"), "farms") or []
    money = final_farms[seat]["money"] if len(final_farms) > seat else None

    return {
        "unit_turns": unit_turns,
        "moves": moves,
        "idle_pass": idle,
        "logistics": logistics,
        "productive": productive,
        "walking_share": round(moves / unit_turns, 4) if unit_turns else None,
        "idle_share": round(idle / unit_turns, 4) if unit_turns else None,
        "logistics_share": round(logistics / unit_turns, 4) if unit_turns else None,
        "productive_share": round(productive / unit_turns, 4) if unit_turns else None,
        "walk_legs": {
            "count": len(leg_lengths),
            "mean_length": round(_mean(leg_lengths), 2) if leg_lengths else None,
            "max_length": max(leg_lengths) if leg_lengths else None,
            "reversals": sum(leg_reversals.values()),
            "reversal_share_of_moves": (
                round(sum(leg_reversals.values()) / moves, 4) if moves else None
            ),
            # Per slot, so the cause is separable: reversals that scale with
            # crew size point at units stealing each other's claims, while a
            # flat per-unit rate points at the task set itself churning.
            "reversals_by_slot": dict(sorted(leg_reversals.items())),
            "turns_by_slot": dict(sorted(turns_by_slot.items())),
        },
        # Where the walking actually goes. `steps` is the lever-sizing number:
        # a purpose's share of `moves` is the ceiling on what perfecting that
        # purpose could return, before any discount for the part of the walk
        # that was necessary anyway.
        "leg_purpose": {
            "legs": dict(purpose_legs.most_common()),
            "steps": dict(purpose_steps.most_common()),
            "step_share_of_moves": {
                k: round(v / moves, 4) for k, v in purpose_steps.most_common()
            },
            "step_share_of_unit_turns": {
                k: round(v / unit_turns, 4) for k, v in purpose_steps.most_common()
            },
            "unterminated_legs": unterminated_legs,
            "unterminated_steps": unterminated_steps,
            # Must equal `moves`. If it doesn't, the buckets are lying.
            "steps_accounted": sum(purpose_steps.values()) + unterminated_steps,
            "closers": dict(legs_by_closer.most_common()),
        },
        "verbs": dict(verbs.most_common()),
        "market_ops": dict(market_ops.most_common()),
        "fertilizer": {
            "collected": sum(collect_by_day.values()),
            "applied": total_fires,
            "sold": sells.get("FERTILIZER", 0),
            "demand_tile_days": total_demand,
            "misses": max(0, total_demand - total_fires),
            "demand_met_share": (round(total_fires / total_demand, 4) if total_demand else None),
            "demand_with_stock_available": stocked,
            "demand_with_no_stock_all_day": unstocked,
            "shed_at_day_start": shed_fert_at_day_start,
            "carried_at_day_start": carried_fert_at_day_start,
            "peak_stock_by_day": dict(sorted(fert_peak_by_day.items())),
        },
        "sells_by_item": dict(sells.most_common()),
        "zone": {
            "alive_by_day": alive_by_day,
            "peak_alive": max(alive_by_day.values()) if alive_by_day else 0,
            "plantings_by_day": dict(sorted(plantings_by_day.items())),
            "last_planting_day": max(plantings_by_day) if plantings_by_day else None,
        },
        "money": money,
    }


def report(res, args):
    ut = res["unit_turns"]
    print(f"=== seed {args.seed} · strawberry_tile_target={args.tiles} · vs {args.opponent} ===")
    print(f"final money: ${res['money']:,.0f}" if res["money"] is not None else "final money: n/a")
    print()
    print(f"--- labor budget ({ut:,} unit-turns) ---")
    print(f"  moving   {res['moves']:>6,}  {res['walking_share']:.1%}")
    print(f"  idle     {res['idle_pass']:>6,}  {res['idle_share']:.1%}   (PASS)")
    print(f"  working  {res['productive']:>6,}  {res['productive'] / ut:.1%}" if ut else "")
    print()
    print("  top verbs: " + ", ".join(f"{k}={v}" for k, v in list(res["verbs"].items())[:12]))
    print()
    w = res["walk_legs"]
    print("--- walk legs (a leg = consecutive moves between two work actions) ---")
    print(f"  legs                 {w['count']:,}")
    print(f"  mean / max length    {w['mean_length']} / {w['max_length']}")
    if w["reversal_share_of_moves"] is not None:
        print(
            f"  mid-leg reversals    {w['reversals']:,}  "
            f"({w['reversal_share_of_moves']:.1%} of all moves)  <- retargeting waste"
        )
    print()
    f = res["fertilizer"]
    print("--- fertilizer ---")
    print(f"  collected            {f['collected']}")
    print(f"  sold off             {f['sold']}")
    print(f"  applied              {f['applied']}")
    print(f"  demand (tile-days)   {f['demand_tile_days']}")
    if f["demand_met_share"] is not None:
        print(f"  demand met           {f['demand_met_share']:.1%}  ({f['misses']} missed)")
        print(f"    demand w/ stock on hand  {f['demand_with_stock_available']}"
              "   <- dispatch/distance")
        print(f"    demand w/ no stock       {f['demand_with_no_stock_all_day']}"
              "   <- supply/collection")
    print()
    z = res["zone"]
    print("--- zone ---")
    print(f"  peak tiles alive     {z['peak_alive']} (target {args.tiles})")
    print(f"  last planting day    {z['last_planting_day']}")
    if z["plantings_by_day"]:
        print(
            "  plantings by day     "
            + ", ".join(f"d{d}={n}" for d, n in z["plantings_by_day"].items())
        )


def run_one(seed, tiles, opponent, seat, turns_per_day, fertilize_ages, extra=()):
    """Play one instrumented game and return its record. Module-level and
    plain-argument so it is picklable for ProcessPoolExecutor, matching
    harness.episodes.play_game's reason for the same shape.

    ``extra`` is passed as tuple-of-pairs rather than a dict purely so the
    whole argument set stays trivially picklable and hashable."""
    from harness.episodes import resolve_agent
    from kaggle_environments import make

    config = {"strawberry_tile_target": tiles, **dict(extra)}
    agents = [None, None]
    agents[seat] = resolve_agent("champion", config)
    agents[1 - seat] = resolve_agent(opponent)

    env = make("kaggriculture", configuration={"seed": seed})
    env.run(agents)
    res = analyze(env, seat, turns_per_day, frozenset(fertilize_ages))
    res["seed"] = seed
    return res


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def sweep_report(records, args):
    """Per-seed table plus aggregates. Mechanism metrics (occupancy, demand
    met, walking share) are far lower-variance than money, so they carry the
    read at seed counts where a money delta is still noise."""
    print(f"=== {len(records)} seeds from {args.seed} · target={args.tiles} · vs {args.opponent} ===")
    print()
    print(f"{'seed':>8}  {'money':>9}  {'walk%':>6}  {'peak':>5}  {'mean_alive':>10}  {'fert':>9}")
    for r in records:
        z, f = r["zone"], r["fertilizer"]
        alive = _mean(list(z["alive_by_day"].values()))
        met = f["demand_met_share"]
        print(
            f"{r['seed']:>8}  {r['money']:>9,.0f}  {r['walking_share']:>5.1%}  "
            f"{z['peak_alive']:>5}  {alive:>10.1f}  "
            f"{(f'{met:.0%}' if met is not None else '-'):>4} "
            f"({f['applied']}/{f['demand_tile_days']})"
        )
    print()
    peaks = [r["zone"]["peak_alive"] for r in records]
    print(f"  mean final money      ${_mean([r['money'] for r in records]):,.0f}")
    print(f"  mean walking share    {_mean([r['walking_share'] for r in records]):.1%}")
    print(f"  mean peak occupancy   {_mean(peaks):.1f} / {args.tiles}"
          f"  ({_mean(peaks) / args.tiles:.0%})" if args.tiles else "")
    met = _mean([r["fertilizer"]["demand_met_share"] for r in records])
    if met is not None:
        print(f"  mean demand met       {met:.0%}")
    nostock = sum(r["fertilizer"]["demand_with_no_stock_all_day"] for r in records)
    print(f"  demand-days w/o stock {nostock}   (0 => supply is never the binding constraint)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=510000)
    ap.add_argument("--n-seeds", type=int, default=1, help="run seeds [seed, seed+n) and aggregate")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument(
        "--tiles", type=int, default=16, help="strawberry_tile_target for the candidate"
    )
    ap.add_argument("--opponent", default="zoo:tape-thunder-719")
    ap.add_argument("--seat", type=int, default=0, help="candidate seat; 0 has full private obs")
    ap.add_argument("--turns-per-day", type=int, default=24)
    ap.add_argument(
        "--fertilize-ages",
        default="9,13",
        help="ages counted as opening the fertilize window, for measuring a widened window",
    )
    ap.add_argument(
        "--agent-config",
        default=None,
        help='extra PolicyConfig knobs as JSON, e.g. \'{"strawberry_plant_daily_cap": 3}\'',
    )
    ap.add_argument("--json", action="store_true", help="emit the raw record instead of a report")
    args = ap.parse_args()

    fertilize_ages = sorted(int(a) for a in args.fertilize_ages.split(",") if a.strip())
    seeds = list(range(args.seed, args.seed + max(1, args.n_seeds)))
    extra = tuple(sorted(json.loads(args.agent_config).items())) if args.agent_config else ()
    identity = {
        "seed_base": args.seed,
        "n_seeds": len(seeds),
        "strawberry_tile_target": args.tiles,
        "agent_config_extra": dict(extra),
        "opponent": args.opponent,
        "fertilize_ages": fertilize_ages,
    }
    call = (args.tiles, args.opponent, args.seat, args.turns_per_day, fertilize_ages, extra)

    if len(seeds) == 1:
        records = [run_one(seeds[0], *call)]
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_one, s, *call) for s in seeds]
            records = [f.result() for f in futures]

    if args.json:
        print(json.dumps({"identity": identity, "records": records}, indent=2, default=str))
    elif len(records) == 1:
        records[0]["identity"] = identity
        report(records[0], args)
    else:
        sweep_report(records, args)


if __name__ == "__main__":
    main()
