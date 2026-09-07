# Pre-registration: wheat_rush_tiles = 30 — promotion-grade confirmation

Date: 2026-09-06
Candidate: `champion` with `{"wheat_rush_tiles": 30}` — CONFIG ONLY. The agent
package is byte-identical to the shipped M3b at b6ce655.
Status: REGISTERED — runs launch after this document merges. No agent source
edits while any registered run is in flight.

## What is already established

`eval/prereg/2026-09-06-wheat-rush-tiles-cap.md` + ADDENDUM returned ALIVE on
band 835000, n=100 seeds / 200 games per arm vs `frozen:m3b_live_b6ce655`:

| arm | W-L | rate | ci_lower | dCand $ | dOpp $ |
|---|---|---|---|---|---|
| CTRL (defaults) | 97-97 | 0.500 | 0.431 | — | — |
| W25 | 148-52 | 0.740 | 0.675 | +796 | −35 |
| **W30** | **172-28** | **0.860** | **0.805** | **+2,143** | **+670** |
| W35 | 140-60 | 0.700 | 0.633 | +494 | −3 |

The control landed exactly 0.500, so the harness is validated. The effect is
production-driven: our money rises AND the opponent's money rises.

## Why this registration exists

Two reasons, both about not fooling ourselves:

1. **W30 was selected as the maximum of a four-arm sweep.** The max of several
   noisy arms is upward-biased. A confirmation on a fresh band at larger n is
   the correction, and it is the only number that should be cited when deciding
   whether to ship.
2. **The repo's promotion convention** (eval/README.md) is a four-tape money
   intersection-union alongside the head-to-head, with a redirection check.
   W30 already has a passing promotion gate — which is what submit.py's upload
   precondition actually reads — but the money discipline has not been run.

## THE CRITERION PROBLEM, fixed before any data exists

The inherited redirection criterion bounds **|opponent money delta| <= $3,000**
— an absolute value. That form is wrong for this candidate, and the reason is
mechanistic, not convenient:

Capping the wheat zone means selling **less** wheat into the shared book, which
**raises** the price for whoever sells next — including the opponent. The
band-835000 money columns show exactly this (opponent +$670 at W30; +$2,480 at
W20). An absolute-value criterion therefore fires on a **positive** opponent
delta — an opponent getting *richer* — which is the precise opposite of the
suppression the criterion exists to catch.

**Registered change, with its own honesty check.** The redirection KILL
criterion here is **one-sided**: it bounds only the direction in which the
opponent LOSES money to us. The positive direction is retained as a reported
**validity diagnostic**, not a kill.

This change does **not** rescue any past verdict, which is the test of whether
it is a principled fix or a laundering: `hand_mule_load` 20 was closed on
2026-09-06 by a traded_market component of **−3,077** on thunder — a NEGATIVE
breach, which the one-sided criterion catches identically. The hml20 line stays
closed and is not reopened by this document.

## Registered design

Band **836000** (fresh; 835000 was the sweep). Candidate `champion` with
`--agent-config '{"wheat_rush_tiles": 30}'` throughout.

**A. Head-to-head confirmation** — promotion gate vs `frozen:m3b_live_b6ce655`,
**n=250 seeds (500 games)**.

**B. Four-tape money intersection-union** — money gates, baseline `champion` at
defaults, nested from 836000:

| tape | bar | n_seeds |
|---|---|---|
| zoo:tape-thunder-719 (primary) | ci_lower > $1,000 | 512 |
| zoo:tape-barnyard-719 | ci_lower > $0 | 256 |
| zoo:tape-metac95-720 | ci_lower > $0 | 384 |
| zoo:tape-mirror-719 | ci_lower > $0 | 256 |

**C. Redirection decomposition** — `harness.opponent_split` on each of the four
money ledgers from B (no extra episodes).

## Decision rule (fixed before launch)

PROMOTE (become a submission candidate) only if ALL hold:

1. **Confirmation.** A's rate >= **0.65** with Wilson ci_lower > **0.55** at
   n=250 on the fresh band. (Same bar the sweep used, re-applied to correct the
   peak-selection bias.)
2. **Money IU.** B clears every bar in the table above, with `vetoes == []` on
   every tape.
