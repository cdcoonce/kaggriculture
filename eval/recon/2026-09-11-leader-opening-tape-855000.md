# kaggriculture public-leader opening spec

> Recon record, committed with `eval/prereg/2026-09-11-leader-tape-slice1.md`. Produced 2026-09-11 by
> `tools/recon-scripts/leader_recon.py` (instrumented games, observed play only; the leaders' source was not
> read) and `tools/recon-scripts/leader_tape_aggregate.py`. Aggregates: `2026-09-11-leader-opening-tape-855000-summary.json`
> and `-aggregate.txt` beside this file. The per-game `raw_records.json` (3.2 MB) is not committed;
> `leader_recon.py` regenerates it deterministically from seeds 855000-855007. The file names under
> "Output files" below are the original working names.


Behavioral spec of `public:sokolovsky-v12`, `public:rayk-v11`, `public:kaito-v4` vs our
shipped `champion` agent, derived entirely from **observed play** (own observations +
own submitted actions in seat 0), never from leader source. 4 game configs x 8 seeds
(855000-855007) = 32 games, engine `kaggle_environments==1.32.7`, repo `9fdf4f5` on
`main`. Every number below is **measured** (read off `agent.view.parse_obs` FarmViews
and submitted action dicts) unless explicitly marked **inferred**.

