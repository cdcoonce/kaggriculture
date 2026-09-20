"""Cross-band variance sweep (kaggriculture#165, step 1).

Recon only. Reads committed `eval/gates/*.json` ledgers; never runs a game,
never consumes a seed or a band, never writes to `eval/gates/`. Does not
touch `packages/harness/src/harness/stats.py` or any estimator/pooling
formula -- this script is a consumer of `money_verdict`'s output, not a
change to how it is computed.

## The question

`harness.stats.money_verdict` derives `stderr` from per-seed dispersion
within ONE run (`packages/harness/src/harness/stats.py:599-608`). Nothing in
that estimator has a `seed_manifest.seed_base` ("band") term. If some
mechanism makes seeds within a band more alike than seeds across bands, every
BETWEEN-band comparison in `eval/gates/` looks more significant than it is,
while within-band comparisons (what every registered verdict to date uses)
stay valid. #165's step 1 counts how many cross-band comparisons of "the same
arm" exist in the corpus and asks whether their z-scores look like draws from
the per-seed model, SEPARATELY for the population #82/`shop_roster_coupling.py`
already has an explanation for (arms that touch a tile-occupancy knob) and
the population that would actually be new evidence (arms that don't).

## Grouping: pooling across opponents within a band (a documented deviation)

The issue's own Step 1 text says group by "identity.agent_config,
identity.opponent, and identity.baseline". Read literally (opponent as a hard
match key), the STACK3-vs-champion example the issue itself works through
(881000 vs 888000, "sqrt(1174^2+1119^2) = $1,622, 2.98 se") does NOT
reproduce: those two bands were each measured against THREE different public
leaders (sokolovsky/rayk/kaito) as separate money-gate ledgers, each already
at n_seeds=64, and the issue's "pooled Delta $3,637 / pooled se $1,174" for
881000 is a pool ACROSS those three opponent-conditioned ledgers, not any
single one of them (verified below).

This script therefore groups by (`agent_config`, `baseline`,
`baseline_agent_config`) -- WITHOUT `opponent` -- and pools every ledger
sharing a (group, `seed_manifest.seed_base`) cell, regardless of which
opponent it used, into one band-level (mean, se) via:

    pooled_mean = mean(ledger means)                    # equal-weight
    pooled_se   = sqrt(sum(ledger se ** 2)) / k          # independent-variance
                                                          # propagation of that
                                                          # equal-weight mean

Verified against the issue's own worked numbers before trusting it for this
sweep (both reproduce to the reported precision; see
`_verify_known_cross_checks`):

  - STACK3 vs champion, 881000 vs 888000 (3 opponents pooled each side):
    reproduces pooled Delta +$3,637 / -$1,203, pooled se $1,174 / $1,119,
    z = -2.98 (this issue's own cross-check number).
  - STACK3 vs frozen:m3b_live_b6ce655, 891000 vs 892000 (#167/#169/#170,
    3 opponents pooled each side): reproduces +$3,722 / +$7,390, z = 3.45
    (the terminal-freeze issue's own cross-check number).

A naive per-opponent grouping (opponent IN the key) does not reproduce
either number -- each of the 3 per-opponent z's for 881000-vs-888000 lands
between -2.3 and -1.4, none near -2.98 -- because the panel-of-opponents
design is a robustness replicate of ONE underlying arm-vs-baseline effect,
not three independent questions. Pooling collapses to the single-ledger case
automatically whenever only one opponent was used at a band (the common
case), so this is a strict generalization, not a special case bolted on for
STACK3.

## Occupancy classification (no explicit knob-list constant exists)

Neither `harness/shop_roster.py` nor `shop_roster_coupling.py` defines a
knob-list constant -- the recon script takes one arbitrary `--knob` name and
measures its effect empirically, one knob at a time. So the set below is
DERIVED, not looked up, from first principles anchored in the same module's
own mechanism plus the vendored engine source
(`kaggle_environments/envs/kaggriculture/kaggriculture.py`):

  - `shop_roster._combined_bare` counts a farm tile as "bare" iff
    `tile is None`, summed over `farm["tiles"]` for both seats.
  - The engine's tile-writing ops are exactly `PLANT` (writes a crop dict),
    `BUILD_PASTURE` / `BUILD_COOP` (write `{"kind": "PASTURE"/"COOP"}` --
    confirmed at kaggriculture.py's op handlers, so COW/SHEEP/GOOSE purchases
    DO touch the same tile grid the bare-tile census reads, not a separate
    pasture counter), and `DIG` (writes tile back to `None`).

A `PolicyConfig` field is classified occupancy-affecting here iff it sets a
target / cap / eligible-frame / day-or-hour gate that is read DIRECTLY by one
of those tile-writing ops or by the dispatch priority that decides whether
such an op fires on a given turn. This is a first-order/direct-effect rule,
stated explicitly because no canonical list exists to defer to (see the
task's own instruction to document a self-invented classification rather
than silently assume one). It does NOT reach second-order channels (e.g. a
labor knob that could shift which day a crew gets around to a PLANT task
under contention, or `rescue_water`/weed dynamics that also flip a tile's
bare/non-bare state) -- `shop_roster_coupling.py` itself does not attempt to
bound those either; doing so would need simulation, which this recon-only
sweep (no game runs) cannot do. See OCCUPANCY_FIELDS / EXCLUDED_FIELDS below
for the full, itemized set and the exclusion reasons, and the companion
markdown for the same table in prose.

## The statistical test

One-sample two-sided Kolmogorov-Smirnov statistic and its ASYMPTOTIC p-value
(Kolmogorov distribution; the reference is the fully-specified N(0,1), not a
distribution with parameters estimated from this sample, so the plain
sqrt(n)*D asymptotic form applies -- not the Lilliefors/Stephens correction,
which is for the estimated-parameter case). Implemented by hand
(`math.erf` only, no scipy import): tools/recon-scripts carries no PEP 723
inline-dependency convention for any existing script, so this follows "no
existing pattern to extend" and implements the ~20-line routine instead of
adding a dependency to the script, per task fence. Cross-validated against
`scipy.stats.kstest(..., mode="asymp")` during development across n in
{5, 12, 30, 60, 100} and an over-dispersed positive control -- all matched
to 6 decimal places; scipy is not imported here.

Usage:
    uv run python tools/recon-scripts/cross_band_variance_sweep.py
    uv run python tools/recon-scripts/cross_band_variance_sweep.py --gates-dir eval/gates
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import subprocess
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# --- occupancy classification (see module docstring for the derivation) -----

#: PolicyConfig fields that set a target/cap/frame/day-or-hour gate read
#: DIRECTLY by a tile-writing op (PLANT / BUILD_PASTURE / BUILD_COOP / DIG)
#: or by the dispatch priority deciding whether such an op fires this turn.
OCCUPANCY_FIELDS: frozenset[str] = frozenset(
    {
        # Strawberry -- PLANT STRAWBERRY writes farm["tiles"][y][x] to a crop dict.
        "strawberry_tile_target",  # final tile-count target for the zone
        "strawberry_plant_daily_cap",  # per-day rate cap on PLANT STRAWBERRY
        "strawberry_start_day",  # gates the day the mechanic may begin at all
        "strawberry_plant_cutoff_day",  # gates the last day a fresh planting issues
        "strawberry_frame_quadrants",  # which tiles are eligible for the zone
        "strawberry_frame_live",  # swaps the eligibility-frame formula itself
        "strawberry_plant_priority",  # dispatch gate on whether PLANT executes under contention
        "strawberry_seed_budget_share",  # caps affordable seed buys, hence achievable plantings
        "zone_fallthrough_multiplier",  # gates idle zone ground falling through to a WHEAT plant
        # Wheat -- PLANT WHEAT writes the same tile-dict shape.
        "wheat_rush_tiles",  # tile-count target/cap for wheat
        "wheat_plant_priority",  # dispatch gate on PLANT WHEAT execution
        "wheat_plant_hour_cutoff",  # hour-of-day gate on PLANT WHEAT
        # Melon -- PLANT MELON, same tile-dict shape.
        "melon_tile_target",
        # Land -- which tiles exist to be bare/occupied at all (LOCKED -> ownable).
        "max_owned_quadrants",  # caps how many quadrants are ever unlocked
        "ne_land_min_day",  # gates WHEN the NE quadrant's tiles leave LOCKED
        # Animals -- BUY_ANIMAL -> BUILD_PASTURE/BUILD_COOP write a tile dict too.
        "cow_target",  # PASTURE-tile target (pasture_tile_target = cow + sheep)
        "sheep_target",  # PASTURE-tile target, other half
        "goose_min_day",  # gates WHEN the (COOP-tile) goose purchase may fire
        "animal_buy_order",  # changes WHICH species' BUILD_PASTURE/COOP fires first
    }
)

#: The rest of PolicyConfig's 41 fields (packages/agent/src/agent/policy.py),
#: excluded with reasons -- listed explicitly so this is a documented choice,
#: not a silent omission. None of these write a farm["tiles"] entry directly.
EXCLUDED_FIELDS: dict[str, str] = {
    # Labor supply/dispatch capacity -- changes worker COUNT, not a tile
    # target or gate. Could in principle shift execution timing under
    # contention (a second-order path this direct-effect rule does not
    # follow -- see module docstring).
    "max_hires_per_turn": "labor supply, not a tile target/gate",
    "hire_slot_floor": "labor supply, not a tile target/gate",
    "extra_hands": "labor supply, not a tile target/gate",
    "land_unlock_hand_burst": "labor supply, not a tile target/gate",
    # Feed/logistics -- act on inventory or already-placed animals.
    "feed_reserve": "feed inventory logistics, not tile occupancy",
    "feed_batch_cap": "feed inventory logistics, not tile occupancy",
    "hand_mule_load": "labor logistics (carry capacity), not tile occupancy",
    # Fertilizer/watering act on an ALREADY-planted tile; they don't create
    # or destroy occupancy.
    "strawberry_fert_reserve": "fertilizer inventory reserve for an existing plant",
    "rescue_water": "watering an existing plant, not a planting decision",
    # Market pricing/selling behavior -- no tile-write link at all.
    "valve_soft_threshold": "market sell-throttle, no tile-write link",
    "valve_hard_threshold": "market sell-throttle, no tile-write link",
    "valve_soft_cap": "market sell-throttle, no tile-write link",
    "wool_floor": "market floor price, no tile-write link",
    "milk_floor": "market floor price, no tile-write link",
    "fert_floor": "market floor price, no tile-write link",
    "wool_crash_trigger": "market crash latch, no tile-write link",
    "milk_crash_trigger": "market crash latch, no tile-write link",
    "crash_trigger_ticks": "market crash latch, no tile-write link",
    "wool_milk_sell_cap": "market sell cap, no tile-write link",
    "clone_front_run": "market order-timing behavior, no tile-write link",
    "strawberry_floor": "market floor price, no tile-write link",
    # Compute budget only.
    "soft_budget_seconds": "search time budget, no tile-write link",
}


def _touches_occupancy(cfg: dict[str, Any] | None) -> bool:
    if not cfg:
        return False
    return bool(set(cfg.keys()) & OCCUPANCY_FIELDS)


# --- commit-identity normalization (short SHA / full SHA / dirty-tagged) ----


def _normalize_commit(raw: str | None) -> tuple[str, bool]:
    """(comparable_form, is_annotated). A `-dirty`/`-<tag>` suffixed commit
    (both shapes occur in eval/gates/) is flagged so it is only ever treated
    as equal to an IDENTICAL annotated string, never prefix-matched against a
    clean SHA it happens to share a prefix with -- a dirty tree's code may
    differ from the clean commit sharing its SHA prefix."""
    if raw is None:
        return "", True
    if "-" in raw:
        return raw, True
    return raw.lower(), False


def _same_commit(a: str | None, b: str | None) -> bool:
    norm_a, dirty_a = _normalize_commit(a)
    norm_b, dirty_b = _normalize_commit(b)
    if dirty_a or dirty_b:
        return a == b
    if not norm_a or not norm_b:
        return False
    shorter, longer = (norm_a, norm_b) if len(norm_a) <= len(norm_b) else (norm_b, norm_a)
    return longer.startswith(shorter)


# --- one-sample KS test against N(0,1), hand-rolled (see module docstring) --


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _ks_pvalue_asymptotic(d: float, n: int) -> float:
    """Asymptotic two-sided p-value for the one-sample KS statistic against a
    FULLY SPECIFIED continuous distribution (Kolmogorov distribution):
    P(D_n >= d) as n -> infinity, via 2 * sum_{k=1..inf} (-1)^(k-1) exp(-2 k^2 t^2)
    with t = sqrt(n) * d. Deliberately NOT the Stephens/Lilliefors correction
    (en = sqrt(n) + 0.12 + 0.11/sqrt(n)), which applies only when the
    reference distribution's parameters are estimated from the same sample --
    ours (N(0,1)) is not."""
    t = math.sqrt(n) * d
    if t < 0.2:  # deep in the "certainly consistent" region; avoids wasted terms
        return 1.0
    total = 0.0
    for k in range(1, 101):
        term = ((-1) ** (k - 1)) * math.exp(-2 * k * k * t * t)
        total += term
        if abs(term) < 1e-12:
            break
    return min(1.0, max(0.0, 2.0 * total))


def _ks_1samp_normal(zs: list[float]) -> tuple[float, float, int]:
    """One-sample two-sided KS statistic + asymptotic p-value of `zs` against
    the standard normal N(0,1). Returns (D, p, n)."""
    xs = sorted(zs)
    n = len(xs)
    if n == 0:
        return 0.0, 1.0, 0
    d_plus = max((i + 1) / n - _norm_cdf(x) for i, x in enumerate(xs))
    d_minus = max(_norm_cdf(x) - i / n for i, x in enumerate(xs))
    d = max(d_plus, d_minus)
    return d, _ks_pvalue_asymptotic(d, n), n


# --- ledger loading -----------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


@dataclass
class Ledger:
    file: str
    agent_config: dict[str, Any] | None
    opponent: str | None
    baseline: str | None
    baseline_agent_config: dict[str, Any] | None
    candidate_commit: str | None
    seed_base: int
    n_seeds: int | None
    mean_delta: float
    stderr: float


def _load_money_ledgers(gates_dir: Path) -> tuple[list[Ledger], dict[str, int], list[str]]:
    gate_type_counts: dict[str, int] = defaultdict(int)
    ledgers: list[Ledger] = []
    problems: list[str] = []
    for fp in sorted(gates_dir.glob("*.json")):
        try:
            payload = json.loads(fp.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            problems.append(f"{fp.name}: unreadable/invalid JSON ({exc})")
            continue
        idn = payload.get("identity", {}) or {}
        gate_type = idn.get("gate_type", "MISSING")
        gate_type_counts[gate_type] += 1
        if gate_type != "money":
            continue  # promotion-gate / fuzz ledgers: out of scope for a money sweep
        sm = payload.get("seed_manifest", {}) or {}
        mv = payload.get("money_verdict", {}) or {}
        if "seed_base" not in sm or "mean_delta" not in mv or "stderr" not in mv:
            problems.append(f"{fp.name}: gate_type=money but missing seed_manifest/money_verdict fields")
            continue
        ledgers.append(
            Ledger(
                file=fp.name,
                agent_config=idn.get("agent_config"),
                opponent=idn.get("opponent"),
                baseline=idn.get("baseline"),
                baseline_agent_config=idn.get("baseline_agent_config"),
                candidate_commit=idn.get("candidate_commit"),
                seed_base=sm["seed_base"],
                n_seeds=sm.get("n_seeds"),
                mean_delta=mv["mean_delta"],
                stderr=mv["stderr"],
            )
        )
    return ledgers, dict(gate_type_counts), problems


# --- pooling + pairing ----------------------------------------------------


@dataclass
class BandStat:
    band: int
    mean: float
    se: float
    n_ledgers_pooled: int
    total_seeds: int
    opponents: list[str]
    commit_repr: str | None
    commits_raw: list[str]


@dataclass
class PairRecord:
    baseline: str | None
    agent_config: dict[str, Any] | None
    baseline_agent_config: dict[str, Any] | None
    band_lo: int
    band_hi: int
    mean_lo: float
    mean_hi: float
    se_lo: float
    se_hi: float
    se_diff: float
    z: float
    same_commit: bool
    occupancy_touching: bool
    commit_lo: str | None
    commit_hi: str | None
    opponents_lo: list[str] = field(default_factory=list)
    opponents_hi: list[str] = field(default_factory=list)


def _group_key(ledger: Ledger) -> tuple[str, str | None, str]:
    """(agent_config, baseline, baseline_agent_config) -- deliberately WITHOUT
    opponent. See module docstring for why."""
    return (
        json.dumps(ledger.agent_config, sort_keys=True),
        ledger.baseline,
        json.dumps(ledger.baseline_agent_config, sort_keys=True),
    )


def _pool_band(rows: list[Ledger]) -> BandStat:
    means = [r.mean_delta for r in rows]
    ses = [r.stderr for r in rows]
    k = len(rows)
    pooled_mean = sum(means) / k
    pooled_se = math.sqrt(sum(s * s for s in ses)) / k
    commits_raw = sorted({r.candidate_commit for r in rows if r.candidate_commit})
    if len(commits_raw) == 1:
        commit_repr: str | None = commits_raw[0]
    elif len(commits_raw) > 1 and all(
        _same_commit(a, b) for a, b in itertools.combinations(commits_raw, 2)
    ):
        commit_repr = max(commits_raw, key=len)  # the most-specific (longest) form
    else:
        commit_repr = None  # genuinely mixed, or no commit recorded -- never "same" downstream
    return BandStat(
        band=rows[0].seed_base,
        mean=pooled_mean,
        se=pooled_se,
        n_ledgers_pooled=k,
        total_seeds=sum(r.n_seeds or 0 for r in rows),
        opponents=sorted({r.opponent for r in rows if r.opponent}),
        commit_repr=commit_repr,
        commits_raw=commits_raw,
    )


def _build_pairs(ledgers: list[Ledger]) -> tuple[list[PairRecord], int, int]:
    groups: dict[tuple[str, str | None, str], list[Ledger]] = defaultdict(list)
    for ledger in ledgers:
        groups[_group_key(ledger)].append(ledger)

    n_groups_total = len(groups)
    n_groups_multi_band = 0
    pairs: list[PairRecord] = []
    seen_pair_ids: set[tuple[tuple[str, str | None, str], int, int]] = set()

    for gkey, rows in groups.items():
        ac_json, baseline, bac_json = gkey
        agent_config = json.loads(ac_json)
        baseline_agent_config = json.loads(bac_json)
        occupancy = _touches_occupancy(agent_config) or _touches_occupancy(baseline_agent_config)

        by_band: dict[int, list[Ledger]] = defaultdict(list)
        for r in rows:
            by_band[r.seed_base].append(r)
        if len(by_band) < 2:
            continue
        n_groups_multi_band += 1

        band_stats = {band: _pool_band(band_rows) for band, band_rows in by_band.items()}
        for band_lo, band_hi in itertools.combinations(sorted(band_stats), 2):
            pair_id = (gkey, band_lo, band_hi)
            assert pair_id not in seen_pair_ids, f"duplicate pair {pair_id}"
            seen_pair_ids.add(pair_id)

            s_lo, s_hi = band_stats[band_lo], band_stats[band_hi]
            se_diff = math.sqrt(s_lo.se**2 + s_hi.se**2)
            if se_diff == 0.0:
                continue  # degenerate (zero-dispersion) pooled estimate; cannot form a z
            z = (s_hi.mean - s_lo.mean) / se_diff
            same_commit = (
                s_lo.commit_repr is not None
                and s_hi.commit_repr is not None
                and _same_commit(s_lo.commit_repr, s_hi.commit_repr)
            )
            pairs.append(
                PairRecord(
                    baseline=baseline,
                    agent_config=agent_config,
                    baseline_agent_config=baseline_agent_config,
                    band_lo=band_lo,
                    band_hi=band_hi,
                    mean_lo=s_lo.mean,
                    mean_hi=s_hi.mean,
                    se_lo=s_lo.se,
                    se_hi=s_hi.se,
                    se_diff=se_diff,
                    z=z,
                    same_commit=same_commit,
                    occupancy_touching=occupancy,
                    commit_lo=s_lo.commit_repr,
                    commit_hi=s_hi.commit_repr,
                    opponents_lo=s_lo.opponents,
                    opponents_hi=s_hi.opponents,
                )
            )

    return pairs, n_groups_total, n_groups_multi_band


def _verify_known_cross_checks(pairs: list[PairRecord]) -> list[dict[str, Any]]:
    """Locate the two cross-band pairs the issue itself works arithmetic for,
    and report this sweep's own numbers against them -- a positive-control
    check that the pooling mechanism is doing what the docstring claims."""
    checks = []
    for baseline, band_lo, band_hi, expected_z, label in (
        ("champion", 881000, 888000, -2.98, "STACK3 vs champion (issue body)"),
        ("frozen:m3b_live_b6ce655", 891000, 892000, 3.45, "STACK3 terminal-freeze (#167/#169/#170)"),
    ):
        match = next(
            (
                p
                for p in pairs
                if p.baseline == baseline and p.band_lo == band_lo and p.band_hi == band_hi
            ),
            None,
        )
        checks.append(
            {
                "label": label,
                "baseline": baseline,
                "bands": [band_lo, band_hi],
                "expected_z_approx": expected_z,
                "computed_z": match.z if match else None,
                "computed_mean_lo": match.mean_lo if match else None,
                "computed_mean_hi": match.mean_hi if match else None,
                "computed_se_lo": match.se_lo if match else None,
                "computed_se_hi": match.se_hi if match else None,
                "found": match is not None,
            }
        )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gates-dir", default="eval/gates", help="default: eval/gates")
    parser.add_argument(
        "--out",
        default="eval/recon/2026-09-19-cross-band-variance-sweep.json",
        help="output JSON path",
    )
    args = parser.parse_args(argv)

    gates_dir = Path(args.gates_dir)
    identity = {
        "script": "tools/recon-scripts/cross_band_variance_sweep.py",
        "issue": "cdcoonce/kaggriculture#165",
        "git_sha": _git("rev-parse", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain")),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gates_dir": str(gates_dir),
    }
    print("identity:", json.dumps(identity, indent=2))

    ledgers, gate_type_counts, problems = _load_money_ledgers(gates_dir)
    total_files = sum(gate_type_counts.values())
    print(f"\nscanned {total_files} files under {gates_dir}/")
    print(f"gate_type counts: {gate_type_counts}")
    if problems:
        print(f"WARNING: {len(problems)} file(s) skipped:")
        for p in problems:
            print(f"  {p}")
    n_money = len(ledgers)
    print(f"money ledgers read: {n_money}  (expected ~168 at origin/main d23b91a)")
    if n_money == 0:
        print("\nSTOP: zero money ledgers found. The spec's assumption about eval/gates/ "
              "(identity.gate_type == 'money') does not hold against this checkout -- "
              "reporting the discrepancy rather than improvising.")
        return 1

    pairs, n_groups_total, n_groups_multi_band = _build_pairs(ledgers)
    print(f"\ndistinct (agent_config, baseline, baseline_agent_config) groups: {n_groups_total}")
    print(f"groups spanning >1 seed_base band: {n_groups_multi_band}")
    print(f"total cross-band pairs: {len(pairs)}")
    if not pairs:
        print("\nSTOP: zero cross-band pairs found -- the spec's grouping assumption "
              "does not hold against this checkout (no arm recurs across bands). "
              "Reporting the discrepancy rather than improvising.")
        return 1

    # --- stratification (a), (b), and the 2x2 combination (c's population) --
    same_commit_n = sum(1 for p in pairs if p.same_commit)
    cross_commit_n = len(pairs) - same_commit_n
    occupancy_n = sum(1 for p in pairs if p.occupancy_touching)
    non_occupancy_n = len(pairs) - occupancy_n
    combo_counts: dict[str, int] = defaultdict(int)
    for p in pairs:
        combo_counts[f"{'same' if p.same_commit else 'cross'}_commit__"
                     f"{'occupancy' if p.occupancy_touching else 'non_occupancy'}"] += 1

    print("\n=== (a) same-commit vs cross-commit pair counts ===")
    print(f"  same-commit: {same_commit_n}   cross-commit: {cross_commit_n}")
    print("\n=== (b) occupancy-touching vs non-occupancy pair counts ===")
    print(f"  occupancy-touching: {occupancy_n}   non-occupancy: {non_occupancy_n}")
    print("\n=== combined 2x2 ===")
    for k in sorted(combo_counts):
        print(f"  {k}: {combo_counts[k]}")

    # --- (c) the KS test, same-commit + non-occupancy population only ------
    target = [p for p in pairs if p.same_commit and not p.occupancy_touching]
    zs = [p.z for p in target]
    d_stat, p_value, n_ks = _ks_1samp_normal(zs)
    beyond2 = sum(1 for z in zs if abs(z) > 2)
    beyond3 = sum(1 for z in zs if abs(z) > 3)
    print(f"\n=== (c) KS test: same-commit, non-occupancy population, n={n_ks} ===")
    print(f"  D={d_stat:.4f}  p={p_value:.4f}")
    print(f"  |z|>2: {beyond2}/{n_ks}   |z|>3: {beyond3}/{n_ks}")
    if zs:
        print(f"  z range: [{min(zs):.3f}, {max(zs):.3f}]")

    # --- positive-control cross-checks against the issue's own arithmetic --
    checks = _verify_known_cross_checks(pairs)
    print("\n=== cross-checks against the issue's own worked numbers ===")
    for c in checks:
        print(f"  {c['label']}: expected z~={c['expected_z_approx']}  "
              f"computed z={c['computed_z']!r}  found={c['found']}")

    # --- all |z|>3 pairs, any stratum, for narrative context ---------------
    outliers = sorted((p for p in pairs if abs(p.z) > 3), key=lambda p: -abs(p.z))
    print(f"\n=== all |z|>3 pairs (any stratum): {len(outliers)} ===")
    for p in outliers:
        ac_keys = sorted(p.agent_config.keys()) if p.agent_config else None
        print(f"  baseline={p.baseline!r} bands={p.band_lo}/{p.band_hi} z={p.z:.3f} "
              f"same_commit={p.same_commit} occupancy={p.occupancy_touching} agent_config_keys={ac_keys}")

    verdict = (
        "consistent with the per-seed model for the non-occupancy population, closed"
        if p_value >= 0.05
        else "measured over-dispersion; follow-up issue #TBD to be filed for step 2"
    )
    print(f"\nfinding: {verdict}")

    payload = {
        "schema_version": 1,
        "identity": identity,
        "corpus": {
            "total_files_scanned": total_files,
            "gate_type_counts": gate_type_counts,
            "money_ledgers_used": n_money,
            "skipped_files": problems,
        },
        "occupancy_classification": {
            "method": (
                "direct-effect PolicyConfig fields: sets a target/cap/frame/day-or-hour "
                "gate read directly by a tile-writing op (PLANT/BUILD_PASTURE/BUILD_COOP/"
                "DIG) or the dispatch priority gating that op -- derived from "
                "harness/shop_roster.py's bare-tile census plus the vendored engine "
                "source, since no explicit knob-list constant exists in either "
                "harness/shop_roster*.py or shop_roster_coupling.py. See module docstring."
            ),
            "fields": sorted(OCCUPANCY_FIELDS),
            "excluded_fields": EXCLUDED_FIELDS,
        },
        "pooling_method": {
            "description": (
                "Groups by (agent_config, baseline, baseline_agent_config) WITHOUT "
                "opponent; pools every ledger sharing (group, seed_base) via "
                "pooled_mean=mean(means), pooled_se=sqrt(sum(se**2))/k. See module "
                "docstring for why opponent is pooled rather than used as a match key."
            ),
            "cross_checks": checks,
        },
        "groups": {
            "distinct_groups_total": n_groups_total,
            "groups_spanning_multiple_bands": n_groups_multi_band,
        },
        "pairs": [asdict(p) for p in pairs],
        "strata_counts": {
            "a_same_vs_cross_commit": {"same_commit": same_commit_n, "cross_commit": cross_commit_n},
            "b_occupancy_vs_non": {"occupancy_touching": occupancy_n, "non_occupancy": non_occupancy_n},
            "c_combined_2x2": dict(combo_counts),
        },
        "ks_test": {
            "population": "same_commit_non_occupancy",
            "n": n_ks,
            "statistic_d": d_stat,
            "p_value": p_value,
            "count_beyond_2sigma": beyond2,
            "count_beyond_3sigma": beyond3,
            "z_scores": zs,
            "method": "asymptotic one-sample two-sided KS vs N(0,1), hand-implemented; see module docstring",
        },
        "outliers_beyond_3sigma_any_stratum": [asdict(p) for p in outliers],
        "finding": verdict,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
