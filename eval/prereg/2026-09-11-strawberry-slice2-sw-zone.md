# Pre-registration: strawberry slice 2 — put the zone on SW, the land the shipped agent leaves idle

Date: 2026-09-11
Candidate: `champion` with `strawberry_start_day` (merged in #128) and three knobs added by
the build PR linked below:
- `strawberry_frame_quadrants` puts the zone on the named quadrants. With `("SW",)` the
  zone is SW's tiles, locked and so unplantable until SW is bought.
- `strawberry_plant_priority` sets the dispatch priority of strawberry plantings.
- `strawberry_fert_reserve` sizes the fertilizer sell-reserve. `"target"` (today) reserves
  one unit per zone tile; `"planted"` reserves one per standing strawberry plant.
Every default is today's behaviour. The build PR proves that with a money gate against a
frozen copy of `main` (mean_delta 0.0, sd_delta 0.0).
Status: **WITHDRAWN BEFORE LAUNCH** (2026-09-11). The expression check below failed its
fill criterion on the knob's build `2bb444e`: a mean of 16.2 tiles at the end of day 12,
against the registered 18. No run was made, and none will be made under this document.
Its bands (863000/864000/865000) stay unused and are retired; a successor takes fresh
ones. See the addendum at the end.
Authorization: owner decision 2026-09-11 (strawberry rebuild).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

Slice 1 (`eval/prereg/2026-09-11-strawberry-slice1-start-day.md`: NOT ADVANCED) fixed the
funding spiral. Holding strawberry off until day N left the opening provably untouched,
but its best arms gained only about $2k. The pooled deltas were START8_T20 +$2,282 and
START10 +$1,873, with lower bounds of +$492 and +$88.

An exact settled-flow breakdown of the same games shows why
(`eval/recon/2026-09-11-strawberry-revenue-breakdown-855000.json`). Its conservation
residual is 0.0 on all 64 episode-seats, and it reproduces the known banks. Strawberry
itself sells: +$17.6k to +$24.2k of revenue, 101-120 units at $171-209 a unit. The cost
is the land it takes:

| our seat, 8 seeds, vs shipped | START8 | START10 | START8_T20 |
|---|---|---|---|
| strawberry revenue | +$24,245 | +$20,552 | +$17,620 |
| wheat revenue | −$10,271 | −$8,948 | −$7,288 |
| fertilizer sales | −$1,951 | −$1,682 | −$1,359 |
| milk | −$3,078 | −$680 | −$3,143 |
| wool | +$1,305 | +$1,491 | +$3,654 |
| strawberry seeds | −$2,963 | −$2,900 | −$1,975 |

A zone in NW+NE is carved out of wheat's 31 tiles there. At switch-on it reclaims all of
them, but only ~22 are planted with strawberry, so each strawberry tile costs ~$475 of
wheat. The shipped agent, meanwhile, buys SW on day 9-10 and never fills it. Across the
same 8 seeds it holds 19.5-34 empty tiles on every day from 12 to 29, and never has more
than ~3.5 wheat tiles beyond NW+NE's 31 (`eval/recon/2026-09-11-early-cash-ledger-855000.json`).

Moving the zone is not enough on its own. The dispatcher assigns each unit to its nearest
task within a priority tier, so a plain SW zone is almost never planted. A fertilizer
reserve sized to the zone target also withholds stock from sale before any plant exists,
and that delays the SW purchase. Both findings are in the amendment history. The
candidate therefore also plants strawberry one tier ahead of wheat, and reserves
fertilizer only for standing plants.

**Hypothesis:** a strawberry zone on SW, the land the shipped agent leaves idle, captures
most of the strawberry revenue without the wheat displacement, once the zone actually
gets planted.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` |
|---|---|
| SW25_FIX | `{"strawberry_frame_quadrants": ["SW"], "strawberry_tile_target": 25, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 9, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted"}` |

The settings explained:
- `strawberry_start_day = 9` keeps every strawberry path off until the herd is complete
  and SW is about to be bought.
- `strawberry_plant_priority = 2` is one tier more urgent than PLANT WHEAT (3). Tier 2
  already holds in-window watering, fertilizing, animal care, and fertilizer collection,
  so strawberry planting competes with those instead of with other planting.
- `strawberry_fert_reserve = "planted"` reserves nothing until a strawberry plant stands.
- `strawberry_plant_daily_cap = 10` lets the zone be planted between the SW purchase and
  the day-12 plant cutoff.

Melon's zone follows the live unlocked quadrants and takes 3 SW tiles when SW is bought, so
22 SW tiles are available to strawberry.

**Expression check (pre-launch recon; a precondition).** Run
`tools/recon-scripts/early_cash_ledger.py` on the knob's build tree (recorded by SHA) with
the shipped reference plus the arm, on seeds 855000-855007 against `public:sokolovsky-v12`.
Commit the record under `eval/recon/` as
`2026-09-11-strawberry-slice2-expression-check-855000.json`. It passes only if ALL hold:
1. the arm's submitted actions match the shipped arm's **through day 8 on 8/8 seeds**;
2. every strawberry tile planted lies in SW (zero strawberry tile-days in any other
   quadrant);
3. **fill:** the mean number of strawberry tiles standing at the end of day 12 is
   **at least 18** over the 8 seeds.
An arm that fails cannot express the hypothesis, and this document is amended before any
run. With occupancy identical through day 8, the first coupled shop draw is end-of-day 11
at the earliest, so **at most 5/8 draws** are coupled.

- **Screen:** band **863000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **864000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **865000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/`, and none is named by
an earlier registration.

## Decision rule (fixed before launch)

This is slice 1's rule, restated so this document stands alone.

For each arm and each leader *i*, take `mean_delta_i`, `stderr_i`, and
`opponent_mean_delta_i` from the ledger. Pool as the simple mean, with pooled se
`sqrt(sum stderr_i²)/3`; intervals are estimate ± 1.96 × se. The ledger's `passed` field
is not the verdict.

**INVALID** if any of these holds:
- the engine is not 1.32.7;
- a knob is absent;
- the expression check has not passed;
- any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
  `opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate` veto.

A `candidate_degenerate` veto is a result, not an invalidity. The games are deterministic,
so a rerun would reproduce it. That arm does not advance, confirm, or pass the guard.

**SCREEN — an arm ADVANCES** only if all hold at band 863000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 864000 n=128, has:
1. pooled own-bank delta **>= +$4,000**;
2. pooled lower bound **> +$1,000**;
3. a pooled **margin delta** point estimate **> −$2,000**. The margin delta is
   `mean_delta_i − opponent_mean_delta_i`, pooled as a simple mean. It is a guard, not a
   mechanism reading and not an Elo proxy: the ladder scores the calibrated pair as tied
   at a margin delta of +$6,177.

**GUARD** (a no-catastrophe check, not a contested-market test): the confirmed arm's
own-bank delta against `frozen:m3b_live_b6ce655` must have a point estimate
**> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

REPORTED, NOT GATING: per arm at screen, the gap (own bank minus the leader's) and the
margin delta. For the selected arm:
- the settled-flow breakdown by item against the shipped agent
  (`tools/recon-scripts/revenue_breakdown.py`);
- `strawberry_labor.py` internals;
- the SW purchase day;
- strawberry tiles planted by day.

## Registered predictions

- **Expression check:** the arm matches shipped through day 8 on 8/8 seeds (and, with the
  reserve at zero until a plant stands, through the SW purchase). Every strawberry tile
  is in SW, and the zone fills to 18-22 tiles by day 12.
- **The SW purchase returns to its shipped schedule** (day 9-10).
- **SW25_FIX advances**, pooled own-bank delta **+$4k to +$12k**. In the breakdown,
  strawberry revenue lands near slice 1's START8_T20 or START10, and wheat revenue lands
  **within $2k of shipped's**, against −$7k to −$10k for slice 1's arms.
- The main remaining cost is labour. Hands spend days 10-12 planting SW instead of
  replanting wheat and melon in NW+NE.
- If the arm **does not advance**, labour was the binding cost once land was freed. The
  next lever is yield per tile: 5.4-6.5 units against a maximum of 8, from fertilizer
  windows missed with stock in the shed and harvesting at the 4-unit cap.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload
evicts M3b (our best live bot), and that remains an owner decision.

## Amendment history

- **2026-09-11, before merge and before any run.** The first draft registered SW25 and
  SW20: frame SW only, target 25 or 20, cap 10, start day 9. Its expression check had two
  criteria, divergence and location.
  - **First check.** On build 66349c3 both arms passed those criteria but planted only 5.0
    tiles by day 12, identically (record:
    `eval/recon/2026-09-11-strawberry-slice2-sw-zone-first-check-855000.json`).
  - **Diagnosis** (`eval/recon/2026-09-11-strawberry-sw-fill-diagnosis-*`). A turn-by-turn
    trace found two causes. First, the dispatcher gives every idle unit the nearest task
    within a shared priority tier, so nearer NW/NE wheat and melon tasks win until
    evening, and the hour-20 cutoff then deletes the SW plantings. On days 10-12, 606 SW
    planting tasks were generated, 61 claimed, and 3 executed. Second,
    `fert_reserve = strawberry_tile_target` zeroed day-9 fertilizer sales (0 vs 10-12
    units), which delayed the SW purchase a day on 4 of 8 seeds.
  - **Changes.** The candidate now also carries
    `strawberry_plant_priority = 2` and `strawberry_fert_reserve = "planted"`,
    and the expression check gains the fill criterion. SW20 is dropped: melon's live zone
    takes 3 SW tiles, so a 20-tile and a 25-tile target differ by only 2 tiles.

## ADDENDUM — EXPRESSION CHECK FAILED; WITHDRAWN BEFORE LAUNCH (2026-09-11)

Run on the knob's build `2bb444e` (engine 1.32.7, `packages/` clean), seeds 855000-855007
against `public:sokolovsky-v12`. Record:
`eval/recon/2026-09-11-strawberry-slice2-sw-fix-check-855000.json`.

1. Actions match shipped through day 8 on 8/8 seeds: **PASS**. The first divergence falls
   on day 9 or 10, the SW purchase day on each seed.
2. Strawberry only in SW: **PASS** (0 tile-days outside).
3. Fill of at least 18 tiles at the end of day 12: **FAIL**, with a mean of 16.2
   (16, 16, 16, 16, 16, 16, 17, 17).

The fixes did what they were built for: the SW purchase is back on shipped's day on 8/8
seeds, and plantings rose from 5.0 to 16.2 tiles. But the zone stops at 16-17 tiles on
every seed and then shrinks, to 13.9 by day 16, long before any plant reaches its final age
(inferred: plants are dying). On the same 8 seeds the arm's own bank is −$1,840 against
shipped (se $2,495; the leader's is −$6,245), so a passing check would not have pointed at
an advancing arm either.

The criterion is not relaxed after the fact. No run was made, and the bands stay unused.

**What it means (recorded, not a verdict).** Each fix exposed the next constraint: cash in
slice 1, then land in the revenue breakdown, then dispatch in the fill diagnosis, and now
labour. The zone plants, loses tiles, and the arm banks less than shipped. The knobs remain
in the code as default-off instruments.
