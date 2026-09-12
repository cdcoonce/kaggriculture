# Pre-registration: the land-unlock hiring burst

Date: 2026-09-12
Candidate: `champion` with the arms' knobs. Both knobs ship default-neutral and
are independently proven no-ops at their defaults, so the build under test is
`main` itself plus two dormant fields.
Status: REGISTERED — the expression check runs only after this document has
merged. The screen runs only if an arm passes the check.
Authorization: owner decision 2026-09-12 (dispatch rewrite), taken after nine slices
closed without an advance.
Instrument: own bank against the public-leader panel, CALIBRATED in
`eval/prereg/2026-09-11-panel-instrument-calibration.md`.

## What this slice is, after two mechanisms were dropped on evidence

The owner's decision named three mechanisms. Two are dropped before any code, each
for a reason found in the repo rather than discovered by running it.

**DROPPED — midnight reachability.** Already built, pre-registered, gated and
refuted, on branch `perf/day-boundary-guard` (`a44dc9d`, `d2b92ba`, `f8689ed`),
which never reached `main`. The implementation is exactly the filter this slice
would have written: a `_day_budget` of `HOURS_PER_DAY - view.hour`, a
`if dist + 1 > budget: continue` in dispatch's nearest-task pass, the farmer
exempted, four tests including the off-by-one boundary. It works mechanically —
orphaned steps fell 838 -> 638 (19.3% -> 15.1% of movement). It does not pay:
`f8689ed` records "mean -1,084, median -2,223, ci_lower -4,212, mde_80 4,684,
n_regressed 11/20" and the diagnosis **"the freed turns go to idle rather than to
work, so there is nothing for the money to come from"** (idle rose 4.1% -> 5.1%,
productive share 31.7% -> 31.9%). The waste is real; removing it does not convert
to money against a crew the labor slices measured saturated. Not re-opened here.

**DROPPED — pairing plantings with same-day watering.** Not implementable and
largely already present. The engine applies exactly one action per unit per turn:
`_apply_unit_action` reads `op = action[0]` and every branch returns, so a
`["PLANT","WATER"]` action parses as `op="PLANT", crop="WATER"`, and since
`"WATER" not in CROPS` it is a silent no-op that plants nothing and waters
nothing. Separately, `_Task` has no multi-action field and no such concept exists
anywhere in the codebase. What the mechanism wanted is already delivered by
dispatch's Pass 1 ("a unit already standing on one of this class's task tiles
keeps it"): PLANT does not move the unit, so next turn Pass 1 claims the
resulting priority-0 WATER task before any distance comparison runs. There is no
walking to save.

**KEPT, and it is the real lever.** The hiring gap, in two coupled parts.

### M1 — the burst (`plan.py`)

The leaders' hand count tracks newly-unlocked land rather than a fixed headcount:
0-4 hands through day 6, 7 the day after NE unlocks, **14 the same day SW unlocks
(day 10)**, then oscillating 8-14 (`eval/recon/2026-09-11-leader-opening-tape-855000.md:65,132-136`,
exact across leaders and seeds through day 15). Ours is flat at 10 from day 10
onward. We field 10 on the day the workable board roughly doubles.

**This is not `extra_hands`, and the distinction is the whole hypothesis.** Hands
are daily rentals — `_end_of_day` empties `farm["hands"]` and resets
`hires_today` — and hire cost is Fibonacci in the count already hired that day.
A day's cumulative cost is ~$143 to reach 10 hands and ~$986 to reach 14: about
**$843, once**. `extra_hands=2` raises the target *every* day for the rest of the
game and measured **−$3,545**; `extra_hands=1` measured +$340. Those are flat
all-game knobs and are not evidence about a one-day burst. `plan_day` already
knows in the same call whether it is submitting a `BUY_LAND`, so the trigger
needs no new cross-turn state.

### M2 — hire slot floor (`market.py` / `policy.py`)

