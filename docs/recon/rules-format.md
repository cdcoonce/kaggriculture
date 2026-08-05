# Kaggriculture — Rules, Submission Format, Runtime Constraints

Recon date: 2026-08-04. Sources: Kaggle CLI (auth failed, see note), in-app browser
(Overview/Data/Rules/Leaderboard/Discussion tabs, live), and local
`kaggle_environments/envs/kaggriculture/{kaggriculture.json,README.md,AGENTS.md}`
from the installed `kaggle-environments` package. Local docs were explicitly
confirmed by Kaggle staff (Domino Weir) in-thread as freshly updated to match the
engine, so they are treated as authoritative for game mechanics.

## 0. Tooling note

`kaggle` CLI is installed (v1.6.17) and `~/.kaggle/kaggle.json` exists with a
valid-looking `{username, key}` pair, but every CLI call
(`competitions list`, `leaderboard`, `files`, `submissions`) returned
`401 - Unauthorized - Unauthenticated`. The stored API key is stale/invalid.
All data below came from the authenticated-looking public web pages instead
(no login was performed; pages that require sign-in, e.g. full Data tab
download, were not accessible — see Data section).

## 1. Submission format

- Root file required: `main.py` at the tarball/zip root, exposing an `agent`
  function (or importable equivalent). Files land at
  `/kaggle_simulations/agent/` at runtime — imports must resolve from there.
- Single-file submission: `kaggle competitions submit kaggriculture -f main.py -m "msg"`.
- Multi-file submission: bundle into `tar.gz` with `main.py` at the root
  (e.g. `tar -czf submission.tar.gz main.py helper.py model_weights.pkl`).
