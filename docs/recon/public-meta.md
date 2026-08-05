# Kaggriculture research — 2026-08-04

Method: in-app browser (Claude Browser tabId tab-2), no sign-in, no votes/comments/joins.
Note on titles: two of the three target notebook titles given in the task do not exist
verbatim on Kaggle; nearest real matches were used (see notes per-item). Treat those two
as best-effort substitutions, not confirmed exact matches.

Leaderboard context (for calibration): 1539 teams. Rank 1 = 3105.6. Top 50 threshold ≈
2625+. Rating scale is Bradley-Terry-derived (per organizer post), not raw bank — matches
the "Public/Best Score" numbers shown on notebooks (e.g. prvsiyan's notebook = 2788.7,
exactly matching their live leaderboard row).

---

## 1. "[STRONG STATR] Baseline Agent | LB 950+" (target title: "[STRONG START]... V10")

Actual title has a typo ("STATR" not "START"), no "V10" in title (body calls itself
"Barnyard Economist v5"). By Roman Rozen. URL: /code/romanrozen/strong-statr-baseline-agent-lb-950
Version 4 of 4. Public Score 767.6, **Best Score 837.2 (V2)** — i.e. despite the "LB 950+"
title, the notebook has never actually scored 950+ in its visible version history. This is
well below the competitive range (top-50 leaderboard cutoff is ~2625).

Key claims/strategy:

- Frames the game as "a scheduling problem (one action per worker per turn) on top of a
  price-impact model... with a third player — the town — quietly draining the market."
- Built by diffing the farm against **five real downloaded ladder replays** day-by-day
  rather than tuning against agents extracted from other notebooks.
- Benchmarked head-to-head vs rebuilt versions of Hamburger, Scenario-Aware Economic
  Policy, Night Harvest/Blackclaw, and Frontier Lab — all "rebuilt from published
  notebooks, not what those teams currently run" (explicit caveat re: relative signal
  only, not literal ladder prediction).
- **Melon actually caps at day 10, not day 12** as the overview page states:
  `window_start = (max_yield_day+1)//2 = 6`; +1 yield per watered in-window day; cap 6 ⇒
  reached after 5 waterings ⇒ age 10. Days 11–12 add nothing.
- Farm-hand hiring cost is Fibonacci-scaled: `hire_cost = mult * fib(n_already_today)`.
  12 hands cost 376 coins for 288 extra actions (~1.3 coins/action) vs one in-window melon
  watering worth ~$250 — hands are "nearly free" in the cheap region.
- **"The mistake that cost 40,000 points"**: price = `base ± amp·f(|inventory−10000|)`
  with per-product, per-side (glut vs. shortage) shape functions (`linear`,`sq`,`sqrt`,`log`).
  V1 misread the shape table and concluded log-curve items (wheat/eggs) were "safe" to spam
  because they "crash softly" — backwards: the log curve means there's _no real ceiling_ on
  how much you can dump, not that dumping little is required. Real MARKET_PARAMS reproduced
  verbatim from `kaggriculture.py`:
  ```
  WHEAT (25,400,log,0.20)  CARROT (35,450,sqrt,0.70)  TOMATO (60,200,sqrt,0.60)
  STRAWBERRY (120,100,linear,1.60)  MELON (250,300,sq,3.60)  EGG (50,332,log,0.20)
  MILK (160,122,linear,1.60)  WOOL (200,105,sq,3.20)  FERTILIZER (100,200,linear,0.40)
  ```
  Printed glut-price table (sold-units 0/25/50/100/200/400) — MELON: 250/244/225/150/1/1;
  STRAWBERRY: 120/72/24/1/1/1; WOOL: 200/164/55/1/1/1. I.e. melon price already halves by
  glut=100 and floors by glut=200 — it does NOT "barely move" at moderate volumes.
- Town/shop demand table: each unlocked shop consumes 1 of every product it demands every
  4 turns (6/day), doubled for single-product shops, plus a town centre taking 1 of
  everything every 12 turns (doubled after day 20).
- Section 3 "What one action is worth": `CARE` mechanic (`cared_today`/`fed_today` flags),
  bonus paid on next scheduled animal turn; till-value table ranks Milk in-window watering,
  Cow/Sheep hand-cared, `COLLECT_FERTILIZER`, Goose hand-cared, Strawberry by coins/action.
