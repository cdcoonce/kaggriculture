# Kaggriculture — Strategy Plan

_Adopted 2026-08-04 after recon (see `docs/recon/`) and two independent cold-read passes (both SOUND-WITH-FIXES; all fixes folded in). Canonical project state lives in the vault: `personal/projects/kaggriculture.md`. This doc is the execution plan the build works from._

Competition: https://www.kaggle.com/competitions/kaggriculture — Kaggle Featured simulation comp. 2-player farming/economy game, 720 turns (24/day × 30 days), most coins wins the match; W/L/T only feeds an Elo-like ladder (margin irrelevant). Final ranking = one-shot Bradley-Terry tournament over episodes played Oct 1–15 on each team's **latest 2 submissions**. $5k × top-10. Entry/merger deadline Sep 23; final submission Sep 30 (UTC). ~1,514 teams as of Aug 4; LB #1 rating 3105, top-10 cutoff ~2690 (ratings start μ=600).

**Goal: top-10. Descope checkpoint: Sep 7 — if pool win-rates are weak or rating trajectory is clearly outside top-100 territory, drop to top-50 + strong writeup mode.**

## Verified hard constraints

- Runtime: CPU-only 1.6 vCPU, 6.5 GiB RAM, **no internet**, 1 s/turn + 60 s per-agent overage bank. Submission ≤100 MiB tar.gz, `main.py` at root exposing `agent`. Runner package set unknown → **pure-stdlib agent** until the probe submission proves otherwise.
- Scoring always uses **default config** regardless of local testing.
- A crashed/timed-out agent is never called again (farm frozen; final reward = frozen money → near-certain loss). Every submission is gated by a **self-play validation episode** — a crash there means zero ladder entry, not bad signal.
- 5 submissions/day; only the latest 2 stay in matchmaking and count for the final. **The last two uploads before Sep 30 ARE the entry.**
- Local env: deterministic given seed, symmetric by construction, ~1 s/episode in-process → massive local experimentation is cheap. Weed RNG is a shared sequential stream (P0 drawn before P1), so mirrored boards are not identical — self-play can legitimately diverge.

## Economy ground truth (engine-verified)

