"""Fertilizer stream economics: how much money is actually on the table.

WHY THIS EXISTS: prior recon (this repo's probe history) established that the
champion never fertilizes anything and never buys fertilizer --
``agent.policy.py``'s ``fert_reserve=resolved_config.strawberry_tile_target``
is always 0 because ``agent.constants.STRAWBERRY_TILE_TARGET`` ships at 0, so
``agent.market.py``'s ``fert_sellable`` path sells 100% of collected
fertilizer every turn, and ``agent.dispatch.py``'s FERTILIZE task is
strawberry-gated and never fires on the shipped board. A prior probe put
per-seed FERTILIZER revenue at roughly $11,322 (third of six items, behind
MILK and MELON) and also found the market crashing to the engine's $1 floor
by day ~25 in every observed seed. Before an orchestrator specs a
FERTILIZE-wheat redirection or any other change to this stream, it needs to
know how much of that $11.3k is genuinely marginal (units that would clear at
a real price under different pacing) versus dead weight already sold for
pennies -- and whether either number can even clear the harness's detectable
floor (``mde_80`` roughly $1,400-4,500/tape at n=64-512; see
``harness.stats.mde_multiplier`` and its docstring). A true effect below that
floor cannot be shipped through a money gate no matter how real it is.

WHAT THIS MEASURES, per (seed, opponent):

  1. FERTILIZER units COLLECTED (the COLLECT_FERTILIZER action stream) by
     day, split into attempted vs actually-successful.
  2. FERTILIZER units SOLD (settled, from the engine's own commit path) by
     day, bucketed into price bands: >$50, $15-$50, and <$15 (near/at the
     $1 floor) -- because the marginal question is what the LAST units of
     the season actually earn, not what the average unit earns.
  3. The market's FERTILIZER price trajectory by day (end-of-day snapshot),
     and the first day it hits the $1 floor.
  4. Standing WHEAT tile counts by day (``harness.occupancy.census``), plus
     a peak-to-peak replant-cycle estimate.
  5. Labor: total unit-turns for the candidate, split walking / productive /
     idle, and unit-turns per successful COLLECT_FERTILIZER as a reference
     cost for pricing a hypothetical new per-season FERTILIZE task.
  6. The OPPONENT's own settled FERTILIZER sell volume/revenue on the same
     seeds -- does withholding our own supply hand them a pricing windfall.

HAZARDS (read before trusting a number out of this):

- SUBMITTED vs SETTLED. ``harness.settlement``'s own docstring measured 26 of
  80 EGG SELL calls as engine-rejected on one seed -- a wrapper that records
  on CALL, not on the engine's return value, books fictional sales. Every
  SELL/BUY_PRODUCT number here comes from a ``_commit_unit`` wrapper's
  **return value**, exactly like ``harness.settlement.play_with_settlement``
  -- never from ``action["market"]``. The COLLECT_FERTILIZER numbers are the
  mirror image: they come from replicating the engine's own success
  predicate (``_apply_unit_action``'s COLLECT_FERTILIZER branch: the unit's
  CURRENT tile is an animal tile AND ``fertilizer_available``) evaluated
  BEFORE the wrapped call runs -- not from counting submitted action ops. A
  unit that submits ``["COLLECT_FERTILIZER"]`` while still walking toward the
  tile, or arrives on a day the tile was already collected, would inflate a
  naive submitted-op count with nothing about it looking wrong.
- SEAT is resolved by OBJECT IDENTITY, but NOT the way ``harness.settlement``
  does it. Measured directly (see this module's own throwaway probe, kept
  out of the shipped script): ``kaggle_environments`` reconstructs the
  ``state``/observation objects between interpreter calls -- a farm dict's
  ``id()`` is stable for every engine call WITHIN one turn (both
  ``_apply_unit_action`` and ``_process_market`` see the identical two farm
  objects that turn) but changes turn over turn, so ``harness.settlement``'s
  pattern of capturing ``state[0].observation.farms`` once and matching
  against it for the rest of the episode is silently wrong here -- it
  resolved 0/2 seats correctly across a real run before this was caught.
  This script instead resolves seat PER TURN: the first not-yet-seen farm
  object each turn is seat 0, the second is seat 1 (interpreter's own
  ``for i, s in enumerate(state)`` loop processes seat 0's farmer-then-hands
  before seat 1's, and only two farms exist), and the two-slot table is
  cleared the instant a THIRD distinct object appears -- which can only mean
  a new turn started. Never assumed from which seat this script happened to
  hand the candidate.
  SEAT-RESOLUTION HAZARD, precisely stated: ``kaggle_environments`` rebuilds
  the farm dict objects between interpreter calls, so an object's identity is
  stable WITHIN one interpreter call but NOT across turns. ``harness.settlement``'s
  own identity-matching pattern (``_Recorder.seat_of`` in
  ``harness/settlement.py``) is not unsound in general -- it is safe only
  because its ``pm_spy`` wrapper re-captures the farms reference on every
  single ``_process_market`` call, and every commit it attributes happens
  inside that same call's scope; it would go stale the instant a caller held
  that reference across a turn boundary instead. This script cannot reuse
  that scope (it hooks ``_apply_unit_action``/``_commit_unit`` directly, not
  ``_process_market``), so it re-resolves the seat itself, per turn, as
  described above. That per-turn resolution was cross-validated against
  ``_process_market``'s own live ``farms`` list across a full 719-turn
  episode with zero seat mismatches before any number in this report was
  trusted.
- PRICE SAMPLING: FERTILIZER's price is a SHARED, per-turn-mutating number
  (``_process_market`` calls ``_refresh_prices`` every turn, not once a day,
  because market orders can arrive on any turn). "By day" here means the
  price after that day's LAST turn -- a closing price -- not an hour-0
  opening snapshot like ``harness.occupancy``'s crop census uses. A mid-day
  spike or dip is invisible to this series.
- WHEAT TILE COUNT is a STANDING census (``harness.occupancy.census``),
  sampled at each day's first turn like every other occupancy read in this
  repo. It answers "how many wheat plants exist to fertilize right now", not
  cumulative wheat ever planted this season.
- REPLANT CYCLE is a PEAK-TO-PEAK ESTIMATE over the standing-WHEAT time
  series (days 8-27, after the opening ramp), not a measured per-tile
  event-to-event interval -- a genuinely staggered field has no single "the"
  cycle length, only a distribution this collapses to one number. It is
  reported alongside the engine's own designed minimum
  (``CROPS["WHEAT"]["max_yield_day"] + 1``) as a sanity cross-check, not a
  replacement for it.
- LABOR unit-turns is a count of SUBMITTED action slots (farmer + every
  ``hands[]`` entry the agent returned that turn), matching what the
  engine's own ``interpreter`` iterates over -- not filtered by whether a
  real unit occupies that slot. An agent that padded its ``hands`` list past
  its actual hand count would inflate this; the shipped champion's
  claims-parity dispatch design does not, but this script does not verify
  that independently, so treat this as a submitted-slot count.
- "UNIT-TURNS PER COLLECTION" IS A THROUGHPUT RATIO, NOT A MARGINAL COST. It
  is TOTAL candidate unit-turns for the whole episode divided by TOTAL
  successful collections -- e.g. an observed ~25 says "one collection lands
  for every 25 turns of the farm's entire labor budget," not "a collection
  costs 25 turns to perform." The action itself is a single turn.
  dispatch.py only emits COLLECT_FERTILIZER once a unit is ALREADY standing
  on an animal tile with FEED/CARE/HARVEST resolved that same visit (see
  ``_goose_task``/``_pasture_task``), so its OWN marginal walking cost is
  near zero -- it rides a trip the agent was making anyway. That is exactly
  why this ratio is not a preview of what a brand-new FERTILIZE-wheat task
  would cost: wheat tiles are a different, and typically farther, part of
  the board than animal structures, so a new task there pays real dedicated
  travel this script does not price. Read the ratio as "how much of the
  farm's total labor budget currently turns over per collection event" --
  useful for sizing whether N new FERTILIZE actions/season would meaningfully
  compete with existing throughput, not as a per-unit labor cost.

Not a gate: prints a report and exits 0 unless the run itself broke. Ledger
the JSON under eval/recon/ if a claim leans on it.

Usage:
    uv run python tools/recon-scripts/fertilizer_economics.py
    uv run python tools/recon-scripts/fertilizer_economics.py --n-seeds 8 --seed-base 830000
    uv run python tools/recon-scripts/fertilizer_economics.py \
        --opponents zoo:tape-thunder-719,builtin:pass
    uv run python tools/recon-scripts/fertilizer_economics.py --json --out /path/to/out.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

TURNS_PER_DAY = 24
FLOOR_PRICE = 1.0
NEAR_FLOOR_MAX = 15.0
MID_BAND_MAX = 50.0
WALK_OPS = {"NORTH", "SOUTH", "EAST", "WEST"}
IDLE_OPS = {"PASS", None}


def _classify_op(op: Any) -> str:
    if op in WALK_OPS:
        return "walking"
    if op in IDLE_OPS:
        return "idle"
    return "productive"


def _price_band(price: float) -> str:
    if price > MID_BAND_MAX:
        return "above_50"
    if price >= NEAR_FLOOR_MAX:
        return "mid_15_to_50"
    return "near_floor_under_15"


@dataclass
class _Recorder:
    """Buffers seat-RESOLVED engine events for one episode.

    Seat resolution happens at record time, per turn -- see the module
    docstring's SEAT hazard. ``turn_farms`` holds at most the two farm
    objects seen so far THIS turn, in first-seen order (seat 0's block of
    ``_apply_unit_action`` calls always precedes seat 1's, and
    ``_process_market``'s per-unit lockstep loop iterates the same two
    objects afterward), and is cleared the instant a third distinct object
    turns up -- which can only be the next turn's seat 0.
    """

    turn_farms: list[Any] = field(default_factory=list)
    current_day: int = 0
    # (seat, day, op, item, price) for every SETTLED SELL/BUY_PRODUCT.
    commit_events: list[tuple[int, int, str, str, float]] = field(default_factory=list)
    # (seat, day, success) for every attempted COLLECT_FERTILIZER.
    collect_events: list[tuple[int, int, bool]] = field(default_factory=list)
    # (seat, day, category) for every submitted unit action slot.
    unit_turn_events: list[tuple[int, int, str]] = field(default_factory=list)
    # day -> FERTILIZER price after that day's last _refresh_prices call.
    price_by_day: dict[int, float] = field(default_factory=dict)

    def seat_of(self, farm: Any) -> int:
        for i, seen in enumerate(self.turn_farms):
            if seen is farm:
                return i
        if len(self.turn_farms) >= 2:
            # A third distinct farm object cannot exist in a 2-player game
            # within one turn -- this call belongs to the NEXT turn.
            self.turn_farms = []
        self.turn_farms.append(farm)
        return len(self.turn_farms) - 1


def play_and_record(
    seed: int, candidate: str, opponent: str, seat: int = 0
) -> tuple[Any, _Recorder]:
    """Run one episode with fertilizer-economics recording active, then restore.

    Follows ``harness.settlement.play_with_settlement``'s wrap-restore
    pattern (same functions wrapped for settled money: ``_process_market``
    calls ``_commit_unit`` internally), plus two extra hooks this recon needs
    and ``harness.settlement`` does not carry: ``_apply_unit_action`` (for
    the COLLECT_FERTILIZER success predicate and the labor category
    breakdown) and ``_refresh_prices`` (for the daily FERTILIZER price
    snapshot). Seat resolution is NOT ``harness.settlement``'s pattern --
    see the module docstring's SEAT hazard for why it can't be reused as-is
    here, and ``_Recorder.seat_of`` for the per-turn replacement.
    """
    from harness.episodes import resolve_agent
    from kaggle_environments import make
    from kaggle_environments.envs.kaggriculture import kaggriculture as engine

    recorder = _Recorder()
    original_cu = engine._commit_unit
    original_au = engine._apply_unit_action
    original_rp = engine._refresh_prices

    def cu_spy(
        op: str,
        item: str,
        price: float,
        farm: Any,
        private: Any,
        market: Any,
        shed_capacity: int = 100,
    ) -> bool:
        ok = original_cu(op, item, price, farm, private, market, shed_capacity)
        if ok and op in ("SELL", "BUY_PRODUCT"):
            seat = recorder.seat_of(farm)
            recorder.commit_events.append((seat, recorder.current_day, op, item, float(price)))
        return ok

    def au_spy(
        farm: Any,
        private: Any,
        idx: int,
        action: Any,
        board_size: int,
        day: int,
        turns_per_day: int,
        shed_capacity: int = 100,
    ) -> Any:
        recorder.current_day = day
        seat = recorder.seat_of(farm)
        op = action[0] if isinstance(action, list) and action else None
        if op == "COLLECT_FERTILIZER":
            # Mirrors the engine's OWN success predicate
            # (_apply_unit_action's COLLECT_FERTILIZER branch) evaluated on
            # the tile BEFORE the wrapped call mutates it -- see the SUBMITTED
            # vs SETTLED hazard in the module docstring.
            pos = farm["farmer"] if idx == 0 else (
                farm["hands"][idx - 1] if idx - 1 < len(farm["hands"]) else None
            )
            success = False
            if pos is not None:
                tile = farm["tiles"][pos[1]][pos[0]]
                success = isinstance(tile, dict) and "animal" in tile and bool(
                    tile.get("fertilizer_available")
                )
            recorder.collect_events.append((seat, day, success))
        recorder.unit_turn_events.append((seat, day, _classify_op(op)))
        return original_au(
            farm, private, idx, action, board_size, day, turns_per_day, shed_capacity
        )

    def rp_spy(market: Any) -> Any:
        result = original_rp(market)
        recorder.price_by_day[recorder.current_day] = float(market["prices"].get("FERTILIZER", 0.0))
        return result

    engine._commit_unit = cu_spy
    engine._apply_unit_action = au_spy
    engine._refresh_prices = rp_spy
    try:
        agents: list[Any] = [None, None]
        agents[seat] = resolve_agent(candidate)
        agents[1 - seat] = resolve_agent(opponent)
        env = make("kaggriculture", configuration={"seed": seed})
        env.run(agents)
    finally:
        engine._commit_unit = original_cu
        engine._apply_unit_action = original_au
        engine._refresh_prices = original_rp

    return env, recorder


@dataclass
class EpisodeReport:
    seed: int
    opponent: str
    candidate_seat: int
    # day -> count, candidate seat only.
    fert_collected_by_day: dict[int, int]
    fert_collect_attempts_by_day: dict[int, int]
    # day -> count, candidate seat only, settled SELL.
    fert_sold_units_by_day: dict[int, int]
    fert_sold_revenue_by_day: dict[int, float]
    # price band -> (units, revenue), candidate seat only.
    fert_price_bands: dict[str, tuple[int, float]]
    fert_total_units: int
    fert_total_revenue: float
    price_by_day: dict[int, float]
    first_floor_day: int | None
    # all settled item revenue, candidate seat, for cross-validation against
    # the prior probe's per-item totals.
    all_item_revenue: dict[str, float]
    # day -> standing WHEAT tile count, candidate seat.
    wheat_standing_by_day: dict[int, int]
    replant_cycle_estimate_days: float | None
    total_unit_turns: int
    unit_turns_by_category: dict[str, int]
    unit_turns_per_collection: float | None
    opponent_fert_units: int
    opponent_fert_revenue: float


def _peak_to_peak_cycle(series: dict[int, int], lo: int, hi: int) -> float | None:
    """Mean gap between local maxima of ``series`` over days [lo, hi]."""
    days = [d for d in sorted(series) if lo <= d <= hi]
    if len(days) < 3:
        return None
    peaks = []
    for i in range(1, len(days) - 1):
        d = days[i]
        if series[d] >= series[days[i - 1]] and series[d] >= series[days[i + 1]] and series[d] > 0:
            peaks.append(d)
    if len(peaks) < 2:
        return None
    # Deliberately uneven zip (peaks vs peaks[1:]) for pairwise iteration --
    # strict=True would raise on every call, since the two are ALWAYS
    # different lengths by construction.
    gaps = [b - a for a, b in zip(peaks, peaks[1:]) if b > a]  # noqa: B905
    return sum(gaps) / len(gaps) if gaps else None


def build_report(seed: int, candidate: str, opponent: str, seat: int = 0) -> EpisodeReport:
    from harness.occupancy import census

    env, rec = play_and_record(seed, candidate, opponent, seat=seat)
    opponent_seat = 1 - seat

    fert_collected_by_day: Counter[int] = Counter()
    fert_attempts_by_day: Counter[int] = Counter()
    for s, day, success in rec.collect_events:
        if s != seat:
            continue
        fert_attempts_by_day[day] += 1
        if success:
            fert_collected_by_day[day] += 1

    fert_sold_units_by_day: Counter[int] = Counter()
    fert_sold_revenue_by_day: defaultdict[int, float] = defaultdict(float)
    fert_bands: defaultdict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    all_item_revenue: defaultdict[str, float] = defaultdict(float)
    opponent_fert_units = 0
    opponent_fert_revenue = 0.0

    for s, day, op, item, price in rec.commit_events:
        if op != "SELL":
            continue
        if s == seat:
            all_item_revenue[item] += price
            if item == "FERTILIZER":
                fert_sold_units_by_day[day] += 1
                fert_sold_revenue_by_day[day] += price
                band = _price_band(price)
                fert_bands[band][0] += 1
                fert_bands[band][1] += price
        elif s == opponent_seat and item == "FERTILIZER":
            opponent_fert_units += 1
            opponent_fert_revenue += price

    fert_total_units = sum(fert_sold_units_by_day.values())
    fert_total_revenue = sum(fert_sold_revenue_by_day.values())

    first_floor_day = None
    for day in sorted(rec.price_by_day):
        if rec.price_by_day[day] <= FLOOR_PRICE:
            first_floor_day = day
            break

    wheat_census = census(env, seat=seat)
    wheat_standing_by_day = {d: c.by_crop.get("WHEAT", 0) for d, c in wheat_census.items()}
    replant_cycle = _peak_to_peak_cycle(wheat_standing_by_day, 8, 27)

    unit_turns_by_category: Counter[str] = Counter()
    total_unit_turns = 0
    for s, _day, category in rec.unit_turn_events:
        if s != seat:
            continue
        unit_turns_by_category[category] += 1
        total_unit_turns += 1

    total_collected = sum(fert_collected_by_day.values())
    unit_turns_per_collection = (total_unit_turns / total_collected) if total_collected else None

    return EpisodeReport(
        seed=seed,
        opponent=opponent,
        candidate_seat=seat,
        fert_collected_by_day=dict(fert_collected_by_day),
        fert_collect_attempts_by_day=dict(fert_attempts_by_day),
        fert_sold_units_by_day=dict(fert_sold_units_by_day),
        fert_sold_revenue_by_day=dict(fert_sold_revenue_by_day),
        fert_price_bands={k: (int(v[0]), float(v[1])) for k, v in fert_bands.items()},
        fert_total_units=fert_total_units,
        fert_total_revenue=fert_total_revenue,
        price_by_day=dict(rec.price_by_day),
        first_floor_day=first_floor_day,
        all_item_revenue=dict(all_item_revenue),
        wheat_standing_by_day=wheat_standing_by_day,
        replant_cycle_estimate_days=replant_cycle,
        total_unit_turns=total_unit_turns,
        unit_turns_by_category=dict(unit_turns_by_category),
        unit_turns_per_collection=unit_turns_per_collection,
        opponent_fert_units=opponent_fert_units,
        opponent_fert_revenue=opponent_fert_revenue,
    )


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def report_opponent(reports: list[EpisodeReport], opponent: str) -> None:
    print(f"\n{'=' * 70}\nOPPONENT: {opponent}   ({len(reports)} seeds)\n{'=' * 70}")

    totals = [r.fert_total_revenue for r in reports]
    units = [r.fert_total_units for r in reports]
    print(f"\nFERTILIZER settled revenue/seed: mean ${_mean(totals):,.0f}  "
          f"range [${min(totals):,.0f}, ${max(totals):,.0f}]")
    print(f"FERTILIZER settled units/seed:   mean {_mean(units):.1f}  "
          f"range [{min(units)}, {max(units)}]")

    band_totals: defaultdict[str, list[float]] = defaultdict(lambda: [0, 0.0])
    for r in reports:
        for band, (n, rev) in r.fert_price_bands.items():
            band_totals[band][0] += n
            band_totals[band][1] += rev
    n_seeds = len(reports)
    print("\nPrice-band decomposition (summed across seeds, then per-seed mean):")
    for band in ("above_50", "mid_15_to_50", "near_floor_under_15"):
        n, rev = band_totals.get(band, [0, 0.0])
        print(f"  {band:<22} units/seed {n / n_seeds:6.1f}   revenue/seed ${rev / n_seeds:8,.0f}")

    floor_days = [r.first_floor_day for r in reports if r.first_floor_day is not None]
    if floor_days:
        print(f"\nFirst day price hits $1 floor: mean day {_mean(floor_days):.1f}  "
              f"(seeds that floored: {len(floor_days)}/{n_seeds})")
    else:
        print("\nPrice never hit the $1 floor in any seed.")

    collected = [sum(r.fert_collected_by_day.values()) for r in reports]
    attempts = [sum(r.fert_collect_attempts_by_day.values()) for r in reports]
    print(f"\nCOLLECT_FERTILIZER: attempted/seed mean {_mean(attempts):.1f}, "
          f"succeeded/seed mean {_mean(collected):.1f} "
          f"(success rate {100 * sum(collected) / max(1, sum(attempts)):.0f}%)")

    wheat_means = []
    for r in reports:
        vals = [v for d, v in r.wheat_standing_by_day.items() if 10 <= d <= 28]
        if vals:
            wheat_means.append(_mean(vals))
    if wheat_means:
        print(f"\nStanding WHEAT tiles (days 10-28): mean {_mean(wheat_means):.1f} "
              f"range [{min(wheat_means):.0f}, {max(wheat_means):.0f}]")
    cycles = [r.replant_cycle_estimate_days for r in reports if r.replant_cycle_estimate_days]
    if cycles:
        print(f"Empirical replant cycle (peak-to-peak, days 8-27): mean {_mean(cycles):.1f} days "
              f"across {len(cycles)}/{n_seeds} seeds with >=2 peaks")
    print("Engine-designed minimum WHEAT cycle "
          "(CROPS['WHEAT']['max_yield_day'] + 1): 5 days")

    turns = [r.total_unit_turns for r in reports]
    cat_totals: Counter[str] = Counter()
    for r in reports:
        cat_totals.update(r.unit_turns_by_category)
    total_cat = sum(cat_totals.values()) or 1
    print(f"\nLabor: total unit-turns/seed mean {_mean(turns):.0f}")
    for cat in ("walking", "productive", "idle"):
        n = cat_totals.get(cat, 0)
        print(f"  {cat:<12} {n:6d}  ({100 * n / total_cat:5.1f}% of all seeds' unit-turns)")
    per_collect = [r.unit_turns_per_collection for r in reports if r.unit_turns_per_collection]
    if per_collect:
        print(
            f"Total-labor-budget turns per successful COLLECT_FERTILIZER: "
            f"mean {_mean(per_collect):.1f} "
            "(a throughput ratio, NOT the action's own cost -- see module docstring hazard)"
        )

    opp_units = [r.opponent_fert_units for r in reports]
    opp_rev = [r.opponent_fert_revenue for r in reports]
    print(f"\nOPPONENT's own settled FERTILIZER: units/seed mean {_mean(opp_units):.1f}  "
          f"revenue/seed mean ${_mean(opp_rev):,.0f}")

    print("\nAll-item settled revenue/seed (candidate), for cross-validation "
          "against the prior probe's per-item totals:")
    item_totals: defaultdict[str, float] = defaultdict(float)
    for r in reports:
        for item, rev in r.all_item_revenue.items():
            item_totals[item] += rev
    for item, rev in sorted(item_totals.items(), key=lambda kv: -kv[1]):
        print(f"  {item:<12} ${rev / n_seeds:9,.0f}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seed-base", type=int, default=830000)
    ap.add_argument("--n-seeds", type=int, default=8)
    ap.add_argument(
        "--seeds",
        default=None,
        help="explicit comma-separated seed list, overrides --seed-base/--n-seeds",
    )
    ap.add_argument("--candidate", default="champion")
    ap.add_argument("--opponents", default="zoo:tape-thunder-719,builtin:pass")
    ap.add_argument("--seat", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=None, help="write JSON ledger to this path")
    args = ap.parse_args()

    if args.seeds:
        seeds = [int(s) for s in args.seeds.split(",")]
    else:
        seeds = [args.seed_base + i for i in range(args.n_seeds)]

    opponents = [o.strip() for o in args.opponents.split(",") if o.strip()]

    all_reports: dict[str, list[EpisodeReport]] = {}
    skipped: dict[str, str] = {}
    for opponent in opponents:
        rows = []
        for seed in seeds:
            try:
                rows.append(build_report(seed, args.candidate, opponent, seat=args.seat))
            except Exception as exc:  # noqa: BLE001 -- recon script: report and move on
                skipped[opponent] = f"seed {seed}: {exc!r}"
                print(f"\n!! {opponent} seed {seed} failed: {exc!r} -- skipping this opponent")
                break
        if rows:
            all_reports[opponent] = rows

    print(f"seeds: {seeds}")
    for opponent, rows in all_reports.items():
        report_opponent(rows, opponent)

    print(f"\n{'=' * 70}\nSUMMARY ACROSS OPPONENTS\n{'=' * 70}")
    for opponent, rows in all_reports.items():
        near_floor_rev = (
            sum(r.fert_price_bands.get("near_floor_under_15", (0, 0.0))[1] for r in rows)
            / len(rows)
        )
        total_rev = _mean([r.fert_total_revenue for r in rows])
        if total_rev:
            pct = 100 * near_floor_rev / total_rev
            print(
                f"{opponent:<24} total ${total_rev:8,.0f}/seed   "
                f"near-floor ${near_floor_rev:8,.0f}/seed   ({pct:.0f}% near floor)"
            )
        else:
            print(f"{opponent:<24} no revenue")

    if args.json or args.out:
        out = {
            "identity": {
                "candidate": args.candidate,
                "opponents": opponents,
                "seat": args.seat,
                "seeds": seeds,
                "skipped": skipped,
            },
            "by_opponent": {
                opponent: [
                    {
                        "seed": r.seed,
                        "fert_total_units": r.fert_total_units,
                        "fert_total_revenue": r.fert_total_revenue,
                        "fert_price_bands": r.fert_price_bands,
                        "fert_collected_by_day": r.fert_collected_by_day,
                        "fert_collect_attempts_by_day": r.fert_collect_attempts_by_day,
                        "fert_sold_units_by_day": r.fert_sold_units_by_day,
                        "fert_sold_revenue_by_day": r.fert_sold_revenue_by_day,
                        "price_by_day": r.price_by_day,
                        "first_floor_day": r.first_floor_day,
                        "all_item_revenue": r.all_item_revenue,
                        "wheat_standing_by_day": r.wheat_standing_by_day,
                        "replant_cycle_estimate_days": r.replant_cycle_estimate_days,
                        "total_unit_turns": r.total_unit_turns,
                        "unit_turns_by_category": r.unit_turns_by_category,
                        "unit_turns_per_collection": r.unit_turns_per_collection,
                        "opponent_fert_units": r.opponent_fert_units,
                        "opponent_fert_revenue": r.opponent_fert_revenue,
                    }
                    for r in rows
                ]
                for opponent, rows in all_reports.items()
            },
        }
        if args.json:
            print("\n" + json.dumps(out, indent=2, default=str))
        if args.out:
            with open(args.out, "w") as fh:
                json.dump(out, fh, indent=2, default=str)
            print(f"\nledger -> {args.out}")


if __name__ == "__main__":
    main()
