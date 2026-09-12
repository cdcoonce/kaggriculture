# Pre-registration: price the surviving strawberry cohort

Date: 2026-09-12
Candidate: `champion` with the strawberry-cohort knobs. **No new agent code**: every knob
here shipped by 2026-09-11 (#128, #130, #140), so each arm is an `--agent-config` override
and the build under test is `main` itself.
Status: REGISTERED — runs launch only after (1) this document has merged and (2) the
expression check below has passed. The runner asserts engine 1.32.7, that `PolicyConfig`
carries every arm's knob at its shipped default, and that the band is unused.
Authorization: owner decision 2026-09-11 (leader-style rebuild, own code). This is a
successor inside that line, not a new one.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why this is a new question and not a relitigation

`eval/prereg/2026-09-11-leader-tape-slice1.md` was NOT LAUNCHED because no arm cleared a
**leader-likeness** bar: 27 standing strawberry tiles on day 12, which is 75% of the
leaders' 36. Its arms reached 23.5-25.5 and the verdict stands.

But that slice never asked what those arms are worth, and **no money gate has ever priced a
surviving cohort of that size**:

| measurement | cohort | fate |
|---|---|---|
| strawberry slice 1 (gated, n=64) | 15-22 tiles, planted from day 8, with deaths | best arm +$2,282, NOT ADVANCED |
| strawberry slice 2 (withdrawn) | 16.2 of 22, decaying to 13.9 by day 16 | never gated |
| the 2026-08-29 31-tile build | 31 tiles, no rescue watering, pre-frame/priority fixes | banked far less than shipped |
| **leader-tape arms (2026-09-11)** | **23.5-25.5 tiles, ~100% survival to day 16** | **never gated** |

**The prior closures are stronger than that table alone suggests, and they belong here.**
`docs/recon/occupancy.md` records that strawberry sized as a satellite on a labor-saturated
farm is "strictly negative -- it takes crew away from wheat and gives back less, and the
zone never fills (peak 13 of 16)".
`eval/prereg/2026-08-28-fallthrough-production-vs-price.md` concludes "every strawberry arm
is catastrophically worse than the shipped agent. The strawberry line is closed", and
`eval/prereg/2026-09-06-strawberry-replacement-screen.md` closes "the strawberry thesis in
both its forms". Those are real verdicts against this crop, and this slice does not get to
ignore them.

**But `occupancy.md` draws the distinction itself, and it was written before today.**
Immediately after the sentence quoted above, under the heading "Why every strawberry arm
measured dead", it says the strong opponent "does not run strawberry as a satellite. It runs
it as ~45% of the farm, **replacing** wheat rather than supplementing it, which lowers total
labor demand per tile-day held instead of raising it", and concludes: "That is a different
intervention from anything screened so far, and the existing negative results do not bear on
it." Every closure above measured the satellite form — tiles added on top of a full wheat
rush. **The arms below are the replacement form**: wheat collapses to 1-4 standing tiles
while strawberry takes 24-25. So the prior negatives are evidence about a different
intervention, by our own recon's reckoning.

What distinguishes this hypothesis from every one of them is also a measured fact rather
than an argument: **the cohort now fills and survives.** Each closure above was measured on a zone
that never filled (peak 13-14 of 16), or on a 31-tile build whose plants died, or on a
satellite bolted onto a full wheat rush. The arms below stand at 23.5-25.5 tiles on day 12
and are still standing on day 16. If the crop is genuinely unprofitable at our labor level,
this slice is where that gets measured on a cohort that actually exists, instead of one that
never grew.

Three things landed on 2026-09-11 that none of the earlier gated arms had: planting ahead of
wheat (`strawberry_plant_priority`), a fertilizer reserve counted on planted tiles rather
than the target (`strawberry_fert_reserve`), and rescue watering (`rescue_water`), which took
missed-water deaths from about 28 a game to about 1. The expression check measured the
result: a cohort that fills by day 12 and is still standing on day 16, which no gated arm
has ever had.

The sizes at stake are large in both directions. Strawberry sells at $171-209 a unit, and a
24-tile cohort yielding 5.4-6.5 units a tile is roughly $22-33k of revenue. Against that,
the 31-tile zone measured wheat down $7.3-10.3k, seed spend up $2-3k, and the leader-tape
probes measured the SW land purchase slipping to day 11-12. Dev-seed recon spans **−$18k to
+$20k across two different 4-seed sets**, which is exactly the situation an n=64 screen
exists to resolve.

**Hypothesis:** a strawberry cohort of at least 20 tiles that survives to day 16 banks more
against the leaders than the shipped wheat farm.

## Registered arms

Each arm is one of the leader-tape arms, unchanged, because those are the configurations
whose cohort has been measured:

- **COH**: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "strawberry_seed_budget_share": 1.0, "rescue_water": true}`
- **COH_HALF**: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "rescue_water": true}`
- **COH_OPEN**: `{"strawberry_tile_target": 36, "strawberry_frame_quadrants": ["NW","NE","SW"], "strawberry_start_day": 3, "strawberry_plant_daily_cap": 11, "strawberry_plant_priority": 2, "strawberry_fert_reserve": "planted", "strawberry_seed_budget_share": 1.0, "rescue_water": true, "ne_land_min_day": 6, "animal_buy_order": ["SHEEP","COW"], "goose_min_day": 7}`

