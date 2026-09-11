# Pre-registration: labor slice 1 — plant the wheat the agent already plans

Date: 2026-09-11
Candidate: `champion` with three labor knobs added by the build PR linked below:
- `max_hires_per_turn` (default 4) caps how many hands are hired in one turn;
- `wheat_plant_priority` (default 3) sets the dispatch tier of PLANT WHEAT tasks;
- `wheat_plant_hour_cutoff` (default 20) is the last hour a wheat planting is scheduled.
Every default is today's behaviour. The build PR proves that with a money gate against a
frozen copy of `main` (mean_delta 0.0, sd_delta 0.0).
Status: REGISTERED — runs launch only after (1) this document and the build PR have merged
and (2) the expression check below has passed. The runner asserts engine 1.32.7, that
`PolicyConfig` has every knob at its shipped default, and that `main`'s `packages/` and
`dist/` equal the expression-checked build.
Authorization: owner decision 2026-09-11 (labor-efficiency pivot).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

A labor diagnosis of the shipped agent (all defaults, seeds 855000-855001 vs Sokolovsky V12;
`eval/recon/2026-09-11-labor-diagnosis-*`) found that it plants about half the wheat it
plans. It instrumented every task type in-process and reproduced the committed banks
exactly.

| task type | generated | claimed | executed |
|---|---|---|---|
| plant wheat (tier 3) | ~7,800 | ~740 (9.5%) | ~200 per game |
| dig weeds (tier 4) | ~1,350 | ~175 | ~15 |
| feed, care, collect fertilizer, harvest | — | 78-100% | not bottlenecked |

The agent's own `plant_quota` intends ~410 wheat plantings a game, and ~200 happen. Three
mechanisms combine:
1. **Tier starvation.** `dispatch()` resolves priority tiers strictly in order, nearest task
   first within a tier, so tier 0-2 work takes the hands before any planting gets one.
2. **A slow morning ramp.** `MAX_HIRES_PER_TURN = 4` rebuilds the crew over three hours each
   morning (1, 5, 9 and 11 units at hours 0-3), just as the day's planting quota resets.
3. **An hour-20 planting cutoff.** Plantings stop there whatever the backlog.

The unit-turn budget agrees. Our units walk 56% of turns against the leader's 44%, and 25%
of our steps are cut off by the midnight hand-wipe, against the leader's 4.9%
(`eval/recon/2026-09-11-strawberry-slice0-{A-tiles0,L-sokolovsky}-855000.json`).

The diagnosis values the shortfall at up to $19k a game, but that counts quota slots, not
land. NW+NE plus SW can turn over roughly 280 wheat plantings a game, and the shipped agent
leaves 20-38 tiles empty every day from day 10
(`eval/recon/2026-09-11-early-cash-ledger-855000.json`). The realistic pool is about $7-10k a
game.

**Hypothesis:** letting more of each day's labor reach wheat planting, through a faster
morning ramp, a higher planting priority and a later planting cutoff, plants more of the
idle land and banks more.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` | purpose |
|---|---|---|
| H10 | `{"max_hires_per_turn": 10}` | the morning ramp alone |
| WP2 | `{"wheat_plant_priority": 2}` | wheat planting one tier ahead of the tier-3 queue |
| CUT22 | `{"wheat_plant_hour_cutoff": 22}` | the late-day planting window alone |
| COMBO | `{"max_hires_per_turn": 10, "wheat_plant_priority": 2, "wheat_plant_hour_cutoff": 22}` | all three levers |

**Expression check (pre-launch recon; a precondition).** Run
`tools/recon-scripts/labor_probe.py --check` on the build's tree (recorded by SHA) with the
shipped reference plus every arm, on seeds 855000-855007 against `public:sokolovsky-v12`.
Commit the record as `eval/recon/2026-09-11-labor-slice1-expression-check-855000.json`. An
arm passes only if every criterion that applies to it holds. The thresholds are committed
before the check runs, and criterion 1 was re-specified after the build's two-seed probe
(see the amendment history).
1. **Mechanism, H10 and COMBO:** the mean units on the farm over hours 1 and 2 (days 1-29,
   all 8 seeds) exceed shipped's by at least **1.0**.
2. **Mechanism, WP2 and COMBO:** mean executed wheat plantings per game at least
   **1.15 × shipped's**.
3. **Mechanism, CUT22 and COMBO:** a mean of at least **10 wheat plantings a game ordered at
   hours 21-22**.
4. **Guardrail, every arm:** mean weed tile-days no more than **1.5 × shipped's**. A
   planting push that starves watering shows up as weeds.
An arm that fails cannot express the hypothesis, and this document is amended before any
run. Every arm changes behaviour from the first day, so the shop-roster coupling can reach
all 8 draws (`eval/README.md`, pairing limitation). That is why confirmation runs at n=128.

- **Screen:** band **866000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **867000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **868000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/`, and none is named by
an earlier registration.

## Decision rule (fixed before launch)

This is the strawberry slices' rule, restated so this document stands alone.

For each arm and each leader *i*, take `mean_delta_i`, `stderr_i`, and
`opponent_mean_delta_i` from the ledger. Pool as the simple mean, with pooled se
`sqrt(sum stderr_i²)/3`; intervals are estimate ± 1.96 × se. The ledger's `passed` field is
not the verdict.

**INVALID** if any of these holds:
- the engine is not 1.32.7;
- a knob is absent;
- the expression check has not passed;
- any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
  `opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate` veto.