- Section 4 "Reading five real replays": three findings the overview never states —
  (1) top agents' land purchases and asset buys front-run the writer's own by ~10 days;
  "at day 15 they have ten times my cash"; (2) "I always leave weeds; they almost never do."
- Section 5 "Three structural bugs, and their fixes": (a) role map recomputed from
  cash/herd size every turn caused tile flip-flopping — fixed by making roles a pure
  function of which quadrants are unlocked; (b) freezing roles alone made things _worse_
  (77k→71k) until a wheat "filler crop" (4-day cycle, self-clearing on harvest) was added so
  the pen is never blocked; (c) planting 45 strawberries on one day is a "time bomb" — they
  all decay together around day 21, since strawberries stop after 4 yields and then rot;
  fix: "do not spend on land before day 4" (opening $3,000 goes into livestock first) —
  moved the benchmark from ~11k deficit to within ~5k on seat 0, level on seat 1.
- Section 7 Validation: engine latency measured directly — mean 1.41 ms, p95 2.42 ms, max
  4.19 ms per `agent()` call (actTimeout = 1000 ms) — plenty of compute headroom.
- **Section 8 "Where this still loses, and an honest caveat" — the most important part**:
  - Frontier Lab still ahead by ~5k on seat 0, level on seat 1. Two remaining structural
    gaps: (1) top agents run **cow-heavy herds** (10-11 cows, rotate ~20 strawberry tiles
    continuously) instead of planting 45 strawberries in waves — author tried this and it
    scored _worse_ in his harness, doesn't yet understand why; (2) top agents **never
    accumulate weeds** (author's farm sits at 5–15 weed tiles from day 12 on, "every one is
    a tile paying nothing").
  - **"Nobody, including me, reads `obs["farms"][1-player]`. It is fully visible: their
    tiles, planting, planting days. Sixteen melons planted on their day 0 means a ~96-melon
    dump lands on day 10 — sell before it, or plant something else. I still think this is
    the largest untapped edge in the competition."** — an explicitly-named, publicly
    documented but (per this author) unexploited edge: using the fully observable opponent
    farm state to anticipate and front-run their sell-offs.
  - Honest caveat on noise: v5 loses a **direct mirror match against v4, 0–4**, while
    beating v4's results against every external opponent — because mirror matches mostly
    measure who exploits the _other's_ specific timing, "close to worthless as a ranking
    signal." Seed sweeps (2–4 seeds) against an identical opponent config ranged 96k–119k.
    **"Treat any difference under ~8k in this notebook as unresolved, and re-measure before
    you act on it."**
  - Mechanics are stated as "quoted from `kaggle_environments/envs/kaggriculture/kaggriculture.py`."

What it ignores / doesn't do: does not read the opponent's observable farm state (explicitly
flagged as the biggest left-on-the-table edge); does not run cow-heavy herds; does not solve
weed accumulation; title's "LB 950+" claim is not reflected in the notebook's own recorded
best score (837.2).

---

## 2. "Kaggriculture: Findings from Zero to Top Meta" (title matches exactly)

By Rayk Kretzschmar. URL: /code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta
Version 14 of 14. **Public Score 2121.9, Best Score 2210.2 (V12)** — solidly mid-tier
relative to the live leaderboard (top 50 ≈2625+), a genuinely reasonable public baseline,
much stronger than #1 and #3.

Framing: "collection of engine notes" that became a build diary. Explicitly distinguishes
"a replay is one match, not source code. The losing player may be excellent, and the winner
may only have had the favorable seed or market order." Cites its own lineage table of public
work used: Bovard (Getting Started/agent contract), Georgy Mamarin (Visualized — melon
timing/job-value framing), Roman Rozen (Barnyard Economist — staged mixed herds,
clone-aware market timing = notebook #1 above), Roman Tamrazov (Hamburger — economic
scheduler), Pilbeoung Kim (Scenario-Aware — herd target experiments), Kun Zhang
(C22/C24/C25 — cross-play gains), crvsgxr (Frontier Lab — repeated schedules/opponent
response/market timing), plus public leaderboard replays.

Engine config constants: `BOARD, DAYS, TURNS_PER_DAY = 10, 30, 24`; `EPISODE_STEPS = 720`;
`STARTING_MONEY = 3000`.

**Section 2 — engine details separating weak from strong agents** (independently derived,
corroborates notebook #1):

- 2.1 Melon: `max_yield_day=12` ⇒ `window_start = ceil(12/2) = 6` ⇒ ages 6–12; +1/day
  in-window (+2 if fertilized); cap 6 ⇒ max reached at **age 10, not 12** (same finding as
  notebook #1, derived independently). 16 tiles × 6 = 96 melons "when execution is
  perfect"; missing water on days 6–10 is "a common silent leak."
- 2.2 `SELL` only sees the shed, not unit inventory — `HARVEST` doesn't auto-fund a same-turn
  buy; you must `DROP` first or the sale doesn't count until end-of-day auto-drop, "often
  too late."
- 2.3 **Fertilizer can be sold** — "Competition text emphasizes buying fertilizer; the
  engine's generic SELL path still accepts it." Each animal generates a fertilizer/day
  side-income stream "until the market is flooded." (Independently corroborated by staff in
  discussion #732450 and #731953 below.)
- 2.4 Ladder scoring is **win/loss/tie only** — "a 140k bank that loses still loses rating."
- Own melon glut-curve simulation (same params: I0=10000, base=250, T=300, above_target=3.6)
  concludes: "Labor and rival sales move the real optimum; public leaders often use ~6-16
  melons, not a full 25-tile dump," `illustrative_peak_tiles: 26`. This directly contradicts
  a "dump everything, price barely moves" framing (see discussion #732623 critique below).

**Section 3 — strategy clusters in the public meta** (taxonomy of the field):

| Cluster                       | Opening                  | Peak farm                     | Strength                          | Failure mode                              |
| ----------------------------- | ------------------------ | ----------------------------- | --------------------------------- | ----------------------------------------- |
| A. Pure cow ranch             | 5-10 cows, little crop   | ~10 cows, often NE only       | punishes soft/crop-only bots      | "milk wars" collapse banks; coin-flip H2H |
| B. Melon IPO                  | 16 melons + 2 cows       | day-10 dump to 12×+8s+3 quads | huge capital spike if uncontested | 2nd melon dumper hits the $1 floor        |
| C. Staged economic herd (C2x) | 3 cows+1 sheep floor     | staged 4→6/10→14/15           | strongest public code family      | everyone forks it → correlated losses     |
| D. Adaptive leader style      | 3c+1s, ~6 melons         | dynamic cow/sheep/goose mix   | robust when contested             | harder to clone cleanly                   |
| E. Stable efficiency tape     | repeated tile trajectory | tight production/labor fit    | reproducible if correct           | can be widely copied                      |

Approx local strength ordering: `starter << pure cow ranch << melon IPO << C03 << C05 <<
Radiant routers << c11/c12/c13 << c14`. Caveat: "a bot that prints 100k-170k vs starter can
still sit mid-ladder, because ladder opponents are other strong farms."

**Section 4 — replay diary, c14 → multi-leader market meta** (the meta-history):

- Rule for trusting a replay: does the same field schedule repeat across opponents? is the
  market schedule stable or reactive? does the distilled tape beat the previous agent from
  both seats?
- c14 beat c11/c12/c13 27-3 each, reached 2182.2 standalone.
- **Hamburger's real innovation was timing, not farm layout**: its best branch
  (`Clone_Quad_H1`) checks if the two public farms are still nearly identical, then sells
  **one turn ahead of the expected shared-market dump** — "6-0 against its anchor, mean
  margin +1,865.7." Wrapping this front-run onto a refreshed base gave c15 (14-2 vs the same
  tape without the wrapper — confirms the timing trick, not a stronger base, drove the win).
- Pulled 5 replays each for the top-5 leaderboard teams (fixed a downloader bug that had
  been sampling teams' _newest, lower-rated_ submissions instead of their leaderboard-
  scoring one). **Result: convergence, not diversity — "all five teams were using versions
  of the same 8-cow/5-sheep, three-quadrant plan."** Tapes from different top teams differed
  by only 2–5 field turns and 2–6 market turns from each other, vs. ~226/402 turns different
  from the author's own c15. VN-Orion's tape was the cleanest source (repeated exactly across
  5 games) → became base for c16, which then beat c15 15-1, beat a Superallen "common-meta"
  control tape only 7-7-2 ("reassuring... the two independently sampled common-meta tapes
  behave like the same policy").
- Later promotions: c18 (hold farm fixed, promote premium market schedule surviving a
  ten-team screen), c27 (move terminal field control from step 712→717, "verified final
  window"). Every promotion tested both seats against the previous agent + ≥1 unrelated
  public family — "a high bank against starter is a smoke test, not a promotion test."

**Section 7 — common bugs (high frequency)**:

| Bug                                    | Symptom                                            | Fix                                       |
| -------------------------------------- | -------------------------------------------------- | ----------------------------------------- |
| CARE ranked above melon WATER          | day-9 waters only part of field, yield <70 not ~96 | water priority first in ages 6-12         |
| No DROP after HARVEST                  | produce stuck in unit inventory, IPO underfunded   | DROP when carrying melon/milk/wool stacks |
| Dig melon tiles for pastures too early | destroys fruit before harvest                      | protect valuable melons until sold        |
| Buy many cows day 0, no feed reserve   | animals escape day 2                               | reserve wheat seed before animal spend    |
| Fixed 10 cows forever                  | mirror banks collapse toward ~40k                  | add sheep/strawberry routing              |
| Optimize mean bank vs starter only     | high local bank, mediocre Elo                      | H2H vs strong bots, both seats            |
| Two near-identical active submits      | a meta shift kills both                            | diversify the second slot                 |

**Section 8 — local evaluation protocol** (validation-episode gotcha, directly answers
target #6): 1) compile/import exact packaged main.py; 2) self-play both agents must finish
DONE; 3) play previous best on several seeds, both seats; 4) play ≥1 different public
family; 5) include a near-mirror control once the meta has converged; 6) keep result files
including losses; 7) only then archive. **"Shared-market games are not symmetric. A
one-seat test can reverse the apparent winner."**

**Section 9 — the strategy history in one line**: "melon tutorials → cow ranches → staged
mixed herds → economic schedulers → larger target herds → tape routers → stable c14
efficiency schedule → c15 clone-aware sale timing → c16 common-meta schedule → c18 rank-one
premium-liquidation schedule → c17 refreshed market-common tape → c27 terminal-717
correction." Explicit note that "the endpoint alone never explained the full gain" — each
step's _type_ of improvement differed (labor/inventory timing → market-order exploitation →
route coordination → field structure → terminal-controller handoff timing).

**Section 11 — where I would look next**: "the field plan has become highly correlated, so
another herd-layout copy is unlikely to help." Open questions: inventory-aware sale sizing,
clone ordering, and whether a rival's higher-variance market route "can be gated from
observable scenario state." c27 stopping point: 90-10 in a fresh field-policy gate, 13-7
directly vs c17.

---

## 3. "Kaggriculture: Structured Economic Policy" (substitute for target title

"Observable Economic Control" — no notebook with that exact title was found via
in-app search under several phrasings; this is the closest thematic + well-voted match:
74 votes/Silver, by Pilkwang Kim, explicitly about market/economic policy formalism.
**Flag this as an unconfirmed substitution.**)

