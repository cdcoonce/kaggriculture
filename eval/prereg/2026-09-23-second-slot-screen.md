# Pre-registration: the second-slot screen — is anything better than STACK3?

Date: 2026-09-23
Candidate: `champion` at `main` = `e682db4`, where STACK3 has been the shipped default since #174. Every
arm is a single `--agent-config` override on top of it. **No new agent code.**
Status: REGISTERED. Runs launch only after this document has merged.
Authorization: owner decision 2026-09-23 ("continue working to improve the competitor"), made
after the STACK3 upload (Kaggle 56508116).
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## What the next upload replaces

The latest two uploads are now **56508116 (STACK3, `4d97638`)** and **56088917 (`a344ab1`)**.
The next upload evicts `a344ab1`. `main` at the *old* defaults is behaviourally identical to
`a344ab1`. That was verified on 2026-09-23: every knob added since `a344ab1` is a no-op at its old
default, and 16 of 16 seeded games against frozen M3b produced identical banks for both players.
So the bot in the slot is exactly the shipped default that STACK3 already beat by
**+$3,401 (LB +$2,357)** at band 893000 (#170).

That makes a **second copy of STACK3** the standing candidate for this slot. It needs no further
measurement, because STACK3 vs `a344ab1` has been measured. A new arm is worth uploading instead only
if it beats **STACK3 itself**. That is the only question this document asks.

The baseline is `champion`, which is the shipped default. So the #91 control ("run the
non-default configuration against the shipped default") is built into the design here instead of
being a separate step.

## Arms

Five arms. Each changes one knob on top of STACK3. None has been measured on top of STACK3,
except where noted.

| arm | `agent_config` | occupancy | why it is here |
|---|---|---|---|
| `EH1` | `{"extra_hands": 1}` | no | The only knob ever measured *inside* the stack: S3EH1 − S3 = **+$1,282** at band 888000, n=64 (`eval/prereg/2026-09-19-labor-inside-the-stack.md`). Real but about a fifth of the old promotion bar. Non-occupancy, so it is well paired. |
| `RESCUE` | `{"rescue_water": true}` | weakly | #140 measured **102–113 missed-water deaths per 4 games in strawberry-heavy configs**, against 47 at the old defaults, and STACK3 is strawberry-heavy. The n=2 mechanism probe lost money on the old defaults, and it attributed the loss to labor at `max_hires_per_turn=4`. STACK3 hires up to 10. It has never been screened on its own. |
| `CUT14` | `{"strawberry_plant_cutoff_day": 14}` | yes | Added in #160 to tune the day-12 strawberry planting window, and never gated. The leaders keep planting strawberries into the second week. |
| `W30` | `{"wheat_rush_tiles": 30}` | yes | ALIVE and never confirmed: rate 0.860 (ci_lower 0.805) against frozen M3b at band 835000, but NOT PROMOTED at 836000. On top of STACK3 it frees crew from wheat throughput for the strawberry zone, which is the labor-exhaustion diagnosis. |
| `COW8` | `{"cow_target": 8}` | yes | The one #59 lever left: the kernel runs **8 cows by day 8**, and we run 6. The prior is negative: cow7/sheep5 lost $2.3k–$3.6k on tapes (`eval/prereg/2026-09-05-cow7-sheep5-disposition.md`), but that was under COW-first ordering and 4 hires per turn. It is included so that the lever is either measured or retired before the season ends. |

Arms were chosen before any data, from the 2026-09-23 knob inventory. `SHEEP1` and the strawberry
target are already inside STACK3. The labor-supply knobs beyond `extra_hands: 1` were closed
negative (EH2 −$3,545). The replacement-form strawberry arms were closed strongly negative.

## Pre-flight: a positive control, read before the screen

On 8 seeds at band 896000–896007, each arm must show `sd_delta > 0` against `champion`. An arm
whose own-bank series is identical to the baseline's has not been measured. **A failed
pre-flight is an INVALIDITY for that arm, not a result.** This matters most for `W30` and `COW8`,
because a cap that never binds under STACK3 would read as a clean zero.

For each occupancy-moving arm (`CUT14`, `W30`, `COW8`), and for `RESCUE`, run
`tools/recon-scripts/shop_roster_coupling.py` at the screen seeds 896000–896007 against
`public:sokolovsky-v12` and record `coupled_draws`, as `eval/README.md` requires. This is reported,
not gating. A coupled arm's result is directional, and its se is honest dispersion.

## Registered design

Gate: `harness.money_gate`, candidate `champion` with the arm's config, baseline `champion` (no
override), against each of `public:sokolovsky-v12`, `public:rayk-v11`, `public:kaito-v4`.