3. **Redirection, ONE-SIDED.** For every tape, the `traded_market` component of
   the opponent's money delta is **>= −$3,000**. A component more negative than
   that is suppression and is disqualifying regardless of win rate.
4. **Skew.** `skew_delta` read on every tape; any tape whose bound only just
   clears its bar AND has `skew_delta < −1.0` is reported inconclusive, not a
   pass.
5. **Instrument validity.** `harness.opponent_split`'s exactness contract holds
   on all four ledgers (per-episode conservation residual exactly 0.0; every
   aggregate == the ledgered `opponent_mean_delta`). Any residual invalidates
   the run.

REPORTED, NOT GATING: any tape where `traded_market` exceeds **+$3,000** — the
arms are then not ceteris paribus and the money comparison is confounded in the
candidate's DISFAVOUR (we handed the opponent price). Record it prominently; it
weakens the money evidence without being suppression.

NOT PROMOTED otherwise. No extensions, no added tapes, no band changes after
launch.

## Registered predictions

- A confirms above 0.65 but **below the sweep's 0.860** — regression toward the
  mean is expected from a selected maximum, and a confirmation landing at
  0.70-0.80 should be read as success, not as a disappointment.
- The money IU is the real risk. Withdrawing wheat supply lifts prices for the
  tape's own sales, so `opponent_mean_delta` may be large and POSITIVE, and the
  money delta may be compressed relative to the head-to-head advantage.
- Criterion 3 does NOT fire (the mechanism gives money away rather than taking
  it). If it does fire, the mechanism story is wrong and that is the finding.

## Consequence

PROMOTE authorizes an upload DECISION, not an upload. Uploading remains HITL:
T-2 freeze 2026-09-28, final submission 2026-09-30, and a new submission evicts
one of the Bradley-Terry pair [M3b 55784368, M3a 55471731]. Nothing in this
document authorizes an upload.

## ADDENDUM (2026-09-06, post-run): NOT PROMOTED — the head-to-head confirmed, the money IU did not

Runs executed 2026-09-06T22:36-23:20Z at `9d3f4e4` (this document's own merge
commit), band 836000, candidate `champion` with `{"wheat_rush_tiles": 30}`,
config-only, agent package byte-identical to the shipped M3b at b6ce655. Serial,
no source edits in flight. `any_candidate_crash` false on all five runs.

**A. Head-to-head confirmation — PASSES, and did not regress.**

| | n_seeds | W-L | rate | ci_lower | bar | |
|---|---|---|---|---|---|---|
| vs `frozen:m3b_live_b6ce655` | 250 | **428-72** | **0.856** | **0.8225** | 0.65 / 0.55 | **PASS** |

Ledger: `eval/gates/2026-09-06T22-36-43Z-champion-vs-frozen_m3b_live_b6ce655-promotion.json`.

**B. Four-tape money intersection-union — FAILS on all four.**

| tape | bar | mean_delta | ci_lower | vetoes | skew | mde_80 | |
|---|---|---|---|---|---|---|---|
| thunder (primary) | > $1,000 | +925 | **−387** | `[]` | +0.119 | 1,984 | FAIL |
| metac95 | > $0 | +1,537 | **−72** | `[]` | +0.146 | 2,432 | FAIL |
| barnyard | > $0 | +1,607 | **−399** | `[]` | +0.048 | 3,030 | FAIL |
| mirror | > $0 | +1,361 | **−479** | `[]` | +0.213 | 2,779 | FAIL |

Ledgers: `T22-52-05Z` (thunder), `T23-04-18Z` (metac95), `T23-12-57Z`
(barnyard), `T23-20-51Z` (mirror).

**C. Redirection, one-sided — passes where measured, UNEVALUATED on mirror.**

| tape | traded_market | bar | conservation | aggregate == ledgered omd | |
|---|---|---|---|---|---|
| thunder | −1,430.23 | ≥ −3,000 | residual 0.0 (512 rows) | yes | PASS |
| metac95 | −179.77 | ≥ −3,000 | residual 0.0 (384 rows) | yes | PASS |
| barnyard | −164.18 | ≥ −3,000 | residual 0.0 (256 rows) | yes | PASS |
| **mirror** | **not computed** | — | — | — | **UNEVALUATED** |

