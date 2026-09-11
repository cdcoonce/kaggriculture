# Pre-registration: an Elo-aligned criterion, and the W30 × hml20 factorial

Date: 2026-09-07
Candidate: `champion`, CONFIG ONLY. No agent source edits while this runs.
Status: REGISTERED — runs launch after this document merges.

## Why the criterion changes, and the evidence that forced it

The competition's own Evaluation page (quoted verbatim in
`docs/recon/competition-rules.md`, retrieved 2026-09-07):

> The actual coin difference in a match does not affect the rating change—only
> the win, loss, or tie outcome matters.

Every promotion decision in this repo has been gated on a four-tape money
intersection-union. That instrument measures a quantity the ladder does not
score. Worse, it measures it in a regime where we lose: across all 99 committed
money gates against a replay tape, the candidate's win rate is 0.0000–0.0750
with a mean of **0.0033**, and 80 of 99 are exactly zero — the unmodified
baseline included. The money gate has therefore been answering "how much cash do
we bank while losing 99.7% of the games" for a ladder that scores only the games.

The head-to-head gate against a frozen copy of our own shipped agent is the
direct proxy for the thing that is scored, and it has been run as a secondary
check rather than the criterion.

## THE HONESTY DECLARATION, made before any data exists

`eval/prereg/2026-09-06-w30-promotion-confirmation.md`'s addendum requires that
any Elo-aligned successor state up front whether the new rule retroactively
rescues a closed line. **It does. Two of them.** Stating this now, with ledger
citations, because discovering it afterwards would make the change laundering:

| closed line | its head-to-head record | why it was closed |
|---|---|---|
| `hand_mule_load` 20 | **193-7, rate 0.965, ci_lower 0.9295** (n=200, band 821000, `eval/gates/2026-09-03T15-29-17Z`) | `traded_market` −3,077.35 on thunder, breaching a ±3,000 redirection bound by **$77.35** |
| `cow_target` 7 + `sheep_target` 5 | 140-60, rate 0.700, ci_lower 0.6332 (n=200, band 821000, `eval/gates/2026-09-03T15-32-04Z`) | every money bar missed (ci_lower −4,979…−6,511); diagnosed as suppression |

Under a win-rate criterion both clear a 0.55 bar. That is a large claim and it
deserves the argument against itself:

**The case that the rescue is legitimate.** The redirection veto exists to
reject gains that come from taking money out of the opponent rather than
producing more, on the theory that suppression will not generalise. Under a
money objective that is right. Under *this* objective it is not obviously right:
the rules score "having the most coins in the bank at the end of 720 turns," so
making the opponent poorer wins exactly as hard as making ourselves richer.
Suppression is a legal winning strategy in a two-player zero-information game.

**The case against.** Suppression measured against a *replay tape* proves
little, because a tape cannot react — an exploit of its fixed behaviour need not
survive contact with an agent that adapts. But hml20's 0.965 is not a tape
number: `frozen:m3b_live_b6ce655` is a full agent that reads the market and
responds. Beating a reacting opponent 193-7 is evidence of strength whatever its
mechanism.

**The residual risk, which no offline gate can retire.** `frozen:m3b_live` is
*our own lineage*. A 0.965 against ourselves may be exploiting a weakness
specific to our build that the 7,927-team field does not share — the
frozen-incumbent monoculture problem this repo has already recorded once. This
registration cannot settle that. Only the ladder can, which is why the
Consequence section below routes the winner to an upload decision rather than
treating a gate pass as the end of the argument.

**What this document does NOT do.** It does not reopen either verdict. hml20 and
cow7/sheep5 stay closed on their own registered terms. What follows is a *new*
measurement on a *fresh* band with a criterion fixed before the data exists, and
hml20 enters it as an unconfirmed candidate — because its 0.965 has been
measured exactly once, at n=200, on a single band, in an unregistered sweep,
whereas W30's has been measured twice (0.860 at n=100 band 835000; 0.856 at
n=250 band 836000).

