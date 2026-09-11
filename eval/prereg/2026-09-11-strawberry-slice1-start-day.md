# Pre-registration: strawberry slice 1 — hold strawberry off until the opening has run

Date: 2026-09-11
Candidate: `champion` with the new `strawberry_start_day` knob. On every turn whose
day is below N, the agent behaves exactly as if `strawberry_tile_target = 0`, on
every code path; from day N on it is the configured strawberry agent. Default 0 =
today's behaviour, proven in the build PR by a money gate against a frozen copy of
`main` (mean_delta 0.0, sd_delta 0.0).
Status: REGISTERED — runs launch only after (1) this document and the knob's build PR
have merged and (2) the expression check below has passed. The runner asserts engine
1.32.7 and that `PolicyConfig` has the knob.
Authorization: owner decision 2026-09-11 (strawberry rebuild).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md` (pooled +$1,331 on the pair
the ladder scores as tied; sd_delta ~$14-15k per seed).

## Why

The live gap to the rating band above us is 94% strawberry, a crop we never plant.
Our three earlier strawberry closures were true about our build — it genuinely banked
less. Slice 0 and an 8-seed early-cash ledger found why. The ledger replays each arm
against Sokolovsky V12 and diffs its submitted actions against the shipped agent's,
turn by turn.

**Switching strawberry on changes the agent from turn 0, before a single strawberry
seed is bought.** The strawberry arms diverge from the shipped agent at day 0, hour 0,
in 16/16 games, through four code paths:

1. **Land.** The zone is carved out of wheat's tile set (`policy.py`, `wheat_tiles`).
   NW+NE hold exactly 31 plantable tiles after melon (8) and pasture (10), so a
   31-tile zone takes all of the wheat land until SW is bought.
2. **Dispatch** (`dispatch.py`, `_field_tasks`) queues strawberry plantings ahead of
   wheat on zone tiles; with no seeds in the shed, those tiles sit empty.
3. **Fertilizer.** `make_policy` passes `fert_reserve = strawberry_tile_target`, which
   withholds up to 31 units from sale from turn 0.
4. **Cash.** The strawberry seed line buys 8-9 seeds ($800-900) on day 0, and the cow
   orders the shipped agent submits on day 0 never come.

Ledger means over seeds 855000-855007
(`eval/recon/2026-09-11-early-cash-ledger-855000.json`):

| | cows d0-4 | cows d5 | sheep d7 | wheat d3 | cash d8 | cash d11 | SW day | peak strawberry | final bank | leader's bank |
|---|---|---|---|---|---|---|---|---|---|---|
| shipped | 1-2 | 6.0 | 3.9 | 31 | $1,506 | $7,092 | 9.5 | — | $66,163 | $116,383 |
| 31 + wheat 21 | 0 | 2.9 | 0 | 19 | $81 | $1,192 | 12 (8/8) | 14.9 | $60,202 | $121,699 |
| 31, cap 10 | 0 | 2.0 | 0 | 11 | $60 | $199 | 13 (8/8) | 12.4 | $59,994 | $130,321 |

Without a herd there is no day-8 milk and wool takeoff and no cash to fund the zone.
SW requires `animals_done` (6 cows or day > 9, **and** 4 sheep or day > 11) plus
$2,500, so it stays locked until day 12-13, at or past the day-12 strawberry plant
cutoff. The zone peaks at 12-15 of 31 tiles: plants are not dying, they are never
planted. The leader banks $5-14k more, most plausibly because our smaller herd stops
competing in milk and wool. Ungated strawberry therefore costs us twice, on our own
bank and on the gap. Slice 0's internals
(`eval/recon/2026-09-11-strawberry-slice0-*-855000.json`) and the SW re-measure
(`eval/recon/2026-09-11-sw-timing-855000.json`) agree: the ledger reproduces their
banks and SW days exactly, on 16/16 games each.

The leader (Slice 0's `L-sokolovsky` record) plants strawberry from day 3 and bursts
10-11 tiles a day on days 7 and 10 as its cash arrives.

**Hypothesis:** holding strawberry fully off until the opening has run (the herd
completes by day 7; the wheat rush and SW keep their shipped schedule), then switching
it on for a planting window from day N to day 12, funds a ~30-tile cohort from the
day 8-11 takeoff, with wheat moving onto SW.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion`
at shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` | purpose |
|---|---|---|
| START8 | `{"strawberry_tile_target": 31, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8}` | primary: on the day after the herd completes |
| START6 | same, `"strawberry_start_day": 6` | earlier: the zone takes NW+NE's wheat land and starts drawing cash two days sooner |
| START10 | same, `"strawberry_start_day": 10` | later: after SW in most games; three planting days, so the cap binds at 30 |
| START8_T20 | START8 with `"strawberry_tile_target": 20` | smaller zone: leaves 11 NW+NE tiles to wheat and draws less cash and labour |

`strawberry_plant_daily_cap` is 10 in every arm so the window can be planted before the
day-12 cutoff; it is not the variable under test.

**Expression check (pre-launch recon; a precondition).** Run
`tools/recon-scripts/early_cash_ledger.py` on the knob's build tree (recorded by SHA)
with the shipped reference plus all four arms, on seeds 855000-855007 against
`public:sokolovsky-v12`, and commit the record under `eval/recon/`. Every arm's
submitted actions must match the shipped arm's **through day N-1 on 8/8 seeds**. An
arm that fails cannot express the hypothesis, and this document is amended before any
run.

The same record bounds the shop-roster coupling (`eval/README.md`, pairing
limitation). With occupancy identical through day N-1, the first coupled shop draw is
the first draw-day at or after N: **6/8 draws** are coupled for START6, START8 and
START8_T20, and **5/8** for START10. Effective power is therefore below `mde_80`,
which is why confirmation runs at n=128.

**Expression check — RESULT (2026-09-11): PASSED on 8/8 seeds for all four arms.**
Run on the knob's build commit `f210195` (engine 1.32.7, `packages/` clean). Record:
`eval/recon/2026-09-11-strawberry-slice1-expression-check-855000.json`. Every arm's
first action that differs from the shipped agent falls on day N, hour 0, on every seed:
day 6 for START6, day 8 for START8 and START8_T20, day 10 for START10. The opening is
untouched by construction, and the coupled-draw counts above hold.

The same record, read as recon only (8 seeds, one leader; not a gate result):

| arm | own bank vs shipped (paired) | leader's bank vs shipped | strawberry tiles at day 12 | SW day |
|---|---|---|---|---|
| START8 | +$6,562 (se $5,495) | +$9,201 | 21.4 | 10.9 |
| START6 | +$8,914 (se $4,740) | +$14,496 | 19.1 | 10.6 |
| START10 | +$7,884 (se $5,398) | +$4,149 | 22.4 | 9.5 |
| START8_T20 | +$6,960 (se $3,737) | +$5,162 | 15.5 | 10.0 |

The predictions below were fixed before this ran and are left unchanged. Two readings
bear on them. First, the zone reaches 15-22 tiles by day 12, not the predicted 25-31:
the NW+NE zone tiles are still under wheat at switch-on, and seed cash is thin on days
8-9. Second, the leader's bank rises in every arm, which is what the confirmation's
margin guard exists to catch.

- **Screen:** band **860000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **861000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **862000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/`.

