# Kaggriculture Recon: How Kaggle Simulation Comps Are Won

Compiled 2026-08-04. Sources are web-search-derived (search-engine summaries plus a
few directly fetched pages — Kaggle's competition/discussion/notebook pages are a JS
SPA that mostly defeats WebFetch, so most Part 2/3 intel below is search-snippet
quality, not primary-source-verified; flag accordingly before acting on specifics).

---

## Part 1 — Prior Kaggle simulation-comp meta

### Halite IV (2020, Two Sigma/Kaggle, ~1100 teams)

- Community consensus per search: rule-based/heuristic agents won the top slots;
  RL was tried widely but did not dominate the top of the leaderboard.
- A documented high-finisher (Kha Vo et al., team "KhaVo Dan Gilles Robga Tung",
  finished 8th/1143) used **imitation learning by semantic segmentation** — a CNN
  trained to predict each ship's action from top replays (centralized, per-cell
  classification), layered with hand-tuned heuristics for base spawning, ship
  conversion, and base protection. This is a hybrid IL+heuristics pattern, not
  pure RL and not pure rules.
- Could not confirm the literal #1 write-up content (site didn't resolve); the
  8th-place pattern (IL core + heuristic overlay for edge decisions) is the
  best-evidenced "recipe" from this era.

### Hungry Geese (2021, ~1100 teams)

- 1st place trained with **HandyRL** (DeNA's open-source distributed self-play RL
  framework) — pure self-play RL won this one, notable because the game (4-player
  snake) has a small, fully-observed action space well suited to self-play.
- Lower placements (11th) used NN+MCTS hybrids — search on top of a learned
  evaluator is a recurring "good but not winning" pattern in these comps.
- Small-board, short-horizon games reward pure self-play RL more than large
  economy/logistics games do (contrast with Kore/Lux below).

### Lux AI Season 1 (2021, ~1200 teams)

- Field split visibly between rule-based bots and imitation-learning bots trained
  on top replays pulled via the Kaggle API. "Toad Brigade" is cited repeatedly as
  a top team; could not confirm their exact method from search alone.
- A documented 9th-place solution used a **hybrid rule-based decision layer +
  ML layer** predicting actions from state features — same hybrid pattern as
  Halite's 8th place.
- Confirms this genre rewards hybrid architectures (learned/tuned core +
  hand-written guardrails) more consistently than either pure end.

### Lux AI Season 2 (2023, NeurIPS-affiliated, ~646 teams)

- **1st place (ryandy) was a solo entrant, rule-based/heuristic** (not RL, not
  deep search) — the competitor states they initially planned a team entry that
  fell through and finished solo. Description: "stateful rules-based bot with no
  full forward projection (some internal forward projection)," in TypeScript.
  Most of the winning edge reportedly came from **the first couple of months of
  self-play-informed iteration**, discovering positional/economic tricks before
  others did.
- Direct evidence that **a solo, non-ML, well-engineered heuristic agent can win
  a modern (2023) large-field Kaggle sim comp** if the state space rewards
  precise game-tree/economic reasoning over pattern-matching.
- This is the single most load-bearing data point for Charles's situation (solo,
  strong engineering, limited GPU, ~2 months): it is a direct existence proof,
  not just "heuristics can place well."

### Kore 2022 (~1300 teams)

- 1st place used a **Vision-Encoder + Transformer-Encoder/Decoder ("pix2seq"-
  style) imitation-learning model**: board state encoded via a custom ConvNeXt +
  TorusConv2d (torus-aware convolution for the wraparound board), actions
  generated as tokenized "action strings" via causal LM decoding, DETR-style
  positional encoding added at every attention layer for faster convergence.
  This is a heavyweight, ML-research-grade approach — signals a real compute/ML
  budget on the winning team, not solo-engineer-with-a-laptop scale.
- Could not confirm team size, hours invested, or late-competition meta shift
  from available sources — treat as an open question.
- A separate solo/small-team GitHub project (khanhvu207) replicated an
  **autoregressive imitation-learning** approach on ~200M state-action tuples
  scraped from the top 5 leaderboard submissions — i.e., "clone the current best
  public bots, then differentiate" is a documented and apparently viable strategy
  in economy-style Kaggle sim comps.

### LLM 20 Questions (2024, ~832 teams)

