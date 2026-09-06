# Pre-registration: wheat_rush_tiles cap — replication, sweep, and a suppression test

Date: 2026-09-06
Candidate commit: 294de16 (config-only; the agent package is byte-identical to the shipped M3b at b6ce655)
Status: REGISTERED — runs launch after this document merges. No agent source
edits while any registered run is in flight.

## Motivation

The strawberry replacement screen
(`eval/prereg/2026-09-06-strawberry-replacement-screen.md`) closed its own
thesis and produced an unregistered surprise in a CONTROL arm: `wheat_rush_tiles`
= 25, with no strawberry, beat the shipped default **150-50 (rate 0.750,
ci_lower 0.686)** head-to-head at n=100 on band 834000
(`eval/gates/2026-09-06T17-51-38Z-champion-vs-frozen_m3b_live_b6ce655-promotion.json`).

That arm was a control, not the registered hypothesis, so it is exploratory and
cannot be promoted from that document. This registration tests it properly.

**Why it was not found earlier.** `wheat_rush_tiles` was screened three times,
all MONEY gates against `zoo:tape-thunder-719` at n=20, never head-to-head
against the shipped agent: 40 → mean +$740.8 (ci_lower −839.1); 30 → mean
−$270.3 (ci_lower −7,777.6); 20 → **mean +$4,745.4 (ci_lower −1,092.0)**. The
`0/40` win-rate field in those ledgers is the against-the-tape number, which is
~0-2% for every configuration including the unmodified baseline and carries no
discriminating signal. The best arm was an underpowered screen at n=20 against
~13k dispersion, not a measured negative — it was dropped rather than confirmed.

**Mechanism under test (hypothesis, not assumption).** The champion holds 42.0
standing tiles with **39.4 bare** (`docs/recon/occupancy.md`), walking is ~57%
of unit-turns and stays flat as hands are added, and added hands raise idle
share rather than production (measured 2026-09-06). That is the signature of a
farm sprawled across more ground than its crew can service. Capping the wheat
zone concentrates the same crew on fewer tiles. This registration measures the
outcome; a successor may instrument the mechanism.

## Registered design

Promotion (win-rate) gates, candidate `champion` + `--agent-config`, opponent
`frozen:m3b_live_b6ce655` (the shipped default), n=100 seeds (200 games each,
both seats), band **835000** (fresh; 834000 was the exploratory screen), all
arms on the same seeds:

| arm | agent_config | purpose |
|---|---|---|
| W20 | `{"wheat_rush_tiles": 20}` | below the exploratory winner |
| W25 | `{"wheat_rush_tiles": 25}` | replication of the exploratory result |
| W30 | `{"wheat_rush_tiles": 30}` | above it |
| W35 | `{"wheat_rush_tiles": 35}` | further above, toward the default |
| CTRL | `{}` (shipped defaults) | reference arm — establishes the self-play baseline for rate AND for both money levels |

The CTRL arm is load-bearing, not ceremony: it supplies the money reference
against which the suppression test below is evaluated, and it validates the
harness (a champion at defaults against a frozen snapshot of itself should sit
near 0.50).

## Decision rule (fixed before launch)

**INVALID** (stop, diagnose, nothing is claimed) if the CTRL arm falls outside
rate [0.40, 0.60], or if `any_candidate_crash` is true on any arm. A control
that does not reproduce self-play means the comparison is not measuring what it
claims to.

**ALIVE** — proceed to a promotion-grade registration (four-tape money
intersection-union plus a redirection decomposition) — only if BOTH hold:

1. **Replication.** At least one W arm reaches **rate ≥ 0.65 with Wilson
   ci_lower > 0.55**. (Deliberately tighter than the exploratory 0.750/0.686:
   an exploratory result found by inspecting a control should have to clear a
   higher bar to survive, not the same one.)
2. **Production, not suppression.** For the best W arm, mean candidate money
   must be **strictly greater** than CTRL's mean candidate money. If instead
   candidate money is flat or lower while the opponent's money falls, that is
   the suppression signature — the same one that closed cow7/sheep5 on
   2026-09-05, where the winning arm earned exactly what the failing arm earned
   and won only by dragging the opponent down — and the arm is NOT promotable
   from this document regardless of its win rate.

**CLOSED** otherwise. Closure ends the wheat-cap line; no successor screen.

Both money figures come from the promotion ledgers' own per-game rows
(`candidate_money`, `opponent_money`), seat-averaged per seed — no extra runs.

No extensions, no added arms, no band changes after launch. A miss is not
re-run at larger n inside this registration.

## Registered predictions

- CTRL lands near 0.50 (the #59 precedent recorded exactly 200-200, rate 0.500).
- At least one W arm replicates above 0.65. Honest prior: **more likely ALIVE
  than not** — unlike every other line closed this session, this one has a
  large measured effect (0.750 at n=100, 200 games) rather than an argued
  mechanism, and the prior money screens leaned positive at the smallest value
  tested rather than negative.
- The production/suppression test is the real risk. A compact farm plausibly
  sells less into the shared market, which would raise prices for the opponent
  rather than lower them — the opposite of suppression — but that is a
  prediction, not a result.

## Consequence

ALIVE authorizes a promotion-grade registration, not a submission. Uploading
remains a separate HITL decision: T-2 freeze is 2026-09-28 and a new submission
evicts one of the Bradley-Terry pair [M3b 55784368, M3a 55471731]. Nothing here
authorizes an upload.
