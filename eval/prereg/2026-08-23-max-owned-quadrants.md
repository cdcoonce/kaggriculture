# Pre-registration — stop buying the SE quadrant

Written **before** any gate seed was burned, at commit `d8f0617`.
Fixes `n`, the arms, the seed band and the decision rule in advance.

## What is being tested

Whether capping owned land at three quadrants — buying NE and SW, refusing
SE — raises banked money, via `PolicyConfig.max_owned_quadrants`.

## Why this is on the table at all

Land has been priced as a one-off purchase everywhere in the chassis. It is
not. Two engine facts make a quadrant a **recurring** cost:

- `_end_of_day` empties `farm["hands"]`. Hands are daily rentals, so the
  whole fibonacci hire ladder is re-paid every morning.
- `hands_target = round(active_tiles / 8) + husbandry`, so owning more tiles
  permanently enlarges the crew that gets re-hired.

`fib(0..9)` is $143/day for 10 hands; `fib(0..12)` is $609/day for 13. SE
takes the champion from 10 hands to 13, so its real price is $4,000 **plus a
standing charge measured at ~$466/day, ~$8,388/season** — roughly three times
its sticker price. The reference tape `tape-thunder-719` never buys SE; the
champion buys it on day 12, hour 1, on 20 of 20 seeds sampled.

This arm was reached by elimination, not by preference. The two hypotheses it
displaces were both run as dials and both failed:

- **Portfolio.** `melon_tile_target` 8 → 32 raises melon volume 96 → 160.5
  and *lowers* money 61,374 → 56,486, with the $1-floor share climbing
  25.8% → 40.8%.
- **Routing.** `wheat_rush_tiles` 81 → 12 removes 302 crop-ACT turns and
  leaves total unit-turns unchanged (7,679 → 7,714); ACT share *falls*
  36.57% → 33.60%. Freed turns became overhead, not output.

## What is explicitly NOT being tested

- **A crew knob.** Cutting the crew while keeping all four quadrants measured
  **−$12,889 with 5/6 seeds regressed**. Crew sizing must stay keyed to owned
  tiles; the error is owning the tiles, not the sizing rule.
- **`crew_reserve_dollars`.** Refuted before it was written: the ladder
  completes 317–318 hires/season and misses its target on exactly one day
  (day 3, one hire, `fib(5)` = $8). A $600 reserve measured −$14,866 with 5/6
  regressed, because `hands_target` never consults budget — withholding cash
  delays land, which shrinks `active_tiles`, which shrinks the crew.
- **`max_owned_quadrants=2`.** Measured worse (+3,580 vs +8,042 at 3), 2/6
  regressed, and `opponent_mean_delta` +$5,818 — outside the price-artifact
  band. Two is not on the arm list.

## The code change under test

`PolicyConfig.max_owned_quadrants: int = MAX_OWNED_QUADRANTS` (=4), gating
`plan._next_quadrant`. The default is a **provable** no-op, not an asserted
one: the board has four quadrants and `_next_quadrant` already returns None
once all four are held, so the guard cannot fire on the shipped path.

## Predictions, registered in advance

All on days 10–28, arm A1 (`max_owned_quadrants=3`) against the frozen
incumbent, unless stated.

1. **Owned land 94.7 → 73.7**, with SE locked all season. *(If not, the knob
   does not bind.)*
2. **Hire spend/season 11,501 → below $4,000.** *(This is the claimed
   mechanism. If hire spend does not fall, the money is coming from somewhere
   else and the stated rationale is wrong even if the bound clears.)*
3. **Bare unlocked ground falls below 33** (from 40.6). Absolute standing crop
   is expected to FALL (43.6 → ~32) and that is not a failure — occupancy is
   measured at `corr(wheat tile-days, final money) = −0.948` and is not the
   objective.
4. `|opponent_mean_delta| <= 3,000` on all four tapes.
5. Money: `ci_lower > $1,000` vs thunder and `> $0` vs barnyard, metac95 and
   mirror, `vetoes == []`.

Prediction 2 is the one that separates a real mechanism from a lucky bound.

## Gate protocol

