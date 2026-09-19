# Pre-registration: the terminal freeze experiment — is anything better than M3b?

Date: 2026-09-19
Candidate: `champion` at current `main`, with shipped knobs only. **No new agent code**: every
arm is an `--agent-config` override (or no override at all), and the build under test is `main`.
Status: REGISTERED — runs launch only after this document has merged.
Authorization: owner decision 2026-09-19, taken twice. First, to push for an advance before the
2026-09-28 T-2 freeze rather than close the upload. Second, on being shown that the knob surface
is exhausted and the +$4,000 bar is unreachable at any feasible n, to register **this**
experiment with its decision question changed prospectively, rather than hunt new agent code.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## The decision question changes, and this section is the whole argument for it

Every prior registration asked a **promotion** question: *is this change worth shipping?*, with
a bar of pooled own-bank delta **>= +$4,000** against `champion` at shipped defaults. Eleven
slices asked it and eleven answered no.

This document asks a different question, and asks it once: **at the freeze, is any candidate
better than the specific bot an upload would evict?**

The two are not the same question with different thresholds.

- The promotion bar exists to avoid churning uploads on noise *while iteration remains
  possible*. Ship something marginal in August and you have burned a slot you could have spent
  on something real, and you can always ship again. That asymmetry justifies demanding a large
  effect.
- At the freeze the asymmetry inverts. **Exactly one upload decision remains**, it is
  irreversible, and the alternative to acting is not "wait for something better" but "keep M3b
  permanently." The only quantity that bears on final Elo is whether the candidate banks more
  than M3b against the field.
- The eviction is concrete and asymmetric in a way `>= +$4,000` does not express: a new upload
  displaces the **older** of the two tracked submissions, which is M3b (`b6ce655`, uploaded
  2026-08-26), currently the better of the live pair. `a344ab1` is not at risk.

So the terminal bar is **> $0 against frozen M3b, with 95% confidence**, not `>= +$4,000`
against `champion`. Different baseline, different question, one shot.

**Disclosure of what this bar costs, stated before any data.** A `> $0` bar is much weaker than
`>= +$4,000`. Had it been the promotion bar, several closed slices would not have closed:
SHEEP1 (+$2,051 vs `champion`), the S3EH1−S3 contrast (+$1,282), STACK3 pooled across both its
bands (+$1,100, se $810). **That is the cost of this change and it is on the record.** Two
things keep it from being a retroactive rescue: the baseline here is **frozen M3b**, not
`champion`, so no closed verdict's comparison is reproduced; and nothing in this document
reopens, amends or re-scores any prior slice. All eleven remain NOT ADVANCED.

**What does not change.** The +$4,000 promotion bar is untouched for promotion questions. No
threshold in any existing registration moves. A verdict fired here is stop-or-remeasure like
any other: if the confirm run fails, the answer is no upload, not a third band.

## Why frozen M3b in own-bank dollars, and not win rate

`eval/prereg/2026-09-07-elo-aligned-factorial.md`'s post-ladder addendum is the governing prior
and it cuts both ways:

> Head-to-head against a near-identical opponent amplifies small edges: it measures the sign of
> an effect, not its size.

That refutes **win-rate** against frozen M3b, which read 0.974 (487-13) offline and produced no
ladder difference at all. It does not refute own-bank delta. The same addendum:

> What transfers is own-bank gain. [...] each **+$10k of own bank at about +100 Elo**

The design here measures own-bank delta with M3b as the *baseline* and a public leader as the
*opponent*: candidate and M3b each play the same leader on the same seed, and the banks are
compared. This is the representative-opponent shape the addendum endorses, not the mirror shape
it refutes.

**Prior, from the only three such runs that exist.** `champion` @ `d1050fd`, no config override,
against `frozen:m3b_live_b6ce655` at band 850000, n=128/leader
(`eval/gates/2026-09-11T02-21-33Z`, `…T02-25-29Z`, `…T02-29-28Z`): +$1,512 / +$1,335 / +$1,147,
pooling to **+$1,331, se $727**, two-sided 95% CI [−$94, +$2,756]. Positive at all three
leaders, not significant at n=128. That interval is why this experiment is worth running and
why it is run at higher n.

## Arms

Three, each against baseline `frozen:m3b_live_b6ce655`.

| arm | `agent_config` | why it is here |
|---|---|---|
| `MAIN_DEF` | *(none — shipped defaults)* | `a344ab1` → `main` is 1,400+ lines of non-test agent source. Every knob added since defaults to a no-op, but **whether default behaviour actually moved has never been measured.** This arm settles it and re-measures the +$1,331 prior at higher n. |
| `SHEEP1` | `{"animal_buy_order": ["SHEEP", "COW"]}` | The largest positive any arm has ever measured against `champion` (+$2,051, band 875000). Expression check passed in `eval/prereg/2026-09-12-never-gated-knob-screen.md`. |
| `STACK3` | `{"strawberry_tile_target": 20, "strawberry_plant_daily_cap": 10, "strawberry_start_day": 8, "animal_buy_order": ["SHEEP", "COW"], "max_hires_per_turn": 10}` | The stack of measured positives, and the only arm with two independent measurements (+$3,637 @ 881000, −$1,203 @ 888000; pooled +$1,100, se $810). Its cross-band instability is the reason it is screened and confirmed rather than trusted. |

