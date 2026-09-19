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

## ADDENDUM — VERDICT (2026-09-19): CONFIRMED, and it should not be uploaded on this evidence

Run at `main` = `a71b5e9`, the commit this document merged as. Engine 1.32.7, clean tree,
baseline `frozen:m3b_live_b6ce655` throughout, no crash and no veto in any of the twelve runs.

**Pre-flight (positive control) PASSED.** All three arms express against this baseline:
`sd_delta` 11,355 / 12,122 / 16,323 on 8 seeds. No arm was mistaken for measured.

### Screen — band 891000, n=128/leader

| arm | sokolovsky | rayk | kaito | pooled Δ (se) | one-sided 95% LB | pooled `mde_80` |
|---|---|---|---|---|---|---|
| MAIN_DEF | +$1,857 | +$888 | +$696 | +$1,147 ($704) | −$11 | $1,760 |
| SHEEP1 | +$1,793 | +$1,701 | +$1,399 | +$1,631 ($758) | +$384 | $1,895 |
| STACK3 | +$4,282 | +$3,568 | +$3,315 | **+$3,722 ($871)** | **+$2,288** | $2,180 |

All three selectable. **SELECTED: STACK3**, highest pooled lower bound, per the registered rule.

### Confirm — band 892000, n=256/leader, STACK3 only

| leader | Δ | se | `opponent_mean_delta` | `n_regressed` |
|---|---|---|---|---|
| sokolovsky-v12 | +$8,768 | $972 | +$4,601 | 80/256 |
| rayk-v11 | +$6,878 | $1,089 | +$2,569 | 92/256 |
| kaito-v4 | +$6,524 | $1,088 | +$2,514 | 98/256 |
| **pooled** | **+$7,390** | **$607** | | |

One-sided 95% LB **+$6,392** > $0; no leader below −$2,000. **STACK3 is CONFIRMED.**

### The verdict is CONFIRMED. The magnitude is not trustworthy, and the transfer is doubtful.

**The two bands disagree at 3.45 se.** +$3,722 at 891000 against +$7,390 at 892000, against an
se of the difference of $1,062. Fixed-effect pooling assumes they agree and gives +$6,191
(se $498); they do not agree. Heterogeneity Q = 11.93 on 1 df implies a between-band sd of
**tau = $2,482**, and the honest random-effects estimate is **+$5,609, se $1,833**, one-sided
LB **+$2,594**.

That lower bound still clears $0, so the *direction* survives the instability. STACK3 banks
more than M3b, and that is now measured on two independent bands. This is the strongest
positive result the project has recorded, and it is recorded as such.

**But this arm has now been measured four times and swung every time.** +$3,637 (881000, vs
`champion`), −$1,203 (888000, vs `champion`), +$3,722 (891000, vs M3b), +$7,390 (892000, vs
M3b). Both same-baseline pairs disagree at about 3 to 3.5 se. Instability is the most
replicated fact about STACK3.

**There is a mechanism for it, and it was measured.** `tools/recon-scripts/shop_roster_coupling.py`
on `strawberry_tile_target` 0-vs-20 at the confirm band's seeds returns **coupled draws 7.9/8,
range [7,8]**, first divergence as early as day 2
(`eval/recon/2026-09-19-terminal-freeze-stack3-coupling-892000.json`). That is the maximum; the
README's worked example (`max_owned_quadrants` 4-vs-3) is 4/8 and already warrants caveats. The
seed-pairing that gives this gate its 2-60x variance reduction is gone for this arm, and the
arm's result depends on shop draws that differ by band. `sd_delta` remains honest dispersion,
so the intervals are not biased — but a band-sensitive arm is exactly what 7.9/8 predicts, and
exactly what four measurements show.

**This registration should have required that probe and did not.** `eval/README.md` mandates
recording `coupled_draws` for an arm that moves tile occupancy "before reading the screen result
as anything but directional." STACK3 sets `strawberry_tile_target`. The omission is recorded as
a defect in this registration, not worked around.

