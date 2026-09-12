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

**The market side has never been tried at all.** The floors, valves, crash triggers, sell
caps and reserves in `PolicyConfig` have never appeared as a key in any `eval/gates/*.json`
ledger's `agent_config`. That inventory is measured and committed with the arms.

This slice therefore tests a different mechanism from every predecessor: not how much we
produce, but the price we realize on what we already produce, and how much of it we sell
before the town's demand saturates. It cannot close the strawberry gap — settled replay
decomposition puts strawberry at 94% of the revenue gap to the 650-750 band, and we plant
none — so its upside is bounded and its cost is hours. A +$4,000 own-bank gain is about +40
Elo on the ladder-derived slope.

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