## Decision rule (fixed before launch)

For each arm and each leader *i*, take `mean_delta_i`, `stderr_i`, and
`opponent_mean_delta_i` from the ledger. Pool as the simple mean, with pooled se
`sqrt(sum stderr_i²)/3`. Intervals are estimate ± 1.96 × se. The ledger's `passed`
field is not the verdict.

**INVALID** if the engine is not 1.32.7, the knob is absent, the expression check has
not passed, or any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
`opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate`
veto. A `candidate_degenerate` veto (the arm itself ends at or below the gate's money
floor on a quarter or more of seeds) is a result, not an invalidity: the games are
deterministic, so a rerun would reproduce it. That arm does not advance, confirm, or
pass the guard.

**SCREEN — an arm ADVANCES** only if all hold at band 860000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 861000 n=128, has:
1. pooled own-bank delta **>= +$4,000**;
2. pooled lower bound **> +$1,000**;
3. a pooled **margin delta** point estimate **> −$2,000**, where margin delta is
   `mean_delta_i − opponent_mean_delta_i`, pooled as a simple mean. This is a guard,
   not a mechanism reading (`eval/README.md` warns against reading
   `opponent_mean_delta` at screen n). The ungated arms enriched the leader by $5-14k,
   and an arm that gains us less than it gives the leaders does not win games. The
   margin is not an Elo proxy: the calibrated pair (shipped vs M3b, which the ladder
   scores as tied) shows a margin delta of +$6,177 in the band-850000 ledgers. The
   guard only screens out an arm that enriches the leaders.

**GUARD** (a no-catastrophe check, not a contested-market test): the confirmed arm's
own-bank delta against `frozen:m3b_live_b6ce655` must have a point estimate
**> −$2,000**. Frozen M3b grows no strawberry, so this cannot test contested strawberry
markets; the panel does that. The guard exists to catch a build that breaks the
economy.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or
threshold change after launch.