**Decision-rule application.** Criterion 1 PASSES. Criterion 2 FAILS on every
tape, including the primary. Criterion 3 passes on the three tapes where it was
computed. Criterion 4 is moot (no tape's bound cleared its bar, and no
`skew_delta` is anywhere near −1.0; all four are positive). Criterion 5 holds on
the three ledgers where the instrument was run.

**Verdict: NOT PROMOTED.** The registered rule required all five to hold.
Criterion 2 failed on all four tapes. The verdict is recorded as the rule was
written, before the run, and is not reopened by this document.

### Protocol defect, recorded rather than smoothed over

Section C registered the decomposition on **each of the four** money ledgers.
Only three were produced — `eval/recon/2026-09-06-opponent-split-mirror-836000.json`
does not exist, tracked or untracked, while bands 824000 and 826000 each carry
all four tapes. So criteria 3 and 5 were never evaluated on mirror. The
promotion outcome does not turn on it (criterion 2 already failed on mirror
independently), but the run as executed is **incomplete against its own
registration**, and a reader who checked only the verdict line would not learn
that. Any successor must verify the instrument ran on every registered ledger
before applying its decision rule.

### The money IU could not have passed for an effect of this size

Not an argument against the verdict — an argument about the instrument, drawn
from the ledgers' own `mde_80` field (the minimum effect detectable at 80%
power):

| tape | observed effect | its own mde_80 | ratio |
|---|---|---|---|
| thunder | +925 | 1,984 | 0.47× |
| metac95 | +1,537 | 2,432 | 0.63× |
| barnyard | +1,607 | 3,030 | 0.53× |
| mirror | +1,361 | 2,779 | 0.49× |

Every tape's observed effect is roughly half its own minimum detectable effect.
A null was the expected outcome on all four **whether or not the effect is
real**, so criterion 2 as registered carried almost no information about W30 at
the n it specified. All four point estimates are positive (+$925 to +$1,607) and
all four bounds are slightly negative (−$72 to −$479); metac95 missed its $0 bar
by $72. This is [[null-results-are-not-measured-absences]]: an empty bucket, not
a measured absence.

**Transferable lesson for every future registration in this repo: compare the
expected effect against `mde_80` BEFORE fixing the bar.** A bar the study cannot
reach is a coin-flip dressed as a criterion. The three prior wheat-cap screens
died the same way at n=20, which is how this knob stayed hidden for a month.

### Registered predictions vs outcome

- *"A confirms above 0.65 but below the sweep's 0.860 — 0.70-0.80 should be read
  as success"* — **wrong, in the candidate's favour.** The confirmation landed at
  0.856 against the sweep's 0.860, on a fresh band at 2.5× the n. Two
  independent bands (835000 n=100, 836000 n=250) agree to within 0.004. Whatever
  W30 is doing, peak-selection bias is not the explanation.
- *"The money IU is the real risk"* — **correct**, and it is what killed it.
- *"opponent_mean_delta may be large and POSITIVE"* — **mixed.** barnyard +1,908
  (its untraded component is +2,072), but thunder −2,000, metac95 −624,
  mirror −1,048. No tape trips the +$3,000 "reported, not gating" clause.
- *"Criterion 3 does NOT fire"* — **correct** on all three tapes measured.

### What this verdict does and does not settle

It settles that W30 does not clear **this repo's inherited money-based promotion
rule**. It does not settle whether W30 is a stronger ladder agent, because the
money rule measures a quantity the competition does not score. From the official
competition Evaluation page, retrieved 2026-09-07 and recorded in
`docs/recon/competition-rules.md`:

> The actual coin difference in a match does not affect the rating
> change—only the win, loss, or tie outcome matters.

That is external evidence about the objective, not a reinterpretation of this
run's data, and it is grounds for a **successor registration** with an
objective-aligned criterion on a fresh band — not for overriding the criterion
that fired here. Before any such successor is written it must pass the same
honesty test this document applied to its own one-sided change: state, with
ledger citations, whether an Elo-aligned rule would retroactively rescue any
line already closed (`hand_mule_load` 20, cow7/sheep5, melon18, strawberry). If
it would, that must be declared in the successor, not discovered afterwards.
