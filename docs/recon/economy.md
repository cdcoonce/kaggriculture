# Kaggriculture Economy Model

Ground truth: `kaggle_environments/envs/kaggriculture/kaggriculture.py` (engine source), cross-checked against the vendored README's own price-curve table. All numbers below come from scripts in `/private/tmp/claude-501/-Users-cdcoonce-Developer-GitHub-the-vault/48f69011-acdd-44c8-850e-fae45901a79f/scratchpad/econ-calcs/` that call the engine's real functions (`_apply_unit_action`, `_daily_refresh_plants`, `_daily_refresh_animals`, `_decay_plants`, `market_price`) directly — not a reimplementation of the rules. Re-run any script with the venv python to reproduce:

```
/private/tmp/claude-501/-Users-cdcoonce-Developer-GitHub-the-vault/48f69011-acdd-44c8-850e-fae45901a79f/scratchpad/kagg-venv/bin/python <script>.py
```

Scripts: `crop_sim.py` (plant lifecycles), `animal_sim.py` (animal lifecycles), `market_curves.py` (price-impact thresholds), `town_demand.py` (town absorption), `land_fert_labor.py` (land payback, fertilizer EV, animal breakeven, labor saturation).

Config assumed throughout: defaults (`episodeSteps=720`, `boardSize=10`, `startingMoney=3000`, `turnsPerDay=24`, `shedCapacity=100`, `townShopUnlockInterval=3`, `townShopSellInterval=4`, `townCenterSellInterval=12`, `farmHandCostMult=1`, `maxMarketOrdersPerTurn=10`).

**Critical structural fact discovered while building this model**: `market` orders (BUY/SELL/HIRE/BUY_LAND) are a _separate_ action list from `farmer`/`hands` tile actions. Selling, buying, and hiring do **not** consume any of the 24 actions/day/unit budget. The 24-action budget only gates movement + tile ops (PLANT/WATER/HARVEST/FERTILIZE/FEED/CARE/COLLECT_FERTILIZER/BUILD_*/DIG/PLACE/PICKUP/DROP). This reframes labor economics entirely: the constraint is never "can I afford to sell," it's "can I afford to _tend_."

---

## 1. Per-tile-per-day profit at base prices

All figures from `crop_sim.py` / `animal_sim.py`, which drive the actual engine state machine turn-by-turn (not hand math). "Steady state" = continuously replanting the same tile the instant it's harvested (verified: a same-day replant needs an _immediate_ extra WATER that same day, or the fresh seedling weeds out overnight — the engine gives zero grace period, `consecutive_unwatered` starts at 1 on the planting day itself).

One-time crops — optimal harvest age is **not** always `max_yield_day`: it's the earlier of (a) age when `yield_units` caps out, or (b) `max_yield_day`, but never before `first_yield_day` (HARVEST no-ops before then even if yield is already banked).

| Crop                              | Optimal harvest age (unfert.) | Single-cycle yield/day/tile | Steady-state yield/day/tile       | Steady-state actions/day/tile | Revenue/day/tile (base $) | Seed cost/day/tile | **Profit/day/tile** | $/action |
| --------------------------------- | ----------------------------- | --------------------------- | --------------------------------- | ----------------------------- | ------------------------- | ------------------ | ------------------- | -------- |
| WHEAT                             | 4                             | 0.80                        | 0.941                             | 1.647                         | $23.53                    | $2.35              | **$21.18**          | $12.86   |
| CARROT                            | 3                             | 0.75                        | 0.923                             | 1.846                         | $32.31                    | $6.15              | **$26.15**          | $14.17   |
| MELON                             | 10                            | 0.545                       | 0.585                             | 1.268                         | $146.3                    | $7.80              | **$138.5**          | $109.2   |
| TOMATO (ongoing, single life)     | n/a (age8–11 sched.)          | 0.308                       | — (single-plant life, no replant) | 1.385                         | $18.46                    | $3.85              | **$14.6**           | $10.6    |
| STRAWBERRY (ongoing, single life) | n/a (age10–16 sched.)         | 0.222                       | —                                 | 1.278                         | $26.67                    | $5.56              | **$21.1**           | $16.5    |

One-time crops' fertilized numbers (own row, since fertilizer is a separate spend decision — see §4):