## Expression check (pre-launch recon; a precondition)

Run `tools/recon-scripts/early_cash_ledger.py` and `tools/recon-scripts/weed_provenance.py`
on the build's tree, reference `{}` first and then every arm, on seeds **856000-856007**
against `public:sokolovsky-v12` — **fresh seeds**, not the 855000-855007 set whose numbers
are quoted above. Then `tools/recon-scripts/leader_tape_check.py LEDGER --weeds SCAN`
reports the measurements, and the criteria below are evaluated from its record.

1. **Cohort exists and survives (positive mechanism):** mean standing strawberry tiles at
   the end of day 16 >= **20**, and >= **0.9 ×** the day-12 mean.
2. **Watering guardrail:** mean plant deaths from missed watering <= **1.5 ×** shipped's, by
   the engine's two-unwatered-days rule, as in the leader-tape slice.
3. **Mechanism-matched collateral guardrail:** combined **WHEAT + STRAWBERRY** settled
   revenue rises by at least **10%** against shipped, measured by
   `tools/recon-scripts/revenue_breakdown.py`. A per-item wheat guardrail would veto this
   slice by construction, because trading wheat land for strawberry land **is** the
   mechanism; the sum is the honest form of the same question.

**Disclosure on criterion 1, in full.** I chose the number 20 already knowing these arms
measure 23.5-25.5 on the 855000-855007 seeds. It is anchored on the prior *gated* arms,
which held 15-22 tiles planted late and dying, so a cohort of 20 standing on day 16 is
materially different from anything a money gate has already priced. It is a definition of
the hypothesis, not a leader-likeness test — the leader-likeness bar is what the previous
slice failed, and that verdict stands untouched. Nothing advances on criterion 1: the money
rule below is the only thing that decides.

An arm failing a criterion is dropped before any run. If none passes, this document is
amended by building, never by relaxing a criterion.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