`market.MAX_ORDERS = 10` caps the whole per-turn order list and the engine
silently drops the overflow (`market.py:100`, truncated at `market.py:426`).
`build_orders` appends sells, then buys, then hires last (`policy.py:941-944`,
"Buys first, hires last"), and `test_hires_beyond_the_market_order_cap_are_dropped_not_deferred`
(`test_policy.py:1395-1416`) proves the drop is silent rather than deferred.

## The registered interaction prediction

**M1 fires on exactly the turn M2 protects.** The burst triggers on the turn that
submits the SW `BUY_LAND` — which is itself an order competing for the same ten
slots, on the busiest turn of the game. So M1 alone is predicted to be partly or
wholly self-defeating: it raises `hire_count`, and the cap silently eats the
extra HIRE orders it generates. This is registered in advance, not discovered
afterward, and it is why BURST_SLOTS is an arm rather than a follow-up.

## Reasons to doubt, on record, before any data

0. **THE HAND GAP IS A SYMPTOM OF A CASH GAP, and this is the reason to expect
   the slice to fail.** The same recon row that shows the leaders fielding 14
   hands to our 10 on the SW-unlock day also shows them holding **$7,425 against
   our $2,520** (`eval/recon/2026-09-11-leader-opening-tape-855000.md:65`) —
   about three times the cash. After a $2,000 land purchase we hold roughly $520,
   and the Fibonacci rungs from the 11th to the 14th hand cost about $843
   (89 + 144 + 233 + 377). **We cannot afford the leaders' crew on that day even
   with every order slot free and the target raised.** The burst is therefore
   expected to be cash-limited rather than slot-limited or policy-limited, and
   the honest form of this slice is that it measures how much of the gap is
   mechanical (slots, target) versus how much is simply that the leaders are
   richer by then. Expression criterion 1 is sized to fail cheaply if the answer
   is "almost none", before the screen spends a single game.

1. **The freed-labor channel is already refuted once.** The day-boundary guard
   removed real waste and the turns went idle. If the farm cannot use the labor
   it already has, four more hands for one day may go idle too. The difference
   this slice bets on is timing: the burst lands on the day the board doubles,
   when there is new ground to work, whereas the guard fired on ordinary days.
   If MID's "freed turns go idle" generalizes, this slice fails the same way.
2. **Cash.** `LAND_RESERVE` keeps only $500 after a $2,000 SW purchase, and the
   engine's `_do_hire` silently returns when money is short. The burst may be a
   partial no-op exactly when it fires. REPORTED as a recon quantity.
3. **More hands has measured negative twice.** EH2 −$3,545, EH1 +$340. The
   one-day-versus-all-game distinction is a real mechanical difference, not a
   rationalization — but it is a distinction this project has never measured.
4. **Every arm here has raised the opponents' banks more than ours.** These are
   production levers, so the confirmation-stage margin guard is the likely
   binding constraint, exactly as it was for STACK3 (−$2,622 against > −$2,000).
5. **The instrument cannot see the population that scores us.** The ladder pairs
   on similar skill rating; against this panel every arm to date wins 0-2% of 128
   games. Own bank is calibrated to rank our own variants, and that is all it is
   used for here.

## Registered arms — values TODO pending the built knobs

- **SLOTS** — `hire_slot_floor=4`. Isolates "are hires actually dropped by the
  cap, and does protecting them pay", with no change to the target.
- **BURST** — `land_unlock_hand_burst=4`. Isolates the burst at the shipped hire
  cap. Per the build recon below this arm is expected to change *timing* and not
  headcount; it is registered so that expectation is measured rather than
  assumed.
- **BURST_CAP** — `land_unlock_hand_burst=4` + `max_hires_per_turn=10` +
  `hire_slot_floor=4`. **The only arm that can express the strategy at all.**
  The burst raises the target, the raised cap lets the turn actually place the
  hires, and the floor keeps them out of the truncation. Registered because an
  arm that cannot express its hypothesis measures nothing: BURST alone is
  bounded by `max_hires_per_turn=4`, and the build recon already showed that
  bound binding.

