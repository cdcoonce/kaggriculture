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

## PRE-LAUNCH ADDENDUM (2026-09-06, diagnostic-only — the registered runs
## below proceed unchanged regardless of anything in this section)

Validation and diagnostic executed at 73b1862 (instrument PR #95 plus the
association fix PR #96; agent package still byte-identical to d7efe73).

**Exactness contract: HOLDS on all four band-824000 ledgers.** Per-episode
conservation residual exactly 0.0 everywhere (6,144 episodes replayed), every
replayed opponent money matched its ledger row exactly, and every aggregate
reproduced the ledgered `opponent_mean_delta` bit-for-bit. One instrument
defect was found and fixed en route (PR #96): the aggregate was computed as
mean-of-diffs while gate.py uses diff-of-means; the two associations differ
by ~5e-12 at any n with an odd factor (metac95's n=384 exposed it; the
power-of-two n's masked it), and the exact `==` correctly refused the
near-miss. The criterion is registered against gate.py's statistic, so the
instrument now replicates gate.py's association verbatim.

**Diagnostic decomposition of the 824000 runs** (ledgered at
eval/recon/2026-09-05-opponent-split-{metac95,thunder,barnyard,mirror}-824000.json;
traded items EGG/FERTILIZER/MELON/MILK/WHEAT/WOOL on every tape):

| tape | traded_market | untraded_market | fixed_price | total (=ledgered) |
|---|---|---|---|---|
| metac95 (n=384) | −1,603.47 | −247.11 | 0.00 | −1,850.59 |
| thunder (n=512) | −2,746.17 | −1,247.87 | −3.16 | −3,997.21 |
| barnyard (n=256) | −1,205.79 | −1,581.65 | 0.00 | −2,787.44 |
| mirror (n=256) | −2,487.59 | −1,438.56 | −1.76 | −3,927.91 |

Read against the registered prediction: every traded_market component sits
inside the ±$3,000 band — both 824000 breaches were carried over the line by
untraded mediator noise. Two honest caveats, recorded before the registered
runs: (1) the margins are thin (thunder $254, mirror $512 inside the band)
and the traded component re-rolls on the fresh band, so criterion 3′ can
still legitimately fire; (2) the traded component is consistently negative
on every tape (−1.2k…−2.7k) — hml20's gain is part genuine redirection, real
but within the registered tolerance. Nothing here changes the rule or the
launch: band 826000, the four gates and their instrument runs, as registered.

## ADDENDUM (2026-09-06, post-run): NOT PROMOTED — criterion 3′ fired on
## thunder. The hml20 line ends here.

Runs executed 2026-09-06T02:41–04:00Z at b60bb6a (agent package byte-identical
to d7efe73 throughout; only harness/eval code landed since), serially,
metac95 first as the binding constraint, no source edits while any run was in
flight. Opponent digests recorded per ledger.

| tape | n | mean_delta | ci_lower | bar | bar met | skew | vetoes |
|---|---|---|---|---|---|---|---|
| metac95 | 384 | +1,947.11 | +830.79 | >$0 | yes | −0.04 | none |
| thunder | 512 | +3,126.29 | +2,148.63 | >$1,000 | yes | +0.02 | none |
| barnyard | 256 | +3,718.10 | +2,290.71 | >$0 | yes | −0.03 | none |
| mirror | 256 | +2,950.57 | +1,552.59 | >$0 | yes | −0.18 | none |

Gate ledgers: eval/gates/2026-09-06T02-52-58Z-…-metac95-720-money.json,
2026-09-06T03-07-49Z-…-thunder-719-money.json,
2026-09-06T03-15-28Z-…-barnyard-719-money.json,
2026-09-06T03-22-59Z-…-mirror-719-money.json. (metac95's ledger records
`passed: false` against the runner's default $1,000 threshold; this
registration's bar for metac95 is >$0, which it clears. The runner's own
flag is not this registration's rule.)

Instrument decomposition (eval/recon/2026-09-06-opponent-split-*-826000.json;
exactness contract holds on all four — per-episode residual 0.0, every
aggregate == the ledgered `opponent_mean_delta`):

| tape | traded_market | untraded_market | fixed_price | total | 3′ |
|---|---|---|---|---|---|
| metac95 | −2,394.26 | −382.44 | 0.00 | −2,776.69 | ok |
| thunder | **−3,077.35** | +226.21 | −2.58 | −2,853.73 | **FIRES** |
| barnyard | −356.07 | −278.96 | 0.00 | −635.02 | ok |
| mirror | −1,886.63 | −516.68 | −1.56 | −2,404.87 | ok |

**Decision-rule application: criteria 1, 2 and 4 HOLD. Criterion 3′ FAILS on
thunder (|−3,077.35| > $3,000, by $77.35). NOT PROMOTED. Per this
registration's own text, that ends the hml20 line for this competition: no
fourth registration.**

Three things this run establishes, recorded because they outlive the verdict:

1. **The mechanism-aware criterion was stricter, not looser — on the tape
   that decided it.** Under the superseded criterion 3 (bounding the WHOLE
   opponent delta), every tape on this band sits inside ±$3,000 (−2,777 /
   −2,854 / −635 / −2,405) and hml20 would have been PROMOTED. Criterion 3′
   killed it. On thunder the untraded component is **+226** — mediator noise
   pointing the other way, partially masking a traded component larger than
   the aggregate ever showed. The successor was built on the hypothesis that
   the old band was too tight for a coupled arm; the instrument answered by
   making the decisive tape's redirection *visible*, not by excusing it. A
   criterion designed to be more permissive that instead refuses a candidate
   the old rule would have passed is the strongest available evidence that it
   is measuring a mechanism rather than laundering a veto.

2. **The gain is real and it is substantially redirection — heterogeneously
   so.** Set our money gain against the opponent's traded-market loss per
   tape: thunder +3,126 vs −3,077 (≈1:1 — the gain is very nearly the
   opponent's lost traded revenue); metac95 +1,947 vs −2,394 (the opponent
   loses more than we gain); mirror +2,951 vs −1,887; barnyard +3,718 vs
   −356 (nearly pure production). The same knob is production against one
   opponent and redirection against another. No single scalar criterion —
   old or new — was ever going to represent that cleanly, and the per-tape
   split is the artifact worth keeping.

3. **The money effect itself replicated.** Two independent bands (824000,
   826000) at n=256–512 per tape, all four intersection-union bars cleared
   both times, vetoes empty, skew flat. "hand_mule_load 20 does not convert
   labor to money" remains refuted; what killed it is how the money arrives.

Not acted on, recorded as hypothesis only, and NOT grounds for a successor:
$77.35 is 2.6% of the band, and the band itself was inherited from the
strawberry-closure convention rather than derived. A future project could
derive a redirection tolerance from the ladder's own scoring (the final is
Bradley-Terry over wins, where taking an opponent's revenue is not obviously
worth less than earning it) instead of borrowing one. That is a different
question, asked before data, in a different competition.