### Why CONFIRMED does not imply "upload"

The dollar-to-Elo slope this project uses — +$10k of own bank ≈ +100 Elo — was derived
explicitly by **holding each opponent's bank fixed**, and its own source calls it an upper
bound in a shared market. STACK3 violates that premise harder than any arm measured:
`opponent_mean_delta` averages **−$1,869** at band 891000 and **+$3,228** at band 892000. The
opponent's bank moves by thousands and **flips sign between bands**. So +$5,609 cannot be read
as +56 Elo. The slope does not apply to this arm.

Four further signals, all pointing the same way and none decisive alone:

- STACK3 won **0 of 768 games** against the leaders across both bands. MAIN_DEF, banking least,
  won a few (0.004 / 0.016 / 0.012). Win rate has no gradient at this distance — that is why
  the money gate exists — but the field is not flat and STACK3 sits at the bottom of it.
- STACK3 is a **satellite** strawberry configuration: it sets `strawberry_tile_target` and
  leaves `wheat_rush_tiles` at its default. That is the shape of the line closed by PRs
  #68/#83/#84.
- The same knob value against this exact baseline has been measured head-to-head before:
  `strawberry_tile_target: 20` vs `frozen:m3b_live_b6ce655` scored **0.015, 0.015, 0.010** at
  n=100, across two commits (`f79f357`, `b2069bc`) and two bands. Different instrument, older
  builds, and the post-ladder addendum gives a real reason to prefer own-bank over mirror win
  rate — so these do not refute the money result. They do not agree with it either.
- #91 exists because an internally rigorous strawberry chain — pre-registered, with a
  production-vs-price control at ci_lower +23,542 — lost to the shipped default **44-456** at
  n=500.

### Recommendation, which is not a verdict

**Do not upload STACK3 on this evidence.** The missing control is the one #91 specifies and
this registration failed to include: run the non-default configuration against the **shipped
default** before trusting it. Concretely, `STACK3` vs `champion` at shipped defaults, high n, on
a fresh band, with `coupled_draws` recorded alongside. If STACK3 is genuinely +$5,609 against
M3b, it should also beat the shipped default; if it loses that comparison the way the 2026-08-28
chain did, the money result is a market artifact and the eviction would be a mistake.

The registered consequence stands as written: a CONFIRMED arm licenses **an owner decision**,
and nothing in this document authorises an upload.

### Predictions scorecard

- `MAIN_DEF` predicted +$500 to +$2,500, landed **+$1,147** — inside, and a near-exact
  replication of the +$1,331 (se $727) measured at band 850000 on a different build. Two
  independent bands agreeing closely is evidence *against* a large band-variance component in
  general, which bears on #165: the instability is this arm's, not the instrument's.
- `SHEEP1` predicted +$500 to +$3,500, landed **+$1,631** — inside, low half.
- `STACK3` predicted −$500 to +$3,000, landed **+$3,722** at screen and **+$7,390** at confirm —
  **outside the range at both bands**, and the miss is in the favourable direction, which is the
  direction that deserves the most scepticism.
- P(at least one arm selectable) was 0.75; all three were.
- P(selected arm CONFIRMED) was 0.55; it was.
- The named most-likely failure mode — a screen pass whose confirm lower bound lands just below
  $0 — did not occur. The confirm came in far stronger, not weaker.

## ADDENDUM — VIABILITY ARM (2026-09-19): the #91 control PASSES, and margin is the new problem

Run at `main` = `fbfc258`, owner-authorized after the CONFIRMED verdict. Criteria were stated
before the data: money LB > $0, and a head-to-head rate far below 0.5 is a veto. Both passed.
Recorded as a **recon/veto control**, not a new promotion registration — it can disqualify
STACK3, never promote it.

**Part A — money, STACK3 vs `champion` at shipped defaults, band 893000, n=256/leader.**

