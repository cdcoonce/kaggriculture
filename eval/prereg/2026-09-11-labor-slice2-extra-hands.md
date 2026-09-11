# Pre-registration: labor slice 2 — buy labor instead of moving it

Date: 2026-09-11
Candidate: `champion` with the new `extra_hands` knob (build PR linked below; default 0 is
today's behaviour, and the build PR proves that with a money gate against a frozen copy of
`main`, mean_delta 0.0 and sd_delta 0.0). One arm also uses `max_hires_per_turn`, merged in
#132.
Status: REGISTERED — runs launch only after (1) this document and the build PR have merged
and (2) the expression check below has passed. The runner asserts engine 1.32.7, that
`PolicyConfig` has every knob at its shipped default, and that `main`'s `packages/` and
`dist/` equal the expression-checked build.
Authorization: owner decision 2026-09-11 (labor-efficiency pivot).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

Labor slice 1 (`eval/prereg/2026-09-11-labor-slice1-wheat-planting.md`: NOT ADVANCED) found
three things:
- **The crew is saturated.** The shipped agent's idle share is ~4.7%, and it executes ~200
  of the ~410 wheat plantings its own quota intends.
- **Moving labor toward planting starves watering.** A higher planting tier, a later
  planting cutoff, and both combined raised weeds 1.8-3.2x. The expression check's
  guardrail caught it.
- **Adding labor earlier helps, a little.** With `max_hires_per_turn = 10` the crew arrives
  an hour sooner, weeds fall (44 vs 58 tile-days), and the arm nets +$781 (se $1,028).
  That is about $18 per extra hand-hour, on ~44 extra morning hand-hours a game.

One extra hand all game is roughly 580 hand-hours. Its hire cost rises with the day's hire
count, on the engine's Fibonacci schedule. The labor diagnosis puts that at about $2k a
game for one extra hand and $4.7k for two (`eval/recon/2026-09-11-labor-diagnosis-*`).
Extra afternoon hours are probably worth less than the morning hours H10 bought, but even
a fraction of that rate would clear the hire cost.

**Hypothesis:** the planting and weeding backlog is labor-bound, so buying more hands, rather
than re-ranking the existing crew, plants and tends more and banks more than the hires cost.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

| arm | `--agent-config` | purpose |
|---|---|---|
| EH1 | `{"extra_hands": 1}` | one hand above the tile-based target |
| EH2 | `{"extra_hands": 2}` | two hands, the second one costlier |
| EH2_H10 | `{"extra_hands": 2, "max_hires_per_turn": 10}` | two hands, arriving an hour sooner |

**Expression check (pre-launch recon; a precondition).** Run
`tools/recon-scripts/labor_probe.py --check` on the build's tree (recorded by SHA) with the
shipped reference plus every arm, on seeds 855000-855007 against `public:sokolovsky-v12`.
Commit the record as `eval/recon/2026-09-11-labor-slice2-expression-check-855000.json`. An
arm passes only if every criterion that applies to it holds. These criteria were written
and committed before any probe of the new knob returned data.
1. **Crew, EH1:** the mean units on the farm over hours 4-20 (days 1-29, all 8 seeds)
   exceed shipped's by at least **0.7**.
2. **Crew, EH2 and EH2_H10:** the same measure exceeds shipped's by at least **1.4**. The
   0.7-per-hand allowance covers hires the 10-order market cap drops on busy turns.
3. **Ramp, EH2_H10:** the mean units over hours 1 and 2 exceed shipped's by at least
   **1.0**, as in slice 1.
4. **Guardrail, every arm:** mean weed tile-days no more than **1.5 × shipped's**.
An arm that fails cannot express the hypothesis, and this document is amended before any
run. Every arm changes behaviour from the first day, so the shop-roster coupling can reach
all 8 draws (`eval/README.md`, pairing limitation). That is why confirmation runs at n=128.

- **Screen:** band **869000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **870000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **871000**, n = 64.

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

**SCREEN — an arm ADVANCES** only if all hold at band 869000:
1. pooled own-bank delta **>= +$4,000** (about +40 Elo on the ladder-derived slope);
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 870000 n=128, has:
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
- the settled-flow breakdown by item, including hire spend, against the shipped agent
  (`tools/recon-scripts/revenue_breakdown.py`);
- units on the farm by hour;
- wheat plantings;
- weed tile-days.

## Registered predictions

- **Expression check:**
  - each arm raises the hours 4-20 crew by roughly its extra hands (EH1 +0.8 to +1.0; EH2
    and EH2_H10 +1.6 to +2.0);
  - EH2_H10 also passes the ramp criterion;
  - weeds fall below shipped's in every arm.
- **EH1 lands below the bar**, +$1k to +$4k: one hand's extra work is worth a few thousand,
  and it costs about $2k.
- **EH2 lands near the bar**, +$2k to +$6k: the second hand is costlier.
- **EH2_H10 has the highest point estimate** and is the likeliest to advance, at +$3k to
  +$8k.
- If **no arm advances**, extra labor is worth less than it costs at these margins. The next
  suspects are pure waste: the midnight orphaning (25% of move-steps) and dispatch churn.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot), and that remains an owner decision.

## ADDENDUM — EXPRESSION CHECK (2026-09-11): all three arms PASS

Run on the build `f0b92d7` (engine 1.32.7, `packages/` clean), seeds 855000-855007 against
`public:sokolovsky-v12`. The criteria were committed beforehand, in 3e1ed9b. Record:
`eval/recon/2026-09-11-labor-slice2-expression-check-855000.json`.

| arm | crew hours 4-20 | hour 1-2 crew | wheat plantings | weed tile-days | verdict |
|---|---|---|---|---|---|
| shipped | 9.9 | 6.6 | 195.2 | 58.1 | reference |
| EH1 | 10.9 (needs >= 10.6) | 6.9 | 215.5 | 37.0 | **PASS** |
| EH2 | 11.9 (needs >= 11.3) | 7.0 | 227.8 | 29.1 | **PASS** |
| EH2_H10 | 11.9 (needs >= 11.3) | 9.6 (needs >= 7.6) | 232.1 | 32.1 | **PASS** |

Each extra hand adds about one unit to the crew. Wheat plantings rise 10-19% and weeds fall
36-50%, so this is the first labor lever that adds work without starving something else.
All three arms go to the screen at band 869000. The record's bank numbers (8 seeds, one
leader, one shared baseline) are recon, not a result, and play no part here.