URL: /code/pilkwang/kaggriculture-structured-economic-policy. Version 30 of 30.
Public Score 1130.1, Best Score 1289.6 (V13) — below the competitive range, well below
notebook #2's tier.

Style: formal/mathematical (LaTeX-like notation) systems description of a policy engine
rather than a narrative strategy log. Sections: 1 Causal ledger, 2 Production value,
3 Roles/jobs/matching, 4 Workload-responsive labor, 5 Shared-market dynamics,
6 Execution invariants, 7 Deterministic season path, 8 Within-day routing.

Market-control-relevant content (section 5, "Shared-market dynamics"):

- Formalizes public inventory update: `I_{r,t+1} = I_{r,t} + S'_{r,t} - D_{r,t} - C_{r,t}`
  where `S'` is inventory-accreting sales (a sale at the $1 floor still earns $1 but does
  **not** register against public inventory — floor sales are "free" of market-impact
  bookkeeping).
- "The marginal price is a rounded monotone inventory curve around equilibrium I_{0,r}" —
  same two-sided base±amp·f(deviation) model as notebooks #1/#2, expressed formally.
- Applies its own conservative **85% haircut** to projected sale proceeds when planning
  ("purchases follow the projected proceeds curve. Sales contribute only 85% of their
  projected proceeds to the planning ledger. The haircut reduces financing risk; residual
  mismatch is handled by unit-wise partial fill.") — a self-imposed risk control, not a
  documented engine rule.
- Section 6 "Execution invariants": final decision satisfies `|a^field| ≤ N^units`,
  `|a^market| ≤ 10` — i.e. a per-turn cap of 10 market actions is baked into this author's
  own action space (unclear if this reflects a hard engine limit or just this agent's
  self-imposed design — no citation given, unlike notebooks #1/#2's explicit "quoted from
  kaggriculture.py" sourcing).
- Section 8 "Within-day routing": formalizes per-hour worker/action assignment as a
  feasibility-constrained bipartite matching (`Σ 1[A_h(i)=j] ≤ 1`) — a formalized version of
  the "assign" step described narratively in notebook #1.

No explicit mention of an "index-0" or seat-order resolution edge in this notebook.

---

## 4. Discussion #732623 — "Crop price crash analysis — why MELON dominates (with math)"

By David Pedersen (297th in comp), posted 1 day ago, 1 vote, 0 comments (unanswered,
low engagement).

**Claim**: crop price crash resistance is governed by two engine params per crop — `T`
("units before price starts declining") and an `above` shape function (`sqrt` = steep,
`linear` = moderate, `sq` = gentle/convex, "price holds near base for a long time"). Table
given: TOMATO ($60, T=200, sqrt) → ~23-tile/2-batch revenue ~$3k, "crashes to ~$1"; STRAWBERRY
($120, T=100, linear) → ~~$8k; MELON ($250, T=300, sq) → "~~$16k+ (barely moves)." Estimates
~138 cumulative units sold ("23 tiles × 3 yield window × 2 batches") as "still well below
T=300." Also recommends: sell before buy each turn (harvested items land in shed mid-turn,
sell first to fund same-turn purchases); NE land is a trap if your crop crashes anyway; use
zone-based (BFS-per-quadrant) worker routing.

**Does the math hold?** The (base, T, shape) parameter table is _accurate_ — it matches
notebook #1's verbatim-quoted `MARKET_PARAMS` exactly (TOMATO 60/200/sqrt, STRAWBERRY
120/100/linear, MELON 250/300/sq), and organizer replies in discussion #731953 confirm the
same fertilizer params and define T precisely: **"T is the production capacity of a single
5×5 field over a 24-day game at optimal watering... "** — i.e. T is a curve-steepness
_calibration constant_, not a free-crash-zone threshold.

