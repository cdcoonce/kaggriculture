# Pre-registration: the paying hand inside the stack

Date: 2026-09-19
Candidate: `champion` with shipped knobs only. **No new agent code**: every knob here has
already shipped and already been gated, so each arm is an `--agent-config` override and the
build under test is `main` itself (`c43d8ed`).
Status: REGISTERED — runs launch only after (1) this document has merged and (2) the
expression check below has passed. The runner asserts engine 1.32.7, that `PolicyConfig`
carries every arm's knob at its shipped default, and that the band is unused.
Authorization: owner decision 2026-09-19 (pursue the joint labor+strawberry arm), taken after
ten slices closed without an advance.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

Every strawberry arm this project has measured shows one signature, and it is not a price
problem. From `eval/recon/2026-09-12-strawberry-price-elasticity-858100.json` (band 858100,
8 seeds, `public:sokolovsky-v12`), our seat:

| arm | units sold | realized price | STRAWBERRY | WHEAT | WOOL | FERTILIZER | MILK | HIRE spend | net |
|---|---|---|---|---|---|---|---|---|---|
| T20 | 102.4 | $120.77 | +$12,364 | −$7,700 | −$2,758 | −$1,390 | +$1,201 | **−$34** | **−$269** |
| COH | 125.0 | $144.94 | +$18,118 | −$14,095 | −$5,744 | −$3,242 | −$3,142 | **−$258** | **−$8,705** |

Our realized price at COH ($144.94) is within 4% of the leader's ($150.74), so we are not
dumping into a saturated market. The leader simply moves **277.6 units to our 125**. And in
both arms **hire spend does not rise** — the agent handed strawberry work does not hire, it
reallocates a crew that labor slice 1 already measured as saturated (idle share ~4.7%,
executing ~200 of the ~410 wheat plantings its own quota intends,
`eval/prereg/2026-09-11-labor-slice1-wheat-planting.md`). The leader spends **$7,155** on
HIRE against our **$3,144**.

That is displacement under a fixed labor budget, measured directly rather than inferred.

**Hypothesis:** strawberry's collateral cost is a labor-supply artefact. Given one more hand
— specifically the hand already measured to pay for itself — the marginal unit of crew time
has $145/unit strawberry work available instead of the marginal wheat and weeding that labor
slice 2 priced at less than its cost. The stack then clears +$4,000.

**The reason to doubt it, on record, stated before launch.** Labor slice 2
(`eval/prereg/2026-09-11-labor-slice2-extra-hands.md`, NOT ADVANCED) screened the supply
lever alone at band 869000, n=64/leader:

| arm | pooled Δ | 95% CI | margin Δ | verdict |
|---|---|---|---|---|
| EH1 | +$340 | [−$1,623, +$2,302] | −$4,897 | NOT ADVANCED |
| EH2 | −$3,545 | [−$5,776, −$1,314] | −$6,674 | NOT ADVANCED |
| EH2_H10 | −$3,586 | [−$5,622, −$1,550] | −$4,984 | NOT ADVANCED |

Its recorded conclusion is blunt: "the work the hands bought is worth less than the hands
cost", and "the labor line's levers are exhausted at these margins." `EH2_H10` is this
slice's labor configuration at **two** hands, and it measured significantly negative.

Two things separate this registration from a re-run of that arm, and both were fixed before
any data here exists:

1. **It is the 11th hand, not the 12th.** Slice 2 priced them separately: the 11th costs
   about $2.6k and roughly pays for itself (EH1, +$340); the 12th costs about $4.2k and does
   not. `EH2`/`EH2_H10` bought both. This slice buys one.
2. **Slice 2 measured those hands with strawberry OFF** (`strawberry_tile_target` 0), so the
   marginal hand had only wheat and weeding to do — exactly the work slice 2 then priced as
   worth less than its cost. Whether a hand is worth buying when high-value strawberry work
   exists is the interaction cell no slice has run.

**This is an interaction claim, and interactions have burned this project before.** The one
factorial on record (`eval/prereg/2026-09-07-elo-aligned-factorial.md`) found two positive
knobs combining to less than the better singleton: additive +868 Elo predicted, +349
observed, interaction −518. The prior here is not favourable.

**On the bar.** STACK3 (`eval/prereg/2026-09-12-stack-measured-positives.md`) measured
+$3,637 [+$1,336, +$5,939] and was NOT ADVANCED, failing the +$4,000 bar by $363. This
registration keeps that bar unchanged at +$4,000. The resemblance between that shortfall and
the interaction this arm needs is noted here deliberately: it is a reason for suspicion of
the result, not a reason to move the threshold. No arm here is scored against a bar it did
not face before launch.

## Registered arms

- **S3** (replication reference): `{"strawberry_tile_target": 20, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8, "animal_buy_order": ["SHEEP","COW"], "max_hires_per_turn": 10}`
- **S3EH1**: `{"strawberry_tile_target": 20, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8, "animal_buy_order": ["SHEEP","COW"], "max_hires_per_turn": 10, "extra_hands": 1}`

S3 is STACK3 exactly. It is re-run here rather than cited across bands so the extra hand's
contribution is a within-band paired contrast; STACK3's +$3,637 was measured at band 881000
and is not comparable seed-for-seed to anything measured at 888000.

`extra_hands: 2` is excluded: measured at −$3,545 alone and −$3,586 with the raised cap.
`rescue_water` is excluded: its own check measured wheat settled revenue falling about 30%,
and the COH arm that carried it is the worst result in the table above.