No new expression check is registered: `MAIN_DEF` overrides nothing, and `SHEEP1` and `STACK3`
are configurations whose knobs have already been gated and whose expression has already been
measured. Cited, not re-run.

## Pre-flight: a positive control, required before the screen is read

Before any arm's result is read, each arm must be shown to **express at all** against this
baseline: on 8 seeds at band 891000-891007, `sd_delta > 0` for every arm. An arm whose own-bank
series is identical to frozen M3b's has not been measured, it has been mistaken for measured.

This is here because this project shipped a bit-exact no-op proof three days ago whose zero
measured nothing — the rig could not express the knob under test, and the tell was `mde_80: 0.0`
(`brain/Gotchas.md`, 2026-09-19). A `> $0` bar is exactly the shape where an inert arm reads as
a clean negative. **A failed pre-flight is an INVALIDITY for that arm, not a result.**

## Registered design

Gate: `harness.money_gate`, candidate `champion` with the arm's config, baseline
`frozen:m3b_live_b6ce655`, against each of `public:sokolovsky-v12`, `public:rayk-v11`,
`public:kaito-v4`.

- **Screen:** band **891000**, n = **128** seeds per leader, all three arms.
- **Confirm:** the selected arm only, band **892000**, n = **256** per leader.

Bands 891000 and 892000 are verified unused by every ledger in `eval/gates/`, claimed by no
earlier registration, and referenced by no file in the repo. (889000 and 890000 are deliberately
avoided: the labor-inside-the-stack registration claimed them for runs it never reached.)

Screen-then-confirm on disjoint bands is the multiplicity control. Three arms are screened; one
is confirmed. It is also the direct control for the cross-band instability recorded in #165 —
which is why a screen/confirm disagreement is a **NOT CONFIRMED**, below, and never grounds for
a third band.

## Decision rule (fixed before launch)

Per arm and leader *i*, take `mean_delta_i` and `stderr_i` from the ledger; pool as the simple
mean with pooled se `sqrt(sum stderr_i²)/3`. The ledger's `passed` field is not the verdict.
Note that the ledger's `mde_80` is **per-leader**; the pooled MDE is `mde_multiplier * pooled
se` and is the only power figure this document uses (see #164).

**INVALID** if the engine is not 1.32.7, an arm fails its pre-flight, or any run records a
crash-type veto (`candidate_crash`, `baseline_crash`, `opponent_crash`, `canary_crash`) or a
`baseline_degenerate` / `opponent_degenerate` veto. A `candidate_degenerate` veto is a result.

**SCREEN — an arm is SELECTABLE** only if, at band 891000: pooled delta **> $0**; pooled
one-sided 95% lower bound **> −$500**; and no single leader's point estimate below **−$2,000**.

**SELECTION:** among selectable arms, the highest pooled one-sided 95% lower bound. If no arm
is selectable, the experiment ends at NOT CONFIRMED and there is no confirm run.

**CONFIRMED** only if the selected arm, at band 892000 n=256, has a pooled one-sided 95% lower
bound **> $0** and no single leader's point estimate below **−$2,000**.

**NOT CONFIRMED** otherwise. No arm substitution, band reuse, or threshold change after launch.

REPORTED, NOT GATING: each arm's per-leader deltas, pooled MDE, the implied Elo at the recorded
+$10k ≈ +100 Elo slope, and for `MAIN_DEF` specifically whether default behaviour differs from
the live `a344ab1` build at all.

## Predictions, recorded before data

- `MAIN_DEF` pooled vs M3b: **+$500 to +$2,500**. P(selectable) = 0.60.
- `SHEEP1` pooled vs M3b: **+$500 to +$3,500** — the additive read of (+$2,051 vs champion) and
  (+$1,331 champion vs M3b) would put it near +$3,400, and effects of this kind have not
  reliably added in this project before. P(selectable) = 0.55.
- `STACK3` pooled vs M3b: **−$500 to +$3,000**, the widest of the three because it is the arm
  that has already failed to replicate once. P(selectable) = 0.40.
- P(at least one arm selectable at the screen) = **0.75**.
- P(the selected arm is CONFIRMED) = **0.55**.
- P(this experiment ends in a CONFIRMED arm, i.e. both) = **0.40**.
- Most likely failure mode, named in advance: an arm clears the screen at n=128 on a point
  estimate near +$1,300 and its confirm lower bound lands just below $0 at n=256, because a
  +$1,331-sized true effect needs a pooled se under ~$810 to clear, and n=256 gives ~$514 —
  adequate, but with little margin. P = 0.30.

## What this authorizes, and what it does not

A CONFIRMED arm licenses **an owner decision to upload that arm's build**, and nothing more. It
does not perform an upload. Uploads stay owner-gated: `submit.py` never calls the Kaggle API, it
validates and prints the command for a human to run.

Note explicitly, because it is now known and would otherwise be assumed to protect this
decision: `submit.py`'s promotion-entry requirement is **not** a strength check. It accepts any
passing `gate_type: "promotion"` entry at the sha regardless of opponent, and `builtin:starter`
passes at rate 1.0 for every build (#166). The authorization for any upload out of this
experiment is **this document's CONFIRMED verdict plus the owner's decision**, not the presence
of a promotion ledger entry.

Nothing in this document authorises an upload.
