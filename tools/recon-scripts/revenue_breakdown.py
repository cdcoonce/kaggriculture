"""Per-item settled revenue breakdown for OUR seat (seat 0) across strawberry
policy arms, vs the shipped agent (strawberry off), on seeds 855000-855007.

Recon only. It never modifies packages/ or git state, and it writes only the
JSON named by --out (the committed record lives under eval/recon/).

Uses harness.settlement.play_with_settlement (the same primitive
harness.opponent_split.split_ledger replays with) to play one game per
(arm, seed) with our agent ("champion", with the arm's PolicyConfig
overrides) in seat 0 and public:sokolovsky-v12 in seat 1 -- exactly the
construction tools/recon-scripts/early_cash_ledger.py uses
(make("kaggriculture", configuration={"seed": seed}) then
env.run([resolve_agent("champion", cfg), resolve_agent(opponent)])), except
play_with_settlement also patches the engine's own commit functions to
record SETTLED (not submitted) SELL/BUY_PRODUCT fills and the two
bypass-commit money paths (HIRE, BUY_LAND), then restores them.

Per harness.opponent_split's own hazard notes (read directly from that
module before writing this script):

- SUBMITTED-vs-SETTLED: only harness.settlement.Settlement's post-fill
  revenue/spend maps are read here -- never a raw action -- so a rejected
  order (insufficient stock/money, full shed) contributes nothing, matching
  the instrument's own contract.
- SEAT: seat 0 is ALWAYS our agent and seat 1 is ALWAYS the opponent in
  every episode this script plays (play_with_settlement(..., seat=0)) --
  there is no seat-swap here (unlike split_ledger's seat-averaging, which
  this task does not need: we want one fixed seat assignment, not a
  seat-symmetric gate statistic).
- CONSERVATION: episode_residual(settlement, seat, final_money,
  starting_money) must be exactly 0 for both seats of every episode. Checked
  and reported below; the run stops before trusting a breakdown if it isn't.

Usage:
    uv run python revenue_breakdown.py                    # full 4 arms x 8 seeds
    uv run python revenue_breakdown.py --seeds 855000      # smoke test, 1 seed
    uv run python revenue_breakdown.py --arms shipped      # smoke test, 1 arm
    uv run python revenue_breakdown.py --workers 6

Run from the kaggriculture repo root with `uv run python`, per task fence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# --- fixed problem definition (per task spec) -------------------------------

ALL_SEEDS: list[int] = list(range(855000, 855008))  # 855000..855007 inclusive, 8 seeds
OPPONENT = "public:sokolovsky-v12"
CANDIDATE = "champion"
OUR_SEAT = 0
OPPONENT_SEAT = 1

ALL_ARMS: dict[str, dict[str, Any]] = {
    "shipped": {},
    "START8": {
        "strawberry_tile_target": 31,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 8,
    },
    "START10": {
        "strawberry_tile_target": 31,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 10,
    },
    "T20": {
        "strawberry_tile_target": 20,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 8,
    },
    "SW25_FIX": {
        "strawberry_frame_quadrants": ["SW"],
        "strawberry_tile_target": 25,
        "strawberry_plant_daily_cap": 10,
        "strawberry_start_day": 9,
        "strawberry_plant_priority": 2,
        "strawberry_fert_reserve": "planted",
    },
    # The never-gated knob screen's arms
    # (eval/prereg/2026-09-12-never-gated-knob-screen.md). Each names one
    # traded item and one direction; the registered expression check reads
    # that item's settled flow out of this instrument's per-item table.
    "RW": {"rescue_water": True},
    "RW_H10": {"rescue_water": True, "max_hires_per_turn": 10},
    "SHEEP1": {"animal_buy_order": ["SHEEP", "COW"]},
}

# Known-good means for OUR seat (seat 0), averaged over the 8 seeds, from a
# prior deterministic run of these exact games -- the task's stop/go gate.
KNOWN_TARGET_MEANS: dict[str, float] = {
    "shipped": 66163,
    "START8": 72725,
    "START10": 74047,
    "T20": 73122,
    "SW25_FIX": 64324,  # the slice-2 expression-check record's mean
}

# Engine default (configuration["startingMoney"]), independently confirmed
# both from harness.opponent_split.DEFAULT_STARTING_MONEY and directly from
# the vendored engine (kaggle_environments/envs/kaggriculture/kaggriculture.py:
# `starting_money = int(get(configuration, "startingMoney", 3000))`). Never
# used to configure a replay -- only as episode_residual's baseline.
STARTING_MONEY = 3000.0

# Print/report column order for revenue and BUY_PRODUCT cost. Any item key
# the instrument reports that isn't in this list is bucketed under "OTHERS".
ITEM_ORDER: list[str] = ["STRAWBERRY", "WHEAT", "MILK", "WOOL", "EGG", "MELON", "FERTILIZER"]

# Fixed-spend category display order. Any spend key the instrument reports
# that isn't listed here is bucketed under "OTHERS" too.
FIXED_CATEGORY_ORDER: list[str] = [
    "BUY_SEED:WHEAT",
    "BUY_SEED:STRAWBERRY",
    "BUY_SEED:MELON",
    "BUY_ANIMAL:COW",
    "BUY_ANIMAL:SHEEP",
    "BUY_ANIMAL:GOOSE",
    "HIRE",
    "BUY_LAND",
]


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


# --- worker (runs in a subprocess) ------------------------------------------


def _play_one(arm: str, seed: int, cfg: dict[str, Any]) -> dict[str, Any]:
    """Play one (arm, seed) episode and return a plain-dict Settlement snapshot.

    Module-level and picklable-args-only (arm: str, seed: int, cfg: dict), so
    it can run under ProcessPoolExecutor with the default 'spawn' start method
    on macOS -- each worker re-imports kaggle_environments/harness/agent fresh,
    exactly like harness.opponent_split.split_ledger's own workers>1 branch
    (which submits play_with_settlement directly, one task per episode).
    """
    import kaggle_environments as k

    assert k.__version__ == "1.32.7", (
        f"worker: engine {k.__version__} != 1.32.7 (arm={arm} seed={seed})"
    )
    from harness.settlement import play_with_settlement

    agent_config = cfg if cfg else None
    t0 = time.monotonic()
    settlement = play_with_settlement(seed, CANDIDATE, OPPONENT, agent_config, seat=OUR_SEAT)
    elapsed = time.monotonic() - t0

    return {
        "arm": arm,
        "seed": seed,
        "elapsed_s": elapsed,
        "final_money": list(settlement.final_money),
        "revenue": {s: dict(settlement.revenue.get(s, {})) for s in (0, 1)},
        "spend": {s: dict(settlement.spend.get(s, {})) for s in (0, 1)},
        "units": {s: dict(settlement.units.get(s, {})) for s in (0, 1)},
        "calls": settlement.calls,
        "filled": settlement.filled,
        "rejected": settlement.rejected,
    }


# --- per-episode decomposition (main process) -------------------------------


def _seat_breakdown(episode: dict[str, Any], seat: int) -> dict[str, Any]:
    """Split one seat's settled flows into revenue / BUY_PRODUCT cost / fixed spend."""
    revenue = dict(episode["revenue"].get(seat, episode["revenue"].get(str(seat), {})))
    spend = dict(episode["spend"].get(seat, episode["spend"].get(str(seat), {})))
    units = dict(episode["units"].get(seat, episode["units"].get(str(seat), {})))

    buy_product_cost = {
        key.removeprefix("BUY_PRODUCT:"): value
        for key, value in spend.items()
        if key.startswith("BUY_PRODUCT:")
    }
    fixed_spend = {key: value for key, value in spend.items() if not key.startswith("BUY_PRODUCT:")}

    return {
        "revenue": revenue,
        "buy_product_cost": buy_product_cost,
        "fixed_spend": fixed_spend,
        "final_money": episode["final_money"][seat],
        "units": units,
    }


