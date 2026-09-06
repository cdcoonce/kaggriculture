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

## ADDENDUM (2026-09-06, post-run): ALIVE — replicated, and production-driven

Runs executed 2026-09-06T22:04-22:11Z at 03c8f17 (agent package byte-identical
to the shipped M3b at b6ce655; config-only arms), serially, CTRL first, no
source edits while any run was in flight. Band 835000, n=100 seeds / 200 games
per arm, opponent `frozen:m3b_live_b6ce655`.

| arm | agent_config | W-L | rate | ci_lower | mean cand $ | mean opp $ | dCand | dOpp |
|---|---|---|---|---|---|---|---|---|
| CTRL | (shipped defaults) | 97-97 | 0.500 | 0.431 | 63,446 | 63,446 | — | — |
| W20 | wheat_rush_tiles 20 | 104-96 | 0.520 | 0.451 | 65,977 | 65,925 | +2,531 | +2,480 |
| W25 | wheat_rush_tiles 25 | 148-52 | 0.740 | 0.675 | 64,242 | 63,411 | +796 | −35 |
| **W30** | **wheat_rush_tiles 30** | **172-28** | **0.860** | **0.805** | **65,589** | 64,116 | **+2,143** | +670 |
| W35 | wheat_rush_tiles 35 | 140-60 | 0.700 | 0.633 | 63,940 | 63,442 | +494 | −3 |

Ledgers: eval/gates/2026-09-06T22-04-08Z (CTRL), T22-05-29Z (W25), T22-06-49Z
(W20), T22-08-10Z (W30), T22-09-49Z (W35), all
`-champion-vs-frozen_m3b_live_b6ce655-promotion.json`. Money figures are the
ledgers' own per-game rows, seat-averaged per seed then meaned over seeds.

**Decision-rule application:**

- VALIDITY: CTRL rate **0.500** (97-97), inside the registered [0.40, 0.60]
  window — a champion at defaults against a frozen snapshot of itself lands
  exactly on the null, so the comparison measures what this document claims.
  `any_candidate_crash` false on all five arms. The run is VALID.
- REPLICATION: **MET.** Best arm W30 at rate 0.860 / ci_lower 0.805, far above
  the registered 0.65 / 0.55. Independently, the exploratory arm W25 reproduced
  on a fresh band: 0.750 (834000) → 0.740 (835000).
- PRODUCTION, NOT SUPPRESSION: **MET, and in the strongest available form.**
  W30's mean candidate money is +$2,143 over CTRL, and the OPPONENT's money is
  also **up** (+$670). Nobody is being starved. Contrast the cow7/sheep5
  closure (2026-09-05), where a similar 0.70 head-to-head record came with
  candidate money identical to the losing arm and opponent money dragged down
  ~$2k — that is the signature this criterion exists to catch, and it is absent
  here.

**Verdict: ALIVE.** Proceed to a promotion-grade registration (four-tape money
intersection-union plus a redirection decomposition). Nothing here authorizes
an upload.

**Shape of the effect, recorded for the successor.** The response is not
monotone in the cap, and the money columns say why. W20 produces the largest
absolute gain (+$2,531) but the weakest edge (0.520), because the opponent
gains almost exactly as much (+$2,480): a smaller wheat zone sells less into
the shared book, which lifts prices for BOTH players. W30 is where our own
productivity gain outruns the price gift handed across the table. A successor
should treat the cap as trading own-production against a market externality,
not as a monotone "smaller is better" knob, and should not assume the optimum
sits at an endpoint.

**Mechanism remains hypothesis, not result.** The champion holds 42.0 standing
tiles with 39.4 bare, walking is ~57% of unit-turns and flat as hands are
added, and added hands raise idle share (all measured 2026-09-06) — consistent
with a farm sprawled beyond what its crew can service, which a cap concentrates.
This registration measured the OUTCOME. Nothing here instruments the mechanism,
and the successor should not cite one as established.