- Different genre (LLM-driven Q&A game, not a board/economy sim) but one useful
  transferable finding: a **65th/832** competitor's most effective lever was a
  **deterministic binary-search-over-vocabulary strategy** layered on top of the
  LLM, i.e., a hand-engineered algorithmic core outperforming naive prompting.
  Reinforces the hybrid-beats-pure-ML pattern seen elsewhere.

### FIDE & Google Efficient Chess AI Challenge (2024)

- Explicitly designed to reward **efficiency under constrained compute/memory**
  rather than raw search depth — organizer framing (per FIDE/Google announcement)
  was "ingenuity over computing force." Could not retrieve winner/solution
  details (comp likely still resolving results at the time of the indexed
  pages). Notable mainly as evidence Kaggle/Google increasingly design comps to
  reward engineering efficiency over brute compute — plausibly a design
  philosophy shared with Kaggriculture given it's also a Kaggle+Google comp.

### Santa 2023/2024

- Different genre (single-agent combinatorial optimization/permutation puzzles,
  not 2-player adversarial sims) — local-search/metaheuristic techniques (TSP-style
  k-opt, double-bridge kicks, weighted candidate generation) won. Not directly
  transferable to Kaggriculture's adversarial 2-player structure, but confirms
  that **classical OR/heuristic search techniques remain highly competitive on
  Kaggle even in 2024**, i.e., deep learning is not a prerequisite for winning.

### Cross-cutting observations (not independently verifiable per-comp, but consistent across searches)

- Could not confirm a specific "meta shifted dramatically in the final two weeks"
  story with a citable source for any single comp in this search pass — this is
  a commonly _believed_ pattern in the Kaggle sim-comp community (a public
  notebook or forum insight late in a comp reshuffling many ranks) but I did not
  find hard evidence tied to Halite/Hungry Geese/Lux/Kore specifically. Treat the
  "late meta shift" risk as a plausible-but-unconfirmed prior, not an established
  fact, for this specific comp set.
- The recurring signal about top-10-vs-top-50 is indirect (generic Kaggle
  hyperparameter-tuning advice, not sim-comp-specific): effort should scale with
  proximity to the cutoff you're targeting — grinding marginal gains only pays
  off once you're already close to the top-10/top-50 boundary.

---

## Part 2 — Kaggriculture-specific public intel

- **Official framing** (from Kaggle/Google announcement + landing page): build an
  AI agent to manage a virtual farm — harvest crops, care for animals, boost
  yields, expand land, trade on a dynamic market where prices react to supply
  and demand. $50,000 total prize pool (note: this figure from the X/Kaggle
  announcement differs from the $5k×top-10 = $50k figure given in the task
  brief — consistent, just phrased differently: total pool likely IS $50k split
  across 10 prizes). Entry deadline cited as September 23, 2026 in the
  announcement (task brief says final submission deadline 2026-09-30 — these may
  be two different deadlines, i.e., team-merger/entry-deadline vs final-submission
  deadline, which is Kaggle's normal pattern; **verify both dates directly on the
  competition rules page before relying on either**).
  As of the indexed snapshot: **~750 teams**, "~2 months to go."
- **Public notebooks exist**: "Kaggriculture: Observable Economic Control" and
  "Kaggriculture: Findings from Zero to Top Meta" are both indexed as public
  Kaggle notebooks (titles alone found; could not fetch bodies — Kaggle's SPA
  blocked WebFetch, and the direct notebook URL 404'd, likely because the
  scriptVersionId in the URL was for a specific saved version). A "[STRONG
  START]: Baseline Agent V10 | LB 950+" notebook also exists, implying a public
  leaderboard baseline in the ~950 score range already circulating — **this is
  the single most actionable unresolved item**: Charles should open these three
  notebooks directly in a browser (not headless fetch) to read the actual
  strategies and copy/beat the baseline score.
- **Confirmed engine-bug forum chatter** (from search snippet, not primary
  source): a discussion thread reports "**Hired hands can spawn on locked land
  and get stuck**" — a genuine engine bug/edge case in unit spawning logic.
  Also referenced: general "documentation vs. engine discrepancies" complaints,
  which is exactly the kind of operational risk the task brief anticipated
  (organizers patching/clarifying engine behavior mid-season). **Action item**:
  monitor the Kaggriculture discussion forum (kaggle.com/competitions/
  kaggriculture/discussion) directly and regularly — this recon pass could not
  reliably enumerate its full thread list through search alone.
