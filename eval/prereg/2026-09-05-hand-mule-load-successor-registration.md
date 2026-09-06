# Pre-registration: hand_mule_load 9 → 20, successor — mechanism-aware redirection criterion

Date: 2026-09-05
Candidate commit: ad3cb75 (landed via PR #95) (agent source byte-identical to d7efe73/ad3cb75 —
this registration lands only harness/tools instrument code)
Status: REGISTERED — the registered runs launch only after this document AND
the harness.opponent_split instrument merge, and after the pre-launch
validation below is ledgered. No agent source may be edited while any
registered run is in flight.

## Motivation

The third registration (`eval/prereg/2026-09-05-hand-mule-load-third-registration.md`)
cleared every intersection-union money bar for the first time — metac95
+1,181 (n=384), thunder +2,628 (n=512), barnyard +1,831, mirror +1,023, band
824000, vetoes empty — and was NOT promoted because criterion 3 fired:
opponent_mean_delta −3,997 (thunder) and −3,928 (mirror) against the
registered ±$3,000 band. Its addendum recorded, as hypothesis only, that the
band was inherited from the strawberry-closure convention without pricing the
mechanism, and that a successor must fix a mechanism-aware criterion before
seeing any new data. This is that successor.

## Mechanism (fixed before any decomposition has been run)

A replay-tape opponent is observation-blind: its submitted orders are
byte-identical across arms (harness/zoo/tape_player.py — the only observation
read is the step counter). Its money can therefore differ between arms only
through:

1. **Market prices in items the champion trades** — the champion's changed
   sell/buy volumes and timing move shared per-item inventory, which prices
   the tape's settled SELLs and WHEAT/FERTILIZER buybacks. This is the one
   channel that carries genuine market interaction (redirection/suppression).
2. **Market prices in items the champion never trades** — the champion has no
   order-side channel into these inventories; they move only through the two
   RNG mediators (the daily shop-roster draw, kaggriculture#82, and the weed
   rolls the tape's tiles consume from the same per-day stream after the
   champion's bare-tile count shifts it). Mediator noise by construction.
3. **Fixed-price flows** (BUY_SEED, BUY_ANIMAL at constant catalog prices;
   HIRE at fib pricing; BUY_LAND at fixed tier prices) — unpriced by any
   market; they differ across arms only through affordability/fill cascades.

The redirection criterion should bound channel 1 and only channel 1.

## Instrument

`harness.opponent_split` (this registration's companion code, tested,
conservation-exact) replays a money-gate ledger's exact episodes via
`harness.settlement.play_with_settlement` (settled fills, not submitted
orders) and decomposes the opponent's seat-averaged money delta per seed into:

- `traded_market` — Δ(settled SELL revenue − settled BUY_PRODUCT cost) summed
  over champion-traded items;
- `untraded_market` — the same over all other items;
- `fixed_price` — Δ(BUY_SEED + BUY_ANIMAL + HIRE + BUY_LAND costs, as money
  contributions).

Champion-traded items: items with any settled champion SELL or BUY_PRODUCT
flow in either arm anywhere in that tape's run (computed from the same
episodes, not assumed). Exactness contract: per episode, final money must
equal startingMoney + revenue_total − spend_total with zero residual, must
match the gate ledger's recorded per-row money exactly, and the three bucket
means must sum exactly to the ledger's opponent_mean_delta. Any residual
anywhere invalidates the instrument run.

## Pre-launch validation and diagnostic (committed before the registered runs)

After this document and the instrument merge, and BEFORE any 826000 run:

1. Run the instrument against all four band-824000 money ledgers. The
   exactness contract above must hold on every ledger — this is the license
   to trust (the strawberry_labor precedent). Any mismatch stops everything.
2. The resulting decomposition of the 824000 opponent deltas is ledgered
   under eval/recon/ and appended here as a PRE-LAUNCH ADDENDUM,
   **diagnostic-only**: whatever it shows — including a traded_market
   component that already exceeds $3,000 — the registered runs below proceed
   unchanged and the criterion stands as written. It informs predictions,
   never the rule.

## Registered design

Money gates, candidate `champion` with `--agent-config
'{"hand_mule_load": 20}'`, baseline `champion` at defaults, band 826000
(fresh; prior operative bands end at 825063), seeds nested from 826000:

| tape | money bar | n_seeds |
|---|---|---|
| zoo:tape-thunder-719 (primary) | ci_lower > $1,000 | 512 |
| zoo:tape-barnyard-719 | ci_lower > $0 | 256 |
| zoo:tape-metac95-720 | ci_lower > $0 | 384 |
| zoo:tape-mirror-719 | ci_lower > $0 | 256 |

After the four gates, the instrument runs against each new ledger; its four
outputs are ledgered under eval/recon/ alongside the gate ledgers.

## Decision rule (fixed before launch)

PROMOTE only if ALL hold:

1. ci_lower > $1,000 on thunder AND ci_lower > $0 on barnyard, metac95 and
   mirror;
2. vetoes == [] on every tape;
3. **(3′)** |traded_market component of the opponent money delta| ≤ $3,000 on
   every tape at final n, per the instrument. untraded_market and fixed_price
   are reported, unbounded — they carry no champion market channel. The
   instrument's exactness contract must hold on every tape or the run is
   invalid.
4. skew rule (verbatim from the 2026-08-16 registration): skew_delta is read
   on every tape; if any tape whose bound only just clears its bar also has
   skew_delta < −1.0, the result is reported as inconclusive, not as a pass.

The band in 3′ is inherited unchanged from the prior registrations — same
tolerance, mechanism-correct scope. It was fixed here before the 824000
decomposition (or any other instrument output) existed.

Otherwise NOT promoted — and if 3′ itself fires, that is the end of the hml20
line for this competition: a traded-market breach means the gain really is
redirection expressed through markets we trade, the thing the criterion has
always guarded. No fourth registration.

No extensions, no added tapes, no band changes after launch.

## Registered predictions

- The 824000 breaches (thunder −3,997, mirror −3,928) decompose mostly into
  untraded_market + fixed_price; traded_market lands inside ±$3,000. That is
  the hypothesis this successor exists to test — if it is wrong, criterion 3′
  fires and the line dies with the mechanism named.
- The four money bars clear again on the fresh band (priors: +2,628 / +1,831 /
  +1,181 / +1,023 at the same n's on 824000).

## Consequence of PASS

hml20 becomes a submission candidate. The head-to-head viability ledger
(193−7 vs frozen:m3b_live_b6ce655, eval/gates/2026-09-03T15-29-17Z-…-promotion.json)
remains valid — the agent package is byte-identical from d7efe73 through this
registration's commit. Uploading is a separate HITL decision — T-2 freeze
2026-09-28; a new submission evicts one of the Bradley-Terry pair
[M3b 55784368, M3a 55471731]. Nothing in this document authorizes an upload.
