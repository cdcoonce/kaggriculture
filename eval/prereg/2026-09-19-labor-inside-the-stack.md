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

## ADDENDUM — SCREEN VERDICT (2026-09-19): NOT ADVANCED, and the reference arm did not replicate

Run at `main` = `6d49bd4`, whose `packages/` and `dist/` are byte-identical to the registered
build `c43d8ed` (the two intervening commits are this document and the check's tooling).
Engine 1.32.7, band 888000, n = 64 per leader, clean tree. The six ledgers are
`eval/gates/2026-09-19T17-06-21Z` through `…T17-21-35Z-*-money.json`, with no crash and no
veto.

| arm | Sokolovsky | rayk | kaito | pooled Δ (se) | 95% CI | margin Δ | verdict |
|---|---|---|---|---|---|---|---|
| S3 | −$1,606 | −$846 | −$1,155 | −$1,203 ($1,119) | [−$3,395, +$990] | +$457 | NOT ADVANCED (fails 1, 2) |
| S3EH1 | +$641 | −$356 | −$47 | +$79 ($1,088) | [−$2,054, +$2,212] | −$343 | NOT ADVANCED (fails 1, 2) |

Neither arm advances. There is no confirmation run, no guard run, and no upload decision.
**Labor-inside-the-stack is NOT ADVANCED.**

**The headline is the replication failure, not the arm.** STACK3 measured **+$3,637**
(se $1,174) at band 881000. `S3` is that configuration verbatim — verified byte-identical
against `ALL_ARMS["STACK3"]` before launch — and at band 888000 it measures **−$1,203**. The
gap is **−$4,840**, more than four pooled se. This is not a small band effect.

That reinterprets the result which motivated this slice. "+$3,637, short by $363" reads as a
near-miss that one more idea could close; the same arm at a fresh band is negative. The
near-miss was substantially band luck.

This registration predicted the symmetric case and the logic is identical: "a NOT ADVANCED arm
re-measured at a fresh band clearing a bar it previously missed would itself be evidence the
instrument is noisier than the pooled se implies, and would be reported." It landed in the
other direction. It is reported.

**The instrument cannot resolve its own bar.** Every run in this screen reported `mde_80`
between **$4,525 and $5,137** — the minimum effect detectable at 80% power is larger than the
+$4,000 bar those runs are scored against. At n=64 per leader this design cannot reliably
detect the effect it is asked to detect. That is the plausible common cause of both the
replication gap here and the thinness of the prior closures, and it bears on every slice
measured this way, not only this one.

**The mechanism is real and too small.** The within-band contrast, which this slice was
designed to isolate, is **S3EH1 − S3 = +$1,282** pooled, positive at all three leaders. The
expression check's reading holds up: the hand is bought (hire spend +$1,942), strawberry holds
(16.0 → 16.4 tiles at day 12), and collateral rises rather than falls (+$5,429). The hand does
what the hypothesis said it would. It is worth about a fifth of the bar.

**Predictions scorecard.**
- Criterion 2 was named as the likely failure at P=0.55 and **passed** (+$1,942 against
  +$1,500). The call to single it out was right; the outcome fell on the favourable side.
- The prediction "both arms pass the expression check on criteria 1 and 3" was
  mis-specified: S3 is the reference arm and is not scored against the criteria. Only S3EH1
  is scored. Recorded as an error in the registration, not reinterpreted.
- **S3 was predicted to replicate at +$2,000 to +$5,000 and landed at −$1,203**, far outside
  the range. This is the largest prediction miss the project has recorded.
- S3EH1 was predicted at −$1,000 to +$5,500 and landed at +$79, inside the range at its low
  end.
- P(S3EH1 advances) was 20%; it did not advance. P(S3 advances) was 15%; it did not.

**What it means (recorded, not a verdict).** The prereg said that if neither arm advanced,
"the labor+strawberry interaction is closed by measurement alongside both main effects." That
claim is now weaker than it was written. The interaction's point estimate is positive
(+$1,282) and small, but an instrument whose `mde_80` exceeds its bar cannot close a +$4,000
question by failing to find one. What is established is narrower: the interaction is real,
directionally positive, and not large enough to be worth an eviction — and the prior NOT
ADVANCED verdicts are weaker evidence of absence than their intervals suggest.

The consequence for the 2026-09-28 freeze is that shipping the existing pair is now the
evidence-backed choice rather than the fallback. A new upload evicts M3b for a candidate whose
best measured contribution is +$1,282, measured on an instrument that has just failed to
reproduce its own headline result. That remains an owner decision.
