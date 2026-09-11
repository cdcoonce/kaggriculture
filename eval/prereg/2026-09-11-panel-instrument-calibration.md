# Pre-registration: calibrate the own-bank-vs-panel instrument on a pair the ladder has already judged

Date: 2026-09-11
Candidate: `champion` at `main` (shipped config) vs baseline `frozen:m3b_live_b6ce655`
Status: REGISTERED — runs launch only after this document merges **and** the
engine pin reads `kaggle-environments==1.32.7`. The runner asserts the loaded
engine version before the first game.
Authorization: owner decision 2026-09-11 (strawberry rebuild, step 1).

## Why

The strawberry rebuild will be gated on own-bank gain against the reactive
public-leader panel (`public:<id>`, PR #122). Nothing in this repo has ever been
checked against the live ladder before being trusted, and the last two
instruments were refuted by it: the replay-tape money gates were underpowered,
and head-to-head against a frozen copy of ourselves read 0.974 offline for a
pair the ladder scores as tied (`eval/prereg/2026-09-07-elo-aligned-factorial.md`,
2026-09-11 addendum). This registration checks the new instrument against the
one comparison the ladder has already judged, before anything is built on it.

## The known pair

- **Candidate** `champion` at `main`: the shipped configuration
  (`hand_mule_load`=20, `valve_soft_threshold`=35, `clone_front_run`=True), i.e.
  submission 56088917.
- **Baseline** `frozen:m3b_live_b6ce655`: submission 55784368.
- **Live verdict** (`eval/submissions/sub-56088917.json`): same-window
  replay-derived records 28-41 vs 13-20, indistinguishable; ratings 609.2 vs
  638.9 under the project's close criterion. Replay-settled own bank averaged
  $71.4k vs $67.3k (+$4.1k), but over disjoint opponent samples, so that
  difference is confounded and is not the target.
- **The band the ladder allows.** On the live slope of about +100 Elo per +$10k
  of own bank (first-order counterfactual on 56088917's live losses), "not
  distinguishable at the ladder's n" — roughly ±40 Elo at one standard error,
  ±80 at two — corresponds to an own-bank delta of roughly **−$4k to +$8k**.

## Registered design

`money_gate --candidate champion --baseline frozen:m3b_live_b6ce655`, seed band
**850000** (verified unused by every ledger in `eval/gates/`; well clear of the
reserved 900000-901249), **n = 128 seeds** per opponent, one run per panel
member:

| opponent | band | n_seeds |
|---|---|---|
| `public:sokolovsky-v12` | 850000 | 128 |
| `public:rayk-v11` | 850000 | 128 |
| `public:kaito-v4` | 850000 | 128 |

The ledger's own `passed` field is **not** the verdict — it compares against the
runner's generic money threshold, which is not this document's rule. The ledger's
`opponent_digest` will be null: `gate.opponent_digest` hashes only
machine-local tapes. Provenance for a `public:` opponent is the committed panel,
SHA-256-verified against `eval/opponents/public-leaders/panel.json` on every
load, at the commit the ledger records.

## Decision rule (fixed before launch)

**INVALID RUN** if the loaded engine is not 1.32.7, or any run records a
candidate or baseline crash or a non-empty `vetoes` list. Invalid runs are
rerun, not reinterpreted.

For each opponent *i*, take `mean_delta_i` and `stderr_i` from the ledger. Pool
as the simple mean of the three, with pooled standard error
`sqrt(sum stderr_i²) / 3`, and report two-sided 95% intervals as
estimate ± 1.96 × standard error.

**CALIBRATED** only if both hold:

1. The **pooled** point estimate lies in **[−$4,000, +$8,000]**.
2. **No single opponent's** point estimate exceeds **+$12,000** — an own-bank
   edge that large would have shown on the ladder as roughly +120 Elo, about
   three standard errors.

**MISCALIBRATED** otherwise. The panel is then not a valid sizing instrument for
this agent; the strawberry screen does not gate on it, and the line returns to
the owner.

REPORTED, NOT GATING: absolute own bank for both arms against each leader, the
leaders' own bank, per-opponent spread, and `sd_delta` (which sets the n the
strawberry screen will need).

## Registered predictions

- Pooled delta lands in **[0, +$5,000]**. HML20 and VST35 each moved own bank by
  roughly $1k or less in their own gates, and `clone_front_run` should not fire:
  it needs an opponent within four total tiles of our layout, and the panel runs
  ~31 strawberry tiles to our zero.
- Our absolute own bank against the leaders lands **below** our ladder mean of
  ~$71k — likely $50-65k — because they supply the shared milk and wool markets
  far harder than a ~650-rated opponent does.
- The leaders bank $120-150k against us (they banked $149-157k against
  `builtin:starter`).

## Consequence

CALIBRATED authorizes using own-bank-vs-panel as the primary instrument of the
strawberry screen, which will be registered separately. MISCALIBRATED stops that
reliance. Neither outcome authorizes an upload; the next upload evicts M3b and
remains an owner decision.

## ADDENDUM (2026-09-11, post-run): CALIBRATED

Runs executed 2026-09-11T02:17-02:29Z at `d1050fd` (PR #125 merged, so the
engine pin reads 1.32.7; the runner asserted the loaded version, the shipped
config, and the frozen M3b package before the first game). Band 850000, n=128
seeds per leader. No crashes, no vetoes, candidate canary clean.

| leader | mean_delta | stderr | 95% interval | our bank (shipped) | our bank (M3b) | leader bank Δ | sd_delta |
|---|---|---|---|---|---|---|---|
| `public:sokolovsky-v12` | +$1,147 | $1,346 | [−$1,491, +$3,786] | $65,255 | $64,107 | −$3,734 | $15,229 |
| `public:rayk-v11` | +$1,512 | $1,202 | [−$843, +$3,867] | $62,644 | $61,133 | −$5,489 | $13,594 |
| `public:kaito-v4` | +$1,335 | $1,226 | [−$1,068, +$3,738] | $62,546 | $61,211 | −$5,313 | $13,870 |

Pooled (simple mean of the three, pooled se `sqrt(sum se²)/3`): **+$1,331,
se $727, 95% interval [−$94, +$2,756].**

Ledgers: `eval/gates/2026-09-11T02-21-33Z-champion-vs-public_sokolovsky-v12-money.json`,
`...T02-25-29Z-champion-vs-public_rayk-v11-money.json`,
`...T02-29-28Z-champion-vs-public_kaito-v4-money.json`. Each ledger's `passed`
field reads false against the runner's generic $1,000 money threshold; as
registered, that field is not the verdict.

**Decision-rule application.** 1. Pooled point estimate +$1,331 lies in
[−$4,000, +$8,000]: met. 2. No single leader above +$12,000 (maximum +$1,512):
met. **Verdict: CALIBRATED.** Own-bank against the panel reproduces the ladder's
verdict on the one pair the ladder has judged, where head-to-head against our
own lineage read 0.974 for the same pair. It may size the strawberry screen.

**Registered predictions vs outcome.**
- *Pooled delta in [0, +$5,000]* — met (+$1,331).
- *Our absolute bank against the leaders below our ~$71k ladder mean, likely
  $50-65k* — met ($61.1k-65.3k across arms and leaders).
- *The leaders bank $120-150k against us* — **missed.** Their mean bank was
  $107,382-$115,086 (sokolovsky-v12 $111,352 vs shipped and $115,086 vs M3b; rayk-v11 $107,382 vs shipped and $112,871 vs M3b; kaito-v4 $109,384 vs shipped and $114,697 vs M3b). The prediction carried over their smoke-game
  banks against `builtin:starter` ($149k-157k); against an agent that competes
  for the same markets they bank far less.

**Reported, not gating.** The shipped configuration also lowers each leader's
bank by $3.7k-5.5k relative to M3b, so its effect on the gap (ours minus theirs)
is roughly +$6k — about +60 Elo on the ladder-derived slope, consistent with the
ladder's small, noisy edge (28-41 vs 13-20). `sd_delta` of $13.6k-15.2k per
seed means a standard error of $1k per leader needs ~232 seeds; an effect of
$10k or more is resolvable at n≈64.

Nothing in this document authorizes an upload.
