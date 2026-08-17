# Pre-registration — capping `wheat_rush_tiles` below its 81-tile default

Written **before** any gate seed was burned, at commit `01a5123`.
Fixes the arms, `n`, the seed bands and the decision rule in advance.

## What is being tested

Config-only A/B: candidate `champion` with `{"wheat_rush_tiles": N}` against
baseline `champion` at defaults (`wheat_rush_tiles = 81`), both at HEAD, one
code version differing by one `PolicyConfig` argument. No frozen incumbent is
required.

## Mechanism, measured before any gate was run

Solo-vs-`zoo:pass` profiling of the champion against a ported competitor plan
(`zoo:kernel-sokolovsky-2883`), 3 seeds, band 660200:

| | champion | kernel |
|---|---|---|
| wheat produced | 852 | 594 |
| wheat quoted sale price | 28.9 | 41.9 |
| implied wheat revenue | ~24.7k | ~24.9k |

**43% more wheat production for the same revenue.** `MARKET_PARAMS["WHEAT"]`
gives the reason directly: `T = 400`, `above_func = "log"`, `above_target = 0.2`
— price decays logarithmically once inventory passes the threshold, toward 0.2x
base. Wheat is the crop with the worst saturation curve on the board, and
`_WHEAT_RUSH_TILES_DEFAULT = 100 - 1 - 8 - 10 = 81` allocates all remaining
tiles to it. The hypothesis is that the marginal wheat tile earns approximately
nothing, so capping the zone frees tiles and unit-turns at little revenue cost.

This is a hypothesis about the **marginal** tile. It does not predict that less
wheat is better without limit: below some cap the fixed wheat obligations
(feed reserve, early cash) must bind.

## Prior art — this knob has been screened once, and it failed

`eval/gates/2026-08-16T14-58-20Z-champion-vs-zoo_tape-thunder-719-money.json`
— `{"wheat_rush_tiles": 40}`, thunder-719, band 300000, n=20:

| mean_delta | median | sd_delta | ci_lower | n_regressed | skew | vetoes |
|---|---|---|---|---|---|---|
| +740.75 | +235.0 | 4,085.97 | **-839.07** | 9/20 | +1.48 | none |

FAIL against the $1,000 bar. No confirm run, and no other tape has ever been
run for this knob. `git log --all --grep=wheat_rush_tiles` is empty.

That run is not being re-litigated. It tested `40`; the arms below are `30` and
`20`, which have never been measured against any tape.

## Arm selection, and why it is weak

Arms were shortlisted on a solo-vs-`zoo:pass` probe, which is **a poor
instrument for this knob** and is reported here rather than relied upon.

Unpaired means, n=8, band 660400 (`vs 81` column):
`70 +52`, `60 +146`, `50 -1,320`, `40 -4,663`, `30 +1,998`, `20 +6,512`.

Paired per-seed deltas, n=16, band 660500:

| `wheat_rush_tiles` | mean_delta | sd_delta | ci_lower | n_regressed |
|---|---|---|---|---|
| 30 | +5,851 | 16,828 | -1,524 | 6/16 |
| 24 | +2,181 | 18,428 | -5,895 | 8/16 |
| 20 | +3,618 | 19,414 | -4,890 | 8/16 |
| 16 | -63 | 20,848 | -9,199 | 9/16 |
| 12 | +2,268 | 17,184 | -5,263 | 7/16 |

**No arm clears zero.** `sd_delta` against `pass` is 17-21k, versus the 4,086
this same knob showed against thunder — pairing quality is arm- *and*
opponent-specific, and `pass` desyncs the shared RNG stream badly enough that
the solo probe cannot rank these arms. The unpaired `20 +6,512` is not
reproduced by the paired estimate (`+3,618`, `ci_lower -4,890`) and is treated
as noise.

The screen is therefore doing the real selection work, not the probe. Recording
this in advance so a screen result is not later described as confirming a
prediction the probe was too weak to make.

## Fixed design (locked before launch)

Two arms are screened. **The multiplicity is declared here rather than hidden**:
screening two arms and reporting the winner inflates the screen-level false-pass
rate, which is exactly what the disjoint-band confirm exists to absorb. No third
arm will be screened on the basis of these results.

| stage | arm | tape | threshold | n | seeds |
|---|---|---|---|---|---|
| screen A | `wheat_rush_tiles: 30` | thunder-719 | > $1,000 | 20 | 660600-660619 |
| screen B | `wheat_rush_tiles: 20` | thunder-719 | > $1,000 | 20 | 660700-660719 |

Every band is disjoint from every band burned to date (through 660515, plus
660000-660011 and 660100 earlier this session).

**Confirm runs only for an arm whose screen returns `ci_lower > $1,000`.** If
both screens clear, the arm with the higher `ci_lower` is confirmed and the
other is dropped without further seeds.

