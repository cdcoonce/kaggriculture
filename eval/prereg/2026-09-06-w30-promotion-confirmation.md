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
