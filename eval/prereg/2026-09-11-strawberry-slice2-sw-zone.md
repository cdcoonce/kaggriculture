# Pre-registration: strawberry slice 2 — put the zone on SW, the land the shipped agent leaves idle

Date: 2026-09-11
Candidate: `champion` with two knobs, `strawberry_start_day` (merged in #128) and the new
`strawberry_frame_quadrants` (build PR linked below). With
`strawberry_frame_quadrants = ("SW",)` the zone is SW's tiles only, and they are locked,
so unplantable, until SW is bought. The default `("NW","NE")` is today's behaviour. The
build PR proves that with a money gate against a frozen copy of `main` (mean_delta 0.0,
sd_delta 0.0).
Status: REGISTERED — runs launch only after (1) this document and the knob's build PR
have merged and (2) the expression check below has passed. The runner asserts engine
1.32.7 and that `PolicyConfig` has both knobs.
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
itself sells: +$17.6k to +$24.2k of revenue, 101-120 units at $171-209 a unit. The
cost is the land it takes:

| our seat, 8 seeds, vs shipped | START8 | START10 | START8_T20 |
|---|---|---|---|
| strawberry revenue | +$24,245 | +$20,552 | +$17,620 |
| wheat revenue | −$10,271 | −$8,948 | −$7,288 |
| fertilizer sales | −$1,951 | −$1,682 | −$1,359 |
| milk | −$3,078 | −$680 | −$3,143 |
| wool | +$1,305 | +$1,491 | +$3,654 |
| strawberry seeds | −$2,963 | −$2,900 | −$1,975 |

A zone in NW+NE is carved out of wheat's 31 tiles there. At switch-on it reclaims all
of them, but only ~22 are planted with strawberry, so each strawberry tile costs ~$475
of wheat. The shipped agent, meanwhile, buys SW on day 9-10 and never fills it. Across
the same 8 seeds it holds 19.5-34 empty tiles on every day from 12 to 29, and never has
more than ~3.5 wheat tiles beyond NW+NE's 31, on days 16-19 and 23-26
(`eval/recon/2026-09-11-early-cash-ledger-855000.json`).

**Hypothesis:** a strawberry zone on SW captures most of the strawberry revenue without
the wheat displacement, because it occupies land the shipped agent leaves idle.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion`
at shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` | purpose |
|---|---|---|
| SW25 | `{"strawberry_frame_quadrants": ["SW"], "strawberry_tile_target": 25, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 9}` | primary: all of SW |
| SW20 | same, `"strawberry_tile_target": 20` | smaller: draws less seed cash, labour and fertilizer |

`strawberry_start_day = 9` keeps every strawberry path off until the herd is complete and
SW is about to be bought. That includes the fertilizer sell-reserve
(`fert_reserve = strawberry_tile_target`), which would otherwise withhold stock from sale
from turn 0 while the SW zone is still locked. `strawberry_plant_daily_cap` is 10 so a
funded zone can be planted between the SW purchase and the day-12 plant cutoff.

**Expression check (pre-launch recon; a precondition).** Run
`tools/recon-scripts/early_cash_ledger.py` on the knob's build tree (recorded by SHA) with
the shipped reference plus every arm, on seeds 855000-855007 against
`public:sokolovsky-v12`. Commit the record under `eval/recon/`. It passes only if both hold:
- every arm's submitted actions match the shipped arm's **through day 8 on 8/8 seeds**;
- every strawberry tile planted lies in SW.
An arm that fails cannot express the hypothesis, and this document is amended before any
run. With occupancy identical through day 8, the first coupled shop draw is end-of-day 11
at the earliest (draw-days 2/5/8/11/…), so **at most 5/8 draws** are coupled.

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

A `candidate_degenerate` veto is a result, not an invalidity. The games are
deterministic, so a rerun would reproduce it. That arm does not advance, confirm, or pass
the guard.

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

- **Expression check:** every arm matches shipped through day 8 on 8/8 seeds, and every
  strawberry tile is in SW.
- **SW25 advances**, pooled own-bank delta **+$5k to +$12k**. In the breakdown, wheat
  revenue lands **within $2k of shipped's**, against −$7k to −$10k for slice 1's arms, and
  strawberry revenue lands near slice 1's START10.
- **The SW purchase stays on its shipped schedule** (day 9-10), because the seed line has
  no plantable zone tile before SW is owned.
- **The zone reaches 18-25 planted tiles by day 12.** Seed cash on days 10-11, right after
  the $2,000 land purchase, is the binding constraint.
- **SW20 advances, below SW25's point estimate.**
- If **no arm advances**, land was not the binding cost once freed. The next suspects are
  labour (walking is already 58% of unit-turns) and yield per tile: 5.4-6.5 units against a
  maximum of 8, from fertilizer windows missed with stock in the shed and harvesting at
  the 4-unit cap.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload
evicts M3b (our best live bot), and that remains an owner decision.
