# Pre-registration: head-to-head screen of the never-measured knob surface

Date: 2026-09-07
Candidate: `champion`, CONFIG ONLY. No agent source edits while this runs.
Status: REGISTERED — runs launch after this document merges.

## Why

Of `PolicyConfig`'s 23 fields, only **5** have ever been tested head-to-head,
and **2 of those 5 produced large winners** (`wheat_rush_tiles`=30 at 0.856,
`hand_mule_load`=20 at 0.968, now shipped). **13 have never appeared in any
gate**; 4 more were money-gated only, on the instrument
`eval/prereg/2026-09-07-elo-aligned-factorial.md` showed measures a quantity the
ladder does not score. The untested set is not peripheral — it is the entire
market-side control surface: the sell floors, the crash latches, the shed valve,
and the per-turn sell cap.

## The baseline moved, so the opponent moves with it

`hand_mule_load`=20 merged at `96d8b41`, so `champion` at defaults **is** HML20.
Gating against `frozen:m3b_live_b6ce655` would now put CTRL near 0.968 — no
validity anchor, and a ceiling that leaves almost nothing to detect. This screen
therefore runs against a **newly frozen incumbent**,
`frozen:m3c_hml20_96d8b41`, verified genuine (all ten files match `96d8b41`
after normalising the import rewrite) and confirmed to carry `hand_mule_load=20`.

Mirror check, band 839500, n=100, unledgered: **97-97-6, rate exactly 0.500**.
The baseline is a true null, so every number below is a marginal gain over what
we now ship.

## Arms DROPPED before launch, with reasons

This half matters as much as the arms kept: an arm spent on a knob that cannot
move behaviour is worse than no arm, because it consumes multiplicity budget
while measuring nothing.

**Provably dead at shipped defaults:**
- `strawberry_plant_daily_cap`, `strawberry_seed_budget_share`,
  `strawberry_floor` — all downstream of `strawberry_tile_target`=0.
  `strawberry_tiles()` returns `[]`, so the dispatch branch is unreachable, the
  seed target is `min(..., 0)`, and the shed can never hold STRAWBERRY. Turning
  strawberry on does not rescue them: the 2026-09-06 replacement screen closed
  that line at 0.015-0.115.
- `valve_hard_threshold` >= 100 — the engine clamps every shed deposit path to
  `shedCapacity`, so `shed_total` can never reach it.