## Correction to the record, made before this run launches

`eval/prereg/2026-09-06-w30-promotion-confirmation.md` states, twice, that the
W30 candidate's "agent package is byte-identical to the shipped M3b at
b6ce655." **That is false**, and the addendum committed in #105 repeated it
without checking. Correcting it here, before this run produces any data.

Two commits touched `packages/agent/src/` after b6ce655 and both are ancestors
of the W30 run commit `9d3f4e4`:

- `aad11ae` (2026-08-29) — "fund wheat before strawberry, and size the
  strawberry seed line to cash" (#83)
- `f79f357` (2026-08-29) — strawberry line closure (#84)

This is not a pedantic correction. #83 did not merely gate dormant strawberry
code; it **restructured the wheat seed purchase**, adding a cap of two days of
the dispatcher's plant quota:

```
quota = plant_quota(day, active_tiles)
seed_target = min(plantable_target_tiles, 2 * quota)
```

`plantable_target_tiles` is derived from the wheat zone — the same zone
`wheat_rush_tiles` caps. So the W30 effect is measured **through** this seed
budgeter and may be partly mediated by it. W30 need not reproduce on M3b's own
code, and nobody should assume it would.

What this does and does not damage:

- It does **not** invalidate the W30 result. The candidate is config-only
  relative to *current main*, which is what a submission bundle would ship, and
  the sweep's CTRL arm — current main at defaults versus frozen M3b — landed
  97-97-6, rate **exactly 0.500**, on band 835000. The intervening changes are
  therefore measured behaviourally neutral at default config, not assumed to be.
- It does mean the phrase "config-only" is only true relative to current main,
  and that **shipping W30 ships current main plus the knob**, not M3b plus the
  knob.
- It makes the CTRL arm load-bearing rather than ceremonial. CTRL is not a
  self-mirror; it measures everything-except-the-knob. An arm's edge over CTRL
  is what is attributable to the knob, and that is how this run reports.

## What is being asked

Two questions, one of which has never been asked at all:

1. Does hml20's 0.965 survive a confirmation at larger n on a fresh band?
2. **Do the two effects combine?** `wheat_rush_tiles` caps the crop zone;
   `hand_mule_load` sets how much a hand carries per shed trip. Both are
   hypothesised to act on the same bottleneck — the crew spends ~57% of
   unit-turns walking — so they may be substitutes rather than complements, and
   the combination could land below either alone. No gate has ever run them
   together.

## Registered design

Band **837000** (fresh; 835000 and 836000 are spent). Opponent
`frozen:m3b_live_b6ce655` throughout section A.

**A. Factorial, n=250 seeds (500 games) per arm:**

| arm | `--agent-config` | status entering this run |
|---|---|---|
| CTRL | `{}` (shipped defaults) | validity anchor; must land on the null |
| W30 | `{"wheat_rush_tiles": 30}` | confirmed twice (0.860, 0.856) |
| HML20 | `{"hand_mule_load": 20}` | measured once (0.965), never confirmed |
| BOTH | `{"wheat_rush_tiles": 30, "hand_mule_load": 20}` | **never measured** |

**B. Structural-diversity check, n=100 seeds (200 games) per arm**, same four
arms against `zoo:meta-clone` — a build from a different lineage (the ranch
meta), against which the shipped champion scores 0.745. This exists solely to
catch an arm that wins against our own lineage by exploiting it.

## Decision rule (fixed before launch)

**INVALID** if CTRL's rate against `frozen:m3b_live_b6ce655` falls outside
[0.40, 0.60], or if `any_candidate_crash` is true on any arm. An invalid run is
rerun, not reinterpreted.

**PRIMARY CRITERION — head-to-head win rate.** An arm is a SHIP CANDIDATE if,
against `frozen:m3b_live_b6ce655` at n=250 on band 837000, its rate is
>= **0.65** with Wilson **ci_lower > 0.55**.

**DIVERSITY GUARD.** A ship candidate is disqualified if its rate against
`zoo:meta-clone` is more than **0.10 below CTRL's** meta-clone rate in this same
run. Winning against our own lineage while regressing against a different one is
the monoculture failure this guard exists to catch.

**SELECTION.** Among surviving ship candidates, the RECOMMENDED arm is the one
with the highest `ci_lower` against `frozen:m3b_live_b6ce655` — the lower bound,
not the point estimate, so that a small-n peak cannot outrank a well-measured
one.

**CONFIRMATION DEBT, declared now.** W30 and HML20 each enter with prior
independent measurements, so a pass here is their confirmation. BOTH enters with
none: if BOTH is selected, it carries a confirmation debt and must clear the
same primary criterion on a further disjoint band (838000) before it is
recommended for upload. W30 or HML20 winning carries no such debt.

**MONEY IS A DIAGNOSTIC, NOT A GATE.** Money and `opponent_mean_delta` are
recorded and reported for every arm. **They cannot fail an arm in this
registration.** This is fixed before the data exists precisely so that it cannot
be adjusted once the numbers are visible. If a selected arm shows a large
negative `opponent_mean_delta`, that is reported prominently as a mechanism note
and as a transfer risk to the live field — it is not a veto.

**NOT RECOMMENDED otherwise.** No extensions, no added arms, no band changes
after launch.

## Registered predictions

- CTRL lands within [0.45, 0.55]; anything else means the harness moved.
- HML20 regresses from 0.965 — a single unconfirmed n=200 maximum is exactly the
  shape that regresses. Landing anywhere at or above 0.85 should be read as a
  strong confirmation, not a disappointment.
- **BOTH lands BELOW the better of W30 and HML20.** If both knobs relieve the
  same walking bottleneck, the second one applied has little left to recover,
  and over-capping the crop zone while also over-loading the mule could cost
  production outright. A BOTH that beats both singletons would mean the two are
  acting on genuinely different constraints, which would be the more interesting
  result and would change what to look for next.
- The diversity guard does not fire. If it does, that is the finding, and it
  matters more than which arm won.

## Consequence

A RECOMMENDED arm authorises an upload **decision**, not an upload. Uploading
stays HITL. Per `docs/recon/competition-rules.md`, only the latest 2 submissions
are tracked; ours are [M3a 55471731 @ 543.6, M3b 55784368 @ 657.2], so exactly
one upload displaces M3a — our weaker slot — and the leaderboard shows only the
best-scoring tracked bot, so a single upload cannot lower our displayed score.
The second upload after that would displace M3b, and M3b's exact code is
recoverable at b6ce655 if it ever needs restoring.

Nothing in this document authorises an upload.

## ADDENDUM (2026-09-07, post-run): RECOMMENDED = HML20, and the two knobs are substitutes

Runs executed 2026-09-07T01:14–01:29Z at `9ad4d36` (this document's own merge
commit), band 837000, serially, CTRL first. The runner refused to start until it
had verified from the *loaded* `PolicyConfig` that the tree carried shipped
defaults (`wheat_rush_tiles=81`, `hand_mule_load=9`) — the CTRL arm is only
meaningful if the tree is not already carrying a treatment.
`any_candidate_crash` false on all eight runs.

**A. vs `frozen:m3b_live_b6ce655`, n=250 seeds (500 games):**

| arm | W-L-T | rate | ci_lower | implied Elo | vs CTRL |
|---|---|---|---|---|---|
| CTRL | 244-244-12 | **0.500** | 0.4563 | +0 | — |
| W30 | 415-85-0 | 0.830 | 0.7946 | +275 | +0.330 |
| **HML20** | **484-16-0** | **0.968** | **0.9487** | **+592** | **+0.468** |
| BOTH | 441-59-0 | 0.882 | 0.8508 | +349 | +0.382 |

**B. Diversity guard vs `zoo:meta-clone`, n=100 seeds (200 games):**

| arm | W-L-T | rate | vs CTRL |
|---|---|---|---|
| CTRL | 159-41-0 | 0.795 | — |
| W30 | 158-42-0 | 0.790 | −0.005 |
| HML20 | 159-41-0 | 0.795 | +0.000 |
| BOTH | 167-33-0 | 0.835 | +0.040 |

**Decision-rule application.** VALIDITY: CTRL 0.500, inside [0.40, 0.60], no
crashes — VALID. PRIMARY: all three treatment arms clear rate >= 0.65 with
ci_lower > 0.55. DIVERSITY GUARD: no arm is more than 0.10 below CTRL's
meta-clone rate; none disqualified. SELECTION on highest `ci_lower`:

**RECOMMENDED: HML20 (`hand_mule_load` = 20), ci_lower 0.9487, rate 0.968.**
It entered with a prior measurement, so it carries no confirmation debt. BOTH
was not selected, so its declared debt never comes due.

### The guard is live, not blind — checked rather than assumed

CTRL and HML20 posted *identical* records against meta-clone (159-41). An
identical record is what a dead knob looks like, so it was checked: **all 200
per-game rows differ**, and HML20 banks +$2,700/game more than CTRL there. The
match is a coincidence of win counts, not of games. A guard that cannot see the
treatment is not a guard, and this one can.

### Money, the registered diagnostic — and why it was never the right gate

Recorded as REPORTED, NOT GATING, fixed before the data existed:

| arm | cand $ | opp $ | dCand | dOpp | **gap (cand − opp)** | rate |
|---|---|---|---|---|---|---|
| CTRL | 65,860 | 65,860 | — | — | **0** | 0.500 |
| W30 | 65,354 | 63,875 | −507 | −1,985 | **+1,479** | 0.830 |
| HML20 | 66,931 | 63,782 | +1,071 | −2,079 | **+3,150** | 0.968 |
| BOTH | 64,401 | 62,963 | −1,460 | −2,898 | **+1,438** | 0.882 |

**Win rate tracks the GAP, not our absolute money.** W30 and BOTH both bank
*less* than CTRL and still win 83% and 88% of games. Under the four-tape money
rule every one of these arms is a failure; under the rule the competition
actually applies — most coins at turn 720 — they are decisive. That is the whole
case for this registration, visible in one table: the old gate measured our
absolute money against a third-party tape, and the objective is the difference
against the opponent in front of us.

**The suppression worry, tested rather than argued.** HML20's edge here is
partly redirection (dOpp −2,079 against dCand +1,071), which is the signature
that closed this line on 2026-09-06. But against `zoo:meta-clone` — a build from
a different lineage — HML20 is *production-driven*: candidate +$2,700 and
opponent **+$2,093**, both players richer. The redirection appears against
`frozen:m3b_live`, our own agent, which competes for the identical market slots.
That is what taking share from a near-clone looks like, and it is evidence the
tape-measured redirection was partly an artifact of tapes that cannot react.
It is evidence, not proof; only the ladder settles transfer.

### Registered predictions vs outcome

- *"BOTH lands BELOW the better of W30 and HML20"* — **correct.** 0.882 against
  HML20's 0.968. The interaction is strongly negative: additive-in-Elo would
  predict +868, observed +349, an interaction of **−518 Elo**. Adding W30 on top
  of HML20 costs **−243 Elo**; adding HML20 on top of W30 gains only +74. The
  two knobs are **substitutes, and HML20 dominates.**
- *"HML20 regresses from 0.965"* — **wrong, in the candidate's favour.** It
  landed 0.968 at n=250 on a fresh band against 0.965 at n=200 on band 821000.
  This is the second registration in two days to predict regression-to-the-mean
  from a selected maximum and be wrong: W30 also held (0.860 → 0.856). These
  effects are large enough that selection bias is not the story.
- *"CTRL lands within [0.45, 0.55]"* — **correct**, and exactly 0.500 for the
  second consecutive band (97-97-6 at 835000; 244-244-12 at 837000).
- *"The diversity guard does not fire"* — **correct.**

### What the mechanism now looks like

Both knobs were hypothesised to relieve the same bottleneck: the crew spends
~57% of unit-turns walking. The interaction says they do, and that
`hand_mule_load` relieves it **better and without giving anything up**. W30 buys
logistics relief by *shrinking the farm* — fewer tiles to service, but less
grown, which is why its own money falls (−$507) while it still wins. HML20 buys
the same relief by *carrying more per trip*, keeping the tiles. Stacking them
pays the tile cost twice for relief already bought, which is exactly the −243
Elo that adding W30 on top of HML20 costs.

**This is a hypothesis consistent with the outcome, not an instrumented result.**
Nothing here measures walking turns per arm. `tools/recon-scripts/strawberry_labor.py`
already instruments assignment and walking and could settle it; a successor
should not cite this mechanism as established.

### Consequence

HML20 is RECOMMENDED, which authorises an upload **decision**, not an upload.
Shipping it needs the same treatment W30 got on `feat/wheat-rush-cap-30`: the
gate measured a `--agent-config` override, a bundle builds from source defaults,
and the two are only equivalent if nothing else derives from `HAND_MULE_LOAD`.
That equivalence must be **proved bit-identically against this ledger**, not
assumed, before any bundle is built.

W30 is not withdrawn; it is simply dominated. `feat/wheat-rush-cap-30` should not
be merged as the ship candidate.

## ADDENDUM (2026-09-11, post-ladder): the head-to-head-vs-self proxy did not transfer

This registration's premise was that head-to-head win rate against a frozen copy
of our own shipped agent is "the direct proxy for the thing that is scored." The
live ladder refutes that premise for the purpose it was used for.

Submission 56088917 (source default `a344ab1`: `hand_mule_load`=20 +
`valve_soft_threshold`=35 + `clone_front_run`) went live 2026-09-08. Offline it
beat frozen M3b **487-13 (0.974)** (`eval/gates/2026-09-07T04-58-43Z`). Live,
under the project's registered close criterion (paired snapshots 12m44s apart,
completed set and rating unchanged), it reads **609.2 over 70 completed
episodes against M3b's 638.9 over 190**. Replay-derived records over the same
window are **28-41 (0.406) against 13-20 (0.394)** — indistinguishable. The
implied "+629 Elo" did not appear.