- **No organizer statements found** about planned patches or rule changes beyond
  what's implied by the "documentation vs engine discrepancies" bug reports.
  Could not confirm whether Kaggriculture has had (or is expected to have) a
  mid-season engine patch — this is an open risk, not a resolved one.
- No GitHub repo, Reddit thread, or X/Twitter strategy chatter specific to
  Kaggriculture surfaced beyond the official Kaggle launch tweet. The comp
  appears too new/niche for third-party community writeups yet (launched
  recently relative to the Aug 4 2026 vantage point, per "~2 months to go"
  language keyed to a Sept 2026 deadline).

---

## Part 3 — Ladder mechanics wisdom (Kaggle skill-rating system)

- **Confirmed mechanics** (from Kaggle's own doc, via search extraction): each
  submission's skill is modeled as a Gaussian N(μ, σ²) — μ is the point estimate,
  σ is uncertainty and shrinks over time as more episodes are played. New
  submissions enter the matchmaking pool at an **initial μ of 600**. Win/loss/draw
  updates move μ up/down (or toward the mean, for a draw) proportional to how
  surprising the result was given prior μ values and current σ. **The margin of
  victory does not affect the rating update** — only win/loss/draw matters, so
  there's no reward for "crushing" an opponent by a wider margin, only for
  winning more often against higher-rated opponents.
- **Newer submissions are matched more frequently** to converge their rating
  faster (higher σ → prioritized for games) — implies early submissions get
  more games than a submission uploaded in the final days, which has direct
  implications for the "when to submit" question below.
- **Validation episode**: uploading a submission triggers a self-play validation
  episode before it's allowed into the ladder; if that episode errors, the
  submission is marked Error and doesn't compete. **This is a hard gate** — a
  submission that works fine against a human-eyeballed test but throws on some
  edge case in self-play (e.g., playing against a copy of itself, which can
  surface state collisions, tie-breaking bugs, or resource contention that never
  show up against a different opponent) never even enters the ladder. Practical
  implication: **test explicitly against self-play locally before every
  submission**, not just against known baseline bots — self-play is a distinct
  and harder failure mode (symmetric states, simultaneous claims on the same
  resource, etc.) than beating an asymmetric baseline.
- **Submission timing / sandbagging**: could not find sim-comp-specific forum
  wisdom on optimal submit timing beyond the general Kaggle norm of "3–5
  submissions/day" (this is the general competition-submission cap, not
  necessarily binding for sim comps, which usually allow continuous submission
  replacement — verify Kaggriculture's specific submission-frequency rule
  directly). No confirmed evidence either way on whether "rating farming" early
  (submit often, accept early rating noise) or "sandbagging" (hold your best
  agent back near the deadline to avoid revealing strategy to competitors who
  study the leaderboard/replays) is the dominant winning pattern for this
  specific comp family. Given that **the final tournament reportedly uses a
  Bradley-Terry model over the pool of final (or last-2) submissions rather than
  the live ladder rating**, the operationally safe default is: **submit early and
  often to shake out validation-episode bugs and build a stable baseline, but
  treat your true best/final agent's replays as somewhat exposed the moment you
  submit it** — anyone can download and study replays of active leaderboard
  agents. This argues for holding your genuinely novel strategic edge (if any)
  for a late-window submission, while still submitting _something_ competitive
  throughout to keep validating your pipeline and catching engine-interaction
  bugs early.
- **"Latest-2-submissions tracked" rule** (per task brief, not independently
  re-confirmed in this pass): if only your latest 2 submissions count toward
  final standing, this changes the calculus from "keep your best agent live the
  whole time" to "make sure your final 2 submissions, whenever they land, are
  each independently robust" — a bad final submission can't be silently
  rescued by an earlier good one still sitting active. **Verify this rule's
  exact wording on Kaggriculture's rules page before finalizing a submission
  strategy** — this recon pass could not independently confirm it.
- **Episode-count convergence**: no source found with a concrete "N episodes to
  converge" number for this comp family; general sim-comp lore (unconfirmed) is
  that ratings stabilize over hundreds of episodes per submission given normal
  matchmaking throughput, and that new submissions late in a comp may not
  accumulate enough episodes for their rating (and thus their queue priority
  for the _next_ round of matches) to reflect true skill before the deadline —
  reinforcing "submit meaningfully-improved agents early enough to accumulate
  games," even if the true competitive edge is saved for near the end.

