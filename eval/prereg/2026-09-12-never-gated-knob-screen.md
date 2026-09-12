# Pre-registration: market-knob screen — the never-tested surface

Date: 2026-09-12
Candidate: `champion` with market-side knob overrides. **No new agent code**: every knob in
this slice already ships, so each arm is an `--agent-config` override and the build under
test is `main` itself.
Status: REGISTERED IN TWO PARTS. This commit fixes the instrument, the decision rule, the
bands, the excluded ranges, and the **form** of the expression check, before any arm data
exists. The arm table and each arm's own directional criterion are added in a later commit,
before the pre-launch probe runs. Runs launch only after (1) this document has merged and
(2) the expression check has passed. The runner asserts engine 1.32.7, that `PolicyConfig`
carries every arm's knob at its shipped default, and that the band is unused.
Authorization: owner decision 2026-09-12 — market-knob screen, chosen over a dispatch
rewrite and over stopping.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md` (pooled +$1,331, se $727, which
reproduces the ladder's tie between our two tracked bots).

## Why

**The production side is exhausted at the knob level.** Five registered slices have closed
without an advance:

| slice | verdict | best arm |
|---|---|---|
| `2026-09-11-strawberry-slice1-start-day.md` | NOT ADVANCED | +$2,282 |
| `…-strawberry-slice2-sw-zone.md` | WITHDRAWN before launch | fill 16.2 of 22 |
| `…-labor-slice1-wheat-planting.md` | NOT ADVANCED | +$781 |
| `…-labor-slice2-extra-hands.md` | NOT ADVANCED | +$340 |
| `…-leader-tape-slice1.md` | NOT LAUNCHED (no arm expressed it) | fill 25.5 of 36 |

Their common finding is a labor ceiling: reallocating the crew starves watering, extra hands
cost more than their work earns, and the last two probes showed wheat is labor-bound rather
than land-bound (handing it every idle zone tile changed nothing, and capping it to the
leaders' size cost $8-18k).

**CORRECTED 2026-09-12, before any arm data: the market side is not untested.** The premise
this slice was opened on — that the floors, valves, crash triggers, sell caps and reserves
had never been gated — is false, and the correction is measured rather than argued. Across
all 257 ledgers in `eval/gates/`, `identity.agent_config` carries 24 of `PolicyConfig`'s 38
fields, and **12 of the 14 market-side fields are already gated**, closed by
`eval/prereg/2026-09-07-untested-knob-screen.md` (which called itself "the entire
market-side control surface") together with the clone-front-run and vst35 experiments. The
two market-side fields never gated, `strawberry_floor` and `strawberry_fert_reserve`, are
provably inert at the shipped default: with `strawberry_tile_target = 0` the shed never
holds strawberry, so `build_orders`' own guard never fires and neither knob changes anything
alone. Inventory record: `eval/recon/2026-09-12-policyconfig-knob-inventory.json`.

**What is genuinely never gated** is a shorter list, most of it this session's own work:
`rescue_water`, `animal_buy_order`, `goose_min_day` and `ne_land_min_day` (merged
2026-09-11, pre-registered but never money-gated), `zone_fallthrough_multiplier` and
`strawberry_frame_live` (never gated and never pre-registered), plus the two inert
strawberry knobs above. This slice screens the subset whose mechanism fits the check form
below — raise one item's flow without wrecking another.

**The honest expectation is modest, and it is registered here rather than discovered
later.** The market-side wins are already shipped (`hand_mule_load` +$3,150,
`valve_soft_threshold` +$354), and the mechanisms left are smaller. Rescue watering saves
the roughly 12 plants a game the engine kills for a missed watering, at something like $60
of wheat yield each — about $700, the size of the labor slices' best arm, against a +$4,000
bar. This slice's value is a measured verdict that closes the last never-gated knobs, not a
likely winner. A +$4,000 own-bank gain is about +40 Elo on the ladder-derived slope.

## Excluded ranges (carried in from earlier work; not to be rediscovered)

An arm inside any of these is not registered, and the reason is cited with the arm table:
- a price floor at or above an item's equilibrium price permits roughly zero sales;
- the shed physically caps at 100 units, so a hard valve threshold at or above 100 cannot
  bind;
- a soft valve threshold at or above 85 combined with a hard threshold at or below 55
  collapses the soft tier entirely;
- `milk_floor` at or above 130 and `wool_floor` at or above 190 reproduce the
  near-equilibrium selling bug of issue #59;
- the strawberry knobs are inert at the shipped `strawberry_tile_target = 0`;
- `soft_budget_seconds` is a runtime guard, not a strategy knob.

## Registered arms

| arm | `--agent-config` | mechanism | targeted item and direction |
|---|---|---|---|
| **RW** | `{"rescue_water": true}` | the engine kills a plant after two unwatered days, and our crop calendars leave gap days that assume the next scheduled water actually happens; at shipped defaults that costs 47 plants per 4 games | WHEAT settled revenue rises |
| **RW_H10** | `{"rescue_water": true, "max_hires_per_turn": 10}` | rescue trips need crew capacity a saturated crew does not have; the raised hire cap puts the crew on the farm an hour earlier (measured: 44 weed tile-days against 58) | WHEAT settled revenue rises |
| **SHEEP1** | `{"animal_buy_order": ["SHEEP","COW"]}` | the shipped opening fills early pasture with cows and reaches 4 sheep only on day 7; the leaders hold 4 from day 0 and bank $16.6-18.9k of wool against our $9.8k | WOOL settled revenue rises |

**Not registered here, and why** — each would fail a committed criterion by construction,
which is a reason to put it in a successor with a guardrail matched to its mechanism, not a
reason to loosen this one:
- any arm that moves land from wheat to strawberry (the `START8_T20` stack, the leader-tape
  cohort): the collateral guardrail fires by construction, since the 31-tile zone measured
  wheat down $7.3-10.3k on a $12-20k base;
- `goose_min_day`: deferring the goose deliberately trades egg revenue for wool, so the same
  guardrail fires by construction;
- `zone_fallthrough_multiplier`, `strawberry_frame_live`, `strawberry_floor`,
  `strawberry_fert_reserve`: all inert at the shipped `strawberry_tile_target = 0`.

## Registered predictions

- **RW** passes its check (wheat revenue up) and lands **+$0 to +$1,500**. The mechanism is
  real and small.
- **RW_H10** has the highest point estimate of the three, **+$500 to +$2,500**.
- **SHEEP1** passes its check (wool up, milk down) and lands **−$1,000 to +$1,500**.
- **No arm advances: about 80% likely.** Said plainly because the bar is +$4,000 and the
  largest mechanism here is worth roughly $700.
- If it lands that way, the never-gated knob surface is closed by measurement, and the
  remaining candidates are the strawberry-cohort successor (a 24-27 tile surviving cohort
  has never been money-gated) and the dispatch rewrite.

## Expression check (pre-launch recon; a precondition) — form fixed now

Every arm's mechanism names **one traded item and one direction**. The per-arm values are
added with the arm table, before any probe of these arms; the bars below are fixed now:

Run `tools/recon-scripts/revenue_breakdown.py` on the build's tree (recorded by SHA) with
the shipped reference and every arm, on seeds 855000-855007 against
`public:sokolovsky-v12`, and commit the record as
`eval/recon/2026-09-12-market-knob-expression-check-855000.json`. An arm passes only if all
three hold:
1. **Positive mechanism criterion:** the arm's targeted item's settled flow moves in the
   arm's predicted direction by at least **10%** against shipped.
2. **Collateral guardrail:** no other item's settled revenue falls by more than **25%**
   against shipped.
3. **Degenerate guardrail:** the arm still sells at least one unit of every item that
   shipped sells at least 10 units of. This is the specific failure mode a floor has — it
   can silently stop all sales of an item rather than raise its price.

An arm that fails a criterion applying to it cannot express its mechanism and is dropped
before any run. If no arm passes, this document is amended by choosing different **values**,
never by relaxing a criterion, and the amendment is disclosed in the history below.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

- **Screen:** band **875000**, n = **64** seeds per leader, every arm that passed the
  expression check.
- **Confirmation:** the selected arm only, band **876000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655` as the opponent, band
  **877000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/` and claimed by no
earlier registration. (The leader-tape slice's "fresh bands ≥ 875000" lines are a forward
pointer, not a claim.)

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

**SCREEN — an arm ADVANCES** only if all hold at band 875000:
1. pooled own-bank delta **>= +$4,000**;
2. pooled 95% lower bound **> $0**;
3. no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the one with the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 876000 n=128, has:
1. pooled own-bank delta **>= +$4,000**;
2. pooled lower bound **> +$1,000**;
3. a pooled **margin delta** point estimate **> −$2,000**, where the margin delta is
   `mean_delta_i − opponent_mean_delta_i` pooled as a simple mean. It is a guard, not a
   mechanism reading and not an Elo proxy: the ladder scores the calibrated pair as tied at
   a margin delta of +$6,177.

**GUARD** (a no-catastrophe check): the confirmed arm's own-bank delta against
`frozen:m3b_live_b6ce655` must have a point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

## Multiplicity

This slice screens a knob surface rather than one mechanism, so it carries more arms than
its predecessors. That is accounted for rather than waved at: the prior slices measured a
pooled se near $1,000 at n=64, so the +$4,000 bar is about 4 standard errors and a null arm
clears it with probability on the order of 1e-4 — under 1e-3 even across ten arms. The
selected arm then has to clear a stricter bar (>= +$4,000 with a lower bound above +$1,000)
at n=128 on a **fresh band**, so nothing advances on the screen alone.

REPORTED, NOT GATING: per arm at screen, the gap (own bank minus the leader's) and the
margin delta. For the selected arm, the settled-flow breakdown by item against shipped, and
the realized price per unit by item.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot), and that remains an owner decision.

## Amendment history

- (this commit) instrument, decision rule, bands, excluded ranges and the expression check's
  form, committed before any arm exists and before the knob inventory was read.
- premise corrected against the measured knob inventory, before any arm data and before any
  probe: the market side is already gated (12 of its 14 fields), so the slice is re-aimed at
  the knobs that are genuinely never gated and whose mechanism fits the committed check
  form. The instrument, decision rule, bands, excluded ranges and check form are unchanged
  from 9ac8180. The file was renamed from `2026-09-12-market-knob-screen.md`. Arms whose
  mechanism the committed guardrails would veto by construction are named above and deferred
  to a successor rather than admitted by loosening a guardrail.

## ADDENDUM — EXPRESSION CHECK (2026-09-12): only SHEEP1 passes

Run on `4c3e3ec`, engine 1.32.7, seeds 855000-855007 against `public:sokolovsky-v12`. The
settlement conserved exactly (max |residual| 0.0 across all 64 episode-seat pairs) and the
shipped arm reproduced its recorded $66,163 mean to the dollar, so these are the games the
registration was written against. Records:
`eval/recon/2026-09-12-market-knob-expression-breakdown-855000.json` and
`…-check-855000.json`.

Settled revenue by item, our seat, mean over 8 seeds:

| arm | WHEAT | WOOL | MILK | EGG | FERTILIZER | our mean bank |
|---|---|---|---|---|---|---|
| shipped | 20,471 | 9,876 | 25,878 | 2,834 | 14,080 | 66,163 |
| RW | 14,382 | 18,011 | 18,999 | 2,735 | 13,757 | 62,852 |
| RW_H10 | 14,104 | 13,422 | 20,635 | 2,841 | 13,752 | 60,263 |
| SHEEP1 | 20,511 | 17,903 | 21,586 | 2,765 | 13,796 | 70,176 |

- **RW fails C1 and C2.** Its targeted item moved the wrong way: wheat settled revenue
  **fell 29.7%** where the criterion needed a 10% rise, and milk fell 26.6% against a 25%
  bar. Rescue watering saves plants and costs more wheat than it saves, because the trips
  come out of the same crew that plants and harvests.
- **RW_H10 fails C1**: wheat fell 31.1%. Putting the crew on the farm an hour earlier did
  not pay for the rescue trips.
- **SHEEP1 passes all three**: wool **+81.3%**, worst other-item drop 16.6% (milk), and no
  item stopped selling.

**Only SHEEP1 goes to the screen**, at band 875000. RW and RW_H10 are dropped before any
run, on their own registered criterion.

**Predictions scorecard.**
- **Wrong on both rescue-water arms.** I predicted each would pass with wheat revenue up;
  wheat fell about 30% in both. The mechanism is real — deaths do fall — but its sign on
  wheat revenue is the opposite of what I registered.
- **Right that SHEEP1 passes**, and right about the direction (wool up, milk down).
- **The recon bank also runs against my registered range for SHEEP1** (−$1,000 to +$1,500):
  it reads +$4,013 against this one leader on a shared baseline. That is not a result and
  not gating — one opponent, one shared baseline, n=8 — but it sits exactly at the screen's
  +$4,000 bar, which is why the n=64 screen against all three leaders is worth running.

**Recorded, not a verdict.** Both rescue-water arms also raise wool by about 82%, the same
size as the arm built to raise wool. That points at labor reallocation rather than anything
about water: a rescue trip is priority 0 and displaces the lowest-priority bulk work, which
is planting. It is a hypothesis, not a measurement, and it changes nothing here — both arms
are dropped on their registered criterion regardless.

## ADDENDUM — SCREEN VERDICT (2026-09-12): NOT ADVANCED

Run at BUILD `df31c9b` (main, with `packages/` and `dist/` verified identical to the
expression-checked tree `4c3e3ec`), engine 1.32.7, band 875000, n = 64 per leader. The three
ledgers are `eval/gates/2026-09-12T17-45-49Z-…`, `…T17-48-48Z-…` and `…T17-51-29Z-…`, with
no crash and no veto.

| opponent | n | mean Δ | se | 95% CI | opponent Δ | margin Δ |
|---|---|---|---|---|---|---|
| public:sokolovsky-v12 | 64 | +$3,342 | 1,563 | [+$278, +$6,405] | +$4,721 | −$1,379 |
| public:rayk-v11 | 64 | +$1,460 | 1,817 | [−$2,102, +$5,021] | +$4,655 | −$3,195 |
| public:kaito-v4 | 64 | +$1,351 | 1,846 | [−$2,267, +$4,969] | +$5,216 | −$3,866 |
| **pooled** | | **+$2,051** | **1,008** | **[+$74, +$4,027]** | | **−$2,814** |

Criterion 1 fails: +$2,051 against the +$4,000 bar. Criteria 2 and 3 pass (pooled lower
bound +$74; worst single leader +$1,351). **SHEEP1 is NOT ADVANCED, and with it the
never-gated knob screen is NOT ADVANCED.** No confirmation or guard ran, and bands 876000
and 877000 are retired unused.

**It would also have failed confirmation.** The pooled margin delta is **−$2,814** against
the registered guard of > −$2,000: the leaders' own banks rise $4.7-5.2k while ours rises
$2.1k, so most of what this arm earns is share the leaders would otherwise have taken rather
than new production. Recorded because the own-bank point estimate on its own reads more
promising than the arm is.

**Predictions scorecard.**
- **Right on the verdict.** I registered "no arm advances, about 80% likely", and that is
  what happened.
- **Wrong on SHEEP1's size.** I registered −$1,000 to +$1,500 and it measured +$2,051, above
  the range. Sheep-before-cows is worth more than I credited it — just not half the bar.
- The two rescue-water arms never reached the screen; their check failure, with wheat revenue
  falling about 30% where a rise was required, is recorded in the addendum above.

**The scoreboard after six slices**, every gated arm's pooled own-bank delta against shipped
on the leader panel: START8_T20 +$2,282, **SHEEP1 +$2,051**, START10 +$1,873, H10 +$781,
EH1 +$340, EH2 −$3,545, EH2_H10 −$3,586. Nothing has reached +$4,000. Sheep-first is now the
second-largest single-knob effect ever measured here and still under half the bar.

**The never-gated knob surface is closed by measurement**, which is what this slice was for.
What remains untested is the strawberry cohort, registered separately in
`eval/prereg/2026-09-12-strawberry-cohort-price.md`.