| Crop       | Fertilized yield (single cycle)                                                 | Fertilized profit @ market $100/unit                        | Fertilized profit @ free fertilizer |
| ---------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------- |
| WHEAT      | 6 (vs 4 unfert.)                                                                | **-$160** (loss)                                            | **$140** (vs $90 unfert.)           |
| CARROT     | 4 (vs 3 unfert.)                                                                | **-$80** (loss)                                             | **$120** (vs $85 unfert.)           |
| MELON      | 6 (**same as unfertilized — 0 benefit**)                                        | always -EV                                                  | always -EV                          |
| TOMATO     | 8 (vs 4 unfert., _only if fertilized 1 day ahead of each scheduled production_) | **+$30** (marginal)                                         | **$430** (vs $190 unfert.)          |
| STRAWBERRY | 8 (vs 4 unfert., same 1-day-ahead requirement)                                  | **+$460** (vs $380 unfert. — positive even at market price) | **$860**                            |

Animals (30-day horizon, fed+harvested daily, no CARE, no fertilizer collection):

| Animal | Product/day (steady)             | Actions/day | $/action (ex. purchase) | 30-day profit incl. $ purchase & feed | Profit/day/tile (incl. purchase amortized) |
| ------ | -------------------------------- | ----------- | ----------------------- | ------------------------------------- | ------------------------------------------ |
| GOOSE  | 1.0 egg (from day 4)             | 1.93        | $9.48                   | $250                                  | **$8.33**                                  |
| COW    | 0.5 milk (from day 8, every 2d)  | 1.43        | $23.49                  | $610                                  | **$20.33**                                 |
| SHEEP  | 0.33 wool (from day 6, every 3d) | 1.33        | $21.25                  | $350                                  | **$11.67**                                 |

Feed cost priced at wheat's **base market price** ($25/unit) as an opportunity-cost baseline — a farm that grows its own wheat feeds animals near-free (marginal cost ≈ wheat's own production cost, not $25), which materially improves all three animal lines. This is the wheat-feed-loop synergy referenced throughout.