`max_hires_per_turn=10` is not a free addition — it is H10, independently
measured at **+$781** (95% CI [−$1,234, +$2,797]). BURST_CAP therefore carries a
known mildly-positive component, and its verdict must be read against H10's
+$781 rather than against zero. Stated here so the comparison cannot be chosen
after the numbers land.

## Disclosure: recon that predates these criteria

The two knobs' build carried a mechanism recon (n=2, seeds 855000-855001 against
`public:sokolovsky-v12`, tracing real `plan_day` calls), and its result is known
before this document's criteria were written. Disclosed rather than buried:

- The burst turn fires as designed — 4 hires requested where shipped asks 0.
- **Peak `hires_today` on the unlock day is 10 in both arms.** The burst applies
  on the turn the order is *submitted*, while `active_tiles` still describes the
  old board, so roughly 3 of the 4 merely pre-empt the climb the next turn's base
  target makes anyway; and `max_hires_per_turn=4` bounds the turn while the
  raised target is gone by the next, so the clamped remainder is never
  re-requested.
- The leaders' 14 is a **one-day spike**: on days 13-15 they run 8/9/9, *below*
  our flat 10. We do not carry a headcount deficit.

Every criterion below is anchored on quantities measured before these arms
existed — shipped's own 10 hands on the unlock day, and the leaders' 14 — not on
any observed value of an arm. That is the same anchoring rule
`eval/prereg/2026-09-12-stack-measured-positives.md` used for its criterion 1.

## Expression check (pre-launch recon; a precondition)

Criteria fixed here, before any arm data exists:

1. **M1 fires:** mean hands on the SW-unlock day rises above the shipped 10.
2. **M2 fires:** HIRE orders emitted that survive truncation rise on the
   unlock turn against shipped.
3. **The interaction is measured, not assumed:** report hands-on-unlock-day for
   BURST and BURST_SLOTS separately. If BURST alone does not raise hands while
   BURST_SLOTS does, the cap was the binding constraint, as predicted.
4. **THE LAND PURCHASE MUST NOT SLIP.** The SW unlock day for every arm must be
   no later than shipped's on every recon seed. This is a hard veto, not a
   reported quantity. The engine spends market orders **in list position** and
   `_do_buy_land` silently returns when money is short, so an arm that puts
   hires in front of a purchase on a cash-bound turn converts a dropped hire
   into a failed land buy with no error anywhere. `hire_slot_floor` exempts
   `["BUY_LAND"]` from displacement specifically to make this impossible, and
   this criterion is the check that the exemption actually holds in play rather
   than only in unit tests. An arm that slips SW is dropped outright.

5. **Degenerate guardrail:** the arm still sells at least one unit of every item
   shipped sells at least 10 units of, and `buys` is unchanged — the burst must
   never cause or suppress a land purchase.

6. **Cash, reported:** mean farm money at the moment of the SW purchase, and the
   number of HIRE orders that were requested versus actually settled on that
   turn. This is what separates "slots were the constraint" from "cash was the
   constraint" (doubt 0), and it is the quantity that tells the writeup which.

An arm failing a criterion cannot express its hypothesis and is dropped before
any run. Amendment is by changing values, never by relaxing a criterion, and is
disclosed.

## Registered design

Money gate: candidate `champion` with the arm's `--agent-config`, baseline
`champion` at shipped defaults, against `public:sokolovsky-v12`,
`public:rayk-v11`, `public:kaito-v4`.

- **Screen:** band **884000**, n = **64** per leader.
- **Confirmation:** selected arm only, band **885000**, n = **128** per leader.
- **Guard:** confirmed arm against `frozen:m3b_live_b6ce655`, band **886000**, n = 64.