- **Frozen incumbent required** — this is a code change. Frozen from `18f9de3`
  as `frozen:m3-preland-18f9de3`, and verified **behaviourally**, not by
  `assert_disjoint` alone: it reproduces owned 94.7 / standing 43.2 / bare
  39.5 / weed 1.1 / SE locked 3.9 at seed 663000 vs `zoo:tape-thunder-719`,
  bit-matching the post-change champion at default on the same seed. Module
  identity is not behaviour (see kaggriculture#73).
- **Screen** n=20. **Confirm** the surviving arm at n=64 on a **disjoint** band.
- **Bands.** 661000–661999 and 662000–662199 are burned by the M3 recon;
  663000 is burned by the behavioural verification above. Screen from
  **663100**; confirm on a disjoint band starting **663300**.
- **Arms.** `max_owned_quadrants` ∈ {4, 3}. Arm A0 (=4) is the no-op proof and
  must come back **bit-exact** (`sd_delta` 0 on every seed); if A0 is not
  bit-exact the knob is wrong and the screen stops there.
- **Tapes.** thunder, barnyard, metac95, mirror. Thunder and barnyard are
  non-negotiable: every arm measured in this project so far has flipped sign
  between them.
- **Decision rule.** Intersection–union: `ci_lower` > $1,000 on thunder and
  > $0 on barnyard, metac95 and mirror, no vetoes.
- Read `opponent_mean_delta`, `n_regressed` and `skew_delta` **before** the
  bound, every time.
- **Predict power from this arm's own `sd_delta`**, not a neighbour's.
  Dispersion is arm-specific.

## Kill criteria

Stop and record a negative rather than widening the search if:

- Arm A0 is not bit-exact against the frozen incumbent.
- Hire spend/season does not fall below $4,000 at arm A1 (prediction 2).
- `opponent_mean_delta` exceeds ±3,000 — the result is a price artifact and
  the money is not ours to claim.
- The bound clears on thunder but fails on barnyard. That is the known sign-flip
  signature, not a reason to add tapes until one passes.

## What this does not establish

- **It does not decompose the bundle.** Dropping SE bundles (i) −$4,000 land,
  (ii) ~−3 hands, (iii) the wheat zone shrinking 81 → 57 tiles. Arm C above
  rules out (ii) *alone* as the mechanism, but (i) and (iii) are **not
  separated** and this gate will not separate them.
- **It does not validate the M3 numbers.** Every figure quoted in this document
  comes from ad-hoc scratch scripts, not from `harness.money_gate`, and has no
  ledger under `eval/gates/`. Under the citation law they are reproducible, not
  citable. This prereg cites them as *motivation*, and nothing here may be
  restated as established until this gate's own ledger exists.

## Known methodology defect, recorded not hidden

**Seeds do not pair arms in this engine.** `_spawn_weeds` calls `rng.random()`
only for `None` tiles, and the day's shop is then drawn `rng.choice(sorted(SHOPS))`
from the same stream — so the town roster is downstream of our own tile
occupancy. Measured at seed 662150: melon=8 → 1 YARN_STORE, melon=24 → 0,
melon=32 → 3, and YARN_STORE is the only wool consumer.

Any arm that changes tile occupancy therefore changes the shop draw, and
"paired" deltas across arms are unpaired differences wearing a paired label.
This arm changes occupancy by construction (43.6 → ~32 standing), so it is
squarely affected. This does not invalidate the gate — the comparison is still
a valid randomized contrast — but the reported `sd_delta` is honest dispersion,
**not** a variance-reduced pair sd, and the effective power is lower than a
paired design would suggest. Applies to every prior gate in `eval/gates/` too.

---

# ADDENDUM — registered 2026-08-23, AFTER the n=20 screen, BEFORE the follow-up

Appended, not edited in. This is a **post-hoc instrument change** and is
labelled as one.

## What happened

The screen returned PASS on all four tapes with no vetoes:

| tape | mean Δ | ci_lower | n_regressed | opponent_mean_delta |
|---|---|---|---|---|
| thunder | +7,920 | +5,962 | 1/20 | **−164** |
| barnyard | +9,524 | +7,593 | 0/20 | **+6,438** |
| metac95 | +7,752 | +5,560 | 2/20 | +949 |
| mirror | +9,650 | +7,662 | 1/20 | +2,551 |

Barnyard's `opponent_mean_delta` of +6,438 exceeds the ±3,000 abort this
document registered in advance. Its bound is therefore **void and not
readable**, and the intersection–union rule — which requires barnyard — cannot
be completed. The screen is **not passed as written**.

A0 was bit-exact (mean_delta 0.0, sd_delta 0.0, 0/20 regressed), so the knob
itself is confirmed inert at default.

## What is being added, and why it is not tape-shopping

The prereg already forbids "adding tapes until one passes." This is **not**
that: no tape is added or dropped. What changes is the **metric on the tape
whose money metric is registered-void**.

The justification is that absolute money is not the competition's objective.
The season ladder is W/L Elo and the final ranking is a one-shot
Bradley-Terry tournament — both are *relative*. A price artifact that enriches
both players by different amounts may leave the win/loss outcome untouched, or
may not; money cannot tell us which, and subtracting the tape's money to find
out is invalid (`opponent_mean_delta` is a veto, not a subtrahend).

Win rate answers the question money cannot: **at cap=3, do we beat barnyard
more often than at cap=4?**

## The follow-up, registered in advance

- **Instrument.** `harness.gate.run_gate`, W/L/T over paired seeds, both seats.
  Not `harness.strength_gate` (that is a crash-only CI smoke gate).
- **Arms.** `max_owned_quadrants` ∈ {4, 3}, both against
  `zoo:tape-barnyard-719`, identical seeds.
- **Band.** n=20 paired seeds (40 games/arm) from **663200**. Bands through
  663199 are burned.
- **Prediction, registered before running.** Win rate at cap=3 is **strictly
  greater** than at cap=4. If cap=3 wins *no more often* than cap=4 despite
  banking +$9,524 more, the barnyard money gain was a shared-price artifact
  in full and the arm does not survive on this tape.
- **Kill criterion.** If win rate is flat or worse at cap=3, record the
  negative and do not promote on the three clean tapes alone. A lever that
  banks money without winning more games is not a ladder lever.

## What this addendum cannot fix

It does not un-void the barnyard money reading, and it does not convert the
other three tapes' money bounds into win-rate evidence. If win rate improves,
the honest claim is "three clean money tapes plus a win-rate confirmation on
the fourth," not "four clean money tapes."
