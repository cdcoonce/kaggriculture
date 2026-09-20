# Cross-band variance sweep (kaggriculture#165, step 1)

> Recon record. Produced by `tools/recon-scripts/cross_band_variance_sweep.py`, reading
> `eval/gates/*.json` at `origin/main` = `d23b91a` (297 files: 168 `money`, 128 `promotion`,
> 1 `fuzz`). Companion machine record: `2026-09-19-cross-band-variance-sweep.json` beside this
> file (full pair-by-pair data, the occupancy field list, and the pooling cross-checks below).
> No game was run and no seed or band was consumed producing this record — it is a pure read
> over already-committed ledgers.

## The question

`harness.stats.money_verdict` derives `stderr` from per-seed dispersion within one run
(`packages/harness/src/harness/stats.py:599-608`); nothing in that estimator has a
`seed_manifest.seed_base` ("band") term. #165 was filed because the same `STACK3` configuration,
measured at three different bands against `champion`, disagreed by 2.98 se between two of
them — and asks whether that is the expected tail of the per-seed model, or evidence of a
band-level variance component the estimator can't see. Per the issue's own scope: this is step 1
only (count and classify the population; test it), never an estimator change, never a new
band measurement, never a reason to reopen a closed slice.

## Method

**Grouping.** Ledgers are grouped by (`identity.agent_config`, `identity.baseline`,
`identity.baseline_agent_config`) — deliberately **without** `identity.opponent` as a match key,
which is a documented deviation from a literal reading of the issue's Step 1 sentence. Reason:
several arms (STACK3 chief among them) are gated against a fixed panel of three public leaders
(sokolovsky/rayk/kaito) at every band, and the issue's own headline numbers ("pooled Δ +$3,637",
"pooled se $1,174") are pools **across that panel**, not any single opponent's ledger. Read
literally, "same opponent" as a match key fragments one panel measurement into three unrelated
per-opponent comparisons, none of which reproduces the issue's own arithmetic. Pooling across
opponents sharing a (group, band) cell — and trivially collapsing to the single-ledger case when
only one opponent was used, the common case — does. This was verified, not assumed, against
three independent numbers the issue itself states, before this sweep was trusted:

| cross-check | issue's stated numbers | this sweep's computed numbers |
|---|---|---|
| STACK3 vs `champion`, 881000 vs 888000 | pooled Δ +$3,637/−$1,203, se $1,174/$1,119, **z ≈ −2.98** | Δ +$3,637.35/−$1,202.52, se $1,174.29/$1,118.54, **z = −2.9843** |
| STACK3 vs `frozen:m3b_live_b6ce655`, 891000 vs 892000 (#167/#169/#170) | +$3,722 vs +$7,390, **3.45 se** | +$3,721.80 vs +$7,389.99, **z = 3.4539** |
| `MAIN_DEF`-shaped arm (`agent_config=None`) vs `frozen:m3b_live_b6ce655`, 850000 vs 891000 | "+$1,331 vs +$1,147", replicating closely | +$1,331.24 vs +$1,146.95, z = −0.18 |

All three reproduce to the precision the issue itself reported. A literal same-opponent grouping
does not reproduce any of them (the three per-opponent z's for 881000-vs-888000 individually land
between −2.3 and −1.4). Pooling formula, per band cell of *k* pooled ledgers:
`pooled_mean = mean(ledger means)`, `pooled_se = sqrt(sum(ledger se²)) / k` — independent-variance
propagation of an equal-weight mean, which is what reproduces the table above (a raw
concatenate-all-per-seed-deltas-and-recompute alternative was also tried and does *not* match the
reported se's as precisely; see the script docstring for both numbers).

**Pairing.** Within each group, every distinct pair of `seed_manifest.seed_base` values ("bands")
is compared exactly once (`itertools.combinations` over the group's distinct bands — no ledger
pair is ever counted twice, and no band is ever compared to itself). For a pair (band_lo <
band_hi), `z = (mean_hi − mean_lo) / sqrt(se_lo² + se_hi²)` — the se of a difference of two
independent estimates, never a pooled/shared-variance se.

**Stratification.** Each pair is classified two ways: same-`candidate_commit` vs cross-commit
(commit strings are compared prefix-aware and dirty/tag-aware — this corpus mixes 7-char, 40-char,
and `<sha>-dirty`/`<sha>-<tag>` forms for the same commits, so naive string equality would
misclassify some same-commit pairs as cross-commit); and occupancy-touching vs non-occupancy.

## Occupancy classification

Neither `packages/harness/src/harness/shop_roster.py` nor
`tools/recon-scripts/shop_roster_coupling.py` defines an explicit knob-list constant — the recon
script takes one arbitrary `--knob` name and measures its effect empirically, one at a time. The
field list below is **derived**, not looked up, from the same census mechanism plus the vendored
engine source (`kaggle_environments/envs/kaggriculture/kaggriculture.py`):

- `shop_roster._combined_bare` counts a farm tile as "bare" iff `tile is None`, summed over
  `farm["tiles"]` for both seats.
- The engine's tile-writing ops are `PLANT` (writes a crop dict), `BUILD_PASTURE` / `BUILD_COOP`
  (write `{"kind": "PASTURE"}` / `{"kind": "COOP"}` — confirmed directly in the engine source, so
  animal purchases *do* write into the same tile grid the census reads, not a separate pasture
  counter), and `DIG` (writes the tile back to `None`).

A `PolicyConfig` field (41 fields total, `packages/agent/src/agent/policy.py`, confirmed by
`dataclasses.fields()` introspection) is classified occupancy-affecting here iff it sets a
target/cap/eligible-frame/day-or-hour gate read **directly** by one of those ops or by the
dispatch priority deciding whether such an op fires on a given turn — a first-order/direct-effect
rule, stated explicitly because no canonical list exists to defer to:

**Occupancy-affecting (19 fields):**

| cluster | fields |
|---|---|
| strawberry (`PLANT STRAWBERRY`) | `strawberry_tile_target`, `strawberry_plant_daily_cap`, `strawberry_start_day`, `strawberry_plant_cutoff_day`, `strawberry_frame_quadrants`, `strawberry_frame_live`, `strawberry_plant_priority`, `strawberry_seed_budget_share`, `zone_fallthrough_multiplier` |
| wheat (`PLANT WHEAT`) | `wheat_rush_tiles`, `wheat_plant_priority`, `wheat_plant_hour_cutoff` |
| melon (`PLANT MELON`) | `melon_tile_target` |
| land (LOCKED → ownable) | `max_owned_quadrants`, `ne_land_min_day` |
| animals (`BUILD_PASTURE`/`BUILD_COOP`) | `cow_target`, `sheep_target`, `goose_min_day`, `animal_buy_order` |

**Excluded (22 fields)**, with reasons — labor supply/dispatch capacity (`max_hires_per_turn`,
`hire_slot_floor`, `extra_hands`, `land_unlock_hand_burst`: change worker *count*, not a tile
target or gate); feed/logistics (`feed_reserve`, `feed_batch_cap`, `hand_mule_load`: act on
inventory, not tiles); fertilizer/watering on an already-planted tile (`strawberry_fert_reserve`,
`rescue_water`); and market pricing/selling with no tile-write link at all (`valve_soft_threshold`,
`valve_hard_threshold`, `valve_soft_cap`, `wool_floor`, `milk_floor`, `fert_floor`,
`wool_crash_trigger`, `milk_crash_trigger`, `crash_trigger_ticks`, `wool_milk_sell_cap`,
`clone_front_run`, `strawberry_floor`, `soft_budget_seconds`). Full per-field reasons are in the
JSON record's `occupancy_classification.excluded_fields`.

**Scope limitation, stated rather than silently assumed:** this is a first-order/direct-effect
classification only. It does not reach second-order channels — a labor knob shifting which day a
crew gets to a `PLANT` task under contention, or `rescue_water`/weed dynamics also flipping a
tile's bare/non-bare state — because `shop_roster_coupling.py` itself does not attempt to bound
those either (it measures one named knob empirically; it does not classify). Bounding second-order
effects would need simulation, which a recon-only sweep (no game runs, per this issue's own
constraint) cannot do. An arm classified "non-occupancy" here is "does not directly set a
tile-writing target/gate," not "provably has zero effect on the census through every channel."
A group is occupancy-touching if **either** its `agent_config` or its `baseline_agent_config` sets
any field in the table above.

## Corpus and population

168 `money`-gate-type ledgers (128 `promotion` and 1 `fuzz` excluded — sanity-printed by the
script and matching the task's ~168 expectation exactly). These fall into 50 distinct
(`agent_config`, `baseline`, `baseline_agent_config`) groups, of which **15 span more than one
band**, forming **93 cross-band pairs** total (all pairs; no ledger pair double-counted, no
self-comparisons).

**(a) same-commit vs cross-commit:** 24 same-commit, 69 cross-commit.

**(b) occupancy-touching vs non-occupancy:** 43 occupancy-touching, 50 non-occupancy.

**(c) combined:**

| | non-occupancy | occupancy-touching |
|---|---|---|
| **same-commit** | **7** | 17 |
| **cross-commit** | 43 | 26 |

## The test: same-commit, non-occupancy population (n=7)

This is the population the issue is actually asking about — a clean band-only contrast (code held
fixed) on arms that don't set a tile-occupancy knob, so #82's coupling mechanism is not in play.

One-sample two-sided Kolmogorov–Smirnov test of these 7 z-scores against N(0,1) (asymptotic
p-value; hand-implemented — see script docstring — and cross-validated against
`scipy.stats.kstest(..., mode="asymp")` during development across five sample sizes plus an
over-dispersed positive control, matching to 6 decimal places):

- **D = 0.2720, p = 0.6784**
- z range: [−0.840, 0.906]
- 0/7 beyond ±2σ, 0/7 beyond ±3σ

n=7 is small — this test has limited power to detect anything short of a large effect, and that
caveat applies below. All 7 pairs come from three groups: a `hand_mule_load`-only family (5
pairs, two configs sharing bands 820000/822000/823000 and one at 591000/592000) and two
`agent_config=None` clean-baseline comparisons (`frozen:presticky-a517afa` 570000/580000, z=0.91).
None of the 7 is remarkable.

## The five |z|>3 pairs in the full corpus (any stratum) — all occupancy-touching or explained

| baseline | bands | z | same-commit | occupancy | knob(s) |
|---|---|---|---|---|---|
| `frozen:straw_seedorder_0d366b9` | 661600/662000 | 8.14 | no | yes | `strawberry_tile_target` |
| `frozen:straw_seedorder_0d366b9` | 661400/662000 | 5.63 | no | yes | `strawberry_tile_target` |
| `frozen:straw_seedorder_0d366b9` | 661800/662000 | 4.84 | no | yes | `strawberry_tile_target` |
| `champion` (STACK3) | 888000/893000 | 3.58 | no | yes | strawberry+animal+labor stack |
| `frozen:m3b_live_b6ce655` (STACK3) | 891000/892000 | 3.45 | **yes** | yes | strawberry+animal+labor stack |

Every one sets `strawberry_tile_target` (or the full STACK3 stack including it) — squarely the
occupancy-touching population #82/`shop_roster_coupling.py` already prices. The STACK3
881000-vs-888000 pair the issue itself opens with (z = −2.98) is in the same occupancy-touching
bucket, just under this ±3 cutoff. None of these five, nor the STACK3 headline pair, are in the
same-commit/non-occupancy population the acceptance criteria asks this sweep to test — consistent
with #169's own finding that STACK3's instability is priced coupling (7.9-8.0/8 draws, near the
`eval/README.md` `max_owned_quadrants` worked example's 4/8), not a hole in the estimator.

## Finding

**Consistent with the per-seed model for the non-occupancy population, closed.** KS p = 0.68 on
the same-commit, non-occupancy population shows no evidence of over-dispersion beyond what the
per-seed model already predicts (0 of 7 pairs beyond even 2σ). Every |z|>3 pair anywhere in the
168-ledger corpus sets an occupancy-affecting knob, and the one same-commit occupancy pair beyond
3σ (891000/892000, STACK3 vs the terminal-freeze baseline) is the mechanism #169 already measured
directly for that arm. Step 2 (a dedicated k≥6-band measurement of the variance component itself)
is not warranted by this population and is not filed.

This does not reopen any of the eleven `NOT ADVANCED` closures (every registered verdict compares
arms within one band, where a band-level component would difference out regardless of whether one
exists) and does not move any threshold.

## Caveats

- **n=7 is small.** This KS test has limited power; it can rule out a large systematic
  over-dispersion but not a small one. The corpus simply does not contain many same-commit,
  non-occupancy band-recurrences yet — most repeat-band arms in `eval/gates/` either touch an
  occupancy knob or were re-measured after the code moved (the 850000-vs-891000 `MAIN_DEF`-shaped
  comparison above is cross-commit for exactly that reason, which is why it isn't in the tested
  n=7 despite replicating almost perfectly).
- **First-order occupancy scope**, stated above: knobs excluded here as "non-occupancy" could
  still carry a second-order effect on the bare-tile census through labor contention or weed
  dynamics. This sweep cannot bound that (no game runs); it classifies by direct mechanism only,
  as documented, not by an exhaustive causal audit.
- **Opponent-pooling is a documented deviation** from a literal reading of the issue's Step 1
  grouping sentence, adopted because it is the only grouping that reproduces the issue's own three
  worked cross-checks (table above) — not something this sweep silently assumed.
- No estimator change, no new band measurement, and no closed-slice reopening are licensed by, or
  performed in, this record.

## Output files

- `tools/recon-scripts/cross_band_variance_sweep.py` — the sweep (read-only over `eval/gates/`).
- `2026-09-19-cross-band-variance-sweep.json` — full machine record: every one of the 93 pairs,
  the occupancy field list with exclusion reasons, the three pooling cross-checks, strata counts,
  and the KS test detail.
- This file.