A `candidate_degenerate` veto is a result, not an invalidity. The games are deterministic,
so a rerun would reproduce it. That arm does not advance, confirm, or pass the guard.

**SCREEN — an arm ADVANCES** only if all hold at band 866000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 867000 n=128, has:
1. pooled own-bank delta **>= +$4,000**;
2. pooled lower bound **> +$1,000**;
3. a pooled **margin delta** point estimate **> −$2,000**. The margin delta is
   `mean_delta_i − opponent_mean_delta_i`, pooled as a simple mean. It is a guard, not a
   mechanism reading and not an Elo proxy: the ladder scores the calibrated pair as tied at
   a margin delta of +$6,177.

**GUARD** (a no-catastrophe check): the confirmed arm's own-bank delta against
`frozen:m3b_live_b6ce655` must have a point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

REPORTED, NOT GATING: per arm at screen, the gap (own bank minus the leader's) and the
margin delta. For the selected arm:
- the settled-flow breakdown by item against the shipped agent
  (`tools/recon-scripts/revenue_breakdown.py`);
- the task funnel (plantings generated, claimed and executed);
- units on the farm by hour;
- weed tile-days.

## Registered predictions

- **Expression check:**
  - H10 and COMBO raise the hour 1-2 crew by about 1.5 units; the order cap still drops
    some hires on busy turns.
  - WP2 and COMBO execute 20-40% more wheat plantings than shipped.
  - CUT22 and COMBO order at least 15 plantings a game at hours 21-22.
  - Weeds stay inside the guardrail, and H10 likely has fewer than shipped.
- **WP2 advances,** pooled own-bank delta **+$4k to +$8k**.
- **H10 alone lands below the bar** (+$1k to +$3k): hands arrive sooner, but planting still
  queues behind tiers 0-2.
- **CUT22 alone lands below the bar** (+$1k to +$4k): the late window adds plantings but
  not enough to clear $4k on its own.
- **COMBO has the highest point estimate** of the four.
- If **no arm advances**, tier starvation was not what binds the bank. Either the extra
  plantings do not sell, or they come out of animal care. The next suspects are the
  midnight orphaning (a finish-before-midnight filter) and labor supply (more hands, at
  about $4.7k a game for two).

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot), and that remains an owner decision.

## Amendment history

- **2026-09-11, before the expression check and before any run.** The build's two-seed
  mechanism probe (seeds 777400-777401; recon, not committed) verified two engine facts the
  first draft had not accounted for:
  - the hour-0 observation always precedes the day's first hire, so units at hour 0 are 1 in
    every configuration;
  - hires sit last in the market order list and are dropped, then re-requested the next
    turn, when the 10-order cap truncates a busy turn.

  With `max_hires_per_turn = 10`, units at hour 1 rose from 4.9 to about 6.5, and the full
  crew arrived at hour 2 (9.7 vs 8.3). That is below the first draft's hour-1 threshold of
  8, although the crew does arrive sooner. Criterion 1 now measures the hour 1-2 crew
  against shipped's, requiring +1.0 units.

  The same probe showed the hour-22 cutoff adding about 30 wheat plantings a game, against
  WP2's 55, so CUT22 joins as an arm of its own. The probe's bank numbers were seen but are
  not a basis for anything here: two seeds that share one baseline are one draw.

## ADDENDUM — EXPRESSION CHECK (2026-09-11): H10 passes; WP2, CUT22 and COMBO fail the weed guardrail

Run on the build `b594240` (engine 1.32.7, `packages/` clean), seeds 855000-855007 against
`public:sokolovsky-v12`. The criteria were committed beforehand, in 423abbd. Record:
`eval/recon/2026-09-11-labor-slice1-expression-check-855000.json`.

| arm | units at h1 / h2 | wheat plantings | plantings at h21-22 | weed tile-days | verdict |
|---|---|---|---|---|---|
| shipped | 4.9 / 8.3 | 195.2 | 0 | 58.1 | reference |
| H10 | 6.5 / 9.7 | 207.1 | 0 | 44.0 | **PASS** (hour 1-2 crew 8.1 vs 7.6 required) |
| WP2 | 5.0 / 8.4 | 248.0 | 0 | 104.4 | **FAIL** (weeds 104.4 > 87.2) |
| CUT22 | 4.9 / 8.3 | 221.1 | 48.5 | 115.9 | **FAIL** (weeds 115.9 > 87.2) |
| COMBO | 7.1 / 9.8 | 256.9 | 27.0 | 183.9 | **FAIL** (weeds 183.9 > 87.2) |

Every mechanism was expressed. The crew arrives sooner, plantings rise 6-32%, and the late
window plants. But the three arms that move labor toward planting raise weeds 1.8-3.2x.
The guardrail caught exactly the failure it was registered for: a planting push that
starves watering. WP2 puts wheat planting in the same tier as maintenance watering, and a
later cutoff plants tiles that go unwatered overnight. Per the rule above, those three arms
are dropped before any run. **The screen runs H10 alone** at band 866000, with confirmation
and guard as registered. The record's bank numbers (8 seeds, one leader) are recon, not a
result, and play no part here.

**What it means (recorded, not a verdict).** Reallocating a saturated crew toward planting
starves watering. Only H10 lowers weeds (44 vs 58), because it adds labor earlier instead of
moving it. The next candidates should add effective labor rather than redistribute it: the
midnight orphaning (25% of move-steps) and labor supply.
