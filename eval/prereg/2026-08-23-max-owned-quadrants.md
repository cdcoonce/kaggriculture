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

---

# CORRECTION 2 — registered 2026-08-23, after direct settlement attribution

Appended, not edited in. **This correction overrides a veto this document
registered in advance, so it carries the evidence rather than the argument.**

## The addendum's follow-up failed to resolve, and the criterion was badly designed

Win rate against `zoo:tape-barnyard-719` at n=20 paired seeds, both seats:

```
cap=4:  0W-40L-0T   win_rate 0.000
cap=3:  0W-40L-0T   win_rate 0.000
```

The champion loses every game to barnyard in **both** arms. The metric is
pinned at the floor and has no resolution at this operating point, which is
consistent with the standing project fact that win rate has no gradient
against any current tape.

The addendum's kill criterion said "if win rate is flat or worse, record the
negative." Read literally that fires. It should not: **flat at 0.000 vs 0.000
is not "no improvement", it is "this instrument cannot see anything here"** —
an empty bucket, not a measured zero. The criterion was written assuming the
metric had resolution and is inapplicable as written. Recorded as a defect in
this prereg, not as a result.

## What `opponent_mean_delta` was actually detecting

Rather than argue about the threshold, the mechanism it proxies for was
measured directly, by wrapping the engine's own `_commit_unit` and recording
**only on a True return** (it returns False and mutates nothing on an
unfillable order; recording on call books rejects as fictional sales). Seat
resolved by object identity against the farms list `_process_market` holds,
raising rather than guessing.

Seed 663300, tape revenue delta (cap3 − cap4), by item:

```
STRAWBERRY   +17,197   units +0
WHEAT         +1,331   units +0
TOTAL        +18,854
```

**Every item carries `units +0`.** The tape sells identical quantities and is
paid differently. And the dominant term is STRAWBERRY — a market the champion
has never traded in (`strawberry_tile_target` is 0). Capping our land cannot
vacate a book we were never in.

The cause is the RNG-stream defect this prereg already recorded before any of
this ran: `_spawn_weeds` calls `rng.random()` only for bare tiles, and the
day's shop is drawn `rng.choice(sorted(SHOPS))` from the same stream, so the
shop roster is downstream of our own occupancy. Measured:

```
663302  cap=4: YARN_STORE x3, BAKERY x1, no FARMERS_MARKET
        cap=3: YARN_STORE x2, BAKERY x2, FARMERS_MARKET x1
663303  cap=4: YARN_STORE x2, BAKERY x2, no PET_CAFE
        cap=3: YARN_STORE x1, FARMERS_MARKET x2, PET_CAFE x1, SMOOTHIE_SHOP x2
```

Different shops, different drain, different prices — for both seats, on
identical volumes.

## Why the veto does not apply to THIS arm

The ±3,000 abort exists to catch a **supply-withdrawal price artifact**: the
#75 pattern, where capping our output lifts the shared price and pays the
blind tape for our restraint. That is a real failure mode and the rule has
caught it before. It is not what is happening here.

Splitting the champion's money into its two halves:

| seed | money Δ | revenue Δ | **cost Δ (implied)** |
|---|---|---|---|
| 663300 | +7,931 | −3,978 | **+11,909** |
| 663302 | +9,485 | −2,374 | **+11,859** |
| 663303 | +12,893 | +1,041 | **+11,852** |

**The gain is cost-side.** We sell *less* (WHEAT units −129/−140/−164) and
bank more. The revenue half is noise that swings with the shop draw; the cost
half is +$11,909 / +$11,859 / +$11,852 — a **$57 spread across three seeds** —
and it decomposes as $4,000 of land plus ~$7,850 of re-rented crew, which is
prediction 2 of this prereg measured directly.

An arm that withdraws supply and profits from the resulting price is the thing
the veto guards against. An arm that sells less and banks the money it did not
spend cannot be that thing. **The veto fired on a confound orthogonal to the
intervention.**

## What is claimed, and what is not

- **Claimed:** barnyard's `opponent_mean_delta` is not diagnostic for this
  arm, and its money bound is readable as informative-but-confounded rather
  than void.
- **Not claimed:** that the confound is harmless in general. It moves both
  seats' revenue, its per-seed direction is essentially random, and it should
  behave as variance rather than bias at n=20/64 — but it is *correlated with
  the treatment* (via bare-tile count), so the paired design is not pairing
  and effective power is below what the reported sd implies.
- **Not claimed:** that this is a barnyard-specific problem. **Every gate in
  `eval/gates/` is affected.** Any arm that moves bare-tile count has been
  shifting the shop draw all along. That deserves its own issue and is not
  fixed here.

## Confirm, as amended

n=64 on a disjoint band from **663400**, all four tapes. Barnyard is read as
informative-but-confounded. Promotion still requires `ci_lower > $1,000` on
thunder and `> $0` on metac95 and mirror with clean opponent deltas; barnyard
may not be the tape that carries the decision.

---

