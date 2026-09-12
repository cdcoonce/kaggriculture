# Pre-registration: stack the two measured positives

Date: 2026-09-12
Candidate: `champion` with both components' knobs. **No new agent code**: every knob here has
already shipped and already been gated, so each arm is an `--agent-config` override and the
build under test is `main` itself.
Status: REGISTERED — runs launch only after (1) this document has merged and (2) the
expression check below has passed. The runner asserts engine 1.32.7, that `PolicyConfig`
carries every arm's knob at its shipped default, and that the band is unused.
Authorization: owner decision 2026-09-12 (stack the two positives), taken after seven slices
closed without an advance.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## Why

Two arms have been measured positive at n=64 against the panel, and they are the two largest
effects this project has produced. Both are ledgered:

| component | knobs | pooled Δ | se | 95% CI | margin Δ | verdict |
|---|---|---|---|---|---|---|
| START8_T20 | 20-tile strawberry zone from day 8, cap 10 | +$2,282 | 913 | [+$492, +$4,072] | **+$1,206** | NOT ADVANCED (bar is +$4,000) |
| SHEEP1 | sheep before cows | +$2,051 | 1,008 | [+$74, +$4,027] | **−$2,814** | NOT ADVANCED |

Ledgers: `eval/gates/2026-09-11T04-21-24Z-…`, `…T04-23-42Z-…`, `…T04-26-01Z-…` (band 860000)
for START8_T20; `eval/gates/2026-09-12T17-45-49Z-…`, `…T17-48-48Z-…`, `…T17-51-29Z-…`
(band 875000) for SHEEP1.

Their own-bank effects sum to **+$4,333**, just over the bar. Nothing else remains: strawberry
in both its satellite and its wheat-replacing forms, the leader-tape rebuild, the labor line
and the never-gated knob surface are all closed by measurement
(`eval/prereg/2026-09-12-strawberry-cohort-price.md` and the six registrations it cites).

**Hypothesis:** the two mechanisms are independent enough that their own-bank effects
substantially add, clearing +$4,000.

**The reason to doubt it, on record.** The one factorial this project has run
(`eval/prereg/2026-09-07-elo-aligned-factorial.md`) found two individually-positive knobs
combining to **less than the better singleton** — additive prediction +868 Elo, observed
+349, interaction −518 — because they turned out to be substitutes. These two touch different
subsystems (a crop zone and the animal buy order), which argues against substitution, but
they draw on the same early cash: slice 0 measured that strawberry seed spending **displaces
the herd** the shipped agent would otherwise buy. That is exactly how sheep-first could be
silently nullified inside the stack, and it is what the expression check below is built to
catch.

**And the distinctive risk is confirmation, not the screen.** START8_T20's margin delta is
+$1,206 (its gain is production) while SHEEP1's is −$2,814 (its gain is share the leaders
would otherwise take). If those add, the stack's margin delta lands near −$1,600 — inside the
registered > −$2,000 confirmation guard, with little room. An arm here can clear +$4,000 on
own bank and still fail confirmation.

## Registered arms

- **STACK2**: `{"strawberry_tile_target": 20, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8, "animal_buy_order": ["SHEEP","COW"]}`
- **STACK3**: `{"strawberry_tile_target": 20, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8, "animal_buy_order": ["SHEEP","COW"], "max_hires_per_turn": 10}`

STACK3 adds the raised hire cap (H10, measured +$781 with a lower bound of −$1,234), which
puts the crew on the farm an hour earlier and competes with neither component's mechanism.

`rescue_water` is deliberately excluded: its own check measured wheat settled revenue falling
about 30%, and it is dropped in `eval/prereg/2026-09-12-never-gated-knob-screen.md`.

## Expression check (pre-launch recon; a precondition)

Run `tools/recon-scripts/early_cash_ledger.py` and `tools/recon-scripts/revenue_breakdown.py`
on the build's tree (recorded by SHA), reference first and then every arm, on seeds
**857000-857007** against `public:sokolovsky-v12`. Then run
`tools/recon-scripts/stack_check.py LEDGER --flows BREAKDOWN`. Commit all three records under
`eval/recon/2026-09-12-stack-expression-*-857000.json`.

The criteria are fixed here, before any arm data exists. The point of a stack's check is that
**both** components still fire inside it:

1. **Strawberry component fires:** mean standing strawberry tiles at the end of day 12 >=
   **10**. Anchored on START8_T20's own measured fill of 15.5 tiles in its slice-1 recon; a
   bar of 10 of its 20-tile zone is the modest version of "the zone exists".
2. **Herd component fires:** WOOL settled revenue rises at least **10%** against shipped.
   SHEEP1 alone measured +81.3%, so this bar catches the nullification case — strawberry
   seed spending eating the early herd — rather than grading the size of the effect.
3. **Combined flow:** WHEAT + STRAWBERRY + WOOL settled revenue rises at least **10%**
   against shipped. These are the three items the stack touches, and the sum is the honest
   form: a per-item wheat guardrail would veto the strawberry component by construction,
   since a zone displaces wheat.
4. **Degenerate guardrail:** the arm still sells at least one unit of every item shipped
   sells at least 10 units of.

An arm failing a criterion cannot express the hypothesis and is dropped before any run. If
neither arm passes, this document is amended by choosing different values, never by relaxing
a criterion, and the amendment is disclosed below.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, **baseline `champion` at
shipped defaults**, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

- **Screen:** band **881000**, n = **64** seeds per leader.
- **Confirmation:** the selected arm only, band **882000**, n = **128** per leader.
- **Guard:** the confirmed arm against `frozen:m3b_live_b6ce655`, band **883000**, n = 64.

All three bands are verified unused by every ledger in `eval/gates/` and claimed by no
earlier registration.

## Decision rule (fixed before launch)

Identical to the seven prior slices, restated so this document stands alone.

Per arm and leader *i*, take `mean_delta_i`, `stderr_i` and `opponent_mean_delta_i` from the
ledger; pool as the simple mean with pooled se `sqrt(sum stderr_i²)/3`; intervals are
estimate ± 1.96 × se. The ledger's `passed` field is not the verdict.

**INVALID** if the engine is not 1.32.7, a knob is absent, the expression check has not
passed, or any run records a crash-type veto (`candidate_crash`, `baseline_crash`,
`opponent_crash`, `canary_crash`) or a `baseline_degenerate` / `opponent_degenerate` veto. A
`candidate_degenerate` veto is a result, not an invalidity: the games are deterministic, so
that arm does not advance, confirm, or pass the guard.

**SCREEN — an arm ADVANCES** only if, at band 881000: pooled own-bank delta **>= +$4,000**;
pooled 95% lower bound **> $0**; and no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 882000 n=128, has pooled delta
**>= +$4,000**, pooled lower bound **> +$1,000**, and a pooled **margin delta**
(`mean_delta_i − opponent_mean_delta_i`, simple mean) **> −$2,000**.

**GUARD:** the confirmed arm's own-bank delta against `frozen:m3b_live_b6ce655` must have a
point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold
change after launch.

REPORTED, NOT GATING: per arm, the gap and the margin delta; for the selected arm, the
settled-flow breakdown by item against shipped, and standing strawberry by day.

## Registered predictions

- **Both arms pass the check.** Each component's mechanism is individually measured, and the
  nullification case (strawberry seed spend eating the herd) is the specific thing criterion 2
  would catch.
- **STACK2 lands +$1,000 to +$4,500.** The parts sum to +$4,333; the factorial precedent says
  interaction can eat most of a stack, and the shared early-cash channel is the plausible
  mechanism for that here.
- **STACK3 lands at or slightly below STACK2.** H10 measured +$781 alone with a lower bound
  of −$1,234, so it adds little and may add nothing.
- **P(any arm advances) 25%.** Higher than the 20% I would have said from the closures alone,
  because these two components touch different subsystems and one of them (START8_T20) gains
  by production rather than by taking share.
- **P(an advancing arm then confirms) is lower still**, because of the margin arithmetic
  above: +$1,206 and −$2,814 summed sit near −$1,600 against a −$2,000 guard.
- **If neither arm advances**, every line this project has opened is closed by measurement,
  and the remaining options are a dispatch rewrite or a freeze. That is an owner decision, not
  a further slice.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next upload evicts
M3b (our best live bot), and that remains an owner decision.

## Amendment history

- (this commit) full registration: arms, criteria, bands, rule and predictions, committed
  before the expression check runs. Criterion 1's threshold is anchored on START8_T20's
  measured fill (15.5 tiles) from its own slice-1 recon, not on any measurement of these
  stacked arms, which have never been run.
