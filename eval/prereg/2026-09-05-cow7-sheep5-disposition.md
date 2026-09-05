# Pre-registration: cow7/sheep5 disposition — production or suppression

Date: 2026-09-05
Candidate commit: d7efe73 (no source change; config-only)
Status: REGISTERED — runs launch after this document merges; no agent source
may be edited while any registered run is in flight.

## Motivation

The 2026-08-29 descope names livestock as the kept-but-rejected half of the
standing-asset thesis, to be resumed only through a vs-shipped-default gate.
The 2026-09-03 unregistered sweep (ledgered in PR #92) ran that gate on the
config-reachable corner, head-to-head vs frozen:m3b_live_b6ce655 (n=100, band
821000):

| config | result | verdict | ledger (eval/gates/) |
|---|---|---|---|
| cow 7 | 80-120, rate 0.40 | FAIL | 2026-09-03T15-30-47Z-...-promotion.json |
| cow 7 / sheep 5 | 140-60, rate 0.70 | PASS | 2026-09-03T15-32-04Z-...-promotion.json |
| cow 8 / sheep 5 | 53-147, rate 0.265 | FAIL | 2026-09-03T15-33-23Z-...-promotion.json |
| cow 8 / sheep 6 | 61-139, rate 0.305 | FAIL | 2026-09-03T15-34-41Z-...-promotion.json |

(cow7/sheep5 and cow8/sheep6 re-verified bit-exact via rerun-ledger
2026-09-05.) The sole survivor, cow7/sheep5, never received a money confirm —
its only money evidence is an n=20 thunder screen (mean -3,193, ci_lower
-8,452; 2026-09-03T15-22-55Z-...-money.json) that is unpowered and, per the
coupling result below, uninformative.

The head-to-head money decomposition (per-game rows of the viability ledgers,
opponent = the same frozen m3b at defaults in every arm) says the win is
suppression, not production:

| arm | mean candidate $ | mean opponent $ |
|---|---|---|
| cow 7 (FAIL) | 62,180 | 62,407 |
| cow 7 / sheep 5 (PASS) | 62,100 | 60,363 |
| cow 8 / sheep 5 (FAIL) | 58,386 | 61,504 |
| cow 8 / sheep 6 (FAIL) | 56,807 | 60,505 |
| hand_mule_load 20 (contrast) | 66,907 | 63,644 |

cow7/sheep5 earns the SAME as the failing cow7 arm (~$62.1k) — zero production
gain — and wins by dragging the opponent down ~$2k (extra wool sold into the
book m3b also sells into). The cow8 arms are self-harm: their own money
collapses while the opponent holds. Suppression does not transfer to opponents
with different market exposure; production does. That is what this
registration tests.

## Viability arm (kaggriculture#91 rule)

Qualifying run ledgered: the 140-60 PASS cited above.

## Pairing caveat (kaggriculture#82)

Shop-roster coupling: cow_target 6→7 and 6→8, sheep_target 4→5 and 4→6 all
couple 8/8 draws from draw-day 2, all 6 probe seeds
(`eval/recon/2026-09-05-shop-roster-coupling-{cow,sheep}-*-822000.json`) —
the pasture zone resizes from day 0, so every draw is downstream of the arm.
Pairing is fully degraded: n=20 screens carry no authority; sd_delta honest
but not pair-reduced; mde_80 optimistic; opponent_mean_delta read only at
final n.

## Registered design

Money gates, candidate `champion` with `--agent-config
'{"cow_target": 7, "sheep_target": 5}'`, baseline `champion` at defaults,
band 825000 (fresh, disjoint from the companion hml20 registration's 824000
and from all prior bands), seeds 825000-825063 on each tape:

| tape | bar | n_seeds |
|---|---|---|
| zoo:tape-thunder-719 (primary) | ci_lower > $1,000 | 64 |
| zoo:tape-barnyard-719 | ci_lower > $0 | 64 |
| zoo:tape-metac95-720 | ci_lower > $0 | 64 |
| zoo:tape-mirror-719 | ci_lower > $0 | 64 |

n=64 per tape, matching the sweep's confirm convention: this is a disposition
test, not a promotion attempt — the registered outcome set is
{ALIVE-continue, CLOSED}.

## Decision rule (fixed before launch)

- ALIVE (proceed to a full promotion-grade registration later): ci_lower >
  $1,000 on thunder AND > $0 on the other three, vetoes == [] everywhere,
  |opponent_mean_delta| <= $3,000 everywhere at n=64, skew rule as in the
  companion hml20 registration.
- CLOSED (the config-only livestock corner is dead): any bar missed, any
  veto, or any |opponent_mean_delta| > $3,000. Closure closes the CONFIG
  corner only; the staged-purchase scale-up (kaggriculture#59 item 1:
  purchase windows COW_LAST_BUY_DAY=9 / SHEEP_LAST_BUY_DAY=11, the 2-per-turn
  buy cap, and the flat +1 husbandry hand are all hardcoded — code required)
  remains a distinct, unmeasured thesis and is not condemned by this result.

No extensions, no post-hoc rescue of a fired criterion: a breach is recorded
as the verdict; hypotheses about it are recorded only as hypotheses.

## Registered predictions

- Honest prior: CLOSED is more likely than ALIVE. The head-to-head
  decomposition above shows zero production gain, and a suppression edge has
  no mechanism against a replay tape. This registration exists to close the
  corner with a citable record — or to be surprised, which is the one outcome
  that would justify a livestock submission before 2026-09-30.
- If the tapes show a large NEGATIVE opponent_mean_delta, that is itself the
  suppression signature expressed against the tape's scripted sells and fails
  criterion 3 by construction.

## ADDENDUM (2026-09-05, post-run): CLOSED

Runs executed 2026-09-05T21:53-22:01Z at 75377a9 (agent source byte-identical
to d7efe73), serially, no source edits while any run was in flight.

| tape | n | mean_delta | ci_lower | bar | bar met | opp_mean_delta |
|---|---|---|---|---|---|---|
| thunder | 64 | -3,001.6 | -5,859.7 | >$1,000 | no | **-4,731.3** |
| barnyard | 64 | -3,601.3 | -6,510.6 | >$0 | no | -2,327.8 |
| metac95 | 64 | -2,619.4 | -4,978.6 | >$0 | no | -1,333.8 |
| mirror | 64 | -2,256.6 | -5,277.8 | >$0 | no | **-4,286.4** |

Ledgers:
- eval/gates/2026-09-05T21-53-12Z-champion-vs-zoo_tape-thunder-719-money.json
- eval/gates/2026-09-05T21-55-42Z-champion-vs-zoo_tape-barnyard-719-money.json
- eval/gates/2026-09-05T21-58-09Z-champion-vs-zoo_tape-metac95-720-money.json
- eval/gates/2026-09-05T22-00-34Z-champion-vs-zoo_tape-mirror-719-money.json

vetoes == [] on all four; barnyard fired the catastrophic_tail blocker
(diagnostic only, does not gate; n_regressed 40/64, tail_quantile -20,106).

Decision-rule application: every money bar is missed (ci_lower -4,979 to
-6,511), and |opponent_mean_delta| > $3,000 on thunder and mirror — the
registered suppression signature, expressed against tapes exactly as
predicted. **CLOSED.**

The config-only livestock corner is dead end to end: cow7, cow8/sheep5 and
cow8/sheep6 failed the head-to-head viability gate (PR #92); the sole
survivor, cow7/sheep5, loses money against every tape while dragging tape
revenue down. The registered prediction (zero production gain head-to-head,
therefore no transfer) is confirmed. The staged-purchase scale-up
(kaggriculture#59 item 1) remains a distinct, unmeasured thesis and is not
condemned by this closure.
