# Pre-registration: leader-tape slice 1 — play the leaders' opening calendar

Date: 2026-09-11
Candidate: `champion` with the leader-tape knobs. New for this slice: `ne_land_min_day` and
`animal_buy_order` (#138). Both are default-neutral: a money gate against a frozen copy of
`9fdf4f5` measured mean_delta 0.0 and sd_delta 0.0, and 7 of 7 guard mutations were caught.
The slice also uses the strawberry knobs from #128 (`strawberry_start_day`) and #130
(`strawberry_frame_quadrants`, `strawberry_plant_priority`, `strawberry_fert_reserve`), plus
the older `strawberry_tile_target`, `strawberry_plant_daily_cap` and
`strawberry_seed_budget_share`.
Status: REGISTERED — runs launch only after (1) this document has merged and (2) the
expression check below has passed. The runner asserts engine 1.32.7, that `PolicyConfig`
has every knob at its shipped default, and that `main`'s `packages/` and `dist/` equal the
expression-checked build.
Authorization: owner decision 2026-09-11 (leader-style rebuild, own code). The spec comes
from observed play only. The leaders' source (`eval/opponents/public-leaders/`) was not
read.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

**The gap is strawberry, and bolting it on has failed four times.** We plant none
(`STRAWBERRY_TILE_TARGET = 0`). The leaders' strawberry sales are worth about $49-54k a
game, roughly half their final bank. The earlier slices all ran into one chain, cash →
land → dispatch → labor:
- **Strawberry slice 1** (`eval/prereg/2026-09-11-strawberry-slice1-start-day.md`): NOT
  ADVANCED. A cohort bolted onto the wheat farm from day 8 filled 15-22 of 31 tiles, late;
  the best arm netted +$2,282.
- **Strawberry slice 2** (`…-strawberry-slice2-sw-zone.md`): WITHDRAWN before launch. A
  zone parked on SW filled 16.2 of 22 tiles, short of the registered 18.
- **Labor slices 1 and 2** (`…-labor-slice1-wheat-planting.md`,
  `…-labor-slice2-extra-hands.md`): NOT ADVANCED. Re-ranking the crew starves watering,
  and extra hands cost more than their work earns.

**The leaders do not bolt strawberry onto a wheat farm. They run one fixed calendar.**
`eval/recon/2026-09-11-leader-opening-tape-855000.md` has 32 instrumented games with zero
seed variance in any non-money field through day 15:
- **Day 0:** 4 sheep and 1 cow, 5 wheat, 5 melon, 4-5 hires, and cash spent to $0.
- **Land:** NE on day 6, SW on day 10, never SE.
- **Strawberry:** planted in bursts right after each quadrant unlocks. NW gets ~7 on days 3
  and 5, NE ~13 on days 6-8, and SW ~16 on days 10-11. That is about 36 tiles, and none are
  planted after day 11.
- **Wheat and fertilizer:** wheat stays at 5-13 tiles through day 15. Fertilizer is applied
  only to strawberry (72 applications = 36 tiles × 2), and the surplus is sold.

We lead on money through day 15 ($27.4k vs $17.1k). The leaders overtake on days 15-20 as
their strawberry yields, and finish at $102-109k against our $66k.

**Our knobs can now express most of that calendar:**
- a strawberry zone of 36 tiles (`strawberry_tile_target`);
- a frame of NW, NE and SW (`strawberry_frame_quadrants`), so each quadrant's share becomes
  plantable the day it unlocks. A non-default frame uses the melon- and pasture-aware zone
  formula (`constants.strawberry_tiles_for_frame`), which has no 31-tile ceiling;
- planting from day 3 (`strawberry_start_day`), up to 11 tiles a day
  (`strawberry_plant_daily_cap`), ahead of wheat (`strawberry_plant_priority` 2);
- a fertilizer reserve sized to the planted tiles, not the target
  (`strawberry_fert_reserve` "planted"), so day-9 fertilizer sales still fund the SW buy;
- for the full opening, NE on day 6 (`ne_land_min_day`) and sheep before cows
  (`animal_buy_order`).

**Hypothesis:** playing the leaders' strawberry calendar (from day 3, on every quadrant as
it unlocks, ahead of wheat) fills and keeps a leader-sized cohort, and banks more against
the leaders than the shipped wheat farm does.

## Registered arms