**The core "barely moves" claim does not hold.** Using the actual formula (confirmed via
notebook #1's own printed reference table, which used these identical MELON params): at
glut=100 units sold, melon price is already **150** (down 40% from base 250); at glut=200,
it's floored at **1**. Recomputing directly from the formula
(`price = base - round(target·base/T² · glut²)` for the "sq" shape) at David's own claimed
volume of ~138 units gives melon price ≈ **$60**, not "barely moves" — a roughly 75% price
collapse well before reaching T=300. This is also independently corroborated by notebook
#2's own melon-glut simulation using the identical (250, 300, 3.6) parameters, which
concluded top public agents sell only ~6–16 melons at a time, "not a full 25-tile dump" —
directly contradicting the idea that a full-field melon dump "barely moves" the price.
**Verdict: directionally correct (melon's convex "sq" curve genuinely does crash slower
per-unit than tomato's concave "sqrt" curve at low glut) but the headline quantitative
claim — that a full ~23-tile/138-unit melon dump stays near base price — is not supported
by the engine's own formula or by two independent notebook-based simulations using the same
parameters.** Revenue estimates in the table are likely substantially overstated for MELON
and roughly right-order for TOMATO/STRAWBERRY only at small volumes.

---

## 5. Discussion #732613 — "Are Agents Really Competing Against Each Other?"

By Ehsan, posted 1 day ago, 1 vote, 4 comments.

**Concern raised**: the format looks vulnerable to trajectory copying because two agents
"do not meaningfully interact or affect each other; they can independently perform the same
actions." The only randomness Ehsan identifies is shop-unlock order. Notes some top public
code submissions "appear to replay the trajectories of leading agents" (independently
corroborated by notebook #2's finding of near-identical top-5 tapes). Asks whether
Bradley-Terry ranking (which does not itself fix the underlying design issue) misses
something, and whether there's a mechanic being overlooked.

**No Kaggle staff reply in this thread** — despite staff (Domino Weir, María Cruz) being
active elsewhere in the forum same-week, this thread got only community replies:

- **rooklift**: "The current meta seems to be to just submit a sequence of actions copied
  from someone else, but I expect a good bot that intelligently reacts to the market to
  take over eventually. Someone needs to write it or train it though."
- **Russell Kirk** (178th in comp), the substantive answer: **"the way you 'cash' out is
  completely determined by market dynamics that you PARTIALLY control. Your opponent's
  decision of what to buy and when to sell directly affects your prices when you try to do
  the same. If an opponent tries to oversell something — it makes it cheaper for you to
  buy. If you both are trying to sell the same thing, both your profits will suffer — and
  the first to sell gets the better price."**

This confirms the shared-market mechanism _is_ the real inter-agent coupling (contra
Ehsan's premise) and explicitly states **"the first to sell gets the better price"** — i.e.
execution-order-within-a-turn matters for identical-good sales. This is the closest public
statement to a "market-order resolution" edge found anywhere in this research, but it does
NOT specify _how_ first-mover is determined (seat/player index, submission order, or
something else) — no thread found states or confirms that seat/index 0 always resolves
first. **The specific "index-0 always wins ties" mechanic does not appear to be publicly
documented or confirmed anywhere searched** (see Meta Picture below).

---

## 6. Discussion-list skim (sorted by Most Votes) — bugs, patches, gotchas, recent activity

**Organizer/staff-confirmed engine patches (both very high-signal, both from Kaggle staff
member Domino Weir within the last ~24h):**

- **#732450 "Crucial Information for Starters and Organizers: Documentation vs. Engine
  Discrepancies"** (SIDHAARTH SHREE, 574th in comp, 2 days ago, 13 votes). Comprehensive
  list of doc/engine mismatches, ALL confirmed and fixed in docs by Domino Weir (Kaggle
  Staff) 8 hours before capture — "TLDR: engine is the source of truth":
  - Animal Care Bonus: engine pays **+1**/day, not +2 as old rulebook said. Fixed in docs.
  - **Fertilizer CAN be sold** despite old docs saying buy-only. Fixed in docs. (Matches
    notebook #2 §2.3 and discussion #731953 below.)
  - DIG only clears **unoccupied** structures (animals must escape first) — rulebook was
    ambiguous, now explicit.
  - Planting-day watering: an unwatered seed becomes a weed **the same night** it's planted
    (end-of-day increment runs before weed check) — now explicit in docs.
  - **Melon Time to Max Yield**: docs said 12 days; actual max (6 units) reached at **age
    10** — the last two documented days are dead turns. **Docs now corrected to reflect
    day 10** — independently matches notebooks #1 and #2's own derivations exactly.
  - **Strawberry**: capped at exactly **4 yields** (ages 10,12,14,16, +1 each) then dies —
    not an indefinite "every other day" producer as the old table implied. Docs updated.
  - Yield-per-day table was internally inconsistent (e.g. claimed Tomato=4/day, Strawberry=2
    /day) vs actual effective yields (Tomato=1/day, Strawberry=0.5/day) — docs corrected to
    match engine.
  - Shed is **not a tile object** in the `tiles` array (a naive search will find nothing);
    its 4 access points are exactly `(4,4) (5,4) (4,5) (5,5)` — now explicitly documented.
  - **Farm Hand Spawning on Locked Tiles — confirmed as an actual engine BUG, and FIXED**:
    hands spawn at the 4 shed-access tiles NWSE-first; since only NW starts unlocked, a hand
    landing on (5,5) (diagonally opposite) was fully enclosed by locked tiles and could not
    move until land was bought. **This is a genuine shipped engine patch, not just a doc
    fix** — "Spawned hands on locked tiles can move back to actionable tiles."
  - Submission pitfall noted: `%%writefile main.py` inside a Kaggle Notebook's "Submit to
    Competition" flow can silently produce no submission artifact.
  - **Unresolved as of capture**: follow-up commenter Charles Kalaba (1204th in comp) asks
    whether `BUY_SEED`/`BUY_PRODUCT`/`SELL`/`BUY_LAND`/`BUY_ANIMAL` market orders require
    standing at a shed access tile to execute (like PICKUP/DROP) — reports these orders
    **never executed once across 30 days** despite being submitted every turn, while HIRE
    always worked. Domino Weir (staff) replied only "I'm looking into these discrepancies
    now!" — **no resolution yet.** This is a live, high-signal, potentially serious open bug
    report (could silently zero out any agent relying on standard per-turn market orders
    without shed-adjacency) and is worth monitoring.

- **#731953 "A few rule questions for the organizers"** (Triston Morgan, 3 days ago,
  6 votes). Also answered by Domino Weir (Kaggle Staff) ~8h before capture:
  - Confirms fertilizer's full market params: Base $100, I0 10,000, T=200, below/above func
    both `linear`, below/above target both 0.40 (matches notebook #1's MARKET_PARAMS row
    exactly on the "below" side; this thread confirms symmetry on "above").
  - **Confirmed: fertilizer CAN be sold** — README updated.
  - **Confirmed: an animal does NOT need CARE to produce fertilizer.** "The comment in
    kaggriculture.py is misleading and has been updated." Fertilizer does not accumulate —
    it's a boolean flag, capped at 1 unit until collected (staff-confirmed, matches the
    reporter's own reading of the observation schema).
  - **T's 24-day basis is an intentional design choice, not legacy wording**: "the early
    days of the game are really setup focused, so the 24-day window represents those later
    days... where things start to heat up." This directly undercuts discussion #732623's
    treatment of T as a "before price starts declining" threshold — T is an explicit
    calibration constant tied to per-field production capacity over a reference window, not
    a flat-price zone.

**Other bug reports found (lower signal / largely superseded by the fix above):**

- #731635 "Bug: Hired hands can spawn on locked land and get stuck" (Victor Mercklé, 6
  votes) — the original report of the bug staff fixed in #732450 above.
- #732886 "Farm hands won't move" (Liam Newsam, posted 3h before capture, 0 votes, 0
  comments) — self-described as "likely an issue on my end," references #731635; reports
  hired hands sometimes ignore North/move commands. Unanswered, likely user error or a
  residual edge of the same locked-tile class of bug, not yet staff-confirmed as new.
- #732820 "Bug? CARE rate" (Jonathan Roy) — not read in full; title suggests another
  CARE-timing report, likely overlaps with the +1-vs-+2 discrepancy already confirmed above.

**Organizer/format announcements:**

- **#731587 "Comment on the final evaluation for this competition"** (María Cruz, Kaggle
  Staff, pinned, 11 votes): confirms the final-evaluation mechanic — after the submission
  deadline, episodes keep running for **two weeks**, then a **single Bradley-Terry
  Tournament** determines final rankings, explicitly to reduce "hot streaks" influencing
  results. This directly validates Ehsan's aside in discussion #732613 that Bradley-Terry
  is the actual ranking mechanism.
- #731215 "Daily Top Episodes Dataset" (Bovard Doerschuk-Tiberi, Kaggle Staff, pinned, 11
  votes) — staff-provided resource (not read in full; a dataset of daily top episodes,
  presumably feeding the replay-download workflows notebooks #1/#2 both used).
- #730708 "How to get started + Competition's Official Discord" (María Cruz, Kaggle Staff,
  pinned) — onboarding/Discord info only, no strategy content.

Nothing found that is more than ~2 days old carries much weight — the whole discussion board
is very fresh (competition is young, "2 months to go" per the header), and the two
staff-driven doc-fix threads (#732450, #731953) are the highest-signal organizer activity in
the last week.