- **Screen:** band **878000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **879000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655`, band **880000**, n = 64.

Bands verified unused by every ledger in `eval/gates/` and claimed by no earlier
registration.

## Decision rule (fixed before launch)

Identical to the four prior slices, restated so this document stands alone.

Per arm and leader *i*, take `mean_delta_i`, `stderr_i` and `opponent_mean_delta_i` from the
ledger; pool as the simple mean with pooled se `sqrt(sum stderr_i²)/3`; intervals are
estimate ± 1.96 × se. The ledger's `passed` field is not the verdict.

**INVALID** if the engine is not 1.32.7, a knob is absent, the expression check has not
passed, or any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
`opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate` veto. A
`candidate_degenerate` veto is a result, not an invalidity: the games are deterministic, so
that arm simply does not advance, confirm, or pass the guard.

**SCREEN — an arm ADVANCES** only if, at band 878000: pooled own-bank delta **>= +$4,000**;
pooled 95% lower bound **> $0**; and no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 879000 n=128, has pooled delta
**>= +$4,000**, pooled lower bound **> +$1,000**, and a pooled **margin delta**
(`mean_delta_i − opponent_mean_delta_i`, simple mean) **> −$2,000**.

**GUARD:** the confirmed arm's own-bank delta against `frozen:m3b_live_b6ce655` must have a
point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

REPORTED, NOT GATING: per arm, the gap and the margin delta; for the selected arm, the
settled-flow breakdown by item against shipped, the realized strawberry price per unit, and
standing strawberry by quadrant and day.

## Registered predictions

- All three arms pass the expression check: the cohort and its survival are already
  measured, and rescue watering holds deaths near 1 a game.
- **The screen resolves a question the dev seeds could not.** Recon spans −$18k to +$20k
  across two 4-seed sets; at n=64 per leader the pooled se has been about $1,000 in every
  prior slice, so this measures the sign at last.
- **COH_HALF has the highest point estimate**, −$1k to +$6k: it keeps early cash for the
  herd and buys SW a day sooner than COH.
- **COH_OPEN lands lowest**, −$10k to +$2k: delaying NE costs our wheat economy more than
  the leaders' herd start returns.
- **P(any arm advances) about 25%.** That number moved twice while this document was
  drafted and the reasoning is recorded rather than tidied away: 30% first, cut to 20% after
  re-reading the three closures cited above, then settled at 25% once `occupancy.md`'s own
  satellite-versus-replacement distinction was verified — those closures measured the
  satellite form, and these arms are the replacement form the same file calls untested.
  Against that: the dev-seed recon for these very arms ran −$8.4k to −$18.0k on the more
  recent of its two 4-seed sets, the strawberry offsets are real (wheat displacement, seed
  spend, an SW purchase slipping to day 11-12, a labor budget rescue watering now also draws
  on), and three registrations have closed this crop before. The case for running it is not
  that it will win; it is that a filled, surviving, wheat-replacing cohort has never been
  priced, and five slices have failed to settle it.
- If no arm advances, the strawberry line is closed by measurement rather than by a
  mechanism bar, which is what five slices have failed to settle.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b, and that remains an owner decision.

## Amendment history

- (this commit) full registration: arms, criteria, bands and predictions, committed before
  the expression check runs on its own fresh seeds. Criterion 1's threshold was chosen with
  knowledge of the arms' measured fill on other seeds, and that is disclosed above rather
  than presented as independent.

## ADDENDUM — EXPRESSION CHECK (2026-09-12): all three arms pass

Run on `047420e`, engine 1.32.7, seeds 856000-856007 against
`public:sokolovsky-v12` — the fresh seeds this document registered, not the set whose
numbers set criterion 1's threshold. The weed scan left none of its births unexplained.
Records: `eval/recon/2026-09-12-strawberry-cohort-expression-{ledger,weeds,flows,check}-856000.json`.

| arm | standing d12 | standing d16 | missed-water deaths | WHEAT | STRAWBERRY | W+S | recon bank |
|---|---|---|---|---|---|---|---|
| shipped | 0.0 | 0.0 | 14.4 | 18,712 | 0 | 18,712 | 72,182 |
| COH | 22.4 | 22.2 | 1.8 | 6,239 | 18,204 | 24,443 (+30.6%) | 66,460 |
| COH_HALF | 20.6 | 20.4 | 3.1 | 6,338 | 19,323 | 25,661 (+37.1%) | 65,908 |
| COH_OPEN | 25.1 | 24.9 | 2.5 | 3,464 | 26,159 | 29,624 (+58.3%) | 58,897 |

All three clear every criterion: **C1** (20.4-24.9 tiles standing on day 16, against a bar of
20, and each above 0.9 × its own day-12 count), **C2** (1.8-3.1 missed-water deaths a game
against a 21.6 bar — shipped itself loses 14.4), and **C3** (combined wheat-plus-strawberry
settled revenue up 30.6% to 58.3% against a +10% bar). **All three go to the screen at band
878000.**

**What the recon says, and why it is not the verdict.** The recon bank — one leader, one
shared baseline, n=8, explicitly not gating — runs **−$5.7k (COH), −$6.3k (COH_HALF) and
−$13.3k (COH_OPEN)** against shipped, even as combined wheat-plus-strawberry revenue rises
$5.7-10.9k. The mechanism does exactly what the hypothesis claims and the bank still falls,
which locates the cost **outside the two items C3 measures**: strawberry seed spend, and
whatever the arms surrender in animal products and fertilizer. C3 was scoped on purpose to
the items the mechanism trades between, so that a per-item wheat guardrail could not veto the
slice by construction; the screen's own-bank rule is what prices the whole farm, and it is
unchanged. The registered P(advance) of 25% now looks generous, and the registered
instrument is still the screen rather than one 8-seed draw against one opponent.

The predicted ordering held in the recon: COH_OPEN lands lowest, as registered.

## ADDENDUM — SCREEN VERDICT (2026-09-12): NOT ADVANCED, and the cohort is measured NEGATIVE

Run at BUILD `047420e` (main, `packages/` and `dist/` verified identical to the
expression-checked tree), engine 1.32.7, band 878000, n = 64 per leader. Nine ledgers, no
crash and no veto.

| arm | pooled Δ own bank | se | 95% CI | opponent Δ (range) | pooled margin Δ |
|---|---|---|---|---|---|
| COH | **−$5,097** | 1,397 | [−$7,834, −$2,359] | −$940 to −$2,245 | −$3,629 |
| COH_HALF | **−$5,900** | 1,470 | [−$8,782, −$3,019] | −$1,403 to −$2,713 | −$3,972 |
| COH_OPEN | **−$10,444** | 1,486 | [−$13,357, −$7,532] | **+$10,550 to +$11,662** | −$21,459 |

Every arm fails all three criteria, and every interval lies **wholly below zero**. **NOT
ADVANCED.** No confirmation or guard ran; bands 879000 and 880000 are retired unused.

**What this settles, which five earlier slices could not.** The cohort is not a failure of
capability. It fills (20-25 tiles), it survives to day 16, missed-water deaths fall from 14.4
a game to under 4, and strawberry itself earns **$18-26k a game** — the crop pays. The farm
still ends **$5-10k poorer**. So the strawberry line closes on price rather than on a
mechanism bar: at our labor level we cannot afford to grow it, because the trips it consumes
and the animal products and fertilizer it displaces cost more than its revenue adds. The
prior closures (`docs/recon/occupancy.md`, the 2026-08-28 and 2026-09-06 registrations) were
about the satellite form; this one is about the **replacement** form that `occupancy.md`
itself called untested, and it lands the same way.

**COH_OPEN carries a separate finding worth more than its own verdict.** Playing the leaders'
full opening — NE on day 6, sheep first, goose deferred — makes *the leaders* about **$11k
richer per game** (opponent delta +$10,550 to +$11,662, margin delta −$21,459). Withdrawing
our wheat and milk from the shared market hands them the prices. Imitating a stronger
opponent's opening is not neutral: in a shared market it can be a transfer to them, and that
is invisible to any instrument that reads only our own bank.

**Predictions scorecard.**
- **Wrong on direction.** I registered P(advance) at 25% and the arms came in significantly
  negative, not marginal. The expression check's own recon had already argued lower and it is
  recorded above; I should have weighted it harder than the registered number.
- **Right on ordering, partly:** COH_OPEN was predicted lowest and is, by a wide margin.
  COH_HALF was predicted highest and came second of three.
- **Right that the screen would resolve the sign.** Dev-seed recon spanned −$18k to +$20k
  across two 4-seed sets; at n=64 per leader the answer is unambiguous.

**The scoreboard after seven slices**, pooled own-bank delta against shipped on the leader
panel: START8_T20 +$2,282, SHEEP1 +$2,051, START10 +$1,873, H10 +$781, EH1 +$340,
EH2 −$3,545, EH2_H10 −$3,586, **COH −$5,097, COH_HALF −$5,900, COH_OPEN −$10,444**. Nothing
has reached +$4,000, and the strawberry and leader-tape lines are now closed by measurement.