- **Wheat + egg are the only glut-proof products** (log above-curve). Carrot is the near-staple third (867-unit glut room, $26.15/tile/day — beats wheat's $21.18 at base price, plantable to day 26). Everything else crashes to the $1 floor within tens–hundreds of units: strawberry 62, wool 59, milk 76, melon 158, tomato 537.
- Melon: best $/action (~$109), ~$138/tile/day steady-state at base price, but **zero town-shop demand** and a tight floor → pure market-share bet.
- Sustainable **per-player** daily sell rates (half the combined absorption — plan on these): wheat ~40, egg ~30, carrot ~8, strawberry ~9→~4.5 contested, milk ~7.5, tomato/wool ~6, **melon ~3.5**. Primary throttle signal is live `market.inventory`/`market.prices` (shared, real-time); opponent tile census is a secondary early-game heuristic only (it's an intent proxy and spoofable).
- Labor is trivially cheap (8th hire = $0.875/action; Fibonacci resets daily); land pays back in 1.9–7.6 days once staffed — capital follows cash flow (day-0 land grab is dominated). **Scaling target: all 4 quadrants + ~12–14 hands by ~day 10.**
- Market orders cost zero farmer actions; only tending costs labor.
- Last profitable start days: sheep d12, strawberry d13, goose d14, cow d15, tomato d18, melon d19, wheat d25, carrot d26.

### Mechanics traps (all engine-verified — encode as invariants/tests)

1. Same-turn BUY_SEED + PLANT no-ops the plant (market resolves after unit actions).
2. Fresh plantings must be watered the same day or they weed overnight.
3. Animals can never be sold — never BUY_ANIMAL without an empty matching structure already built.
4. Melon fertilizer is worthless; tomato/strawberry fertilizer must land the day BEFORE a production tick; re-fertilizing a covered plant burns the unit.
5. Ongoing crops need only every-other-day watering (weed prevention); daily watering only matters for the fert bonus.
6. Shed cap 100, silent overflow discard — sell cadence is a correctness requirement, not an optimization.
7. Unsold inventory = $0 at game end — full liquidation by final turn.
8. Skipping FEED on a production day zeroes the banked CARE bonus.
9. First hire of a day spawns on locked (5,4) until NE is bought — budget a move turn.
10. `SELL X 99999` is a safe "sell all" idiom (no upper-bound validation).

### Verified market edges

- **Index-0 sell priority (cold-read discovery, simulation-verified ~20% edge on contested sales):** market orders resolve by list index; an order at index 0 fully executes (moving price) before the opponent's same-item order at index 1 is parsed. Quoting within the same index is simultaneous and fair — but across indices, earlier wins. → Always queue price-sensitive/crashable-good SELLs at index 0. Add an index-front-running opponent to the eval pool to confirm we're not vulnerable either.
- **Town-tick timing (satellites only):** town consumption fires after market resolution every 12 steps with no mean reversion between ticks — sell crashable goods on the turn right after a tick. Wheat/egg are exempt: their curve doesn't care, and holding them risks shed overflow — sell staples early and often.
- **Fertilizer buyback:** fertilizer market crashes at ~495 net oversupply; buy-side is not floor-protected → late-game cheap fertilizer if the shared market gluts (free animal byproduct makes this reachable).

## Strategy

**Macro: wheat+egg+carrot compounding chassis + per-player-capped satellites, adaptive.** Day 0 opens wheat rush + goose (recon Plan A: ~$4.2k bank by day 5). Scale hands/land off wheat cash flow to the day-10 target. Route surplus labor into melon/strawberry/cow/sheep satellites, each throttled by live market inventory against its per-player cap.

**Matchup framing: robustness over ceiling — but scoring is relative.** Rating is W/L only: consistent 5,500 beats occasional 6,500. AND: a play that is −EV for us but costs the opponent strictly more is correct (relative scoring). Explicit denial policy: when the opponent over-concentrates in a crashable good (esp. melon, zero town demand), either front-run their sales at index 0 or dump to crash their market — whichever costs us less than it costs them.

**Agent architecture (pure Python stdlib, stateful):**

- State tracker with `if obs["step"] == 0: reset_state()` guard (assume nothing about process reuse across episodes).
- Daily planner at day boundaries: portfolio vs per-player caps + market state + opponent census; hire count; land purchases; sell schedule.
- Per-turn dispatcher: farmer+hands task assignment with travel cost; market order list with price-sensitive sells at index 0.
- Market module: staples sell-often, satellites tick-timed and inventory-throttled; feed-wheat buy-vs-grow.
- Safety shell: top-level try/except → PASS; **hard watchdog** (self-policed elapsed-time checks at every loop boundary; `signal.alarm` belt-and-suspenders if the runner allows it); import/init time budgeted separately (heavy work lazy or at step 0 within budget); no unbounded loops anywhere.

**Eval methodology (Orbit-Wars scars applied):**

- Promotion gate: paired seeds (both sides play each seed), ≥400 non-mirror games vs pool; promote only if the 95% binomial CI lower bound on win-rate > 50% vs the incumbent.
- Regression bar (non-transitivity-tolerant): candidate must hold ≥45% win-rate (95% CI) vs every prior submitted version — no strict beat-all requirement, no deadlock on rock-paper-scissors cycles.
- Pool: starter, pass, wheat-only-spam, melon-rusher, index-front-runner, hybrid-lite, prior self-versions, plus ≥1 cloned/approximated public baseline once notebooks are mined.
- **Self-play fuzz before every submission** (separate from ranking): many-seed mirror matches hunting crashes only — the validation episode IS a mirror match and it's all-or-nothing.
- Ops rule: nothing is submitted that hasn't cleared promotion + fuzz locally. No "see how it does live" submissions.
- During M3: always keep the last known-good validated submission as a named fallback artifact, ready to resubmit in minutes if a late candidate fails validation.

## Roadmap

- **M0a (Aug 4–6) — probe first:** regenerate Kaggle API token (401s today — account-level risk, unbounded turnaround; resolve NOW). Submit a trivial legal agent (starter-equivalent + logging shim) to (a) prove the submission path end-to-end, (b) log runner Python version / package availability, (c) pull a real Kaggle replay and diff against local sim for mechanics parity. No chassis work until this is in flight.
- **M0b (by Aug 10) — Chassis v1:** repo scaffold (`src/` → `build.py` → single-file submission, Orbit-Wars pattern), eval harness v1 + self-play fuzz, chassis (wheat rush + goose + index-0 price-aware selling + safety shell). Submit.
- **M1 (by Aug 24) — economy engine:** hand/land scaling to day-10 target, shed cadence, tick-timed satellite selling with inventory throttles, carrot integration. Public notebooks/threads mined; cloned baseline joins the gating pool. Submit ~2×/week, gates first.
- **M2 (Aug 24–Sep 14) — adaptivity (honest framing: heaviest phase, collides with semester start):** opponent census reactions, satellite contest/abandon, denial policy, fertilizer buyback, endgame liquidation, CARE micro. Optional: CEM/grid parameter tuning with the noise-hardened gates. afk-shaped slices to route through the pipeline: opponent bots (wheat-spam, melon-rusher, index-front-runner — spec'd against documented CROPS/MARKET_PARAMS), harness features (paired-seed runner, CI gate calculator), replay-diff tooling.
- **M3 (Sep 15–28) — hardening + freeze:** timeout/resource fuzz, adversarial opponents, long-tail bugs. Final two submissions up by **Sep 28**; buffer reserved for fallback resubmission, not new features.
- **Oct 1–15:** hands off; monitor Bradley-Terry convergence.

## Risks

1. **Mid-season engine patches** (staff already shipping fixes) → weekly `pip install -U kaggle-environments`, diff MARKET_PARAMS + engine, re-run gates.
2. **Local-vs-server skew today** — local package may not match the runner right now; strategy edges (index-0, fertilizer thresholds) are load-bearing → M0a replay-parity diff; re-verify before relying on any numeric exploit.
3. **Tuning-on-noise** (Orbit-Wars scar) → pinned CI thresholds above; paired seeds; no best-of-N promotion.
4. **Validation-episode crash = zero signal** → self-play fuzz every submission; hard watchdog; fallback artifact during M3.
5. **Ladder ≠ final** — live rating is dev signal; the Oct Bradley-Terry is the exam. September is for shipping the two best bots, not ladder cosmetics.
6. **School collision** — M2 is the real crunch (not M0/M1); descope checkpoint Sep 7; afk slices named above.
7. **Replay exposure** — others can scrape our live submissions (Daily Top Episodes Dataset) → hold the most novel exploit behavior for a late-window submission.
8. **CC-BY 4.0 winner obligation** (open-source + methodology writeup) → write the agent assuming publication; keep the repo clean.
9. **Solo bus factor** → this doc + vault note stay current; anything in-flight is committed daily.

## Open questions carried forward

- Runner Python/env details + mechanics parity (M0a resolves).
- Daily Top Episodes Dataset: replay-mining/imitation viability (Kore-2022 precedent) as an M2+ option.
- Realized shop-unlock ramp effects on satellite sizing (expectation-model gap).
- Travel-cost multiplier on labor math (recon assumed stationed hands; likely 1.5–2×).
- Forum threads to mine: "why MELON dominates" (#732623), "Are Agents Really Competing Against Each Other?" (#732613), Daily Top Episodes Dataset (#731215), plus the three public notebooks (incl. "LB 950+" baseline).