All three bands verified unused by every ledger in `eval/gates/` (272 files
checked 2026-09-12: no `seed_base` >= 884000 anywhere) and claimed by no earlier
registration. 900000-901249 remain reserved for #119.

## Decision rule (fixed before launch)

Per arm and leader i, take `mean_delta_i`, `stderr_i` and `opponent_mean_delta_i`
from the ledger; pool as the simple mean with pooled se `sqrt(sum stderr_i^2)/3`;
intervals are estimate +/- 1.96 x se. The ledger's `passed` field is not the verdict.

**INVALID** if the engine is not 1.32.7, a knob is absent, the expression check
has not passed, or any run records a crash-type veto or a `baseline_degenerate` /
`opponent_degenerate` veto. A `candidate_degenerate` veto is a result, not an
invalidity.

**SCREEN — an arm ADVANCES** only if, at band 884000: pooled own-bank delta
**>= +$4,000** (about +40 Elo on the ladder-derived slope); pooled 95% lower
bound **> $0**; and no single leader's point estimate below **−$2,000**.

**SELECTION:** among advancing arms, the highest pooled lower bound.

**CONFIRMED** only if the selected arm, at band 885000 n=128, has pooled delta
**>= +$4,000**, pooled lower bound **> +$1,000**, and pooled **margin delta**
**> −$2,000**.

**GUARD:** the confirmed arm's own-bank delta against `frozen:m3b_live_b6ce655`
must have a point estimate **> −$2,000**.

**NOT ADVANCED / NOT CONFIRMED** otherwise. No arm substitution, band reuse, or
threshold change after launch.

REPORTED, NOT GATING: per arm the gap and the margin delta; hands-by-day for the
selected arm; and the idle share, so this slice can say whether the burst's labor
went to work or to idle the way the day-boundary guard's did.

## Registered predictions

Stated before the expression check runs, so the scorecard is honest either way.

- **BURST fails expression criterion 1 — 80%.** The build recon already showed
  peak `hires_today` unchanged at 10 on the unlock day, because the burst lands
  on the submission turn while `active_tiles` still describes the old board and
  `max_hires_per_turn=4` bounds that turn. At the shipped cap this knob buys
  timing, not headcount.
- **BURST_CAP passes criterion 1, but narrowly — 60%.** It raises target and cap
  together, which is the only combination that can place the hires. The reason it
  might still fail is cash: after a $2,000 land purchase we hold roughly $520
  against Fibonacci rungs of ~$89/$144/$233/$377, so the affordable burst is
  about **two** hands, not four.
- **SLOTS passes criterion 2 — 75%.** Hires demonstrably are dropped by the cap
  (`test_hires_beyond_the_market_order_cap_are_dropped_not_deferred`: 10
  requested, 3 land), so protecting the first few should raise settled hires on
  contended turns. Whether that is worth money is a separate question.
- **No arm advances at the screen — 92%.** Two affordable hands on one day of a
  thirty-day game, against a +$4,000 bar (~+40 Elo on the ladder-derived slope).
  The largest effect this project has ever measured is +$3,637 and it came from
  a whole-game crop-and-herd change, not a one-day crew nudge.
- **If an arm does clear the bar, its margin delta is negative — 80%.** Every arm
  measured in this project has raised the opponents' banks by more than ours.
- **The finding that survives is about cash, not labor — 85%.** The leaders field
  14 hands on the unlock day because they hold **$7,425 to our $2,520**, and they
  run 8/9/9 on days 13-15, *below* our flat 10. If that is what the numbers say,
  the hiring line closes and the open question moves upstream of the dispatcher
  entirely, to why day 10 finds us $4,900 poorer.

## Consequence for the record

Whatever this returns, the two knobs are default-neutral and stay shipped-off.
A NOT LAUNCHED here closes the last mechanism named in the 2026-09-12 owner
decision, which would make the dispatch-rewrite branch closed in all three of its
parts — midnight reachability by the 2026-08-16 gate, plant/water pairing by the
engine's one-action-per-unit-per-turn rule, and hiring by this document.