**Why, from the replays.** Both agents win about 70% against opponents rated
below 650 and lose about 85% above it, and roughly 90% of losses are to
opponents banking over $70k while we bank about $71k. A live game is decided by
whether our bank exceeds the opponent's, against an opponent-bank spread of
roughly $60k-110k. In a mirror match the two banks are nearly equal, so an edge
of a few thousand dollars flips most games and reads as 0.97. Against the live
spread the same edge flips almost none. **Head-to-head against a near-identical
opponent amplifies small edges: it measures the sign of an effect, not its
size.**

**What transfers is own-bank gain.** A first-order counterfactual on
56088917's 41 losses — holding each opponent's bank fixed, so an upper bound in
a shared market — prices each +$10k of own bank at about +100 Elo (+$5k: 0.507;
+$10k: 0.565; +$20k: 0.652; +$30k: 0.768, from a 0.406 base). This
registration's own money diagnostic recorded HML20 at **+$1,071** own bank over
CTRL: about +10-20 Elo by that slope, invisible at the ladder's n, and
consistent with what the ladder shows.

**How to read this file now.** The RECOMMENDED verdict stands as a statement
about head-to-head against our own lineage, and the arms' *signs* are plausibly
right — 56088917's loss deficits are smaller than M3b's (median $24.9k against
$38.6k). The Elo magnitudes quoted above (+275, +349, +592) must not be read as
field Elo. And the money-gate critique in "Why the criterion changes" was half
right: money is not the scored quantity, but own-bank gain against a
representative, reactive opponent is a better transfer proxy than win rate
against ourselves. The money gate's real failures were power (effects at
0.47-0.63x `mde_80`) and replay-tape opponents that cannot react — not its
metric.
