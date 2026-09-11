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
