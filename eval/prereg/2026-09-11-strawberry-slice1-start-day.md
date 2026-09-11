# Pre-registration: strawberry slice 1 — fund the cohort from the day-8 cash takeoff

Date: 2026-09-11
Candidate: `champion` with the new `strawberry_start_day` knob (default 0 =
today's behaviour; its no-op at default is proven by the build PR before any run).
Status: REGISTERED — runs launch only after this document AND the knob's build PR
have merged. The runner asserts engine 1.32.7 and that `PolicyConfig` has the knob.
Authorization: owner decision 2026-09-11 (strawberry rebuild).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md` (pooled +$1,331 on the pair
the ladder scores as tied; sd_delta ~$14-15k per seed).

## Why

The live gap to the rating band above us is 94% strawberry, a crop we never plant.
Our three earlier strawberry closures were true about our build: it genuinely banked
less. Slice 0 (band 855000, recon) and a day-by-day ledger on the current tree found
**why**, and it is not what the earlier diagnoses named:

- **The zone never fills.** A 31-tile target peaks at 14.9 live tiles (Sokolovsky V12:
  35.6), with only ~3 more plantings than peak — tiles are not dying, they are never
  planted. The 6/day plant cap binds on a single day.
- **The cause is cash.** With strawberry on, the day-0 plan buys ~8 strawberry seeds
  (~$800) before any pasture exists — cash the shipped agent spends on cows a few turns
  later. Shipped: 6 cows by day 5 and 4 sheep by day 7, after which milk and wool pay
  out: **$1.9k on day 8, $2.9k day 10, $6.5k day 11**. Strawberry-on: 2 cows and 0 sheep
  until day 10, and **$2-122 of cash every day through day 11**. No herd, no day-8
  takeoff, no money to fund the zone. The SW purchase slips from day ~9.5 to day 12 in
  16/16 games.
- The leader plants strawberry from day 3 and bursts 10-11 tiles a day on days 7 and 10
  as its cash arrives.

**Hypothesis:** gating strawberry seed purchases until after the herd is bought lets
the shipped opening run intact and funds a ~30-tile cohort from the day 8-11 takeoff.
The shipped herd completes on day 7, so day 8 is the natural start.

## Registered design

Money gate, candidate `champion` with the arm's `--agent-config`, **baseline `champion`
at shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` | purpose |
|---|---|---|
| START8 | `{"strawberry_tile_target": 31, "strawberry_start_day": 8, "strawberry_plant_daily_cap": 10}` | primary hypothesis |
| START6 | same, `"strawberry_start_day": 6` | competes with the day 5-7 herd buys: mechanism check |
| START10 | same, `"strawberry_start_day": 10` | later, fewer planting days, more cash |
| START8_W30 | START8 plus `"wheat_rush_tiles": 30` | labor relief for the cohort |

`strawberry_plant_daily_cap` is raised to 10 in every arm so a funded cohort can be
planted in the 5-day window before the day-12 plant cutoff; it bound only once in
Slice 0, so it is not the variable under test.

- **Screen:** band **860000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **861000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent,
  band **862000**, n = 64.

All three bands verified unused by every ledger in `eval/gates/`.

## Decision rule (fixed before launch)

For each arm, per leader *i*, take `mean_delta_i` and `stderr_i` from the ledger; pool
as the simple mean with pooled se `sqrt(sum stderr_i²)/3`; intervals are
estimate ± 1.96 × se. The ledger's `passed` field is not the verdict.

**INVALID** if the engine is not 1.32.7, the knob is absent, or any run records a
crash or a non-empty `vetoes` list.

**SCREEN — an arm ADVANCES** only if all hold at band 860000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 861000 n=128, has pooled delta
**>= +$4,000** and pooled lower bound **> +$1,000**.

**GUARD** (a no-catastrophe check, not a contested-market test): the confirmed arm's
own-bank delta against `frozen:m3b_live_b6ce655` must have a point estimate
**> −$2,000**. Frozen M3b grows no strawberry, so this cannot test contested strawberry
markets — the panel does that; it exists to catch a build that breaks the economy.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or
threshold change after launch.

REPORTED, NOT GATING: the gap (own delta minus the leader's bank delta) per arm;
`strawberry_labor.py` internals on the selected arm (plantings by day, peak alive,
walking share, fertilizer demand met); and the SW purchase day.

## Registered predictions

- **START8 advances**, pooled own-bank delta **+$5k to +$15k**, with plantings reaching
  ~28-31 and the SW purchase back to day ~9-10.
- **START6 lands below START8**: a day-6 start still competes with the herd buys on
  days 6-7.
- **START10 lands near START8** (within its interval): a day-10 planting still fits all
  four yield ticks before the game ends, and cash is ample by then.
- START8_W30 is uncertain; the labor relief and the lost wheat roughly offset.
- If **no arm advances**, the funding spiral was not the binding constraint once
  removed, and the next suspects are labor (walking 60% against the leader's 44%) and
  harvest cadence (we harvest at the 4-unit cap; the leaders harvest after every tick).

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only; the next upload
evicts M3b (our best live bot), and that remains an owner decision.