| leader | own Δ | se | leader Δ | margin | `n_regressed` |
|---|---|---|---|---|---|
| sokolovsky-v12 | +$5,613 | $1,070 | +$5,249 | +$364 | 97/256 |
| rayk-v11 | +$2,512 | $1,113 | +$3,677 | −$1,165 | 121/256 |
| kaito-v4 | +$2,078 | $1,114 | +$3,033 | −$955 | 125/256 |
| **pooled** | **+$3,401** | **$635** | **+$3,986** | **−$585** | |

One-sided 95% LB **+$2,357** > $0. **Criterion PASSES.** No vetoes.

**Part B — head-to-head, STACK3 vs `champion` (shipped default), band 894000, n=250.**
Rate **0.978** (489-11 of 500), Wilson `ci_lower` **0.961**, `passed: True`. **Criterion PASSES**,
and it is the near-exact inverse of the 0.088 (44-456) that closed the 2026-08-28 strawberry
chain. **STACK3 is not a repeat of that configuration.**

**The three money comparisons are internally consistent.** STACK3 vs default (+$3,401) plus
default vs M3b (+$1,342 at band 891000) predicts +$4,548 for STACK3 vs M3b; the random-effects
estimate across bands 891000/892000 is +$5,609 (se $1,833) — a gap of 0.58 se. Three separately
measured comparisons that add up is meaningful evidence the money instrument is capturing
something real here.

### What the control did not clear: margin

`eval/prereg/2026-09-07-elo-aligned-factorial.md`'s post-ladder addendum states what decides a
live game: *"A live game is decided by whether our bank exceeds the opponent's."* The
corresponding diagnostic is the **margin delta** (`mean_delta_i − opponent_mean_delta_i`), and
across every band measured in this experiment it tells a different story from own bank:

| comparison | own Δ | leader Δ | **margin** |
|---|---|---|---|
| MAIN_DEF vs M3b (891000) | +$1,147 | −$3,862 | **+$5,009** |
| SHEEP1 vs M3b (891000) | +$1,631 | −$1,472 | +$3,103 |
| STACK3 vs M3b (891000) | +$3,722 | −$1,869 | +$5,591 |
| STACK3 vs M3b (892000) | +$7,390 | +$3,228 | +$4,162 |
| **STACK3 vs shipped default (893000)** | **+$3,401** | **+$3,986** | **−$585** |

**STACK3's large own-bank advantage over the shipped default does not survive as a margin
advantage.** It raises our bank by $3,401 and the leader's by $3,986. It grows the market rather
than out-earning the opponent in it, and on the quantity the addendum names as decisive it is
very slightly *behind* the default.

By contrast **MAIN_DEF reaches a comparable margin against M3b (+$5,009) with a fraction of the
own-bank gain**, by *reducing* the leader's bank rather than inflating it — and it does so on a
genuinely paired instrument, since it changes no occupancy (STACK3's coupling is 7.9/8 at
892000 and **8.0/8** at 893000,
`eval/recon/2026-09-19-viability-stack3-coupling-893000.json`).

Margin is a REPORTED, NOT GATING diagnostic in this and every prior registration, and it carries
no interval here, so this is not a veto and is not recorded as one. It is the reason the
own-bank result should not be read as a ladder advantage over the shipped default.

### Recommendation, updated and not a verdict

The previous addendum recommended against uploading STACK3 pending this control. **The control
passed, and that recommendation is withdrawn as stated.** What replaces it is narrower:

- **Against M3b — the bot an upload actually evicts — STACK3 is better on both own bank and
  margin**, across two bands. That comparison is the registered question and STACK3 answers it.
- **Against the shipped default, STACK3 is not better on margin.** So the case for uploading
  STACK3 specifically, rather than current `main` at defaults, is unproven.
- The mirror head-to-head at 0.978 establishes **sign, not size** — structurally identical to
  the 0.974 that produced no ladder difference in September. It refutes the veto; it is not
  evidence of magnitude.

The owner decision is therefore not "STACK3 or nothing" but **"STACK3, or `main` at defaults, or
neither"** — and the margin column is the reason that is a real question rather than a formality.
Nothing in this document authorises an upload.
