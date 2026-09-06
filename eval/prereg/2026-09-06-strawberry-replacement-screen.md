# Pre-registration: strawberry as REPLACEMENT, not satellite — viability screen

Date: 2026-09-06
Candidate commit: 39d0939 (config-only; no agent source change)
Status: REGISTERED — runs launch after this document merges. No agent source
edits while any registered run is in flight.

## Why this is not the closed strawberry line

The closed line (PRs #68/#83/#84, verdicts 0-200, 3-197, 44-456 at n=500)
screened strawberry as a SATELLITE: a zone added on top of a wheat rush whose
own zone was left effectively uncapped (`wheat_rush_tiles` defaults to ~89,
i.e. the whole board). `docs/recon/occupancy.md` drew the distinction before
today and stated it plainly: "Thunder does not run strawberry as a satellite.
It runs it as ~45% of the farm, REPLACING wheat rather than supplementing it…
That is a different intervention from anything screened so far, and the
existing negative results do not bear on it."

Audit of every committed gate ledger (2026-09-06): 20 arms carry
`strawberry_tile_target`; **none has ever also set `wheat_rush_tiles`**. The
joint configuration — the actual replacement mix — is unmeasured.

## What today's measurement CHANGED about the thesis (recorded before running)

The mechanism occupancy.md proposed is **falsified**, and this registration
proceeds on a different, weaker one. Both facts are recorded here so the
result cannot later be attributed to a story it did not test.

- FALSIFIED: "strawberry holds ground at ~0.8 actions/tile-day vs wheat's
  ~1.0, so replacing wheat lowers labor demand per tile-day held." Direct
  measurement on a thunder replay puts strawberry at **~0.995
  actions/tile-day — statistically equal to wheat**. There is no labor saving.
- SURVIVING mechanism: `plant_quota` (dispatch.py:245) is **wheat-only by
  explicit comment**, so wheat's standing area is throttled by a daily
  replant cap while a strawberry patch is established in one unthrottled
  burst and then holds for 16+ days. The claim under test is an
  ACQUISITION-RATE advantage, not a labor-cost advantage.
- Also measured today and weighing AGAINST the thesis: strawberry explains
  only ~59% of thunder's revenue gap (the rest is more hired labor, which we
  measured as strictly negative for us — adding hands raises idle share);
  husbandry is the largest revenue category for both agents (52-56%); and
  thunder's patch is 37 tiles while our zone is hard-capped at 31 by
  construction (49 NW+NE tiles − 8 melon − 10 pasture), with wheat reaching
  zero at target 31 — the known killer.

Honest prior: **CLOSED is more likely than ALIVE.** This screen exists because
the joint arm is cheap, unmeasured, and the last untested form of the thesis —
not because the evidence favors it.

## Registered design

Promotion (win-rate) gates, candidate `champion` + `--agent-config`, opponent
`frozen:m3b_live_b6ce655` (the shipped default — kaggriculture#91's viability
comparison), n=100 seeds (200 games, each seed played at both seats), band
834000, all arms on the same seeds:

| arm | agent_config | purpose |
|---|---|---|
| R1 | `{"strawberry_tile_target": 16, "wheat_rush_tiles": 20}` | replacement, conservative |
| R2 | `{"strawberry_tile_target": 20, "wheat_rush_tiles": 25}` | replacement, thunder-like ratio |
| R3 | `{"strawberry_tile_target": 24, "wheat_rush_tiles": 30}` | replacement, aggressive |
| C1 | `{"strawberry_tile_target": 20}` | CONTROL: satellite (wheat uncapped) — must reproduce the known failure |
| C2 | `{"wheat_rush_tiles": 25}` | CONTROL: wheat reduction alone, no strawberry |

The two controls are the point of the design: they isolate whether the JOINT
configuration does something neither knob does alone. If R2 ≈ C1, the
"replacement" framing adds nothing and the closed line already covered it.

## Decision rule (fixed before launch)

- **ALIVE** (proceed to a promotion-grade registration, and only then consider
  any code work): at least one R arm reaches **win rate ≥ 0.50 with Wilson
  ci_lower > 0.40** vs the shipped default, AND beats control C1 by a margin
  larger than the gap between C1 and the best previously-measured satellite
  arm (rate 0.088).
- **CLOSED**: no R arm clears that bar. The replacement framing is then
  measured, not merely argued, and the strawberry thesis is closed in both its
  forms for this competition. No successor screen.

Rationale for the 0.50 bar: a mix that loses head-to-head to the agent we
already ship has no path to shipping, whatever its money profile. The best
prior strawberry arm reached 0.088. Anything that cannot at least draw with
the shipped default does not justify a code change, let alone a reference-frame
change to a deliberately frozen invariant.

No extensions, no added arms, no band changes after launch. A failure is not
re-run at larger n inside this registration.

## Pairing note (kaggriculture#82)

Every arm here moves tile occupancy from day 0, so shop-roster coupling is
expected at or near 8/8 draws. That is acceptable: this is a head-to-head
WIN-RATE gate where both agents play the same episode, so there is no
cross-arm pairing to degrade. No money-gate claim is made from this screen.

## Consequence

ALIVE authorizes a full registration, not a submission. CLOSED ends the
strawberry thesis. Nothing here authorizes an upload; T-2 freeze is
2026-09-28 and a new submission evicts one of the Bradley-Terry pair
[M3b 55784368, M3a 55471731].