**Caveat on all "actions/tile/day" figures above**: they assume the tile is worked in place with zero travel — i.e., a hand permanently stationed on/adjacent to that tile. Realistic play requires ~1 extra MOVE action per tile visited per day for hands tending a spread-out cluster (WATER/HARVEST/FEED don't require shed-adjacency, but reaching each tile does cost a move). Treat the "actions/day/tile" column as a **floor**; real per-tile action cost is likely 1.5–2x higher for a hand tending multiple non-adjacent tiles. This does not change $/day/tile (revenue is action-count-independent) but does change how many hands are needed to work a given tile count — see §3.

---

## 2. Price-impact-adjusted profit at scale

### 2a. Glut-side (player selling) thresholds — units sold **above I0** to move price

| Product    | Base $ | T   | −25% at | −50% at   | Floor ($1) at                          | Shape                                  |
| ---------- | ------ | --- | ------- | --------- | -------------------------------------- | -------------------------------------- |
| WHEAT      | 25     | 400 | 1,793   | 3,220,036 | **practically unreachable** (3.1×10¹²) | log — "absorbs gluts"                  |
| CARROT     | 35     | 450 | 57      | 230       | 867                                    | sqrt — crashes fast                    |
| TOMATO     | 60     | 200 | 35      | 139       | 537                                    | sqrt                                   |
| STRAWBERRY | 120    | 100 | 16      | 31        | 62                                     | linear, target 1.6 — crashes very fast |
| MELON      | 250    | 300 | 79      | 112       | 158                                    | sq, target 3.6 — crashes very fast     |
| EGG        | 50     | 332 | 1,422   | 2,023,533 | **practically unreachable** (2.3×10¹²) | log — "absorbs gluts"                  |
| MILK       | 160    | 122 | 19      | 38        | 76                                     | linear, target 1.6 — crashes very fast |
| WOOL       | 200    | 105 | 29      | 42        | 59                                     | sq, target 3.2 — crashes very fast     |

**This is the single most important structural fact in the whole game economy**: WHEAT and EGG use a `log` above-curve, which is asymptotically bounded — no realistic volume of selling (hundreds of thousands to trillions of units) crashes their price meaningfully. Every other product (carrot, tomato, strawberry, melon, milk, wool) crashes to the floor within **tens to low hundreds of units**. Wheat/egg are the only two products that scale; everything else is a boutique/timing play.

### 2b. Scarcity-side (town/buyer draining inventory) — units consumed **below I0** to move price up

| Product    | +25% at | +50% at | +100% at     |
| ---------- | ------- | ------- | ------------ |
| WHEAT      | 39      | 156     | 625          |
| CARROT     | 2,077   | 4.3M    | ~unreachable |
| TOMATO     | 125     | 250     | 500          |
| STRAWBERRY | 13      | 51      | 204          |
| MELON      | 1,253   | 1.57M   | ~unreachable |
| EGG        | 208     | 415     | 830          |
| MILK       | 21      | 85      | 339          |
| WOOL       | 339     | 115,681 | ~unreachable |

Wheat spikes fast on scarcity (good to _buy_ early if short on feed, bad if you're relying on cheap market wheat); carrot/melon/wool barely react to scarcity at all (mirrors the README's own framing).

### 2c. Town absorption capacity (expected, over the shop-unlock RNG)

Shop unlock order is randomized (`rng.choice` among remaining shops every 3 days); modeled via the hypergeometric expectation — a product's demand ramps in proportion to `(shops unlocked so far)/8`. Town center scales 1x→2x (day 10)→4x (day 20).

| Product    | # supporting shops | Full post-unlock demand/day | Expected 30-day cumulative town demand | −25%-band threshold | **Sustainable combined (both players) sell/day** |
| ---------- | ------------------ | --------------------------- | -------------------------------------- | ------------------- | ------------------------------------------------ |
| WHEAT      | 5                  | 30                          | 635                                    | 1,793               | **81/day** (~40 each)                            |
| CARROT     | 2                  | 18                          | 437                                    | 57                  | **16/day** (~8 each)                             |
| TOMATO     | 2                  | 12                          | 338                                    | 35                  | **12/day** (~6 each)                             |
| STRAWBERRY | 4                  | 24                          | 536                                    | 16                  | **18/day** (~9 each)                             |
| MELON      | **0**              | 0                           | 140 (town-center only)                 | 79                  | **7/day** (~3.65 each)                           |
| EGG        | 2                  | 12                          | 338                                    | 1,422               | **59/day** (~29 each)                            |
| MILK       | 3                  | 18                          | 437                                    | 19                  | **15/day** (~8 each)                             |
| WOOL       | 1                  | 12                          | 338                                    | 29                  | **12/day** (~6 each)                             |

MELON is not sold by _any_ town shop — its only town sink is the town-center's flat per-product draw. Combined with the tightest glut floor (158 units) of any product, melon is entirely dependent on selling into a market the opponent also has full access to, with almost no external demand cushion. This is the game's most fragile high-value product.

Wheat and egg's "sustainable" figures above (~81 and ~59/day combined) look small only relative to their true ceiling — since their glut curve is log-bounded, in practice you can sell far more than this and stay well above the −25% band for the whole season; the number shown is just the volume that keeps price _exactly flat_ against town + opponent activity, not the volume before things go wrong.

---

## 3. Labor economics

Hire cost is Fibonacci-scaled and **trivial** at every realistic hand count:

| Hire # (n already hired) | Cost | Cumulative cost that day | Total actions after (farmer + hands) |
| ------------------------ | ---- | ------------------------ | ------------------------------------ |
| 1                        | $1   | $1                       | 48                                   |
| 2                        | $1   | $2                       | 72                                   |
| 3                        | $2   | $4                       | 96                                   |
| 4                        | $3   | $7                       | 120                                  |
| 5                        | $5   | $12                      | 144                                  |
| 6                        | $8   | $20                      | 168                                  |
| 7                        | $13  | $33                      | 192                                  |
| 8                        | $21  | $54                      | 216                                  |
| 9                        | $34  | $88                      | 240                                  |
| 10                       | $55  | $143                     | 264                                  |

The 8th hire costs $21/day for 24 actions ($0.875/action) — an order of magnitude below the _cheapest_ crop's $/action (wheat $12.86, up to melon's $109.2). **Hire cost never saturates within any realistic hand count.** Labor "saturates" only when:

1. **You run out of tiles to work.** Full board = 100 tiles. At wheat's steady-state 1.65 actions/tile/day (zero-travel floor), fully working 100 tiles needs ~165 actions/day ≈ 6.9 farmer-equivalents (no travel) or realistically ~11–14 hands once travel overhead is included.
2. **You run out of market absorption for what those tiles produce** — see §2c. Once a product's sustainable-sell rate is saturated, marginal hands produce inventory that either crashes price (crashable products) or simply piles up unsold in a 100-item shed (hard cap — overflow is silently discarded).