## Expression check (pre-launch recon; a precondition)

Run `tools/recon-scripts/early_cash_ledger.py` and `tools/recon-scripts/revenue_breakdown.py`
on the build's tree (recorded by SHA), reference first and then every arm, on seeds
**887000-887007** against `public:sokolovsky-v12`. Commit the records under
`eval/recon/2026-09-19-labor-in-stack-expression-*-887000.json`.

The criteria are fixed here, before any arm data exists. The point of this check is that the
hand is actually **bought** and actually **works strawberry** — the failure this slice is
built to detect is a hand that is hired and then spends its hours on the same marginal wheat
slice 2 already priced:

1. **The hand is bought:** S3EH1 mean crew hours over days 4-20 >= S3 + 0.7. Slice 2 measured
   each extra hand adding about one unit of crew (shipped 9.9 -> EH1 10.9); 0.7 allows for
   the raised cap already pulling some crew forward in S3.
2. **Hire spend rises:** S3EH1 mean HIRE spend > S3 by >= $1,500. The whole diagnosis is that
   hire spend does not move; an arm where it still does not move has not tested the
   hypothesis. Anchored on slice 2's ~$2.6k cost for the 11th hand, discounted for overlap.
3. **Strawberry still fires:** S3EH1 mean standing strawberry tiles at end of day 12 >= 14.0,
   and within 15% of S3's. STACK3's own check measured 16.1. A hand that buys strawberry
   tile-days by abandoning the zone is not the mechanism claimed.
4. **No collateral collapse:** S3EH1 WHEAT + WOOL + FERTILIZER settled revenue >= S3's
   less 5%. The hypothesis is that the hand *reduces* displacement; an arm that deepens it
   has falsified its own mechanism before the screen.

An arm clears only if all four pass. A failing arm is dropped and does not reach the screen.

## Registered design

Gate: `harness.money_gate`, candidate `champion` with the arm's config against baseline
`champion` **at shipped defaults**, against each of `public:sokolovsky-v12`,
`public:rayk-v11`, `public:kaito-v4`.

- **Screen:** band **888000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **889000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655`, band **890000**, n = 64.

All four bands (887000, 888000, 889000, 890000) are verified unused by every ledger in
`eval/gates/`, claimed by no earlier registration, and referenced by no file in the repo.

## Decision rule (fixed before launch)

Identical to the ten prior slices, restated so this document stands alone.

Per arm and leader *i*, take `mean_delta_i`, `stderr_i` and `opponent_mean_delta_i` from the
ledger; pool as the simple mean with pooled se `sqrt(sum stderr_i²)/3`; intervals are
estimate ± 1.96 × se. The ledger's `passed` field is not the verdict.

**INVALID** if the engine is not 1.32.7, a knob is absent, the expression check has not
passed, or any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
`opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate` veto. A
`candidate_degenerate` veto is a result, not an invalidity.

**SCREEN — an arm ADVANCES** only if, at band 888000: pooled own-bank delta **>= +$4,000**;
pooled 95% lower bound **> $0**; and no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 889000 n=128, has pooled delta
**>= +$4,000**, pooled lower bound **> +$1,000**, and a pooled **margin delta**
(`mean_delta_i − opponent_mean_delta_i`, simple mean) **> −$2,000**.

**GUARD:** the confirmed arm's own-bank delta against `frozen:m3b_live_b6ce655` must have a
point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

REPORTED, NOT GATING: per arm, the gap and the margin delta; for the selected arm, the
settled-flow breakdown by item including HIRE spend against shipped, standing strawberry by
day, and the S3EH1−S3 within-band contrast that isolates the hand.

## Registered predictions

- **Both arms pass the expression check on criteria 1 and 3.** Slice 2 measured the hand
  arriving and STACK3 measured the zone filling; neither is in doubt.
- **Criterion 2 is the one that may fail.** Hire spend not moving is the diagnosis itself, and
  nothing in the agent explicitly couples strawberry demand to the hiring line. I put
  P(criterion 2 passes) at 55%.
- **S3 replicates STACK3 within its interval**, landing +$2,000 to +$5,000 at band 888000.
- **S3EH1 lands −$1,000 to +$5,500**, wider than S3 in both directions: the hand costs a known
  ~$2.6k and its strawberry value is unmeasured.
- **P(S3EH1 advances) 20%.** Below the 25% the stack registration gave itself. The
  interaction precedent is negative, the labor line is closed by its own measurement, and the
  effect needed is precisely the size of the gap the predecessor missed by — which is as much
  a warning as a target.
- **P(S3 advances on replication alone) 15%**, entirely from band variation; a NOT ADVANCED
  arm re-measured at a fresh band clearing a bar it previously missed would itself be
  evidence the instrument is noisier than the pooled se implies, and would be reported.
- **If neither arm advances**, the labor+strawberry interaction is closed by measurement
  alongside both main effects, and the remaining option before the 2026-09-28 freeze is to
  ship the existing pair. That is an owner decision, not a further slice.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot, `sub-55784368`, `b6ce655`), and that remains an owner decision.
Nothing in this document authorises an upload.

## Amendment history

- (this commit) full registration: arms, criteria, bands, rule and predictions, committed
  before the expression check runs. Criterion 1's threshold is anchored on labor slice 2's
  measured crew-hour rise (9.9 -> 10.9) and criterion 3's on STACK3's measured fill (16.1),
  not on any measurement of these arms, which have never been run.