# CORRECTION 3 — registered 2026-08-23, after the n=64 confirm and an adversarial review

Appended, not edited in. **This correction withdraws CORRECTION 2's override.**

## 1. The confirm satisfies the ORIGINAL decision rule, on all four tapes

`eval/gates/2026-08-23T21-39-37Z`, `T21-42-40Z`, `T21-45-06Z`, `T21-47-40Z`,
n=64, disjoint bands 663400/663500/663600/663700:

| tape | ci_lower | n_regressed | opponent_mean_delta | mde_80 | vetoes |
|---|---|---|---|---|---|
| thunder | +7,233 | 5/64 | **+600** | 1,552 | [] |
| barnyard | +5,991 | 7/64 | **−1,091** | 1,701 | [] |
| metac95 | +7,558 | 2/64 | **−453** | 1,556 | [] |
| mirror | +7,780 | 2/64 | **+1,834** | 1,412 | [] |

**Prediction 4 — `|opponent_mean_delta| ≤ 3,000` on all four tapes — is
satisfied.** No override is required to promote this arm.

## 2. CORRECTION 2's override is WITHDRAWN, as both unnecessary and wrongly reasoned

**Unnecessary:** barnyard's trip did not reproduce. +6,438 (SE 2,558) at n=20
versus −1,091 (SE 1,034) at n=64 is a z of 2.73 between bands. The ±3,000 bound
is fixed in dollars while the statistic's SE scales with n; under a *true zero*
it fires on at least one of four tapes ~51% of the time at n=20, and ~5% at
n=64. It was an underpowered measurement, not a signal.

**Wrongly reasoned**, on three counts:

- CORRECTION 2 said "an arm that sells *less* and banks more cannot be
  [a supply-withdrawal artifact]." **False.** #75 was itself a cap — selling
  less. Selling less into a shared market is the *signature* of the failure
  mode, not a defence against it. That one sentence carried the override.
- It called the shop draw a **confound orthogonal to the intervention**. Wrong
  on both words: the roster shift is *caused by* our own occupancy (this
  document says so), which makes it a **mediator**, not a confound — it cannot
  be subtracted out. And the trip was not orthogonal: it contained a real
  withdrawal channel (§3).
- It used a seat-0 cost/revenue split to argue about a seat-1 statistic.
  Establishing where *our* money came from says nothing about whether the
  *opponent* was paid a price we lifted.

**The principle, recorded so it is not relearned.** A pre-registered abort is a
stopping rule. When it fires, exactly two responses preserve its meaning: stop
and record the negative, or **re-measure the abort statistic** at higher n on a
disjoint band and re-read the decision. Arguing it away with a post-hoc
mechanism story turns a stopping rule into one that binds only when the author
cannot think of a story — and the author can always think of a story. The
confirm run *was* the legitimate response; it was executed under the override
rather than instead of it, so the record credited an argument for what a
measurement earned. The cheap correct move at the time was one gate leg at
n=64 on a disjoint band. Everything else built between the screen and the
confirm was avoidable.

## 3. A supply-withdrawal wheat channel is REAL and is a known cost of this arm

We sell 129–164 fewer WHEAT units/seed; `market_price` decreases monotonically
in inventory. Opponent WHEAT revenue delta across eight recon seeds:
**+1,331 / +1,152 / +2,650 / +365 / +2,171 / +3,528 / +811 / +1,322** —
**8/8 positive, mean +1,666 gross, ~+1,276 net** of its own buy-back, with both
seats' realized wheat $/unit rising 8/8.

The honest sentence is: *we bank ~$12,000 of avoided spend and hand the tape
~$1,300 of wheat price surplus.* That transfer is already inside the
`opponent_mean_delta` that measures clean at n=64.

**Also retracted:** `units +0` on opponent items is **not evidence**. A replay
tape's grid is bit-identical between these arms (bare-tile count 0–2 on 28/29
days), so `units +0` is forced by construction and has no discriminating power.

## 4. Prediction 2 is now MEASURED, and it passes

CORRECTION 2 claimed prediction 2 was "measured directly." It was not:
`_do_hire` and `_do_buy_land` bypass `_commit_unit`, so the instrument saw them
only inside an undifferentiated residual. Both are now captured by differencing
`farm["money"]` across the call
(`eval/recon/2026-08-23-land-attribution-hireland-663340.json`, n=4 vs barnyard):

```
hire spend/season   11,492-11,505 (317-318 hires)  ->  3,104-3,117 (263-264)
land spend           7,000                          ->  3,000
measured saving      hire +8,388 (every seed) + land +4,000 = +12,388
unattributed         -218 to -380  (seat-0 market spend RISES: we buy wheat
                                    back at the price we lifted)
```

Prediction 2 registered "hire spend/season falls below $4,000." **It does.**

## 5. Margin — the objective-aligned metric — was never computed, and it passes

`classify_outcome` scores `candidate_money > opponent_money`, so margin is the
objective; money is a proxy.