---

## Top 10 transferable lessons, ranked

1. **A solo, well-engineered heuristic/rule-based agent can win a modern
   (2023+) large-field Kaggle sim comp** — Lux AI S2's 1st place (ryandy) is
   direct proof, not inference. This is the most important single data point
   for Charles's exact situation (solo, strong engineering, ~2 months, limited
   GPU): the dominant strategy for his profile is almost certainly **precise
   game/economy-tree reasoning encoded as fast, well-tuned heuristics**, not
   training a novel deep RL/IL model from scratch under time pressure.
2. **Hybrid (learned-or-tuned core + hand-written guardrail layer) beats either
   pure end** across Halite (8th place: IL+heuristics), Lux S1 (9th place:
   rules+ML), and even LLM 20 Questions (LLM+deterministic binary search) —
   if any learned component is used at all, wrap it in explicit rule-based
   safety/edge-case handling rather than trusting it end-to-end.
3. **"Clone the current best public bots, then differentiate" is a legitimate,
   documented strategy** (Kore 2022's autoregressive-IL-on-scraped-replays
   project) — once Kaggriculture's public baseline/leaderboard has meaningful
   agents on it, downloading and studying top replays is standard practice, not
   an edge case.
4. **Self-play validation is a distinct, harder failure mode than beating a
   baseline** — the mandatory validation episode is self-play, and any
   submission that errors there never enters the ladder. Build a local
   self-play test harness from day one and run every candidate submission
   through it before uploading, specifically hunting for simultaneous-resource-
   claim / symmetric-state / tie-breaking bugs.
5. **Kaggriculture already has at least one confirmed engine bug in the wild**
   ("hired hands can spawn on locked land and get stuck") plus general
   "documentation vs engine" complaints — go read the live discussion forum
   directly (not via search) before finalizing any strategy that depends on
   documented rules; the effective rules may differ from the written ones, and
   organizer patches are a real operational risk this comp has already shown
   signs of.
6. **Margin of victory does not affect Kaggle's skill rating** — optimize
   purely for win probability against your matched opponent pool, not for
   maximizing score differential; a strategy that wins narrowly 90% of the time
   outranks one that wins big 60% of the time.
7. **New submissions get matched more frequently to converge σ faster** — submit
   early and often (even mediocre-but-working agents) to build rating history
   and catch engine-interaction bugs, rather than holding everything for a
   single late "big reveal" submission.
8. **If a "latest-2-submissions" rule genuinely governs final standing (verify
   this), each of your last two submissions must be independently robust** —
   don't treat submission N-1 as a safety net for a risky submission N; both
   need to individually clear validation and play competitively.
9. **Genre matters for method choice**: small fully-observed short-horizon games
   (Hungry Geese) reward pure self-play RL; large economy/logistics games with
   long horizons (Kore, Lux, and structurally Kaggriculture — 720-turn
   farm/market economy) have historically rewarded heuristic/hybrid/IL
   approaches over pure RL, likely because the effective search/state space and
   reward sparsity make from-scratch RL convergence expensive relative to a
   solo competitor's 2-month, limited-GPU budget.
10. **Public replays of any live leaderboard agent are visible to competitors**
    — anything you submit early can be studied and countered by others before
    the deadline. Balance "submit early to build rating and shake out bugs"
    (lesson 7) against "your best novel strategic idea is safest revealed only
    in a late submission" — submit competitively throughout, but consider
    holding your most differentiating edge for the closing window.

### Explicitly unresolved / needs direct follow-up (not resolvable by search alone)

- Exact Kaggriculture submission-frequency limit and whether "latest-2-
  submissions" is real — read the competition rules page directly.
- Whether the Sept 23 vs Sept 30, 2026 date discrepancy is team-merger deadline
  vs final-submission deadline, or a source error — confirm on the rules page.
- Full content of the "Observable Economic Control" and "Findings from Zero to
  Top Meta" public notebooks, and the "[STRONG START] Baseline Agent V10 | LB
  950+" notebook — open these directly in-browser; they are almost certainly
  the fastest path to understanding the current public meta and score scale.
- Whether Kaggriculture has had, or the organizers have signaled, any mid-season
  engine patch — monitor the discussion forum directly and periodically.
- Full text of any Kaggriculture-specific discussion threads beyond the single
  "hired hands" bug snippet surfaced here.