- **Screen:** band **896000**, n = **128** seeds per leader, all five arms.
- **Confirm:** the selected arm only, band **897000**, n = **256** per leader.

Bands 896000 and 897000 appear in no ledger in `eval/gates/`, no recon record, and no file in the
repo (checked at `e682db4`). 895000 is taken by the STACK3 promotion gate (`d62db8f`).

## Decision rule (fixed before launch)

Per arm and leader *i*, take `mean_delta_i` and `stderr_i` from the ledger. Pool them as the simple
mean, with pooled se `sqrt(sum stderr_i²)/3`. The ledger's `passed` field is not the verdict. The
pooled MDE is `mde_multiplier * pooled se` (see #164).

**Margin, with an interval, for the first time.** The ledger stores per-game `candidate_money`
and `opponent_money` for both the candidate and the baseline rows. Per leader *i* and seed *s*,
the paired margin delta is `(cand_own − cand_opp) − (base_own − base_opp)`, averaged over the two
seat orders of that seed when both are present. Take its mean and se over seeds, and pool across
leaders exactly as own bank is pooled. This addresses the gap #170 recorded, where STACK3's margin
against the shipped default (−$585) had no interval.

**INVALID** if any of these hold:

- the engine is not 1.32.7;
- an arm fails its pre-flight;
- any run records a crash-type veto (`candidate_crash`, `baseline_crash`, `opponent_crash`,
  `canary_crash`);
- any run records a `baseline_degenerate` or `opponent_degenerate` veto.

A `candidate_degenerate` veto is a result.

**SCREEN: an arm is SELECTABLE** only if, at band 896000:

- pooled own-bank delta **> $0**;
- pooled one-sided 95% lower bound **> −$500**;
- no single leader's point estimate is below **−$2,000**.

**SELECTION:** among selectable arms, take the highest pooled one-sided 95% lower bound. If no arm
is selectable, the experiment ends at NOT CONFIRMED and there is no confirm run.

**CONFIRMED** only if the selected arm, at band 897000 with n=256, meets all three:

- pooled own-bank one-sided 95% lower bound **> $0**;
- no single leader's point estimate below **−$2,000**;
- the pooled margin delta's one-sided 95% **upper** bound is **not below $0**.

The last condition is a veto only when margin is *confidently* worse. It is there because STACK3
showed that own bank can grow the market without winning it.

**NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold change after launch.
A screen/confirm disagreement is a NOT CONFIRMED and never grounds for a third band.

REPORTED, NOT GATING: per-leader own-bank and margin deltas for every arm, pooled MDE,
`coupled_draws`, and each arm's candidate-degenerate count.

## Predictions, recorded before data

- `EH1`: **−$500 to +$2,000**. P(selectable) = 0.50.
- `RESCUE`: **−$1,500 to +$2,500**, wide because the mechanism is large and the labor cost is
  unknown at 10 hires. P(selectable) = 0.40.
- `CUT14`: **−$1,500 to +$1,500**. P(selectable) = 0.30.
- `W30`: **−$2,500 to +$1,500**. P(selectable) = 0.30.
- `COW8`: **−$3,000 to +$1,000**. P(selectable) = 0.20.
- P(at least one arm selectable) = **0.80**.
- P(the selected arm is CONFIRMED) = **0.40**, lower than the terminal freeze's 0.55 because the
  baseline is now the strongest configuration this project has, and the likely effect sizes are
  about $1k.
- P(the experiment ends CONFIRMED) = **0.32**.
- The most likely failure mode, named in advance: the max of five screened arms clears on a point
  estimate near +$1,000–$1,500 that is mostly selection. The confirm then regresses toward zero,
  and its lower bound lands below $0. P = 0.35.

## Consequences

- **CONFIRMED:** licenses **an owner decision** to upload the arm's build into `a344ab1`'s slot.
  The pair would then be {arm, STACK3}. That upload waits for the 2026-09-27 STACK3 revert check
  recorded in `eval/submissions/sub-56508116.json`, because uploading evicts `a344ab1`, which is
  that check's comparator.
- **NOT CONFIRMED:** the slot question reverts to **a second copy of STACK3 vs keeping `a344ab1`**.
  That is an owner decision too, with #170's +$3,401 and the live 09-27 record as its evidence.

Nothing in this document authorises an upload.

## ADDENDUM — VERDICT (2026-09-24): W30 is CONFIRMED

Run at `main` = `7d11abf` (the commit this document merged as — a documentation-only add, so the
candidate is behaviourally `e682db4`, shipped STACK3). Engine 1.32.7, clean worktree throughout
(`/private/tmp/.../scratchpad/wt-screen`, branch `eval/second-slot-verdict`), verified before the
first run and unchanged until every gate below was ledgered. No crash-type veto and no
`baseline_degenerate`/`opponent_degenerate` veto in any of the 21 money-gate runs (15 screen + 3
confirm + the 3 cited `#170` cross-check ledgers). No `candidate_degenerate` veto either — every
result below is a genuine measurement, not a vetoed run reported anyway. Total wall time for all
money-gate and coupling-probe runs: **~1h50m** (first ledger 01:53:29Z, last 03:43:05Z), plus
setup/analysis; all screen/confirm calls ran strictly sequentially, arm by arm, at the harness's
default worker count.

### Pre-flight (positive control) — PASSED for all five arms

Per the terminal-freeze precedent's actual method (reproduced and confirmed by recomputing its
recorded `sd_delta` values from the raw ledgers before trusting the shortcut here): the pre-flight
reuses seeds 896000–896007 from each arm's own **sokolovsky-v12** screen run rather than firing a
separate call — cheaper, and it writes no additional ledgers.