Configs: `sokolovsky-v12`/`rayk-v11`/`kaito-v4` = that leader in seat 0 vs `champion` in
seat 1; `champion-vs-sokolovsky` = `champion` in seat 0 vs `sokolovsky-v12` in seat 1
(our agent's own instrumented trace, for the comparison columns below).

**Final money** (mean [min, max] over 8 seeds): sokolovsky $101,826 [$70,888,
$146,804] &middot; rayk $107,659 [$97,885, $123,770] &middot; kaito $109,320 [$101,196,
$126,895] &middot; champion (as seat 1, vs those three) $59,620 / $62,706 / $62,876
&middot; champion (as seat 0 vs sokolovsky) $66,163 [$42,574, $84,522] vs sokolovsky (as
seat 1) $116,383 [$89,765, $147,125]. Matches the ~$100-115k vs ~$66k framing in the
task.

## Headline finding: the three leaders run one near-fixed opening tape

Within each leader, almost every non-money field (quadrant-purchase day, animal-buy
day, hands count, tile counts, strawberry-planting day) has **zero standard deviation**
across all 8 seeds through day 15. Only money (market-price RNG) and, downstream of it,
one or two day counts vary at all. More strikingly, **`rayk-v11` and `kaito-v4` are
point-for-point identical through day 9** (money, tiles, animals, hands, hires — every
field in the table below) despite being independent submissions by different authors
(`panel.json`: distinct lineages — rayk's "C70 route" off a THUNDER THUNDER episode,
kaito's "719-action backbone" off an Ezzzzzekki submission). `sokolovsky-v12` runs the
*same schedule* (identical NE/SW days, identical strawberry-burst calendar) with only
small quantitative offsets (one extra day-0 hire, one fewer steady-state cow, ~$570
less cash cushion before the NE buy). Practically: these are near-deterministic
schedules keyed to elapsed day/hour and the engine's fixed land/crop-timing constants,
not seed- or opponent-reactive strategies. Section 2's "decision rules" are closer to
*calendar entries* than thresholds, and that's the main reason they replicate so
cleanly across authors and seeds.

## 1. Day-by-day table, days 0-15 (leaders vs champion)

Leaders shown as **sokolovsky-v12** (rayk/kaito deltas in the footnote — they're all but
identical). Money is mean [min, max] over 8 seeds; everything else is mean (all have
seed-SD ≤ 0.2 for the leaders unless shown as a range).

| Day | $ Leaders | $ Champion | Quads (both) | C/S/G Leaders | C/S/G Champion | Hands Ldr | Hands Champ |
|---|---|---|---|---|---|---|---|
| 0 | 0 [0,0] | 3 [3,3] | NW | 1/4/0 | 1/0/1 | 5 | 6 |
| 1 | 0 [0,0] | 6 [6,6] | NW | 1/4/0 | 2/0/1 | 0 | 5 |
| 2 | 0 [0,0] | 13 [8,45] | NW | 1/4/0 | 2/0/1 | 2 | 6 |
| 3 | 20 [20,22] | 47 [47,48] | NW | 1/4/0 | 2/0/1 | 3 | 6 |
| 4 | 372 [371,373] | 274 [269,301] | NW | 1/4/0 | 2/0/1 | 4 | 6 |
| 5 | 20 [19,21] | 203 [113,242] | NW | 2/4/0 | 6/1/1 | 3 | 7 |
| 6 | 337 [57,380] | 182 [87,218] | **NE** unlocked | 3/4/0 | 6/2/1 | 4 | 7 |
| 7 | 1,520 [1477,1715] | 68 [0,345] | NW+NE | 5/4/0 | 6/4/1 | 7 | 7 |
| 8 | 1,061 [1021,1235] | 1,506 [454,1904] | NW+NE | 7/4/0 | 6/4/1 | 6 | 7 |
| 9 | 2,533 [2411,2698] | 1,120 [1,2320] | NW+NE | 7/4/0 | 6/4/1 | 7 | 8 |
| 10 | 7,425 [7145,8305] | 2,520 [2126,2861] | **SW** unlocked | 7/4/0 | 6/4/1 | 14 | 10 |
| 11 | 8,378 [8110,9281] | 7,092 [6348,8267] | NW+NE+SW | 7/4/0 | 6/4/1 | 10 | 10 |
| 12 | 10,083 [9511,10701] | 11,769 [10912,12465] | NW+NE+SW | 7/4/0 | 6/4/1 | 10 | 10 |
| 13 | 11,555 [10823,12064] | 17,080 [15670,18542] | NW+NE+SW | 7/4/0 | 6/4/1 | 8 | 10 |
| 14 | 13,206 [11916,14074] | 25,105 [20645,28552] | NW+NE+SW | 7/4/0 | 6/4/1 | 9 | 10 |
| 15 | 17,149 [13632,20541] | 27,447 [23706,30639] | NW+NE+SW | 7/4/0 | 6/4/1 | 9 | 10 |

Leader-vs-leader deltas (footnote): rayk/kaito buy the **same** 1 cow but spend 1 fewer
HIRE on day 0 (hands=4 not 5, cash left =$6 not $0); their cow count settles at **8**,
not 7, from day 8 on; SW-purchase cash cushion is ~$2,800 vs sokolovsky's ~$2,530.
Everything else (quad days, strawberry calendar, hands schedule) is identical to the
row above. kaito's SE was never bought in any of the 24 leader-seed games (0/24) — none
of the three leaders touch SE inside 30 days.

Tiles by crop, days 0-15 (sokolovsky repr.; rayk/kaito wheat/strawberry match within
±1, melon is **12→14** from day 11 for rayk/kaito, not 12):

| Day | Wheat Ldr | Straw Ldr | Melon Ldr | Weed Ldr | Wheat Champ | Straw Champ | Melon Champ |
|---|---|---|---|---|---|---|---|
| 0 | 5 | 0 | 5 | 0.0 | 17 | **0** | 2 |
| 3 | 6 | 3 | 5 | 0.2 | 31 | **0** | 7 |
| 6 | 7 | 8 | 5 | 0.2 | 8 | **0** | 8 |
| 7 | 10 | 18 | 5 | 0.4 | 15 | **0** | 8 |
| 10 | 13 | 31 | 12 | 0.4 | 18 | **0** | 8 |
| 11 | 13 | 36 | 12 | 0.4 | 18 | **0** | 8 |
| 15 | 13 | 36 | 12 | 0.5 | 30 | **0** | 9 |

Champion's strawberry column is **0 at every observation, all 8 seeds, all 30 days** —
confirmed by the shipped `STRAWBERRY_TILE_TARGET = 0` constant in
`agent/constants.py` ("shipped default: the zone is empty, so the mechanic is
dormant"), not just a behavioral coincidence.

### Days 16-29, summarized

| Day | $ Leaders (sok) | $ Champion | Wheat Ldr | Wheat Champ | Straw Ldr | Straw Champ |
|---|---|---|---|---|---|---|
| 20 | 50,120 [40896,61718] | 42,908 [31019,49956] | 26 | 30 | 33 | 0 |
| 25 | 80,628 [64587,109869] | 55,736 [38450,67821] | 46 | 34 | 16 | 0 |
| 29 | 101,826 [70888,146804] | 66,163 [42574,84522] | 1 | 28 | 0 | 0 |

**The crossover is between day 15 and day 20**: champion is *ahead* through day 15
($27,447 vs $17,149) and only falls behind once the leaders' strawberry plantings start
producing (first strawberry, planted day 3, first yields day 13; the big day-7/8/10/11
bursts yield from day 17/18/20/21). One seed's full trace (sokolovsky vs champion,
855000) shows melon tiles hit 0 for every agent by day 20 (not a leader-specific
pattern) and wheat surges to 40-57 tiles for the leader in the final third of the game
as strawberry/melon cycles age out and everyone dumps remaining capacity into wheat's
fast 2-4 day cycle; strawberry tiles decay to 0 by day 28 (last planted day 11, 4
harvests every 2 days from day 21 exhausts by ~day 27, never replanted after day 11).

## 2. Decision rules (evidence + consistency)

1. **Day-0 buy: 1 cow + 4 sheep, plus melon/wheat seed, 4-5 hires, spend to $0-6.**
   `BUY_ANIMAL COW 1` + `BUY_ANIMAL SHEEP 4` submitted turn 1, all 3 leaders, 24/24
   seed-games. *Consistency: exact.*

2. **Land purchases run on a fixed calendar, not a cash-only trigger: NE day 6, SW day
   10, SE never (0/30 days).** All 3 leaders, 24/24 seed-games, zero variance. `NE`/`SW`
   prices are fixed engine constants ($1,000/$2,000; `agent/constants.py` and the
   installed engine agree). End-of-day-5 cash is only ~$20 (sokolovsky) or ~$588
   (rayk/kaito) — both *below* $1,000 — so the $1,000 is earned same-day (day 6) and
   spent immediately; end-of-day-9 cash is already $2,530-$2,810, *above* the $2,000 SW
   price, so the SW buy lags affordability by up to a day. **Inferred**: exact
   within-day timing (hour of purchase) wasn't captured, only day-boundary money.
   *Consistency: day is exact; the affordability story is inferred from before/after
   day-boundary cash.*

3. **Hands track newly-unlocked land, not a fixed headcount.** 0-4 hands through day 6
   (confirms the task's prior), jumping to 7 the day *after* NE unlocks (day 7) and to
   14 the *same* day SW unlocks (day 10), then oscillating 8-14 for the rest of the
   window rather than holding any single cap. *Consistency: exact across leaders/seeds
   through day 15.*

4. **Strawberry plants in 5 land-triggered bursts, never revisited after day 11.**
   Aggregate burst calendar (all 3 leaders, all 8 seeds, tiles/seed): day 3 → 3.0, day 5
   → ~3.9, day 6 → 1.0, day 7 → 10.0, day 8 → ~1.9, day 10 → 11.0, day 11 → 5.0; total
   ~35.6-35.9/seed. This matches the task's Sokolovsky prior (~3/~4/~10/~11/~5, ~36
   total) almost exactly **and turns out to be shared by all three leaders, not
   sokolovsky-specific**. By quadrant: days 3+5 → NW (24+~30 tiles), days 6+7+8 → NE
   (8+80+~15), days 10+11 → SW (88+40) — i.e. bursts fire in NW/NE/SW immediately after
   each quadrant unlocks, filling that quadrant's melon+pasture-adjacent tile budget in
   one shot. Burst-start cash varies enormously ($0-$3,191, sd ~$1,150) — **this
   contradicts a simple cash-threshold framing**; the trigger looks tied to newly
   *available tiles*, not to a bankroll level. *Consistency: burst days are exact
   (sd=0); burst sizes vary by at most 1 tile; the "land-triggered not cash-triggered"
   read is inferred from the wide burst-cash spread.*

5. **Fertilizer is over-supplied on purpose and monetized before it's used.**
   `COLLECT_FERTILIZER` runs at 5-12/day from day 1 (matching hand count); cumulative
   supply reaches 129 by day 15 and 300 by day 29, while `FERTILIZE` stays at 0 until
   day 12 and totals only 72 by day 29 — under a quarter of what's collected. The
   surplus is sold throughout (`SELL:FERTILIZER`, ~$10-14k/game revenue, ~10-14% of
   final money) rather than left idle. Supply never binds: leaders are never caught
   short when they do decide to fertilize. This is the mechanism behind the task's
   "meets 100% of fertilizer demand" prior — restated more precisely, *supply is
   never the constraint; application timing (day 12+) is a deliberate choice, and the
   pre-day-12 surplus is cash, not waste.* *Consistency: exact through day 15 (sd=0
   for collect/fertilize counts), tight through day 29.*

6. **Champion's land purchase is front-loaded, not sequenced — and that's not obviously
   a mistake on its own.** Champion buys NE at turn 0 (alongside NW) every game, and
   SW on day 9-10 (9.5 mean, close to the leaders' day 10). It plants far more tile
   area immediately (17-31 wheat + 2-9 melon by day 3-8, vs. leaders' 5-13/5) and, per
   the crossover in section 1, is *ahead* of every leader through day 15. The
   land-timing difference is real but its sign is ambiguous from money alone — treat it
   as a style difference, not a confirmed leak, pending a controlled A/B.

## 3. Differences from champion, ranked by likely economic impact

1. **Strawberry is entirely off in champion (highest impact, high confidence).**
   Measured 0 strawberry tiles at every observation, all 8 champion-seat0 games and (by
   construction) all 24 leader-seat1 games our agent played. Leaders' strawberry sell
   revenue alone averages $48,900-$53,700/game (quoted-price proxy — see caveats),
   roughly half of their $100-115k final total. The day-15→day-20 money crossover in
   section 1 lines up almost exactly with strawberry's first-yield window (day 13 for
   the earliest-planted tiles), which is strong circumstantial evidence this specific
   mechanic, not general play quality, is what flips the game. This is also the
   mechanic our own code already flags as shipped-dormant (`STRAWBERRY_TILE_TARGET =
   0`), so it's a known, named gap, not a new discovery — this recon adds the
   quantified timing (bursts at day 3/5/6/7/8/10/11, ~36 tiles/game total, concentrated
   in NW/NE/SW right after each unlocks) needed to replicate it.

2. **Fertilize is never used at all (medium-high impact, high confidence, cheap to
   fix).** Champion collects fertilizer at essentially the leaders' own rate (~11/day,
   263-300 collected over 29 days) but the `FERTILIZE` verb count is exactly 0 across
   all 8 champion-seat0 games — it sells virtually 100% of what it collects instead of
   applying any of it. `FERTILIZE` doubles a tile's yield-per-water (engine-confirmed:
   `+2` vs `+1` yield_units), so this is a clean multiplicative lever that costs no new
   input (the fertilizer is already being produced and thrown away as low-value sale
   volume) — arguably the single cheapest fix in this list since it requires no new
   resource acquisition, only routing an existing one.

3. **Sheep ramp is 8 days slower (moderate impact, high confidence).** Leaders buy all
   4 sheep on day 0; champion buys 0 sheep on day 0, reaching 4 only by day 8. Wool
   revenue reflects this: champion $9,799/game vs leaders $16,600-$18,900/game
   (40-48% lower) — directionally consistent with an 8-day head-start gap on a
   steady-state producer, though other factors (care/feed cadence) weren't isolated
   here.

4. **Land-purchase sequencing and the goose/egg pipeline are lower-confidence, possibly
   neutral (low-to-unclear impact).** See rule 6 above — champion is ahead through day
   15 despite (or because of) front-loading land. Separately, champion is the *only*
   one of the 4 agents that ever buys a goose (1/1 champion-seat0 games; 0/24 across
   all leader-seed games) and runs a standing `SELL EGG <sell-all>` order on ~26 of 30
   days per game (see caveats — quantity not literally observable). Its net revenue
   contribution could not be cleanly isolated from the money trajectory in this pass;
   flagging it as a candidate low-value distraction worth a follow-up, not a confirmed
   one.

## Caveats — what's measured vs inferred, and known gaps

- **Submitted ≠ filled.** All `orders_submitted` figures (BUY_*, HIRE, SELL) are
  *submitted* market orders, read from each seat's own `action["market"]`, not
  confirmed fills. Cross-checked once: on one seed/day, a submitted `HIRE` order failed
  silently (insufficient cash) — `hires_confirmed_eod` (the engine's own
  `hires_today` counter) is the fill-confirmed number and is included alongside
  `hires_submitted` in every day record for exactly this reason. Tile census
  (wheat/strawberry/melon/animals), money, and `hires_confirmed_eod` are all
  state-based and fill-confirmed by construction.
- **SELL pricing.** Confirmed from the installed engine source
  (`kaggle_environments/envs/kaggriculture/kaggriculture.py`): SELL fills at the
  currently-quoted price with no slippage or order-book depth, so "quoted price at
  submission" (recorded for every `sell_events` entry) is the actual per-unit price,
  not an approximation. What's *not* independently confirmed is that a multi-unit
  order fills its full submitted quantity in one turn — order records carry a
  `"remaining"` field suggestive of gradual/queued fulfillment, and one probe (a 9-unit
  WHEAT sell) showed money essentially flat one step later, consistent with a
  1-ish-unit-per-turn fill rate. Sell-revenue figures in this spec are therefore a
  **qty(submitted) × quoted-price proxy**, not a ledger-reconciled total.
- **Sell-all sentinel.** Champion submits `["SELL","EGG",99999]` every turn once geese
  lay (`agent/market.py`'s `SELL_ALL` constant) — a "sell whatever's in the shed"
  idiom, not a literal quantity. These are excluded from all sums/means (flagged
  separately as a standing-order behavior, ~26/30 days) rather than allowed to corrupt
  aggregates; none of the three leaders use anything like it (no other verb:item ever
  exceeds a few hundred units/game for any of the four agents).
- **Harvest-by-crop attribution is unreliable and reported only qualitatively.**
  `HARVEST`/`FERTILIZE`/`COLLECT_FERTILIZER` *counts* per day are directly observable
  (verb tallies in `action["farmer"]`/`action["hands"]`) and used throughout. A
  best-effort per-crop breakdown (acting unit's position × that turn's own tile state)
  was attempted but is dominated by a "?" bucket — spot-checked and confirmed to be
  *harvest attempts on tiles with nothing ready* (empty ground or a not-yet-producing
  animal tile), i.e. leaders issue routine/speculative HARVEST regardless of whether
  something's there (a real behavior, silently a no-op server-side), which swamps the
  wheat/melon signal specifically. Treat `harvest_by_crop_inferred` in the JSON as
  suggestive (it does cleanly separate STRAWBERRY and animal-product harvests) and rely
  on the tile-count trajectory for wheat/melon throughput instead.
- **Land-timing verdict (rule 6 / impact item 4) is a style observation, not a tested
  claim** — no controlled A/B was run in this pass; money is confounded by every other
  difference (crop mix, sheep timing, fertilize use) between day 0 and day 15.
- All comparisons use 8 seeds (855000-855007); "consistency" statements describe
  agreement within that set, not a claim about the full seed space.

## Output files

- `leader_recon.py` — instrumented game runner (per-day FarmView + action trace, seat 0
  only).
- `aggregate.py` — cross-seed aggregation (means, ranges, decision-rule evidence
  extraction) over `raw_records.json`.
- `probe.py` — one-off empirical validation script (engine data-shape checks, timing).
- `raw_records.json` — full per-seed, per-day JSON records for all 4 configs × 8 seeds
  (money, tiles, animals, quadrants, hands/hires, plantings, verb counts, orders,
  sell events, strawberry-by-quadrant detail).
- `summary.json` — cross-seed aggregates (mean/min/max/sd) per config: day-by-day
  series, quadrant/animal purchase-day distributions, strawberry burst histogram,
  fertilizer balance, order totals, sell-revenue proxy.
- `aggregate_output.txt` — human-readable rendering of `summary.json`.
- `leader_opening_spec.md` — this file.
