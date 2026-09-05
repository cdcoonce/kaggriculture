# Pre-registration: hand_mule_load 9 → 20, third registration (post-sticky champion)

Date: 2026-09-05
Candidate commit: d7efe73 (no source change; config-only)
Status: REGISTERED — runs launch after this document merges; no agent source
may be edited while any registered run is in flight.

## Motivation

`hand_mule_load` (carry threshold before a hand mules home; shipped default 9,
tuned against shed capacity, never against travel cost) has been registered
twice and executed zero times:

- `eval/prereg/2026-08-16-hand-mule-load.md` — band 620000 design, never run.
  Contemporaneous disposition (commit ff8266a): "real positive effect
  (~+$1,500-4,800/seed...) but NOT promoted: barnyard's bound does not clear
  $0" at exploratory n=64; mde_80 was about the size of the effect.
- `eval/prereg/2026-08-16-hand-mule-load-remeasure.md` — band 650000, never
  run.

The champion has since changed materially: sticky task assignment (PR #69,
retargets ~45%→~11%), the M2c shed valve and crash latches (PR #61/#62), and
the SE-quadrant purchase stop (PR #81, b6ce655). Walking remains ~58% of
unit-turns, so the carry threshold is the standing untested labor lever.

The 2026-09-03 unregistered sweep (ledgered in PR #92, bands 820000-823000)
re-probed the knob on the current champion:

| check | result | ledger |
|---|---|---|
| viability vs frozen:m3b_live_b6ce655, n=100, band 821000 | 193-7, rate 0.965, PASS | eval/gates/2026-09-03T15-29-17Z-champion-vs-frozen_m3b_live_b6ce655-promotion.json |
| thunder n=64, band 822000 | ci_lower +1,057.5 | eval/gates/2026-09-03T15-38-34Z-champion-vs-zoo_tape-thunder-719-money.json |
| barnyard n=64, band 822000 | ci_lower +1,636.9 (the 08-16 blocker now clears) | eval/gates/2026-09-03T15-41-18Z-champion-vs-zoo_tape-barnyard-719-money.json |
| metac95 n=64, band 822000 | ci_lower -1,230.4 | eval/gates/2026-09-03T15-43-56Z-champion-vs-zoo_tape-metac95-720-money.json |
| metac95 n=192, band 823000 | ci_lower +794.0 | eval/gates/2026-09-03T16-14-08Z-champion-vs-zoo_tape-metac95-720-money.json |
| mirror n=64, band 822000 | ci_lower +369.7 | eval/gates/2026-09-03T15-46-34Z-champion-vs-zoo_tape-mirror-719-money.json |
| mirror n=192, band 823000 | ci_lower +676.6 | eval/gates/2026-09-03T16-19-48Z-champion-vs-zoo_tape-mirror-719-money.json |

The n=192 runs were launched AFTER observing the n=64 metac95 failure —
conditionally-run evidence, not citable as a pass. This registration is the
tiebreaker, executed on a fresh band with the decision rule fixed in advance.

Head-to-head money decomposition from the viability ledger rows (same PR):
candidate mean $66,907 vs opponent mean $63,644 — the candidate EARNS more
while the opponent roughly holds; a production effect, not the suppression
signature the cow/sheep arms show (see the companion registration).

Saturation (2026-08-16 registration, adversarially confirmed): 20/24/32 are
byte-identical arms; 20 is the canonical representative. No value tuning
remains — this is a promote/don't decision.

## Viability arm (kaggriculture#91 rule)

Required comparison for any non-default configuration: candidate-at-config vs
shipped default, run FIRST. Qualifying run already ledgered and re-verified
bit-exact via rerun-ledger on 2026-09-05: the 193-7 promotion gate cited above.

## Pairing caveat (kaggriculture#82)

Shop-roster coupling for hand_mule_load 9→20: 7/8 coupled draws, first
divergence draw-day 5, identical across all 6 probe seeds
(`eval/recon/2026-09-05-shop-roster-coupling-hml-9-20-822000.json`).
Mechanism: the carry threshold shifts harvest/replant timing, which shifts
bare-tile counts. Consequences applied here: sd_delta is honest dispersion but
not a variance-reduced pair sd; mde_80 is optimistic; n=20 screens carry no
authority; opponent_mean_delta is read only at final n.

## Registered design

Money gates, candidate `champion` with `--agent-config
'{"hand_mule_load": 20}'`, baseline `champion` at defaults, band 824000
(fresh: the operative 1000-increment band sequence tops at 823000; the
8050000 outlier ledgers from 2026-08-06 sit outside the sequence and their
seed ranges do not overlap). Seeds nested from 824000:

| tape | bar | n_seeds | seeds |
|---|---|---|---|
| zoo:tape-thunder-719 (primary) | ci_lower > $1,000 | 512 | 824000-824511 |
| zoo:tape-barnyard-719 | ci_lower > $0 | 256 | 824000-824255 |
| zoo:tape-metac95-720 | ci_lower > $0 | 384 | 824000-824383 |
| zoo:tape-mirror-719 | ci_lower > $0 | 256 | 824000-824255 |

metac95 gets 384, not 256: it is the weakest tape (observed means +1,359 at
n=64, +2,384 at n=192) and the >$0 bar at n=256 needs a true mean above
~$1,370 at the observed sd ≈ $13.3k; n=384 lowers that to ~$1,120.

## Decision rule (fixed before launch)

PROMOTE only if ALL hold:

1. ci_lower > $1,000 on thunder AND ci_lower > $0 on barnyard, metac95 and
   mirror;
2. vetoes == [] on every tape;
3. |opponent_mean_delta| <= $3,000 on every tape at final n (market-redirection
   kill, per the strawberry-closure convention; a breach makes the run invalid
   for promotion — it is a veto, never a subtrahend);
4. skew rule (verbatim from the 2026-08-16 registration): skew_delta is read
   on every tape; if any tape whose bound only just clears its bar also has
   skew_delta < -1.0, the result is reported as inconclusive, not as a pass.

Otherwise NOT promoted, recorded as "the effect does not clear the bar at the
n actually run", with the intervals — explicitly not as "labor does not
convert to money".

No extensions, no added tapes, no band changes after launch. A failure is not
re-run on another band inside this registration.

## Registered predictions

- thunder clears $1,000 (prior +1,057 at n=64; n=512 shrinks the interval).
- barnyard clears $0 with margin (prior +1,637).
- metac95 is the live risk: priors straddle its bar (-1,230 / +794). This
  registration exists because that question is open.
- mirror clears $0 (priors +370 / +677).

## Consequence of PASS

hml20 becomes a submission candidate (config-only change; the viability ledger
above already satisfies submit.py's promotion precondition at d7efe73).
Uploading is a separate HITL decision — T-2 freeze 2026-09-28, and a new
submission evicts one of the Bradley-Terry pair [M3b 55784368, M3a 55471731].
Nothing in this document authorizes an upload.

## ADDENDUM (2026-09-05, post-run): NOT PROMOTED — criterion 3 veto

Runs executed 2026-09-05T21:53-22:43Z at 75377a9 (agent source byte-identical
to d7efe73; only eval/ changed between the shas), serially, binding constraint
first, no source edits while any run was in flight.

| tape | n | mean_delta | ci_lower | bar | bar met | opp_mean_delta | skew |
|---|---|---|---|---|---|---|---|
| metac95 | 384 | +2,281.4 | +1,181.2 | >$0 | yes | -1,850.6 | +0.13 |
| thunder | 512 | +3,553.2 | +2,628.3 | >$1,000 | yes | **-3,997.2** | -0.12 |
| barnyard | 256 | +3,354.6 | +1,831.3 | >$0 | yes | -2,787.4 | -0.20 |
| mirror | 256 | +2,381.6 | +1,022.7 | >$0 | yes | **-3,927.9** | -0.13 |

Ledgers:
- eval/gates/2026-09-05T22-12-27Z-champion-vs-zoo_tape-metac95-720-money.json
- eval/gates/2026-09-05T22-27-21Z-champion-vs-zoo_tape-thunder-719-money.json
- eval/gates/2026-09-05T22-35-15Z-champion-vs-zoo_tape-barnyard-719-money.json
- eval/gates/2026-09-05T22-42-58Z-champion-vs-zoo_tape-mirror-719-money.json

vetoes == [] and blockers == [] on all four tapes.

Decision-rule application: criteria 1, 2 and 4 HOLD — the intersection-union
money bars clear on every tape, for the first time in this knob's three
registrations. Criterion 3 FAILS: |opponent_mean_delta| > $3,000 on thunder
(-3,997) and mirror (-3,928). Per the registered rule, the run is invalid for
promotion. **NOT PROMOTED.**

Recorded as hypothesis only — it arrived after the criterion fired and is not
acted on here: a replay tape cannot change its behavior in response to the
candidate, so its revenue can move only through prices and the shop roster,
and this arm carries 7/8 roster coupling (see Pairing caveat above). The
±$3,000 band was inherited from the strawberry-closure convention without
pricing that mechanism; the same arm measured thunder -2,536 / mirror -1,180
(inside the band) at n=64 on band 822000, and lands just outside at final n on
band 824000. Whether the band is too tight for a heavily-coupled arm — e.g.
whether the criterion should instead bound opponent revenue split by items the
champion actually trades — is a question for a successor registration, which
must fix its criterion before any further runs and may reuse none of this
band's data. Deciding it inside this document would be laundering a veto.