## Consequence

CONFIRMED plus a passing GUARD authorizes an upload **decision** only. The next
upload evicts M3b and that remains an owner decision.

## ADDENDUM — EXPRESSION CHECK (2026-09-12): SLOTS VETOED, BURST FAILS, BURST_CAP passes alone

Run on `a24aeee` (#155's pre-merge SHA, squash-merged as `20427d6`; `packages_dirty:
false`), engine 1.32.7, seeds 858000-858007 against `public:sokolovsky-v12`.
Record: `eval/recon/2026-09-12-land-unlock-hiring-check-858000.json`.

| arm | SW day | hands @ SW day | peak hands d0-14 | recon bank |
|---|---|---|---|---|
| shipped | 9.50 | 9.75 | 10.00 | 73,331 |
| SLOTS | 9.88 | 10.00 | 10.00 | 71,940 |
| BURST | 9.00 | 10.00 | 10.00 | 61,826 |
| BURST_CAP | 9.00 | **11.00** | **11.00** | 71,325 |

Criterion 1 is read against its **registered anchor of 10** — shipped's value measured
before these arms existed — and not against shipped's 9.75 in this run. The anchor was
fixed in advance precisely so a noisy baseline could not manufacture a pass, and it is
honoured here even though the looser reading would have passed two more arms.

**SLOTS is VETOED by criterion 4, and the veto is the finding.** `hire_slot_floor=4`
alone slips the SW purchase from day 9 to day 10 on **four of eight seeds** (858002,
858003, 858005, 858007) — and it does so *with* `BUY_LAND` already exempted from
displacement. The exemption works; the mechanism is not order position but cash.
Protecting hire orders from truncation means more hires actually settle, the daily
Fibonacci wage bill rises, cash accumulates more slowly, and `plan_day`'s
`budget >= 2000 + LAND_RESERVE` gate trips a day later. **The knob buys hands by
spending land.** That is the same cash constraint criterion 4 was written to catch,
arriving through a channel the registration did not anticipate: it predicted the hazard
as an order-position failure and got it as a wage-accumulation failure.

**BURST fails criterion 1 at 10.00 against the anchor of 10**, and the reason is in the
adjacent column: peak hands over days 0-14 is **10.00 for BURST and 10.00 for shipped**,
identical. The burst changed nothing about headcount. It fires, and the hires it requests
displace hires the base target would have made anyway — exactly what the build recon
found at n=2 and what this check confirms at n=8 on fresh seeds.

**BURST_CAP passes both criteria and goes to the screen alone**, at 11.00 hands against
shipped's 9.75 and an unslipped SW day. It reached **11, not the leaders' 14** — the
cash ceiling the registration named: after a $2,000 land purchase we hold roughly $520
against rungs of ~$89/$144/$233/$377, which buys about one hand. The registration
predicted "about two"; the measurement says one.

**Reported, not gating.** Every arm's recon bank is at or below shipped's (71,940 /
61,826 / 71,325 vs 73,331), and BURST alone is $11.5k below it. This is n=8 against one
leader on a shared baseline and it decides nothing — the screen at n=64 across three
leaders is the instrument. It points the same way the cash argument does.

**Predictions scorecard (the check).**
- **Right that BURST fails criterion 1** (registered 80%). Right for the registered
  reason, too: no headcount gain, peak identical at 10.00.
- **Right that BURST_CAP passes narrowly and is cash-limited** (registered 60%), and
  right about the mechanism; **wrong on the size** — I said about two extra hands, it
  bought one.
- **Wrong about SLOTS.** I registered 75% that it would pass, on the grounds that hires
  demonstrably are dropped by the cap. They are, and protecting them still costs more
  than it earns, because the wage is daily and the land gate is a threshold.
- **Right that the binding constraint is cash rather than labor** (registered 85%). Every
  arm that added a hand paid for it somewhere else, and the one that added the most hands
  is the one that slipped the purchase.

## ADDENDUM — SCREEN VERDICT (2026-09-12): NOT ADVANCED at −$214, and the margin signal was opponent-specific

Run at BUILD `20427d6` (`main` with both knobs merged), engine 1.32.7, band 884000,
n = 64 per leader. Three ledgers, no crash and no veto.

| opponent | n | mean Δ | se | 95% CI | opponent Δ | margin Δ | regressed |
|---|---|---|---|---|---|---|---|
| public:sokolovsky-v12 | 64 | +$768 | 1,986 | [−$3,124, +$4,660] | −$7,533 | **+$8,301** | 31/64 |
| public:rayk-v11 | 64 | −$720 | 2,214 | [−$5,059, +$3,619] | +$4,660 | −$5,380 | 33/64 |
| public:kaito-v4 | 64 | −$688 | 2,221 | [−$5,041, +$3,665] | +$3,686 | −$4,374 | 33/64 |
| **pooled** | | **−$214** | **1,237** | **[−$2,639, +$2,211]** | | **−$485** | |

Criterion 1 fails at **−$214** against the +$4,000 bar; criterion 2 fails with a pooled
lower bound of −$2,639; criterion 3 passes (worst leader −$720). **BURST_CAP is NOT
ADVANCED, and with it the land-unlock hiring slice.** No confirmation or guard ran;
bands 885000 and 886000 are retired unused.

This is not a power failure at the size that mattered. Per-leader `mde_80` runs
$4,997-$5,572, so pooled the design could detect roughly +$3,000; a +$4,000 effect was
within reach and is not there. The arm is indistinguishable from zero.

**The margin signal did not survive its second leader, and that is worth recording.**
Against sokolovsky-v12 the arm took **$7,533 off the opponent** for a margin delta of
**+$8,301** — the first strongly positive margin this project has measured, on a
scoreboard where every prior arm made the leaders richer than it made us. Against the
other two the sign flips: +$4,660 and +$3,686 to the opponent, margins of −$5,380 and
−$4,374, pooling to −$485. One leader's opponent delta is not a property of the arm.
This repo already carries that lesson from the other direction (*one opponent's gate
promotes what four opponents reject*); this is the same trap wearing the opposite sign,
and it was reported rather than gated on precisely because the registration fixed own
bank as the metric before the run.

**Predictions scorecard.**
- **Right that no arm advances** (registered 92%). Pooled −$214 against a +$4,000 bar.
- **Right that the binding constraint is cash rather than labor** (registered 85%).
  BURST_CAP bought exactly one extra hand on the unlock day and it bought nothing.
- **Not triggered:** the prediction that an advancing arm's margin would be negative.
  No arm advanced.
- **Wrong, in the check, about SLOTS** (registered 75% to pass), and wrong in a way that
  taught the most: protecting hire orders from truncation slips the land purchase,
  because the wage is daily and the purchase gate is a threshold.

## Consequence — the dispatch rewrite is closed in all three parts

The 2026-09-12 owner decision named midnight reachability, plant/water pairing, and
burst hiring. All three are now closed:

- **Midnight reachability** — by the 2026-08-16 gate `f8689ed` on branch
  `perf/day-boundary-guard`: the filter removes the orphaned walking it targets and the
  freed turns go to idle, so there is nothing for the money to come from.
- **Plant/water pairing** — by the engine: one action per unit per turn, and dispatch's
  Pass 1 already keeps a unit on the tile it planted.
- **Burst hiring** — by this screen.

Ten registered slices have now closed without an advance. Both knobs stay shipped-off at
their defaults and both are proven byte-identical no-ops there, so `main`'s behavior is
unchanged by any of this. Nothing here authorizes an upload, a default change, or a
further run.