| arm | `sd_delta` (8 seeds, vs sokolovsky-v12) | result |
|---|---|---|
| EH1 | $19,285.8 | PASS |
| RESCUE | $16,179.0 | PASS |
| CUT14 | $4,053.4 | PASS |
| W30 | $6,736.1 | PASS |
| COW8 | $19,666.0 | PASS |

No arm's series was identical to the baseline's. All five express and none is INVALID on this
ground.

### Coupling probes (896000–896007 vs public:sokolovsky-v12) — reported, not gating

`EH1` is excluded per the prereg's own table (non-occupancy-moving).

| arm | coupled draws (mean/8) | range | note |
|---|---|---|---|
| CUT14 | 3.6 | [2, 4] | first divergence mostly day 14; comparable to the README's `max_owned_quadrants` worked example |
| W30 | 4.25 | [2, 5] | |
| RESCUE | 8.0 | [8, 8] | fully coupled on every seed — watering changes bare-tile counts from day 1 onward |
| COW8 | 7.0 | [7, 7] | uniformly 7/8 across all seeds |

RESCUE and COW8 are the two most heavily coupled arms measured in this project to date (matching
or exceeding STACK3's 7.9–8/8). Their screen `sd_delta` is honest dispersion but not
variance-reduced; this is noted, not treated as a caveat that would change their (already
decisively negative) screen results below — see the Pairing limitation in `eval/README.md`.

### Screen — band 896000, n=128/leader, all five arms

| arm | sokolovsky | rayk | kaito | pooled Δ (se) | one-sided 95% LB | pooled `mde_80` | pooled margin (se) | margin UB |
|---|---|---|---|---|---|---|---|---|
| EH1 | +$403 | +$962 | +$924 | +$763 ($783) | **−$525** | $1,958 | +$1,566 ($541) | +$2,457 |
| RESCUE | −$4,549 | −$9,614 | −$9,821 | **−$7,995** ($1,013) | −$9,661 | $2,533 | −$15,032 ($920) | −$13,519 |
| CUT14 | −$241 | +$364 | +$309 | +$144 ($248) | −$263 | $619 | +$277 ($166) | +$549 |
| W30 | +$684 | +$411 | +$145 | +$413 ($373) | −$200 | $933 | +$38 ($242) | +$436 |
| COW8 | −$10,401 | −$11,860 | −$11,851 | **−$11,370** ($991) | −$13,001 | $2,479 | −$17,380 ($1,283) | −$15,270 |

Applying the SCREEN rule mechanically (pooled Δ > $0; pooled one-sided 95% LB > −$500; no leader
below −$2,000):

- **RESCUE** fails on pooled Δ (−$7,995 < $0). Not selectable. Consistent with the prereg's own
  mechanism note — 10 hires, not 4, and the missed-water-death mechanism did not pay for itself.
- **COW8** fails on pooled Δ (−$11,370 < $0). Not selectable, and it is the worst result measured
  in this project's history against the public panel — consistent with the prior negative
  disposition (cow7/sheep5, −$2.3k to −$3.6k) generalizing rather than reversing.
- **EH1** clears pooled Δ (+$763 > $0) and every per-leader floor, but its pooled one-sided 95%
  LB is **−$525.36**, which does **not** clear the −$500 bar — a $25 miss. EH1 is **not
  selectable**, despite the highest screen point estimate of the two knobs that do clear. This is
  the finding worth flagging: EH1 was the closest of the two failures to selectability, and it
  failed on the LB threshold, not the sign.
- **CUT14** and **W30** both clear all three SCREEN criteria. **SELECTABLE: {CUT14, W30}.**

**SELECTION: W30**, highest pooled one-sided 95% lower bound (−$200.21 vs CUT14's −$263.37), per
the registered rule.

### Confirm — band 897000, n=256/leader, W30 only

| leader | own Δ | se | margin Δ | se |
|---|---|---|---|---|
| sokolovsky-v12 | +$196 | $405 | −$155 | $306 |
| rayk-v11 | +$678 | $393 | +$394 | $255 |
| kaito-v4 | +$683 | $399 | +$448 | $279 |
| **pooled** | **+$519** | **$230** | **+$229** | **$162** |

- pooled own-bank one-sided 95% LB: **+$139.81** > $0 — **PASSES**.
- min leader own Δ: +$195.74 (sokolovsky) — no leader below −$2,000 — **PASSES**.
- pooled margin one-sided 95% UB: **+$495.19** — not below $0, so the margin veto does **not**
  fire — **PASSES**.
- pooled `mde_80`: $574.45.

All three CONFIRMED criteria are met. **W30 is CONFIRMED.**

Unlike STACK3's terminal-freeze confirm (which blew *past* its screen point estimate,
+$3,722 → +$7,390), W30's screen and confirm pooled deltas are close and both modest: +$413 at
screen, +$519 at confirm, a difference well inside one pooled se of either. The margin sign also
holds up at confirm (+$229, UB +$495) rather than flipping negative the way STACK3's did against
the shipped default (−$585) — W30 is not showing the "grows the market, does not win it" pattern
that closed off STACK3's margin case.

### The #170 margin cross-check — reproduces the recorded −$585 point estimate exactly

Running `tools/recon-scripts/second_slot_verdict.py` against the three `#170` viability ledgers
(band 893000, STACK3 vs `champion` at shipped defaults, `eval/gates/2026-09-19T21-*-champion-vs-
public_*-money.json`) gives:

- pooled own-bank Δ: **+$3,401.20** (se $634.54, LB +$2,357.39) — matches #170's recorded
  +$3,401 (se $635) exactly, confirming the pairing key against a previously-known result.
- pooled margin Δ: **−$585.25** (se $626.68), one-sided 95% UB **+$445.63**.

The point estimate reproduces #170's stated −$585 to the dollar. The interval #170 lacked is now
available: at n=256/leader, STACK3's margin disadvantage against the shipped default is **not**
statistically distinguishable from $0 (UB is positive) — the sign is directional, not confirmed
negative. This does not overturn #170's finding, which was never framed as a statistically
significant margin loss; it supplies the interval that finding was missing.

### Predictions scorecard

- `EH1` predicted **−$500 to +$2,000**, P(selectable) = 0.50. Landed pooled **+$763** — inside
  the range — but **not selectable**: the LB criterion, not the point estimate, is what excluded
  it. The prediction range was about the point estimate and did not anticipate a near-miss on the
  LB bar specifically.
- `RESCUE` predicted **−$1,500 to +$2,500**, P(selectable) = 0.40. Landed pooled **−$7,995** —
  **far outside the range**, and the miss is in the unfavourable direction the prereg flagged as
  possible (10-hire labor cost dominating the missed-water mechanism).
- `CUT14` predicted **−$1,500 to +$1,500**, P(selectable) = 0.30. Landed pooled **+$144** —
  inside the range, near zero. Selectable.
- `W30` predicted **−$2,500 to +$1,500**, P(selectable) = 0.30. Landed pooled **+$413** (screen)
  / **+$519** (confirm) — inside the range at both bands. Selectable, selected, and confirmed.
- `COW8` predicted **−$3,000 to +$1,000**, P(selectable) = 0.20. Landed pooled **−$11,370** —
  **far outside the range**, well below even the pessimistic end.
- P(at least one arm selectable) was 0.80; **two were** (CUT14, W30).
- P(the selected arm is CONFIRMED) was 0.40; **it was**.
- P(the experiment ends CONFIRMED) was 0.32; **it did**.
- The named most-likely failure mode — a screen pass near +$1,000–$1,500 that is mostly
  selection, regressing below $0 at confirm — **did not occur**. W30's screen point estimate
  (+$413) was smaller than that band, and its confirm **improved** rather than regressed: the
  one-sided LB went from an unrequired-to-be-positive −$200 at screen to a **positive** +$140 at
  confirm. The two RESCUE/COW8 misses were both far outside their predicted ranges in the
  unfavourable direction — a bigger surprise than the named failure mode, which concerned the
  selected arm's stability, not two arms landing an order of magnitude worse than predicted.

### Consequences, applied

Per the registered Consequences section: **CONFIRMED licenses an owner decision** to upload W30's
build into `a344ab1`'s slot, pairing {W30, STACK3}, subject to the 2026-09-27 STACK3 revert check
already on record. Nothing in this document, or in this addendum, authorises an upload.
