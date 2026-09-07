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