def _episode_residual(episode: dict[str, Any], seat: int) -> float:
    """Re-derive harness.opponent_split.episode_residual from the plain-dict snapshot.

    Reimplemented (not imported) because workers return plain dicts, not
    harness.settlement.Settlement objects -- but the arithmetic is copied
    verbatim from opponent_split.opponent_flows + episode_residual so the
    identity checked is the SAME one that module defines, not a look-alike.
    Cross-checked against the real functions in main() via a live import
    before this is trusted (see verify_instrument_agrees()).
    """
    revenue = episode["revenue"][seat]
    spend = episode["spend"][seat]
    buyback_items = {
        key.removeprefix("BUY_PRODUCT:") for key in spend if key.startswith("BUY_PRODUCT:")
    }
    per_item_market = {
        item: revenue.get(item, 0.0) - spend.get(f"BUY_PRODUCT:{item}", 0.0)
        for item in set(revenue) | buyback_items
    }
    fixed_price_map = {
        key: -value for key, value in spend.items() if not key.startswith("BUY_PRODUCT:")
    }
    final_money = episode["final_money"][seat]
    return (
        final_money
        - STARTING_MONEY
        - sum(per_item_market.values())
        - sum(fixed_price_map.values())
    )


def verify_instrument_agrees(sample_episode: dict[str, Any]) -> None:
    """Sanity check: our re-derivation above must match the REAL, imported
    harness.opponent_split functions bit-for-bit on a real episode, not just
    on the module's own hand-built fixtures. Raises loudly if they diverge --
    that would mean this script's copy of the arithmetic has drifted from the
    instrument it claims to use.
    """
    from harness.opponent_split import episode_residual
    from harness.settlement import Settlement

    settlement = Settlement(
        seed=sample_episode["seed"],
        final_money=list(sample_episode["final_money"]),
        units={s: dict(sample_episode["units"][s]) for s in (0, 1)},
        revenue={s: dict(sample_episode["revenue"][s]) for s in (0, 1)},
        spend={s: dict(sample_episode["spend"][s]) for s in (0, 1)},
    )
    for seat in (0, 1):
        real = episode_residual(
            settlement, seat, sample_episode["final_money"][seat], STARTING_MONEY
        )
        mine = _episode_residual(sample_episode, seat)
        if real != mine:
            raise AssertionError(
                f"revenue_breakdown._episode_residual drifted from the real "
                f"harness.opponent_split.episode_residual: seat={seat} "
                f"real={real!r} mine={mine!r}"
            )