Every arm sets `rescue_water` (#140), whose build measured missed-water deaths falling from
29 a game to 1 in this configuration. An arm that lets its own crop die is not playing the
tape — the leaders hold weeds at 0.0-0.5 through day 15 — and C5 below makes that explicit.

| arm | what it adds to the shipped agent |
|---|---|
| **LTS** | the leaders' strawberry calendar: 36 tiles across NW, NE and SW, from day 3, at most 11 a day, planted ahead of wheat, the fertilizer reserve counted on planted tiles only, and the whole seed budget available for strawberry seed |
| **LTS_HALF** | the same calendar at the shipped seed-budget split, which keeps more early cash for the herd |
| **LTF** | LTS plus the leaders' opening: NE bought on day 6, sheep before cows, and the goose deferred to day 7 (the goose build's probe showed a day-6 goose spending the cash NE needs that day) |

Configs, verbatim — the runner refuses to launch unless each appears in this document:

- LTS: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "strawberry_seed_budget_share": 1.0, "rescue_water": true}`
- LTS_HALF: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "rescue_water": true}`
- LTF: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "strawberry_seed_budget_share": 1.0, "rescue_water": true, "ne_land_min_day": 6, "animal_buy_order": ["SHEEP","COW"], "goose_min_day": 7}`

## Registered predictions

- **Expression check.** All three arms clear C5: rescue watering takes missed-water deaths
  to about 1 a game against a bar near 18-24. LTS and LTF clear C3 and C4. **LTS_HALF fails
  C3's day-9 bar** — it measured 14.5 NW+NE tiles against the required 15 on dev seeds — and
  is dropped before any run. LTF clears C2, with NE on day 6 or 7.
- **LTS has the highest point estimate, +$2k to +$12k.** That is below the +$19.9k its
  design probe showed on four dev seeds, for two reasons: rescue watering spends trips
  (−$4k and −$7k on the build's two probe seeds), and a 4-seed shared-baseline probe is one
  draw, not an estimate.
- **LTF lands below LTS, −$5k to +$6k.** Delaying NE costs our wheat economy more than the
  leaders' herd start returns: the opening-knob probe measured NE-on-day-6 alone at −$13k to
  −$39k without strawberry.
- **At least one arm advances: about 40%.** The mechanism is worth $49-54k a game to the
  leaders, but our dispatcher fills ~30 of 36 tiles and our late game leaves the freed land
  idle where theirs surges back into wheat.
- **If no arm advances**, the leaders' strawberry economics do not transfer at our labor
  level, and this line closes alongside the strawberry and labor lines. The recorded next
  suspects are the late-game land conversion (their wheat goes to 40-57 tiles as the cohort
  ages out; ours does not) and burst-day hiring (14 hands on the SW day against our 10).

## Expression check (pre-launch recon; a precondition)

Run `tools/recon-scripts/early_cash_ledger.py` and `tools/recon-scripts/weed_provenance.py`
on the build's tree (recorded by SHA), both with the shipped reference `{}` first and then
every arm, on seeds 855000-855007 against `public:sokolovsky-v12`. Then run
`tools/recon-scripts/leader_tape_check.py LEDGER --weeds SCAN`, which refuses the pair
unless both records carry the same build, arms, seeds and opponent, and a clean
`packages/`. Commit all three: the ledger as
`eval/recon/2026-09-11-leader-tape-expression-ledger-855000.json`, the weed scan as
`eval/recon/2026-09-11-leader-tape-expression-weeds-855000.json`, and the verdict as
`eval/recon/2026-09-11-leader-tape-expression-check-855000.json`.

The criteria were fixed in bde7a55, from the leaders' measured tape, before any
expression-check data existed and before either design probe was read. Each bar is loose
enough that an arm which really plays the tape clears it, and tight enough that the
shipped opening fails it. An arm passes only if every criterion that applies to it holds:
1. **C1 herd order** (arms whose `animal_buy_order` puts SHEEP first): mean sheep on the
   farm at the end of day 2 >= **3.5**. The leaders own 4 sheep from day 0; shipped
   reaches 4 on day 7.
2. **C2 land calendar** (arms with `ne_land_min_day` = N > 0): NE first unlocks on day N or
   N+1 on every seed, and SW is unlocked by the end of day **11** on at least 7 of 8 seeds.
3. **C3 strawberry fill** (every arm; the positive mechanism criterion): mean NW+NE
   strawberry tiles at the end of day 9 >= **15**, and mean strawberry tiles at the end of
   day 12 >= **27**. These are 75% of the leaders' ~20 and 36.
4. **C4 survival** (every arm): mean strawberry tiles at the end of day 16 >= **0.9 ×** the
   day-12 mean. Strawberry credits yield at ages 9, 11, 13 and 15 and is swept at 16, so a
   tile planted on day 3 or later still stands at the end of day 16 unless it died.
5. **C5 watering guardrail** (every arm): mean **plant deaths from missed watering** per
   game <= **1.5 ×** shipped's. A death is a tile the engine turns into a WEED under its
   two-consecutive-unwatered-days rule (the daily refresh does
   `consecutive_unwatered += 1` on a tile that went unwatered, and `>= 2` replaces the
   plant with a WEED). Measured by `tools/recon-scripts/weed_provenance.py`, which
   re-derives the engine's own condition per tile; a birth it cannot explain is labelled
   UNEXPECTED and the check refuses the record.

An arm that fails a criterion that applies to it cannot express the hypothesis, and it is
dropped before any run. If no arm passes, this document is amended by building, not by
relaxing a criterion. The leaders' tape was measured on the same eight seeds; that does not
bias the check, since the thresholds are the leaders' numbers and no leader-tape arm of
ours had been played on those seeds. Every arm changes behaviour on day 0 (the fertilizer
reserve mode) or day 3, so the shop-roster coupling can reach all 8 draws
(`eval/README.md`, pairing limitation). That is why confirmation runs at n=128.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

- **Screen:** band **872000**, n = **64** seeds per leader, every arm that passed the
  expression check.
- **Confirmation:** the selected arm only, band **873000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **874000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/`, and none is named by
an earlier registration.