- `valve_soft_threshold` >= 85 or `valve_hard_threshold` <= 55 — collapses the
  soft tier band, making `valve_soft_cap` a no-op *in that arm*
  (`_valve_tier`'s if/elif order).
- `max_owned_quadrants` >= 5 — `LAND_ORDER` has three rungs past NW, so 4 and up
  are identical.
- `melon_tile_target` in [9, 18] — `pasture_tiles` slices from the *module*
  constant, so the realized zone stays at 8 (kaggriculture#108). **Not bit-exact
  dead**: the raw set still leaks via `empty_melon_tiles` into seed timing, which
  is why the August ledgers show nonzero deltas there. Screened at 4 and 20, not
  inside the dead range.

**Unsafe — reproduces the kaggriculture#59 near-equilibrium bug:**
- `milk_floor` >= 130 (permits only 15 units before the floor latches shut) and
  `wool_floor` >= 190 (14 units). The repo's own guard requires >= 15 permitted
  units but checks only shipped constants, never `--agent-config` overrides.

**Not a strategy knob:**
- `soft_budget_seconds` — a wall-clock tripwire whose only effect is emitting
  `pass_action()` on a turn that trips it; `remainingOverageTime` is never read
  anywhere in the agent. 0.0 is degenerate (passes every turn). A win-rate gate
  is a poor instrument for a rare-truncation reliability question. **Zero arms.**

## Registered design

Band **838000** (fresh). Opponent `frozen:m3c_hml20_96d8b41` throughout.
**n=100 seeds (200 games) per arm.** CTRL first, then the arms in this order:

| # | `--agent-config` |
|---|---|
| 0 | CTRL `{}` |
| 1 | `{"max_owned_quadrants": 4}` |
| 2 | `{"max_owned_quadrants": 2}` |
| 3 | `{"wool_floor": 110}` |
| 4 | `{"milk_floor": 90}` |
| 5 | `{"wool_milk_sell_cap": 8}` |
| 6 | `{"melon_tile_target": 4}` |
| 7 | `{"melon_tile_target": 20}` |
| 8 | `{"wool_floor": 180}` |
| 9 | `{"milk_floor": 127}` |
| 10 | `{"wool_milk_sell_cap": 2}` |
| 11 | `{"valve_hard_threshold": 65}` |
| 12 | `{"valve_hard_threshold": 75}` |
| 13 | `{"feed_reserve": 0}` |
| 14 | `{"valve_soft_threshold": 35}` |
| 15 | `{"valve_soft_threshold": 70}` |
| 16 | `{"valve_soft_cap": 25}` |
| 17 | `{"valve_soft_cap": 4}` |
| 18 | `{"feed_reserve": 8}` |
| 19 | `{"wool_crash_trigger": 140}` |
| 20 | `{"milk_crash_trigger": 100}` |
| 21 | `{"crash_trigger_ticks": 4}` |
| 22 | `{"fert_floor": 40}` |
| 23 | `{"feed_batch_cap": 2}` |

## Decision rule (fixed before launch)

**INVALID** if CTRL's rate falls outside [0.40, 0.60], or if
`any_candidate_crash` is true on any arm. An invalid run is rerun, not
reinterpreted.

**SCREEN BAR: rate >= 0.65**, calibrated rather than assumed. Simulating 40,000
null screens of 23 arms at 200 games each (arms independent, p=0.5) puts the
distribution of the *maximum* at E=0.568, p95=0.600, p99=0.615; **rate >= 0.65
was reached in 0 of 40,000**. Arms here share seeds and are therefore positively
correlated, which tightens the max further, so this bar is conservative in the
safe direction.

**THE SCREEN SELECTS; IT DOES NOT PROMOTE.** Nothing ships off a screen number.
Every arm clearing the bar carries a **confirmation debt**: it must clear the
factorial's full criterion — rate >= 0.65 **and** Wilson ci_lower > 0.55 — at
**n=250 on disjoint band 839000** before it is recommended for anything.

**REPORT THE COUNT.** The number of arms clearing the bar is reported
prominently. Given the calibration above, even one clean pass is meaningful, but
a cluster of arms landing at 0.60-0.64 is exactly what the null max looks like
and must be described that way rather than as near-misses.

**MONEY IS A DIAGNOSTIC, NOT A GATE**, on the same terms as the factorial:
recorded and reported for every arm, unable to fail any arm. Fixed before the
data exists so it cannot be adjusted after.

## Registered predictions

- CTRL lands within [0.45, 0.55].
- **Most arms land near 0.50.** This is a screen of knobs nobody has ever had a
  reason to believe in; the base rate for a randomly chosen default being
  mis-set is low. A screen that returns nothing is a real and likely outcome and
  will be reported as such.
- `max_owned_quadrants`=4 is the most likely single winner — it has the largest
  already-quantified effect of anything here (+$5,991…+$7,780 money `ci_lower`
  for cap 3 vs 4), measured on the instrument we now know was wrong.
- The floors (`wool_floor`, `milk_floor`) are the most likely place for a
  *second* effect, because the shed valve exists precisely because they back up.
- `feed_batch_cap`=2 does **not** clear the bar: its regression is already
  documented in-source from an action-share metric, not a money one, so it
  should be instrument-robust.

## Consequence

A surviving arm authorises a **confirmation run**, nothing more. Uploading stays
HITL. The tracked pair is unchanged at [M3a 55471731, M3b 55784368]; the HML20
bundle at `96d8b41` is built and cleared by `submit.py` but **has not been
uploaded**, so one free slot remains.

Nothing in this document authorises an upload.