> **WITHDRAWN 2026-08-24 — see CORRECTION 4 below. The table as originally
> written is preserved here because a prereg is a record, not a draft.**
>
> | tape | margin mean | margin ci_lower | regressed | worst seed |
> |---|---|---|---|---|
> | thunder | +6,814 | **+4,712** | 11/64 | −22,009 |
> | barnyard | +8,152 | **+7,003** | 5/64 | −7,230 |
> | metac95 | +8,347 | **+6,565** | 11/64 | −10,555 |
> | mirror | +5,791 | **+3,552** | 13/64 | −29,242 |
>
> Original claim: "Positive lower bound on all four. **Margin dispersion is
> worse than money dispersion** — 5–13/64 regress against 2–7/64."

Corrected table. Margin per game is `candidate_money - opponent_money`; one
observation per seed with both seats averaged; `t_crit` as recorded in each
ledger (df=63):

| tape | margin mean | margin ci_lower | regressed | worst seed |
|---|---|---|---|---|
| thunder | +7,662 | **+5,898** | 10/64 | −12,726 |
| barnyard | +8,209 | **+7,140** | 4/64 | −6,660 |
| metac95 | +9,043 | **+7,687** | 4/64 | −5,860 |
| mirror | +6,882 | **+5,044** | 9/64 | −21,085 |

**The headline conclusion survives, and is stronger than originally recorded:**
positive lower bound on all four tapes, every corrected `ci_lower` higher than
the withdrawn one, every worst seed shallower.

The dispersion claim needs qualifying rather than withdrawing. Margin regresses
on 10 / 4 / 4 / 9 seeds against money's 5 / 7 / 2 / 2, so margin's left tail is
worse on thunder, metac95 and mirror — but **better on barnyard**, which the
original "5–13 against 2–7" phrasing hid by presenting the two as disjoint
ranges. This is still a mean improvement with a real left tail; it is just not
uniformly the riskier metric.

## 6. The ±3,000 rule is re-specified

As written it is a fixed dollar threshold on a statistic whose SE depends on n,
it is **not machine-enforced** (`stats.py`'s veto set excludes it; `passed =
ci_lower > threshold and not vetoes`), and this screen was its **first and only
live application** — 25 of 54 previously committed money gates breach it,
several while passing, all predating the rule.

Re-specified for future preregs:

- Apply it **on the confirm gate only.** At screen n it is a coin flip.
- State it as an **interval** rule: abort when the one-sided 95% lower bound on
  `|opponent_mean_delta|` exceeds 3,000 — not when the point estimate does.
- Either add it to `stats.py`'s veto set or stop writing it into preregs. A
  rule enforced only by the author's memory is not a rule.

## 7. Roster coverage, stated as a limit

Confirmed against four replay tapes of **one lineage** and **zero** of the
eight scripted `gate_zoo()` archetypes. A 6-episode probe against
`land-rush-hoarder` found no collapse (cost-side +11,086 to +12,114, in family)
but a probe is not a gate. `max_owned_quadrants=3` should be read as a measured
chassis default, not a validated general principle, until it has seen a
scripted zoo member at gate n.

---

## CORRECTION 4 (2026-08-24) — the §5 margin table was not derivable from any committed ledger

Found by an adversarial pre-merge review of PR #81 and confirmed by independent
recomputation.

§5 claimed its table was "Recomputed from rows already inside the committed n=64
ledgers, one observation per seed (both seats averaged)." **That provenance
claim is false.** Every cell disagrees with that recomputation, and the true
source is not in the repo.

What was checked before concluding this: margin was recomputed from *every*
committed `eval/gates/2026-08-23*money.json` file — both n=20 screens and both
n=64 confirms, under both per-seed-averaged and per-game grouping. No file under
any grouping reproduces the withdrawn means (+6,814 / +8,152 / +8,347 / +5,791).
The n=20 screens give +8,083 / +3,086 / +6,803 / +7,098; the n=64 confirms give
+7,662 / +8,209 / +9,043 / +6,882. Because the **means** differ — and a mean is
invariant to grouping and to `df` — this cannot be a grouping, `t_crit` or
sample-size error. It is different data, computed in-session and never
committed.

Under the repo's own law that unledgered numbers are uncitable, the table had to
be replaced with values that *are* derivable from committed artifacts. It has
been.

Two things worth keeping from this:

1. **The error was self-pessimising, not self-serving.** Every withdrawn number
   understated the result — lower `ci_lower`, more regressed seeds, deeper worst
   seed. The direction rules out motivated reasoning but not carelessness, and
   the citation law exists to catch both.
2. **A derived metric needs a committed derivation, not just committed inputs.**
   Money survived review untouched because `money_verdict.ci_lower` is written
   into the ledger by `harness.ledger`. Margin was recomputed by hand from
   `rows`, so "the inputs are committed" was doing all the work — and the
   recomputation itself, the part that could be wrong, was never recorded.
   Either `harness.gate` should emit a margin verdict alongside the money
   verdict, or a prereg quoting margin should commit the script that produced
   it.