## Decision rule (fixed before launch)

This is the earlier slices' rule, restated so this document stands alone.

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

**SCREEN — an arm ADVANCES** only if all hold at band 872000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 873000 n=128, has:
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
  (`tools/recon-scripts/revenue_breakdown.py`): strawberry, wheat, wool, milk, fertilizer
  and seed spend;
- standing strawberry by quadrant and day;
- the day-15 and day-20 banks against the leaders' curve.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot), and that remains an owner decision.

## Amendment history

- bde7a55: the checker and criteria C1-C5, committed before any expression-check data. A
  4-seed design probe (dev seeds 778800-778803, existing knobs only) had finished but was
  unread. The opening-knobs builder's 2-seed mechanism probe (seeds 777600-777601) was
  reported after the file was written and before that commit. No threshold changed after
  either.
- **C5 re-specified, still before any expression-check data**, from total weed tile-days
  to plant deaths from missed watering, with `tools/recon-scripts/weed_provenance.py`
  promoted to measure it. The reason is the engine source, not our numbers: a plant that
  reaches the end of its life becomes a WEED tile by engine rule (the decay pass zeroes
  its yield and replaces the tile), and only DIG clears it, so a leader-sized cohort turns
  about 36 tiles into weeds however well it is watered. The original measure therefore
  could not be met by any arm that plants the tape at all — the criterion firing by
  construction instead of catching damage. The replacement keeps the same 1.5 × bar and
  measures what the guardrail was for: watering starved by the arm's own work. It is not
  a relaxation that admits a preferred arm — on the design probes every arm fails the new
  version too (shipped 11.8 deaths a game, the strawberry calendar 28.2, the full tape
  25.5), so it stays binding and the fix stays a build. Total weed tile-days are still
  printed, as a reported, non-gating number.

## ADDENDUM — EXPRESSION CHECK (2026-09-11): NO ARM PASSES; NOT LAUNCHED

Run on `c7503e9`, whose `packages/` and `dist/` are identical to `main` (8cc7b06; this
branch adds only `eval/` and `tools/`). Engine 1.32.7, seeds 855000-855007 against
`public:sokolovsky-v12`. Records: `eval/recon/2026-09-11-leader-tape-expression-ledger-855000.json`,
`…-weeds-855000.json` and `…-check-855000.json`. The weed scan left none of its births
unexplained.

| arm | sheep@d2 | NE day | SW day | NW+NE@d9 | total@d12 | @d16 | missed-water deaths | weed tile-days |
|---|---|---|---|---|---|---|---|---|
| shipped | 0.00 | 0 | 9-10 | 0.0 | 0.0 | 0.0 | 11.4 | 58.1 |
| LTS | 0.00 | 0 | 11-12 | 18.5 | 23.5 | 23.5 | 1.1 | 101.2 |
| LTS_HALF | 0.00 | 0 | 11 | 15.8 | 24.9 | 24.8 | 1.1 | 94.5 |
| LTF | 4.00 | 7 | 10-12 | 13.9 | 25.5 | 25.1 | 2.8 | 99.9 |

- **C5 passes in every arm**: 1.1-2.8 missed-water deaths a game against a 17.1 bar.
  `rescue_water` does what it was built to do.