- Notebook submission also supported (`-k USERNAME/notebook -f submission.tar.gz -v N`).
  CAUTION (from discussion #732450): a Kaggle Notebook that only does
  `%%writefile main.py` and then uses "Submit to Competition" can produce **no
  submission artifact** and silently fails at scoring — must actually bundle
  files or use `submission.py` per the platform's expected entry point.
- **Submission size limit: 100 MiB for everything in the submission, including
  model weights** (confirmed by Kaggle staff Bovard Doerschuk-Tiberi in
  discussion #731810, and matches the FAQ quoted there).
- 5 submissions/day max (Kaggle-wide Submission Limits rule, also echoed in
  the FAQ block quoted in #731810).
- Only the **latest 2 submissions per team are tracked/scored** — they play
  more frequently and are what's used for final leaderboard evaluation
  (Overview > Evaluation section). Older submissions stop accumulating new
  episodes but remain visible on your Submissions page.
- On upload, a **validation episode** runs (agent vs. itself); failure marks
  the submission "Error" with downloadable agent logs.

## 2. Runtime constraints (the hard bounds on what kind of agent you can build)

From discussion #731810 (Kaggle staff, Bovard Doerschuk-Tiberi) and #732762,
cross-checked against the local env spec:

| Constraint                               | Value                                                                                                                                                                                             | Source                                                                                                                                                                            |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Per-turn (`actTimeout`)                  | **1 second**, with a **60-second overage/time bank** (`remainingOverageTime: 60`) shared across the episode                                                                                       | local `kaggriculture.json` (`actTimeout: 1`, `observation.remainingOverageTime: 60`) + confirmed live by staff: "1s per turn with a 60s time bank"                                |
| HDD space                                | 8 GiB                                                                                                                                                                                             | staff-quoted FAQ, #731810                                                                                                                                                         |
| RAM                                      | 6.5 GiB                                                                                                                                                                                           | staff-quoted FAQ, #731810                                                                                                                                                         |
| vCPUs                                    | 1.6                                                                                                                                                                                               | staff-quoted FAQ, #731810 (a commenter in #732762 flagged this as effectively "1.6 CPU seconds per move" reasoning re: feasibility of in-episode LLM inference)                   |
| GPU / TPU                                | **None — CPU only**                                                                                                                                                                               | staff, #731810                                                                                                                                                                    |
| Internet access during episode           | **None**                                                                                                                                                                                          | staff, #731810; also Rules §2.12 "NO INGRESS OR EGRESS... may not pull in or use any information external to the Submission and Environment and may not send any information out" |
| Configuration used for scoring           | **Default configs** (not whatever you test locally)                                                                                                                                               | staff, #731810                                                                                                                                                                    |
| Python version                           | Not explicitly stated anywhere found; local kit installs via `pip install -U kaggle-environments` — no pinned interpreter version surfaced in docs, FAQ, or discussion                            |
| Preinstalled packages on episode runners | Not stated in any source found — UNKNOWN. Given the 100 MiB submission cap and no-internet rule, any non-stdlib dependency beyond what's preinstalled must be vendored inside that 100 MiB budget |
| Episode length                           | 720 turns (24 turns/day × 30 days), `episodeSteps: 720`                                                                                                                                           |
| Agents per episode                       | 2 (`agents: [2]` in spec)                                                                                                                                                                         |

Practical implication (also raised explicitly on the forum, #732762): running
an actual LLM as the live in-episode policy is "essentially impossible" —
no GPU, ~1 CPU, 1s/turn budget. LLM use is _allowed_ by the rules (Kaggle
staff Addison Howard: "Yep! As long as you have the rights to use them and
their outputs for this competition") but is realistically only viable for
**offline** design/tuning work (e.g., using an LLM to help write/tune the
agent's logic beforehand), not as an online decision-maker per turn.

## 3. Game / observation / action contract (engine ground truth)

Config defaults (all overridable at episode-creation time, not by the
competition host per-submission — competition uses **default configs**):

- `episodeSteps=720`, `boardSize=10` (four 5×5 quadrants, only NW unlocked at
  start), `startingMoney=3000`, `maxMarketOrdersPerTurn=10`,
  `turnsPerDay=24`, `shedCapacity=100`, `weedSpawnChance=0.005`,
  `townShopUnlockInterval=3`, `townShopSellInterval=4`,
  `townCenterSellInterval=12`, `farmHandCostMult=1`.
- Reward = player's money at end of game. Win = most coins; ties possible.
- Observation: `player`, `step`, `day`, `hour`, `farms[2]` (public, both
  players' tiles/money/farmer/hands/unlocked_quadrants/hires_today visible to
  both), `private` (own shed/seeds/per-unit inventories only — opponent's
  private state hidden), `market` (shared inventory+prices), `town` (shared
  unlocked_shops list).
- Action: `{"farmer": [op,...], "hands": [[op,...],...], "market": [[op,...],...]}`.
  Invalid actions are silent no-ops (no crash, no penalty beyond the wasted
  turn) — this matters for defensive coding under the 1s/turn budget.
- Full mechanics (crop/animal yield curves, market price-curve formula per
  resource, turn processing order, shed/hire/land-purchase costs, town-demand
  schedule) are documented in detail in the local README.md/AGENTS.md, which
  Kaggle staff confirmed on 2026-08-04 were just synced to match the engine
  after a round of discrepancy reports. Do not trust older cached copies of
  these docs — several mechanics differ from what's on the competition page
  vs. README vs. AGENTS.md, and staff explicitly said "engine wins" when they
  disagree (see Discussion section below).

## 4. Rules page (accepted via browser, not submitted/joined)

- **Sponsor**: Google LLC. **Hosting platform**: Kaggle Inc.
- **Total prizes: $50,000** — ten prizes of **$5,000 each** (1st through
  10th place), confirmed identically on both the Rules page and the
  Overview > Prizes section.
- **Team size**: max 5. Team mergers allowed pre-merger-deadline, combined
  submission count must stay within the per-day cap × days-running formula.
- **Submissions/day**: 5 max. **Final submissions selectable for judging**: up
  to 2.
- **No Private Leaderboard** for this competition type — Rules §2.10 states
  simulation competitions have no private/public split; final ranking comes
  from the live episode-based skill ladder + end-of-competition Bradley-Terry
  tournament (see Timeline/Evaluation below), not a held-out test set.
- **External data/tools**: allowed under a "Reasonableness Standard" — must be
  free/low-cost and equally accessible to all participants; AMLT (automated ML
  tools, e.g. AutoML products) explicitly permitted if properly licensed.
- **LLM/AI-tool policy**: allowed generally (staff confirmed explicitly, see
  §2 above), subject to having rights to the LLM's outputs; constrained in
  practice by the no-internet/no-GPU/1s-per-turn runtime, not by rule text.
- **Winner obligations**: winning submission's code must be licensed
  **CC-BY 4.0** (open source); winner must post a detailed methodology
  write-up on the competition forum (architecture, preprocessing, training
  details, hyperparameters, reproducible repo link) and may be asked to do a
  recorded call with the sponsor/other winners.
- **Competition Data license**: **Apache 2.0** (per Rules §1.7 and the Data
  tab metadata).
- **No ingress/egress during episode evaluation** (§2.12) — reinforces the
  no-internet runtime constraint as a rules matter, not just infra.
- **Private code sharing banned** outside of your own Team; public sharing on
  Kaggle forums/notebooks is fine and implicitly OSI-licenses the shared code.
- Eligibility: standard Kaggle geo/sanctions exclusions (Crimea/DNR/LNR, Cuba,
  Iran, North Korea, OFAC-sanctioned parties); 18+ or age of majority.

## 5. Timeline (Overview tab)

- **Start Date**: July 29, 2026.
- **Entry Deadline**: September 23, 2026, 11:59 PM UTC.
- **Team Merger Deadline**: September 23, 2026 (same as entry deadline).
- **Final Submission Deadline**: September 30, 2026, 11:59 PM UTC — matches
  the deadline given in the task context.
- **Post-deadline evaluation window**: October 1 – ~October 15, 2026. Games
  keep running (or until leaderboard convergence); at the end, a **single
  Bradley-Terry tournament** run on the accumulated episodes from that window
  determines final placement — explicitly designed (per pinned staff post,
  discussion #731587) to reduce "hot streak" luck versus a pure live-ladder
  cutoff.

## 6. Evaluation / ranking mechanics (Overview tab)

- Each submission gets an Elo-like **skill rating**; win → rating up, loss →
  down, tie → ratings converge. Rating delta is a function of the
  rating gap (upsets pay more), NOT the coin margin — margin of victory is
  irrelevant to rating movement during the ladder phase.
- Matchmaking pairs similar-skill submissions. Only the **latest 2**
  submissions per team stay in active matchmaking; newer submissions get
  more frequent games (to converge rating faster) than older ones.
- Leaderboard shows only your **best-scoring** submission; track others via
  the Submissions page.
- At the Final Submission Deadline, the locked set of eligible submissions
  keeps playing for ~2 more weeks, then the one-shot Bradley-Terry tournament
  on that accumulated episode set is authoritative for final rank (not the
  live ladder rating at deadline time).

## 7. Leaderboard snapshot (2026-08-04, live)

- **1514 teams total** ("50 - 1514, See 1465 More" below the visible top 49).
- Top score: **3105.6** (team "somewhere after").
- Rank 2–10 range: **2690.0 – 2937.4** — a large gap (~168 pts / ~5.4%) between
  #1 and #2, then a dense, gently-sloping tail from #2 down through the
  visible top 49 (2637–2937), i.e. one clear outlier leader, then a fairly
  flat competitive pack. Scores are skill ratings (Elo-like), not raw coin
  totals — do not treat as $ figures.
- A "manual player" entry (rank 12, score 2799.8) is on the board — Kaggle
  supports a human-played "Play in Browser" mode that evidently also nets a
  ladder rating.
- Given the competition started only ~5 days before this recon and has ~2
  months left, current rankings are early-season and expected to move
  substantially; rating convergence claims from staff (§6) suggest the
  October Bradley-Terry pass is the number that actually matters.

## 8. Data tab

- Only artifact listed: **README.md (25 kB)** — "the folder for the Python
  kit," i.e. the same README bundled in the local `kaggle-environments`
  package (`kaggriculture/README.md`, 25,077 bytes locally, exact word-for-
  word match to what's rendered on the live Overview "How to Play" section).
  A note links to the Lux AI Challenge GitHub repo as an example for kits in
  other languages (implies this competition core kit is Python-first but the
  environment protocol itself is language-agnostic).
  Metadata: **License: Apache 2.0**.
- Actual "Competition Data" download (beyond the README) requires accepting
  the competition rules while signed in — this recon did not sign in or join,
  so the full download listing behind that gate was not inspected. Given the
  nature of this environment (procedurally-generated episodes, no train/test
  files), it's likely there isn't much more than the README + kit files
  behind that gate, but this is UNCONFIRMED.

## 9. Discussion tab — top threads (sorted by votes, 2026-08-04)

Pinned:

1. **"Comment on the final evaluation for this competition"** (María Cruz,
   Kaggle staff, 11 votes) — explains the Bradley-Terry final-tournament
   design rationale (§5/§6 above). No replies.
2. **"Daily Top Episodes Dataset"** (Bovard Doerschuk-Tiberi, Kaggle staff,
   11 votes) — a dataset of daily top episodes exists (title only inspected,
   not opened in depth — worth a follow-up read for anyone building by
   imitation/replay-mining).
3. **"How to get started + Competition's Official Discord"** (María Cruz,
   3 votes, 3 comments) — points to an official Discord; not opened in depth.

Top of "All other topics" (by votes): 4. **"Crucial Information for Starters and Organizers: Documentation vs.
Engine Discrepancies"** (SIDHAARTH SHREE, 14 votes) — READ IN FULL. Staff
(Domino Weir) confirmed and fixed doc/engine mismatches: animal CARE bonus
is +1/day not +2; fertilizer CAN be sold (`SELL FERTILIZER n` valid, docs
were wrong); `DIG` only clears _unoccupied_ coops/pastures; an unwatered
seed becomes a weed the same night it's planted (no grace period); Melon's
documented 6–12 day bonus window has dead turns after day 10 (cap already
hit); Strawberry is capped at exactly 4 yields (ages 10/12/14/16), not
indefinite; per-day yield table numbers were inconsistent and have been
corrected. Also flags a **notebook-submission trap**: `%%writefile main.py`
inside a Kaggle Notebook plus "Submit to Competition" can produce no
submission artifact. All of this is now folded into the local
README/AGENTS.md, which staff say are current as of this recon date. 5. **"A few rule questions for the organizers"** (Triston Morgan, 6 votes) —
READ IN FULL. Confirms: fertilizer IS sellable (readme updated); animals do
NOT need CARE to produce fertilizer (the in-code comment was wrong, fixed);
fertilizer does not accumulate — a new unit isn't available until the
previous one is collected; the market's `T` calibration window is
deliberately 24 days (not the full 30-day season) because staff judge the
opening days as "setup focused" — an explicit, non-obvious design choice
now documented in the README. 6. **"Bug: Hired hands can spawn on locked land and get stuck"** (Victor
Mercklé, 6 votes) — real engine bug, confirmed fixed by staff per the
#732450 thread (spawned hands on locked tiles can now always move back to
playable tiles). 7. **"Did anyone else think of board games?"** (Kaito Fukami, 3 votes) — meta/
flavor discussion, not strategy-bearing; not opened. 8. Japanese self-introduction thread (nk, 3 votes) — social, not
strategy-relevant. 9. **"Query on Submission Resources"** (harshraj22, 2 votes) — READ IN FULL,
this is the source of the runtime numbers in §2 above (100 MiB, no
internet, CPU-only, default configs, 1s/turn + 60s bank). 10. **"(Resolved) How to show episodes?"** (RiLi, 1 vote) — tooling/UI
question, not opened. 11. **"Crop price crash analysis — why MELON dominates (with math)"** (David
Pedersen, 1 vote) — STRATEGY-BEARING TITLE, not opened in depth due to
time; flagging as a priority follow-up read — likely argues Melon's
weak scarcity reaction + high base price makes it a strong early-market
pick before glut sets in (consistent with the market table: Melon's
`above_target=3.60` means it crashes hard on oversupply, so the claim is
probably about sequencing/quantity discipline, not "always plant melon"). 12. **"[Problem] Too many requests to ListEpisodes"** (Ali, 1 vote) — API/
tooling complaint, not opened. 13. **"Are Agents Really Competing Against Each Other?"** (Ehsan, 1 vote) —
title suggests a question about matchmaking/opponent pool fairness; not
opened, worth a follow-up given it touches evaluation trust. 14. **"NameError: name 'agent' is not defined"** (Bikash Gyawali, 0 votes) —
likely a submission-format pitfall (matches the `agent` function
requirement in §1); not opened. 15. **"Farm hands won't move"** (Liam Newsam, 0 votes, posted 2h before
recon) — too fresh to have signal; not opened. 16. **"Can we use LLMs?"** (Gokul Prasath, 0 votes) — READ IN FULL, source of
the LLM policy confirmation in §2/§4 above. 17. **"Multi-Sensory Colour Coded Ai to Ai Communication Tool"** (Angus Mc
Gregor, 0 votes) — title suggests an off-topic/gimmick post (this is a
2-player competitive game — "AI to AI communication" doesn't map to any
game mechanic); not opened, low-priority. 18. **"Bug? CARE rate"** (Jonathan Roy, 0 votes) — almost certainly the same
CARE +1-vs-+2 discrepancy already resolved in thread #4 above; not opened. 19. **"New to simulation competitions — where should I start?"** (Jesmi
George, 0 votes) — onboarding question, not opened. 20. **"Alternative replay viewer"** (rooklift, 0 votes) — tooling, not opened.

## Answers to the explicit checklist

- **Submission format**: `main.py` at tarball root exposing `agent`; tar.gz for
  multi-file; notebook submission supported but has a known footgun. Max
  **100 MiB total** including weights. ANSWERED.
- **Runtime — per-step limit**: **1s/turn + 60s overage bank** (episode-wide).
  ANSWERED.
- **Runtime — total episode budget**: not stated as a wall-clock episode cap
  beyond the per-turn/bank mechanism; 720 turns × 1s + 60s bank is the
  effective ceiling (~13-14 min of compute budget per episode if fully used).
  UNKNOWN whether there's an additional hard wall-clock kill switch on top.
- **Runtime — memory**: 6.5 GiB RAM, 8 GiB HDD. ANSWERED.
- **Runtime — CPU/GPU**: 1.6 vCPUs, **CPU only, no GPU/TPU**. ANSWERED.
- **Runtime — Python version**: UNKNOWN — not stated anywhere found.
- **Runtime — preinstalled packages**: UNKNOWN — not stated anywhere found.
  Plan conservatively: vendor everything needed inside the 100 MiB cap.
- **Runtime — internet access during episodes**: **None** (rules + staff both
  confirm). ANSWERED.
- **Rules — team size**: max 5. ANSWERED.
- **Rules — submissions/day**: 5/day, 2 tracked/active, 2 selectable as
  finals. ANSWERED.
- **Rules — external data/pretrained-model policy**: allowed under a
  "Reasonableness Standard" (low-cost, equally accessible); AMLT explicitly
  OK. ANSWERED.
- **Rules — LLM/AI-tool policy**: explicitly allowed by rules/staff; made
  practically inert as an _in-episode_ policy by the runtime constraints
  (no GPU, no internet, 1s/turn). Offline use (dev-time) unconstrained.
  ANSWERED.
- **Rules — winner obligations**: CC-BY 4.0 open-source release of winning
  code + detailed reproducible methodology write-up on the forum + possible
  recorded call. ANSWERED.
- **Rules — prize eligibility**: standard Kaggle geo/sanctions/age exclusions;
  no special eligibility carve-outs found for this competition beyond the
  Foundational Rules. ANSWERED.
- **Leaderboard — current top scores**: #1 = 3105.6, #2-10 range
  2690.0-2937.4. ANSWERED (see caveats on early-season volatility in §7).
- **Leaderboard — score distribution shape**: sharp single leader, then a
  dense near-linear pack. ANSWERED.
- **Leaderboard — active teams**: **1514**. ANSWERED.
- **Data tab — files provided**: just the README.md (25 kB, Apache 2.0) at
  the unauthenticated level; full data-download gate requires sign-in +
  rule acceptance, not inspected (UNCONFIRMED whether anything beyond the kit
  exists behind it).
- **Discussion — top threads skimmed**: 20 titles captured, 6 opened in full
  (see §9). Two flagged as high-value unread follow-ups: "Daily Top Episodes
  Dataset" and "Crop price crash analysis — why MELON dominates (with math)".