Marginal value of the Nth hire, in practice: hands 1–~7 (through full NW+NE+SW tile coverage on wheat/egg) are worth their full crop $/action minus the ~$1–13 hire cost — i.e. still 10–100x ROI. Beyond that, marginal hands should be routed into the **narrow-absorption premium crops** (melon/strawberry/cow/sheep) up to _their_ sustainable caps (a few tiles/animals each, per §2c), not into more wheat/egg tiles once the board is full. Given hire cost triviality, the real cap on hand count through the whole 30-day season is architectural (board size, shed capacity, travel time), never financial.

---

## 4. Capital

### 4a. Land quadrants

Using wheat's steady-state $21.18/tile/day (base price, negligible price impact at this scale — 25 tiles × 0.94 wheat/day ≈ 23.5 wheat/day, well under wheat's ~81/day combined sustainable-sell rate):

| Quadrant | Cost   | Quadrant profit/day (25 tiles, wheat) | Actions needed/day (no travel / ~2x w/ travel) | **Payback**  |
| -------- | ------ | ------------------------------------- | ---------------------------------------------- | ------------ |
| NE       | $1,000 | $529                                  | 41 / ~82                                       | **1.9 days** |
| SW       | $2,000 | $529                                  | 41 / ~82                                       | **3.8 days** |
| SE       | $4,000 | $529                                  | 41 / ~82                                       | **7.6 days** |

Even the priciest quadrant pays for itself inside a single week if staffed. Land is essentially never the bottleneck resource in this game — money is abundant relative to land cost, and land cost is trivial relative to season-long wheat/egg cash flow. The real gate on buying all four quadrants early is whether you have (a) the hands to work the extra tiles and (b) seed capital left over after the land purchase (see §5 — this is where "land grab first" opening plans go wrong).

### 4b. Fertilizer economics ($100 market vs. free via COLLECT_FERTILIZER, 1/animal/day, 1 action)

| Crop       | Fertilizer @ market $100/unit                                                                                                                                  | Fertilizer if free               |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| WHEAT      | **−EV** (−$250 vs. unfertilized)                                                                                                                               | **+EV** (+$50)                   |
| CARROT     | **−EV** (−$165)                                                                                                                                                | **+EV** (+$35)                   |
| MELON      | **Always −EV — zero yield benefit** (yield is gated by `first_yield_day`=10, which lands after the fertilizer-accelerated cap is already reached unfertilized) | still −EV (0 benefit, pure cost) |
| TOMATO     | **≈breakeven, marginally +EV** (+$30) — _only if fertilized exactly 1 day ahead of each scheduled production; naive same-day fertilizing is actually −EV_      | **strongly +EV** (+$240)         |
| STRAWBERRY | **+EV** (+$80, positive even at market price)                                                                                                                  | **strongly +EV** (+$480)         |

Rule of thumb: **never buy fertilizer at market price for wheat, carrot, or melon.** Free fertilizer (from keeping animals) is worth routing to strawberry first, tomato second, then wheat/carrot as a distant third — and never to melon. If running the egg-engine, each goose throws off 1 free fertilizer/day (1 extra action to collect) — with 4+ geese that's easily enough to fully fertilize a strawberry patch.

---

## 5. Phase structure

Season = days 0–29 (720 steps / 24 turns-per-day). "Last profitable planting/purchase day" = latest day a fresh investment can still complete at least one full harvest cycle before day 29.

| Crop/animal  | Optimal harvest age / first yield                                  | Last profitable planting day (full cycle) | Last day for _any_ positive marginal yield |
| ------------ | ------------------------------------------------------------------ | ----------------------------------------- | ------------------------------------------ |
| WHEAT        | age 4                                                              | day 25                                    | day 27 (first_yield_day=2)                 |
| CARROT       | age 3                                                              | day 26                                    | day 27                                     |
| MELON        | age 10                                                             | day 19                                    | day 19 (fully gated by first_yield_day)    |
| TOMATO       | full 4-production cycle by age 11                                  | day 18                                    | day 21 (1st yield only)                    |
| STRAWBERRY   | full 4-production cycle by age 16                                  | day 13                                    | day 19 (1st yield only)                    |
| GOOSE ($300) | breakeven needs ~12 days of egg production after first egg (day+4) | **day 14** (full $300 payback)            | day 25 (any marginal profit)               |
| COW ($400)   | breakeven needs ~7.3 days of production after first milk (day+8)   | **day 15**                                | day 21                                     |
| SHEEP ($500) | breakeven needs ~12 days of production after first wool (day+6)    | **day 12**                                | day 23                                     |