- **C4 passes in every arm**: what gets planted survives to day 16.
- **C1 passes in LTF**: 4.00 sheep at the end of day 2, the leaders' own opening herd.
  `goose_min_day` 7 freed the pasture slot it was built to free.
- **C2 fails in LTF**: NE lands on day 7 on 8 of 8 seeds, which the criterion allows, but SW
  is unlocked by day 11 on only 6 of 8 seeds, and the criterion needs 7.
- **C3 fails in every arm**: the day-12 cohort reaches 23.5-25.5 tiles against the required
  27. The day-9 NW+NE bar is cleared by LTS (18.5) and LTS_HALF (15.8), and missed by LTF
  (13.9).

**NOT LAUNCHED.** No screen, confirmation or guard ran. Bands **872000, 873000 and 874000
are retired unused**; a successor takes fresh bands ≥ 875000.

**What the check measured (recorded, not a verdict).**
- **SW land timing is the binding constraint.** SW unlocks on day 11-12 in these arms,
  against day 9-10 for the shipped agent and day 10 for the leaders, because strawberry seed
  spending competes with SW's $2,500. The strawberry plant cutoff is day 12, so the zone's SW
  share gets about one day: LTS stands at 18.5 NW+NE tiles on day 9 and 23.5 in total on day
  12, meaning only about 5 of the zone's ~12 SW tiles are ever planted.
- **Rescue watering trades plantings for survivals at our labor level.** Deaths fall from
  about 28 a game to about 1, and the day-12 cohort falls from 29.5 on the design probes,
  which had no rescue watering, to 23.5 here. Both effects are real and both point at labor.
- **The cohort is still the largest any slice has held**: about 24 tiles standing from day 12
  through day 16, against 15-22 in strawberry slice 1 and 16.2 decaying to 13.9 in slice 2.

**Predictions scorecard.**
- **Right:** C5 passes in every arm; C1 passes in LTF at 4.00 sheep.
- **Wrong:** LTS_HALF was predicted to fail the day-9 fill bar and it passed at 15.8. LTS and
  LTF were predicted to clear C3 and C4; both cleared C4 and failed C3's day-12 total. The SW
  slip that causes the failure was not predicted at all.
- **Unscored:** the money predictions (LTS +$2k to +$12k, LTF below it, about 40% that any arm
  clears the bar) stand unresolved, because no screen ran.

No criterion was relaxed after seeing this. A successor in the same line has to make SW land
on time, or plant the zone before the cutoff, and then face the same bars on fresh bands.

## ADDENDUM — CORRECTION (2026-09-11): the SW slip is not mainly seed cash

The check addendum above explains the day-11/12 SW purchase as strawberry seed spending
competing with SW's $2,500. A follow-up diagnosis (dev seeds 779000-779003; records
`eval/recon/2026-09-11-leader-tape-sw-timing-*-779000.json`, instrument
`tools/recon-scripts/sw_timing_instrument.py`) shows that explanation is at most partial,
and the dominant mechanism is a different one. The verdict does not change: slice 1 stays
NOT LAUNCHED on C3 and C2, with bands 872000-874000 retired unused.

- **Cash is the later-binding condition**, not the animals precondition — by 2-3 days for
  the shipped agent and on 3 of 4 seeds for LTS. But **day 10's shortfall against the $2,500
  gate is $2,150-2,490, larger than the $1,900 LTS diverts into strawberry seed through day
  10**, so zeroing the seed line would not have bought SW on day 10 either.
- **Config levers do not move it.** `strawberry_seed_budget_share` at 0.25 moved the SW day
  by zero days on 4 of 4 seeds. Lowering `sheep_target` to trip the animals precondition
  sooner made SW *later*, because freed cash reaches strawberry before SW in `plan_day`'s
  spend order. No config in a 10-arm sweep landed SW by day 10 with 27 tiles standing on day
  12.
- **The measured driver is what the zone does to wheat.** Standing wheat collapses from day 6
  under LTS — 1-8 tiles against the shipped agent's 8-23 — because `wheat_tiles` subtracts
  the whole reserved strawberry zone, and `_zone_fallthrough_tiles` returns idle zone ground
  to wheat only beyond `2 × strawberry_plant_daily_cap`, which is 22 tiles at cap 11. Wheat
  funds the early economy, so the zone starves the cash that buys SW and the animals, and the
  seed line is a smaller part of the same squeeze.

That formula is pinned by no test today, which is its own defect. A successor slice takes it
as the first lever, on fresh bands ≥ 875000, against these same criteria.
