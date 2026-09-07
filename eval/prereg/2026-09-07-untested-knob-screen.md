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

## ADDENDUM (2026-09-07, post-run): one confirmed survivor, and a prediction that was flatly wrong

Screen executed 2026-09-07T02:5x-03:3xZ at `5528223`, band 838000, n=100 seeds
per arm vs `frozen:m3c_hml20_96d8b41`, CTRL first, after the runner verified
from the loaded `PolicyConfig` that the tree carried the shipped HML20 champion.
`any_candidate_crash` false on all 24 arms.

**VALIDITY: CTRL 99-99-2, rate exactly 0.500.** VALID.

| rate | ci_lower | W-L-T | arm |
|---|---|---|---|
| **0.690** | 0.6228 | 138-62-0 | **valve_soft_threshold=35** |
| **0.685** | 0.6177 | 137-63-0 | **feed_reserve=0** |
| 0.635 | 0.5663 | 127-73-0 | valve_soft_cap=25 |
| 0.590 | 0.5208 | 118-82-0 | wool_milk_sell_cap=8 |
| 0.585 | 0.5157 | 117-83-0 | valve_hard_threshold=65 |
| 0.570 | 0.5007 | 114-86-0 | valve_hard_threshold=75 |
| 0.525 | 0.4560 | 104-94-2 | wool_floor=110 |
| 0.520 | 0.4510 | 104-96-0 | milk_floor=90 |
| 0.515 | 0.4461 | 103-97-0 | milk_crash_trigger=100 |
| 0.505 | 0.4363 | 100-98-2 | wool_floor=180 |
| 0.505 | 0.4363 | 100-98-2 | wool_crash_trigger=140 |
| 0.505 | 0.4363 | 100-98-2 | crash_trigger_ticks=4 |
| **0.500** | 0.4314 | 99-99-2 | **CTRL** |
| 0.450 | 0.3826 | 90-110-0 | milk_floor=127 |
| 0.435 | 0.3682 | 87-113-0 | fert_floor=40 |
| 0.390 | 0.3251 | 78-122-0 | wool_milk_sell_cap=2 |
| 0.155 | 0.1114 | 31-169-0 | feed_reserve=8 |
| 0.130 | 0.0903 | 26-174-0 | valve_soft_threshold=70 |
| 0.070 | 0.0422 | 14-186-0 | feed_batch_cap=2 |
| 0.065 | 0.0384 | 13-187-0 | valve_soft_cap=4 |
| 0.050 | 0.0274 | 10-190-0 | melon_tile_target=20 |
| 0.005 | 0.0009 | 1-199-0 | melon_tile_target=4 |
| 0.000 | 0.0000 | 0-200-0 | max_owned_quadrants=2 |
| 0.000 | 0.0000 | 0-200-0 | max_owned_quadrants=4 |

**ARMS CLEARING 0.65: 2.** One arm (0.635) sits inside the simulated null-max
band [0.60, 0.615 at p99] and is reported as noise, per the registration.

## Confirmation, band 839000, n=250 — and the screen-then-confirm rule earning its keep

| arm | screen (n=100) | confirm (n=250) | ci_lower | registered bar | |
|---|---|---|---|---|---|
| CTRL | 0.500 | **0.500** (243-243-14) | 0.4563 | [0.40,0.60] | VALID |
| **valve_soft_threshold=35** | 0.690 | **0.698** (349-151) | **0.6564** | >=0.65 & ci>0.55 | **CONFIRMED** |
| feed_reserve=0 | 0.685 | **0.568** (284-216) | 0.5242 | >=0.65 & ci>0.55 | **FAILED** |

**One of the two survivors was a selection artifact.** `feed_reserve=0` came out
of the screen at 0.685 and fell to 0.568 on a disjoint band — inside the range
the null maximum reaches at 23 arms. Had the screen been allowed to promote
directly, it would have shipped. This is the entire reason the registration said
*the screen selects, it does not promote*, and it is the first time in this
project's record that the multiplicity discipline has visibly caught something.

`valve_soft_threshold`=35 went the other way: 0.690 -> **0.698** on a fresh band
at 2.5x the n, implying **+146 Elo** on top of the shipped HML20 champion.

## The registered prediction that was flatly wrong

> *"max_owned_quadrants=4 is the most likely single winner."*

It was the **worst arm in the screen**: 0-200, rate 0.000, candidate money
**-$9,325**. The other direction (=2) also went 0-200 at -$3,375. The shipped
cap of 3 is strongly optimal in both directions.

**This refines the central claim of the Elo-aligned registration, and the
refinement matters more than the miss.** The reasoning behind the prediction was
"the money instrument was wrong about other things, so a large money effect
might reverse on win rate." That treated a *known-direction* prior as if it were
uninformative. It is not: the money gate said cap 3 beats cap 4 by
$5,991-7,780, and the win-rate screen agrees emphatically.

So the accurate statement is narrower than "the money gate measures the wrong
thing": **the money gate fails when the effect lives in the opponent-relative
GAP rather than in our absolute bank.** That is precisely the W30/HML20 case,
where arms banked *less* than CTRL and still won 83-97% of games. When a change
costs $9,325 in absolute terms, both instruments agree and always would have.
`eval/prereg/2026-09-07-elo-aligned-factorial.md` should be read with that
qualification.

## What the screen actually bought: negative knowledge

Nine arms scored below 0.16 — `melon_tile_target` in both directions,
`valve_soft_cap`=4, `feed_batch_cap`=2, `valve_soft_threshold`=70,
`feed_reserve`=8, and both land caps. The shipped configuration is well-tuned
across most of the surface nobody had ever measured, which retroactively
supports the earlier money-gated work and says where *not* to spend the days
before the 2026-09-28 freeze. Two in-source priors were also confirmed on the
new instrument: `feed_batch_cap`=2 regressed as its own source comment predicted
(0.070), and `fert_floor`=40 did nothing (0.435), matching the fertilizer recon.

**Scale honestly.** The confirmed winner's money gap is **+354** against HML20's
**+3,150**. It is a real marginal gain, an order of magnitude below the knob
that was just shipped, and it should not be described as comparable.

## Consequence

`valve_soft_threshold`=35 is CONFIRMED and is a ship candidate. It was measured
with the shipped HML20 champion on both sides, so it stacks with HML20 **by
construction** — unlike the wheat/mule pair, which the factorial showed were
substitutes. Shipping it requires the same treatment HML20 got: change the
source default, then prove bit-identically against this ledger that the shipped
default reproduces the measured arm.

`feed_reserve`=0 is CLOSED by its own registered confirmation. No successor.

Nothing in this document authorises an upload.
