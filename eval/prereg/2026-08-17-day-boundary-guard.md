# Pre-registration — don't send a hand on a walk the day boundary will wipe

Written **before** any gate seed was burned, at commit `a44dc9d`.
Fixes `n`, the seed band and the decision rule in advance.

## What is being tested

Pass 2 of the dispatcher now filters candidate tasks a hand cannot both reach
and work before `_end_of_day` empties `farm["hands"]`. The farmer is exempt —
the engine respawns it rather than deleting it.

This is a **code change**, so the baseline is a frozen incumbent
(`frozen:preguard-9fb6539`, materialized from `9fb6539` via
`harness.frozen.freeze_incumbent`), not a config-only A/B.

## Mechanism, measured before the gate

Recon leg attribution, band 660800, n=6, solo vs `zoo:pass`, shipped config:

| | champion @9fb6539 | ported competitor plan |
|---|---|---|
| orphaned steps | 838 (19.3% of accounted movement) | 140 (4.9%) |
| walking share | 58.8% | 44.1% |
| productive share | 31.7% | 48.5% |

An orphaned leg is one still open at the day boundary: the unit was walking
somewhere at midnight and ceased to exist before arriving, so every step it
took bought nothing. It is a **rate**, so it is not explained by our having
more hands (14 slots) and more land (4 quadrants vs 3).

Manhattan distance is exact rather than a lower bound here: `_step_toward` is
pure axis-stepping with no obstacle avoidance.

## Disjointness, verified behaviourally and not only structurally

`assert_disjoint` checks module identity, which is not behaviour. The frozen
copy was therefore run through the same instrument, band 660800, n=3:

| | orphaned | walking |
|---|---|---|
| `frozen:preguard-9fb6539` | 838 (19.3%) | 58.8% |
| live `champion` | 646 (15.2%) | 57.4% |

The frozen arm reproduces the pre-change signature exactly. It is the old
agent, not a mirror of the new one.

## The mechanism worked and the money did not follow

Same band, n=6, solo vs `zoo:pass`, before → after:

| | before | after |
|---|---|---|
| orphaned steps | 838 (19.3%) | 638 (15.1%) |
| walking | 58.8% | 57.4% |
| **idle** | **4.1%** | **5.1%** |
| productive | 31.7% | 31.9% |
| money | 87,356 | 82,368 |

**The freed turns became idle, not productive.** Removing waste did not create
output. Money reads about 5k lower, and about 11.8k lower on the n=3 frozen
comparison above — at n=6 unpaired against a ~12k money sd both are noise in
either direction, but neither is evidence of a gain.

Only about 200 of the ~700-step gap closed. The residue is expected to sit in
channels this guard deliberately does not cover: `_mule` walks and the
nobody-idles fallback are movement no task filter sees, the farmer is exempt,
and `needs_carry` legs route via the shed so their real journey is longer than
the straight-line distance compared against.

## Predicted outcome, stated in advance

**I expect this screen to fail.** The mechanism check shows the intended
behaviour change with no output to show for it and a money reading that is
flat-to-negative. It is registered and run anyway because solo-vs-`pass`
already proved a poor instrument once this session — it ranked
`wheat_rush_tiles` arms that the tape screen then contradicted — and because a
ledgered answer is worth more than a hunch either way.

If it fails, the honest conclusion is **"orphaned walking is real waste that
this guard removes without converting it to money"**, not "the measurement was
wrong". A pass would be the surprise and should be treated with suspicion, and
confirmed before it is believed.

## Fixed design (locked before launch)

| stage | tape | threshold | n | seeds |
|---|---|---|---|---|
| screen | thunder-719 (primary) | > $1,000 | 20 | 660900-660919 |

Band 660900 is disjoint from every band burned to date (through 660805).

**Confirm runs only if the screen returns `ci_lower > $1,000`**, at n=128 on
band 661000-661127 across all four tapes. **No band is extended after a result
is seen.** If the screen lands inside its own noise band, the reported answer
is the interval, not a re-run.

Given the dispersion actually observed on this session's other screens
(15,098 and 19,417 against a predicted 4,086), n=20 detects roughly +6,800 or
better and nothing smaller. That number, not the $1,000 bar, is the real
sensitivity of this run, and it is recorded here so a null is read as a power
limit rather than as a measured absence.

## Decision rule (per `eval/README.md`, unchanged)

PROMOTE only if all hold: `ci_lower > 1000` on thunder **and** `ci_lower > 0`
on barnyard, metac95 and mirror; `vetoes == []` everywhere; and `skew_delta`
read on every tape — any tape that only just clears its bar while
`skew_delta < -1.0` is reported **inconclusive**, not passed.

`n_regressed`, `opponent_mean_delta` and `skew_delta` are read before the bound.

## Standing operational hazard

The gate resolves `champion` from the **live working tree** and builds a fresh
worker pool per arm. **No agent source is edited while this run is in flight.**