Wheat and carrot stay plantable almost the entire season (5-day cycles leave huge runway); strawberry and sheep close out earliest because of their long first-yield lag combined with a real purchase-price/seed-cost to amortize.

### Candidate opening build orders (days 0–3), starting $3,000 / 25 tiles / 24 actions/day

These are directional sketches (hand arithmetic from the tables above, not a full multi-agent sim — see Open Questions) to illustrate the shape of the decision, not exact optimized numbers.

**Plan A — "Wheat Rush + Day-0 Goose"** (aggressive compounding)

- Day 0: buy 1 GOOSE ($300) + BUILD_COOP (free, 1 action) + PLACE (1 action); buy ~20 WHEAT seeds ($200); buy ~5 market wheat for early goose feed before self-sufficiency ($125); hire 3 hands (~$4); plant + water ~20 tiles. Spend ≈ $629. **Bank ≈ $2,371.**
- Days 1–3: water everything, feed goose from the small wheat buffer. No major spend.
- Day 4: first egg (+$50); original 20 wheat tiles hit age 4 → harvest ~80 wheat (20 tiles × 4 yield unfertilized); immediately replant (buy ~20 more seeds, ~$200) using the freed tiles. **Bank ≈ $2,221** (pre-sale) with 80 wheat + eggs sitting in shed.
- Day 5: sell 80 wheat at ~$25 (price impact negligible — 80 units is nothing against a 1,793-unit −25% threshold) → **+$2,000, bank ≈ $4,221** — already past starting capital by day 5.
- This plan is **robust**: wheat's log glut curve means dumping 80+ units/day repeatedly all season barely moves price, and the goose is a costless (in action terms) side engine that starts compounding immediately.

**Plan B — "Land Grab First"** (illustrative anti-pattern)

- Day 0: buy NE ($1,000) + SW ($2,000) = $3,000, **$0 left for seeds**. Zero plantable action available; actions are wasted (idle movement/PASS) until day 1+ once some money trickles in from... nothing, since there's no income source yet.
- This plan is **dominated** — land pays back in under 8 days _once staffed and seeded_, but buying it before establishing any cash flow leaves you unable to seed anything, burning the season's most valuable early days. Land should follow cash flow, not precede it.

**Plan C — "Balanced Ramp"** (lower-variance middle path)

- Day 0: buy NE land ($1,000); buy 15 WHEAT seeds ($150); buy 1 GOOSE ($300) + coop; hire 2 hands (~$2). Spend ≈ $1,452. **Bank ≈ $1,548** buffer retained.
- Days 1–3: water/tend; keep buffer in case of unexpected shed-capacity or price surprises.
- Day 4: harvest ~15×4=60 wheat + 1 egg; sell for ~$1,500+; reinvest the buffer into SW ($2,000) around day 6–7 once cash flow is clearly positive, rather than day 0.
- Slower initial compounding than Plan A, but keeps capital in reserve against the (unmodeled) risk of opponent behavior or shed-capacity mistakes.

---

## 6. Dominant strategy hypotheses (ranked)

Modeling the opponent as producing comparable volume in whatever the shared market prices most reward (i.e., assume symmetric competition on the scalable staples, asymmetric/uncertain competition on premium goods).