| stage | tape | threshold | n | seeds |
|---|---|---|---|---|
| confirm | thunder-719 (primary) | > $1,000 | 128 | 661000-661127 |
| confirm | barnyard-719 | > $0 | 128 | 661000-661127 |
| confirm | metac95-720 | > $0 | 128 | 661000-661127 |
| confirm | mirror-719 | > $0 | 128 | 661000-661127 |

n=128 is twice the documented confirm size. At the 4,086 `sd_delta` this knob
showed historically it gives stderr ~361; at the 13-16k other arms have shown it
gives stderr ~1,150-1,410.

**No tape and no arm gets additional seeds after its result is seen.** If a
screen or a tape lands inside its own noise band, the reported answer is the
interval, not a re-run.

## Predicted outcome, stated in advance

The prior `40` screen returned `+741` with `sd_delta` 4,086. If the true effect
at `30`/`20` is of similar magnitude, n=20 gives stderr ~914 and `ci_lower`
~ mean - 1,580 — meaning **a real effect below about +2,600 will fail this
screen.** A screen failure should therefore be read as "not detectable at n=20",
not as "the marginal wheat tile is valuable". Stating this now so that a null is
not re-interpreted after the fact, and so that a near-miss does not attract an
unregistered extra band.

## Decision rule (per `eval/README.md`, unchanged)

PROMOTE only if all hold: `ci_lower > 1000` on thunder **and** `ci_lower > 0` on
barnyard, metac95 and mirror; `vetoes == []` everywhere; and `skew_delta` read on
every tape — any tape that only just clears its bar while `skew_delta < -1.0` is
reported **inconclusive**, not passed.

`n_regressed`, `opponent_mean_delta` and `skew_delta` are read on every run
before the bound, per the standing rule.

## Standing operational hazard

The gate resolves `champion` from the **live working tree** and `run_money_gate`
builds a fresh worker pool per arm, so editing `packages/agent/**` mid-run can
hand the two arms different code. **No agent source is edited while any of these
runs are in flight.** A prior session discarded a 768-seed confirm for exactly
this.

> ### CORRECTION (appended after both screens returned, before any interpretation was written down)
>
> **The power prediction above was wrong, and wrong in a way this prereg had
> already warned itself about.** It predicted `sd_delta ~ 4,086` by carrying over
> the `40`-arm run's dispersion, one paragraph after stating that pairing quality
> is arm- and opponent-specific. Observed:
>
> | screen | arm | band | mean_delta | median | sd_delta | ci_lower | mde_80 | n_reg | skew | opponent_mean_delta | vetoes | verdict |
> |---|---|---|---|---|---|---|---|---|---|---|---|---|
> | A | 30 | 660600 | -270.3 | -5,744.3 | 19,416.6 | **-7,777.6** | 11,245.3 | 12/20 | +0.48 | +5,311.0 | none | FAIL |
> | B | 20 | 660700 | +4,745.4 | +5,575.0 | 15,097.5 | **-1,092.0** | 8,743.9 | 8/20 | +0.14 | +18,264.6 | none | FAIL |
>
> Ledgers: `eval/gates/2026-08-17T01-29-29Z-...json`,
> `eval/gates/2026-08-17T01-30-47Z-...json`.
>
> Actual `sd_delta` was 3.7-4.8x the predicted 4,086, so the real detectable
> effect at n=20 was ~+13,900 (arm 30) and ~+6,838 (arm 20), not the ~+2,600 this
> document predicted. **Both screens were far more underpowered than registered.**
>
> **Neither arm is promotable, and no confirm run is launched** — the registered
> rule requires `ci_lower > $1,000` at the screen and neither cleared. Per the
> "no additional seeds after a result is seen" rule, no band is extended.
>
> **Arm 30 is a measured negative**, not merely undetected: `mean -270` with
> `median -5,744` and 12/20 seeds regressed.
>
> **Arm 20 is undetected, not absent.** Its `+4,745` sits below its own run's
> `mde_80` of 8,744, so this is a power failure and must not be written up as
> "the marginal wheat tile is valuable" or as "capping wheat does not help". The
> honest statement is the interval: one-sided 95% lower bound **-1,092**.
>
> **A finding that outranks the bound itself.** Arm 20's `opponent_mean_delta` is
> **+18,264.6** — the blind tape earned $18.3k more against the capped candidate
> than against the default, while the candidate gained $4.7k. Withdrawing wheat
> supply lifts the shared price and hands most of the benefit to an opponent that
> sells wheat unconditionally. `opponent_mean_delta` on arm 30 is +5,311, the same
> sign. Whatever this knob is doing, it is moving the market price far more than
> it is moving our own conversion, and it pays the opponent roughly 4:1 against
> us. That is an argument against re-screening this knob at higher `n` even though
> arm 20 is formally undetermined — the effect being chased is a price artifact,
> not the conversion gain the mechanism section hypothesized.