def _mean_map(maps: list[dict[str, float]]) -> dict[str, float]:
    keys = set()
    for m in maps:
        keys.update(m)
    n = len(maps)
    return {k: sum(m.get(k, 0.0) for m in maps) / n for k in keys}


def _ordered_rows(mean_map: dict[str, float], order: list[str]) -> list[tuple[str, float]]:
    rows = [(k, mean_map.get(k, 0.0)) for k in order if k in mean_map]
    others = {k: v for k, v in mean_map.items() if k not in order}
    if others:
        rows.append(("OTHERS", sum(others.values())))
    return rows


# --- reporting ---------------------------------------------------------------


def print_table(title: str, arms: list[str], row_keys_per_arm: dict[str, dict[str, float]]) -> None:
    all_keys: list[str] = []
    seen = set()
    for arm in arms:
        for k, _ in row_keys_per_arm[arm]:
            if k not in seen:
                seen.add(k)
                all_keys.append(k)
    means = {arm: dict(row_keys_per_arm[arm]) for arm in arms}

    print(f"\n--- {title} ---")
    header = f"{'line':<16}" + "".join(f"{arm:>14}" for arm in arms)
    if "shipped" in arms:
        header += "".join(f"{'d(' + arm + ')':>14}" for arm in arms if arm != "shipped")
    print(header)
    for key in all_keys:
        row = f"{key:<16}" + "".join(f"{means[arm].get(key, 0.0):>14,.2f}" for arm in arms)
        if "shipped" in arms:
            base = means["shipped"].get(key, 0.0)
            row += "".join(
                f"{means[arm].get(key, 0.0) - base:>14,.2f}" for arm in arms if arm != "shipped"
            )
        print(row)
    total_row = f"{'TOTAL':<16}" + "".join(
        f"{sum(means[arm].values()):>14,.2f}" for arm in arms
    )
    if "shipped" in arms:
        base_total = sum(means["shipped"].values())
        total_row += "".join(
            f"{sum(means[arm].values()) - base_total:>14,.2f}" for arm in arms if arm != "shipped"
        )
    print(total_row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        default=",".join(str(s) for s in ALL_SEEDS),
        help="comma-separated seeds (default: 855000..855007)",
    )
    parser.add_argument(
        "--arms",
        default=",".join(ALL_ARMS),
        help="comma-separated arm names (default: all 4)",
    )
    parser.add_argument("--workers", type=int, default=6, help="process pool size (default 6)")
    parser.add_argument(
        "--out",
        required=True,
        help="output JSON path (committed records live under eval/recon/)",
    )
    args = parser.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",") if s]
    arm_names = [a for a in args.arms.split(",") if a]
    arms = {name: ALL_ARMS[name] for name in arm_names}

    import kaggle_environments as k

    engine_version = k.__version__
    print(f"engine version: {engine_version}")
    assert engine_version == "1.32.7", f"ABORT: engine {engine_version}; requires 1.32.7"

    identity = {
        "script": "tools/recon-scripts/revenue_breakdown.py",
        "cwd": str(Path.cwd()),
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty_packages": bool(_git("status", "--porcelain", "--", "packages")),
        "engine": engine_version,
        "candidate": CANDIDATE,
        "opponent": OPPONENT,
        "our_seat": OUR_SEAT,
        "opponent_seat": OPPONENT_SEAT,
        "starting_money": STARTING_MONEY,
        "seeds": seeds,
        "arms": arms,
        "workers": args.workers,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    print("identity:", json.dumps(identity, indent=2))

    tasks = [(arm, seed, cfg) for arm, cfg in arms.items() for seed in seeds]
    print(f"\nplaying {len(tasks)} episodes ({len(arms)} arms x {len(seeds)} seeds) "
          f"with up to {args.workers} worker processes...")

    episodes: dict[tuple[str, int], dict[str, Any]] = {}
    t_start = time.monotonic()
    with ProcessPoolExecutor(max_workers=min(args.workers, len(tasks))) as pool:
        futures = {pool.submit(_play_one, arm, seed, cfg): (arm, seed) for arm, seed, cfg in tasks}
        done = 0
        for fut in as_completed(futures):
            arm, seed = futures[fut]
            episode = fut.result()
            episodes[(arm, seed)] = episode
            done += 1
            print(
                f"  [{done}/{len(tasks)}] {arm} seed={seed} "
                f"our_final={episode['final_money'][OUR_SEAT]:,.2f} "
                f"opp_final={episode['final_money'][OPPONENT_SEAT]:,.2f} "
                f"({episode['elapsed_s']:.1f}s)",
                file=sys.stderr,
            )
    print(f"all episodes played in {time.monotonic() - t_start:.1f}s total")

    # Sanity: our hand-copied residual arithmetic must agree with the real
    # harness.opponent_split.episode_residual on a real episode before it is
    # trusted for the validation gate below.
    verify_instrument_agrees(next(iter(episodes.values())))

    # --- VALIDATION (1): conservation residual must be 0 on every episode, both seats
    violations: list[dict[str, Any]] = []
    max_residual = 0.0
    for (arm, seed), episode in episodes.items():
        for seat in (0, 1):
            residual = _episode_residual(episode, seat)
            max_residual = max(max_residual, abs(residual))
            if residual != 0.0:
                violations.append(
                    {"arm": arm, "seed": seed, "seat": seat, "residual": residual}
                )

    print(f"\n=== VALIDATION (1): conservation residual ===")
    print(f"max |residual| across {len(episodes) * 2} (episode, seat) pairs: {max_residual!r}")
    if violations:
        print(f"NONZERO RESIDUALS: {len(violations)}")
        for v in violations:
            print(f"  arm={v['arm']} seed={v['seed']} seat={v['seat']} residual={v['residual']!r}")
    else:
        print("PASS: residual == 0 on every (episode, seat) pair.")

    # --- VALIDATION (2): our seat's mean final money vs known values
    print(f"\n=== VALIDATION (2): our-seat mean final money vs known deterministic run ===")
    means_seat0: dict[str, float] = {}
    validation_ok = True
    for arm in arms:
        vals = [episodes[(arm, seed)]["final_money"][OUR_SEAT] for seed in seeds]
        mean_val = sum(vals) / len(vals)
        means_seat0[arm] = mean_val
        expected = KNOWN_TARGET_MEANS.get(arm)
        if expected is not None and len(seeds) == len(ALL_SEEDS) and set(seeds) == set(ALL_SEEDS):
            diff = mean_val - expected
            ok = abs(round(mean_val) - expected) < 0.5
            validation_ok = validation_ok and ok
            print(
                f"  {arm:<10} observed_mean={mean_val:,.4f}  expected={expected:,.0f}  "
                f"diff={diff:+.4f}  {'PASS' if ok else 'FAIL'}"
            )
        else:
            print(f"  {arm:<10} observed_mean={mean_val:,.4f}  (partial seed set, no check)")

    full_run = len(seeds) == len(ALL_SEEDS) and set(seeds) == set(ALL_SEEDS)
    full_arms = set(arm_names) == set(ALL_ARMS)
    if full_run and full_arms and not validation_ok:
        print(
            "\nSTOP: our-seat mean final money does NOT reproduce the known "
            "deterministic-run values to the dollar. Not producing a trusted "
            "breakdown -- see the per-arm PASS/FAIL lines above for which arm(s) "
            "diverged, and the residual check above for whether conservation "
            "itself already broke (which would point at the instrument/engine "
            "rather than at seat/config wiring)."
        )
        # Still write the raw episodes + partial validation for diagnosis.
        diag_path = Path(args.out).with_name("FAILED_" + Path(args.out).name)
        diag_path.write_text(
            json.dumps(
                {
                    "identity": identity,
                    "validation": {
                        "max_residual": max_residual,
                        "violations": violations,
                        "means_seat0": means_seat0,
                        "expected_means_seat0": KNOWN_TARGET_MEANS,
                    },
                    "raw_episodes": {
                        f"{arm}|{seed}": ep for (arm, seed), ep in episodes.items()
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"diagnostic dump written: {diag_path}")
        return 1

    # --- Build per-arm/seed/seat breakdown -----------------------------------
    results: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in arms:
        results[arm] = {}
        for seed in seeds:
            episode = episodes[(arm, seed)]
            results[arm][str(seed)] = {
                "seat_0_ours": _seat_breakdown(episode, 0),
                "seat_1_opponent": _seat_breakdown(episode, 1),
                "calls": episode["calls"],
                "filled": episode["filled"],
                "rejected": episode["rejected"],
            }

    # --- Means per arm per seat ------------------------------------------------
    means: dict[str, dict[str, Any]] = {}
    for arm in arms:
        seat0_list = [results[arm][str(seed)]["seat_0_ours"] for seed in seeds]
        seat1_list = [results[arm][str(seed)]["seat_1_opponent"] for seed in seeds]

        def _agg(seat_list: list[dict[str, Any]]) -> dict[str, Any]:
            revenue_mean = _mean_map([s["revenue"] for s in seat_list])
            cost_mean = _mean_map([s["buy_product_cost"] for s in seat_list])
            fixed_mean = _mean_map([s["fixed_spend"] for s in seat_list])
            units_mean = _mean_map([s["units"] for s in seat_list])
            final_mean = sum(s["final_money"] for s in seat_list) / len(seat_list)
            straw_units_total = sum(s["units"].get("STRAWBERRY", 0) for s in seat_list)
            straw_rev_total = sum(s["revenue"].get("STRAWBERRY", 0.0) for s in seat_list)
            straw_price = (straw_rev_total / straw_units_total) if straw_units_total else None
            return {
                "revenue": revenue_mean,
                "buy_product_cost": cost_mean,
                "fixed_spend": fixed_mean,
                "units": units_mean,
                "final_money": final_mean,
                "strawberry_units_sold_total_over_seeds": straw_units_total,
                "strawberry_units_sold_mean_per_seed": straw_units_total / len(seat_list),
                "strawberry_mean_realized_price": straw_price,
            }

        means[arm] = {
            "seat_0_ours": _agg(seat0_list),
            "seat_1_opponent": _agg(seat1_list),
        }

    # --- Deltas vs shipped ------------------------------------------------------
    deltas: dict[str, dict[str, Any]] = {}
    if "shipped" in arms:
        base0 = means["shipped"]["seat_0_ours"]
        base1 = means["shipped"]["seat_1_opponent"]
        for arm in arms:
            if arm == "shipped":
                continue

            def _diff_agg(agg: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
                return {
                    "revenue": _mean_map_diff(agg["revenue"], base["revenue"]),
                    "buy_product_cost": _mean_map_diff(agg["buy_product_cost"], base["buy_product_cost"]),
                    "fixed_spend": _mean_map_diff(agg["fixed_spend"], base["fixed_spend"]),
                    "final_money": agg["final_money"] - base["final_money"],
                }

            deltas[arm] = {
                "seat_0_ours": _diff_agg(means[arm]["seat_0_ours"], base0),
                "seat_1_opponent": _diff_agg(means[arm]["seat_1_opponent"], base1),
            }

    # --- Write JSON ---------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "identity": identity,
        "validation": {
            "conservation_max_abs_residual": max_residual,
            "conservation_violations": violations,
            "final_money_seat0_means": means_seat0,
            "final_money_seat0_expected": KNOWN_TARGET_MEANS,
            "final_money_seat0_validated": full_run and full_arms and validation_ok,
        },
        "per_arm_per_seed": results,
        "means_per_arm": means,
        "deltas_vs_shipped": deltas,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {out_path}")

    # --- Printed tables -------------------------------------------------------
    arm_list = list(arms)

    def rows_for(seat_key: str, field: str, order: list[str]) -> dict[str, list[tuple[str, float]]]:
        return {arm: _ordered_rows(means[arm][seat_key][field], order) for arm in arm_list}

    print("\n\n########## OUR SEAT (seat 0, champion + arm cfg) ##########")
    print_table("revenue by item ($)", arm_list, rows_for("seat_0_ours", "revenue", ITEM_ORDER))
    print_table(
        "BUY_PRODUCT cost by item ($)",
        arm_list,
        rows_for("seat_0_ours", "buy_product_cost", ITEM_ORDER),
    )
    print_table(
        "fixed-price spend by category ($)",
        arm_list,
        rows_for("seat_0_ours", "fixed_spend", FIXED_CATEGORY_ORDER),
    )
    print("\n--- final money ($) ---")
    header = f"{'':<16}" + "".join(f"{arm:>14}" for arm in arm_list)
    if "shipped" in arm_list:
        header += "".join(f"{'d(' + arm + ')':>14}" for arm in arm_list if arm != "shipped")
    print(header)
    row = f"{'final_money':<16}" + "".join(
        f"{means[arm]['seat_0_ours']['final_money']:>14,.2f}" for arm in arm_list
    )
    if "shipped" in arm_list:
        base = means["shipped"]["seat_0_ours"]["final_money"]
        row += "".join(
            f"{means[arm]['seat_0_ours']['final_money'] - base:>14,.2f}"
            for arm in arm_list
            if arm != "shipped"
        )
    print(row)

    print("\n--- strawberry units sold (mean per seed) and mean realized price ---")
    for arm in arm_list:
        agg = means[arm]["seat_0_ours"]
        price = agg["strawberry_mean_realized_price"]
        price_str = f"{price:,.2f}" if price is not None else "N/A (0 units)"
        print(
            f"  {arm:<10} units_sold_mean={agg['strawberry_units_sold_mean_per_seed']:>8.2f}  "
            f"mean_realized_price={price_str}"
        )

    print("\n\n########## OPPONENT SEAT (seat 1, public:sokolovsky-v12) ##########")
    print_table("revenue by item ($)", arm_list, rows_for("seat_1_opponent", "revenue", ITEM_ORDER))
    print_table(
        "BUY_PRODUCT cost by item ($)",
        arm_list,
        rows_for("seat_1_opponent", "buy_product_cost", ITEM_ORDER),
    )
    print_table(
        "fixed-price spend by category ($)",
        arm_list,
        rows_for("seat_1_opponent", "fixed_spend", FIXED_CATEGORY_ORDER),
    )
    print("\n--- final money ($) ---")
    print(header)
    row = f"{'final_money':<16}" + "".join(
        f"{means[arm]['seat_1_opponent']['final_money']:>14,.2f}" for arm in arm_list
    )
    if "shipped" in arm_list:
        base = means["shipped"]["seat_1_opponent"]["final_money"]
        row += "".join(
            f"{means[arm]['seat_1_opponent']['final_money'] - base:>14,.2f}"
            for arm in arm_list
            if arm != "shipped"
        )
    print(row)

    return 0


def _mean_map_diff(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    keys = set(a) | set(b)
    return {k: a.get(k, 0.0) - b.get(k, 0.0) for k in keys}


if __name__ == "__main__":
    raise SystemExit(main())