REPORTED, NOT GATING: per arm at screen, the gap (own bank minus the leader's) and the
margin delta. For the selected arm: `strawberry_labor.py` internals (plantings by day,
peak alive, walking share, fertilizer demand met), the SW purchase day, and wheat
tiles by day.

## Registered predictions

- **Expression check:** every arm matches the shipped agent through day N-1 on 8/8
  seeds, by construction.
- **START8 advances**, pooled own-bank delta **+$5k to +$15k**. Its SW purchase slips
  from day ~9.5 to about day 10-11, because the seed line runs ahead of the SW line in
  the budget order. The zone reaches **25-31** planted tiles by day 12 as the wheat on
  zone tiles is harvested and wheat moves to SW.
- **START6 lands below START8.** It takes NW+NE's wheat land while the day-4/5 replant
  is still growing, and draws on the cash SW needs sooner.
- **START10 lands within START8's interval.** Three planting days cap it at 30 tiles,
  but SW is usually already bought.
- **START8_T20 advances, below START8's point estimate.** The market projection puts
  ~120 units at most of the value, and it protects 11 tiles of wheat.
- If **no arm advances**, the funding spiral was not the binding constraint once
  removed. The next suspects are the zone's land still being under wheat at
  switch-on; labour (walking 60% against the leader's 44%); and harvest cadence (we
  harvest at the 4-unit cap, while the leaders harvest after every tick).

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload
evicts M3b (our best live bot), and that remains an owner decision.

## Amendment history

- 2026-09-11, before merge and before any run: the first draft gated only the
  strawberry seed-buy line and included a START8 + `wheat_rush_tiles: 30` arm. The
  8-seed ledger and a code map showed the zone acting from turn 0 through land,
  dispatch and fertilizer paths, so the knob now holds strawberry fully off before day
  N. `wheat_rush_tiles` defaults to 81 and never truncates, so the W30 arm was nearly a
  no-op; START8_T20 replaces it. The margin guard and the expression check were added
  in the same pass.

## ADDENDUM — SCREEN VERDICT (2026-09-11): NOT ADVANCED

Run at `main` = `1d02dae`, whose `packages/` and `dist/` are byte-identical to the
expression-checked build `f210195`. Engine 1.32.7, band 860000, n = 64 per leader. The
twelve ledgers are `eval/gates/2026-09-11T04-00-30Z` through `…T04-26-01Z-*-money.json`,
with no crash and no veto. The registered rule was applied verbatim: the pooled estimate
is the simple mean over the three leaders, with pooled se = sqrt(Σ se²)/3.

| arm | Sokolovsky | rayk | kaito | pooled Δ (se) | 95% CI | margin Δ | verdict |
|---|---|---|---|---|---|---|---|
| START8 | −$571 | −$1,041 | −$1,495 | −$1,036 ($1,008) | [−$3,011, +$939] | −$1,423 | NOT ADVANCED (fails 1, 2) |
| START6 | −$1,287 | +$852 | +$429 | −$2 ($947) | [−$1,857, +$1,853] | −$2,609 | NOT ADVANCED (fails 1, 2) |
| START10 | +$1,863 | +$2,110 | +$1,646 | +$1,873 ($911) | [+$88, +$3,659] | +$1,344 | NOT ADVANCED (fails 1) |
| START8_T20 | +$1,712 | +$2,711 | +$2,422 | +$2,282 ($913) | [+$492, +$4,072] | +$1,206 | NOT ADVANCED (fails 1) |

No arm reaches the +$4,000 pooled bar. There is therefore no selection, no confirmation
run, no guard run, and no upload decision. **Slice 1 is NOT ADVANCED.**

**Predictions scorecard.** The expression check held by construction. Every other
prediction was wrong:
- START8 lost $1.0k rather than gaining the predicted $5-15k.
- START6 did not land below START8 (−$2 vs −$1,036, within noise).
- START10 landed above START8's interval, not within it.
- START8_T20 did not advance, and it was the best arm.
The expression check's own recon (8 seeds, one leader) overstated every arm by $4.7-8.9k.
Its paired deltas shared the same eight baseline games, so its errors were correlated
across arms: four positive arms at n=8 were one draw, not four.

**What it means (recorded here, not part of the verdict).** Holding strawberry off until
the opening has run fixed the funding spiral; the expression check proved the opening
untouched. But the cohort this architecture can field by the day-12 cutoff pays about
+$2k at best: 15-22 tiles, planted late, on land taken from wheat. The two arms with a
positive lower bound are the two that take least from wheat. The 20-tile zone leaves 11
NW+NE tiles to wheat, and the day-10 start keeps SW on its shipped schedule. The 31-tile
arms reclaim all of NW+NE's wheat land at day 6-8, and they lose. The binding cost is now
the zone's displacement of wheat, not cash. That points to the registered next suspects,
land first (a zone that does not sit on wheat land), then labour and harvest cadence.