1. **Wheat + Egg compounding core (highest projected 30-day bank, most robust).** Wheat's 5-day cycle, $10 seed cost, and — critically — its `log` glut curve (practically un-crashable even under full two-player mutual spam, since −50% requires 3.2M units) make it the only crop that can absorb unlimited hand-count scaling without self-destructing its own price. Egg shares the same log-curve immunity and needs almost no per-tile action budget (1.93 actions/day for an _entire animal_, not per-tile). Feeding geese from self-grown wheat closes the loop at near-zero marginal feed cost. **This pair should be the majority of every build regardless of overall strategy** — it's less "a strategy" and more "the floor every other strategy is built on top of."
2. **Hybrid diversified portfolio (wheat/egg core + absorption-capped satellites) — likely the actual profit-maximizing play, if executed well.** Once wheat/egg tile+hand allocation saturates the board (~7–14 hands, §3), route surplus hands into strawberry, melon, cow, and sheep — but capped at _each product's own_ narrow sustainable-sell volume (§2c: strawberry ~9/day, melon ~3.65/day, cow ~8/day, sheep ~6/day, each halved further if the opponent competes in the same good). This captures melon's $109/action and strawberry's $16.5/action upside without concentrating enough volume in any one crashable product to blow through its −25%/−50% thresholds. **Fragility**: requires active monitoring of market inventory to know when to stop scaling a given satellite product and reallocate — a static build order can't do this; it needs an adaptive policy.
3. **Max-hands wheat spam (simple, strong floor, moderately robust).** A simplified version of #1 that skips the diversification of #2 entirely: buy all land ASAP (payback 2–8 days — see §4a), hire up to the ~100-tile ceiling, run wheat exclusively. Lower ceiling than #2 (leaves melon/strawberry/animal $/action on the table) but operationally trivial and immune to the market-timing risk that #2 carries. Good baseline / fallback if opponent behavior is unpredictable or a more complex policy proves too hard to implement reliably in-agent.
4. **Premium-crop timing play (melon/strawberry-heavy, fertilizer-timed).** High $/action (melon $109, strawberry $16.5 base, higher with correctly-timed fertilizer) but **fragile**: melon has zero town-shop demand and the tightest floor of any product (158 units); strawberry's floor is even tighter (62 units) and its glut target (1.6) is one of the harshest in the game. A build concentrated here is a bet that the opponent _doesn't_ also grow the same premium crop — if both players lean into melon or strawberry, the shared market crashes fast (mutual glut, no external demand cushion for melon) and both players lose most of the upside. Only sound as a _minority_ allocation (see #2), never as the backbone.
5. **Cow/sheep specialty animal play.** Best single-animal $/action-excl.-purchase economics (cow $23.49, sheep $21.25) and best 30-day-inclusive profit/tile/day (cow $20.33 > sheep $11.67 > goose $8.33) — but both milk and wool have hard, tight glut floors (76 and 59 units respectively) and only moderate town demand (milk 3 shops, wool 1 shop). Excellent for a **small, capped number of animals** (a handful of each), useless — actively harmful — if scaled the way wheat/egg can be. Same fragility profile as #4, smaller in absolute stakes since animals are capital-gated (can't just spam-buy cows the way you can spam-plant wheat) which naturally limits downside.

**Bottom line ranking by projected 30-day bank**: #2 (hybrid) ≥ #1 (wheat+egg core, effectively a subset of #2) > #3 (max-hands wheat-only) > #4 (premium timing) ≈ #5 (specialty animals), with #4 and #5 carrying materially higher variance/opponent-dependence than the top three. Any winning agent almost certainly needs wheat+egg as its chassis; the ranking above is really about how aggressively to bolt premium/animal satellites on top, and that answer should be adaptive to observed opponent behavior (visible via the shared `market.inventory`/`market.prices` and the opponent's visible farm layout) rather than fixed at build time.

---

## Open questions / follow-up work

- **Travel-cost modeling is unmodeled.** All "actions/tile/day" figures assume a hand stationed with zero movement cost. Real per-tile action cost for a hand tending a spread cluster is likely 1.5–2x higher; this doesn't change $/day/tile but does change how many hands are needed to reach a given tile count, and thus how fast the ~100-tile ceiling in §3 is actually reachable. A full turn-by-turn sim with real pathfinding is the natural next step.
- **Town shop unlock ramp is modeled as an expectation (hypergeometric mean over the random unlock order), not a specific seed's realized draw.** A specific episode's realized town-demand ramp could unlock a product's shops much earlier or later than the expected curve in §2c.
- **Opening build order bank trajectories (§5) are directional sketches**, not output of a full 2-agent kaggle_environments run. Validating them (and the "robust to opponent crash" claims in §6) against an actual `env.run([agentA, agentB])` episode — especially one where the opponent is scripted to specifically dump wheat, melon, or strawberry — would sharpen the fragility claims from qualitative to quantitative.
- **Shed capacity (100 items) is a hard, easy-to-hit cap** once wheat production scales into the tens-of-tiles range (e.g., Plan A harvests 80 wheat in a single day) — sell/drop cadence discipline matters and isn't modeled here; a build that harvests faster than it sells/drops will silently lose inventory to shed overflow.
- **CARE bonus mechanics (animal `pending_care_bonus`) are not modeled** — the analysis in §1/§6 uses fed+harvested-only animal economics; CARE adds a small additional yield bonus on top that could modestly improve the cow/sheep/goose numbers further.
