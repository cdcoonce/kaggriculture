# Research R4 — Learned components in Kaggle sim comps, viability for "Kaggriculture"

Date: 2026-08-04. Method: WebSearch/WebFetch (some Kaggle writeup pages only rendered
title+snippet even via r.jina.ai proxy — flagged per-row where full text wasn't retrievable).

## Target constraints (Kaggriculture)

2-player farming/economy, 720 turns, submission ≤100MiB tar.gz Python, CPU-only
(~1.6 vCPU, 6.5GiB RAM), no internet, 1s/turn + 60s overage bank (bank shared across
all 720 turns — can be hoarded and spent on a few expensive turns), package availability
UNKNOWN (possibly stdlib-only, numpy at best).

## Evidence table

| Comp (year, turns, actTimeout)                                                                                           | Best learned entry                                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Approach                                                                                                                                                                                                                                                                                                                           | Footprint / inference stack                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Outcome vs heuristics                                                                                                                                                                                                                                                               |
| ------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Kore 2022** (400 turns, actTimeout=3s, runTimeout=9600s)                                                               | khanhvu207, **1st place overall**                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Pure IL. Encoder-decoder Transformer: ConvNeXt/ResNet-style vision encoder + TorusConv2d, transformer encoder, autoregressive transformer decoder emitting ship-plan tokens (pix2seq/DETR-style). Trained on ~200M single-timestep (obs, plan) tuples scraped from top-5 leaderboard replays.                                      | PyTorch. Training: 2×A100, batch 64, AdamW, 20 epochs. **No published per-turn CPU latency or inference-time package footprint** — biggest evidence gap for this row.                                                                                                                                                                                                                                                                                                                      | **Won outright.** Best precedent that IL cloned from top replays can beat all heuristics in an economic/resource-optimization sim comp.                                                                                                                                             |
| **Lux AI S1** (2021)                                                                                                     | 9th/1178 place, hybrid                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Rule-based scoring engine + ML-predicted per-unit action scores; stateless, multi-pass scoring across units.                                                                                                                                                                                                                       | Lightweight ML scorer, not a full policy net.                                                                                                                                                                                                                                                                                                                                                                                                                                              | Mid-pack, respectable but not top-tier; hybrid, not pure-ML.                                                                                                                                                                                                                        |
| **Lux AI S2** (2023)                                                                                                     | **1st place = pure heuristic** (ryandy): stateful, role-based bot, hand-tuned via bot-vs-bot iteration, written in TypeScript, no ML. **4th place = FLG**, deep RL.                                                                                                                                                                                                                                                                                                                     | FLG: custom lightweight CNN, "DoubleCone" architecture — downsamples to 12×12 compute path with skip connections around it, full-res 48×48 ResBlocks only at the edges, SqueezeExcitation instead of norm layers, avoided 1×1 convs (GPU-favored, CPU-unfriendly) — because Kaggle's eval ran on **"unreliable single-core VMs."** | PyTorch, pure Python, no RL framework. Had to predict **4-8 step action queues per NN call** because single-step inference couldn't hit the per-turn budget — "below that [4-6 steps], performance was crippling." **Attempted ONNX+OpenVINO CPU acceleration and it failed to deploy** on Kaggle's runner. Also blended in IL (2000 downloaded matches) + pattern-matching fallback — pure RL alone wasn't enough.                                                                        | **Heuristic won outright; the serious, CPU-latency-engineered RL effort only reached 4th.** Single best cautionary case study for a tight CPU-only turn budget.                                                                                                                     |
| **Halite IV** (2020, 4-player, ~21×21 board)                                                                             | Winner **ttvand**: explicit hybrid — repo has separate "Rule agents" and "Deep Learning Agents" folders, rule-based components "significant" per author. 4th place: simple pure rule-based bot. **8th/1140 gold — Kha Vo**: IL via U-Net (modified EfficientNet-B0 encoder, shallow depth-2, 5 extra stride-1 convs to preserve pixel detail), 20-30 engineered feature channels in, 5-channel action-probability map out, resolved via linear-sum-assignment for multi-agent conflict. | PyTorch + Catalyst. Trained on ~3,000 curated top-daily replays out of 100k+ scraped total.                                                                                                                                                                                                                                        | **Pure-ML-only version alone reached only ~rank 20**; blending IL scores with hand-tuned heuristic overlays (spawn/convert/defend rules) is what pushed it to **rank 8/1140 (gold)**. Cleanest evidence that hybrid (IL as one signal inside a heuristic-gated decision) beats either pure IL or pure heuristic alone.                                                                                                                                                                     |
| **Hungry Geese** (2021, 200 turns, **actTimeout=1s** — exact match to Kaggriculture's per-turn budget, small 7×11 board) | HandyRL-based top entries                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Small dual policy/value ResNets (one cited top writeup: **8 layers × 46 channels**), trained via behavior cloning + RL fine-tuning (V-trace), light MCTS at some entries' inference time.                                                                                                                                          | PyTorch (HandyRL framework). Runs comfortably inside the 1s CPU budget on Kaggle's infra — this is the best **concrete sizing anchor**: an 8-layer/46-channel CNN is "small enough" for a 1s actTimeout on Kaggle-class CPU.                                                                                                                                                                                                                                                               | RL/IL-trained nets were competitive at the top of a fast, low-actTimeout comp — the closest _timing_ analog to Kaggriculture found.                                                                                                                                                 |
| **Lux AI S3** (2024, NeurIPS)                                                                                            | 1st **Flat Neurons**: IMPALA, ~200M-param ResNet+ConvLSTM+Transformer, ~1000+ features/tile, trained 3-4 days on 8×H100. 2nd **Frog Parade**: PPO, ~300M-param net (×2 self-play pool), ResNet, rewrote environment in **Rust** purely to speed up _training_ env-stepping (bottleneck was 10M steps/day vs rivals' 200-300M/day).                                                                                                                                                      | RL/IL categorically dominated — **best pure-heuristic finish was only 20th place** (a reversal from S2). Minimalist reward design (win-rate only) beat granular reward engineering by S3.                                                                                                                                          | **Training-time footprint only** — could not retrieve the actual writeup body (Kaggle SPA pages returned title-only via WebFetch/r.jina.ai even on retry) to confirm what ran at **submission/inference** time (quantization? distillation to a smaller net? or genuinely full-size?). **Flag as an evidence gap** — do not assume a 200-300M-param net runs at competition inference; the Rust rewrite reported is documented as a training-throughput fix, not an inference-latency fix. | RL/IL swept the podium; this is the strongest _rising_ signal that as game mechanics get richer, learned approaches pull further ahead of heuristics — but with a genuine unknown about how the winning models were shrunk (if at all) to survive per-turn actTimeout at eval time. |

### Supporting structural facts

- Kaggle sim-comp `actTimeout` values cluster at **1-3 seconds** (tictactoe/ConnectX-style default 1s; Hungry Geese 1s; Kore 2022 3s) — same order of magnitude as Kaggriculture's 1s/turn.
- All the above competitions ran inside **Kaggle's standard competition Docker image**, which already bundles numpy/pandas/PyTorch/TensorFlow/sklearn by default; competitors only vendor a private Kaggle-dataset for anything _beyond_ that. **This is the single biggest structural difference from Kaggriculture**, where package availability is explicitly unknown/possibly-stdlib-only. None of the torch-dependent precedents above (Kore winner, FLG, Halite U-Net, Lux S3 top nets, HandyRL) can be assumed transferable as-is without confirming the runner ships torch, or vendoring a working CPU wheel inside the ≤100MiB tarball — a **PyTorch CPU wheel alone typically runs 150-200MB+**, likely blowing the whole budget; a hand-rolled numpy-only (or even pure-python) forward pass of a _small_ net is the realistic fallback if only numpy is confirmed.

## Insertion-point ranking for Kaggriculture (solo engineer, ~4 weeks part-time, deadline Sep 30)

Kaggriculture's "daily planner" naming implies a two-tier decision structure (infrequent
daily/strategic portfolio choice + frequent per-turn execution). Combined with the 60s
overage **bank being poolable rather than per-turn**, this structurally favors putting the
learned component at the _infrequent_ decision point, not on every single turn.

1. **(c) Offline-distilled decision tree / lookup table — do first, lowest risk.**
   Effort: ~3-5 days part-time. Zero runtime-dependency risk (works even if the runner is
   stdlib-only — a distilled tree can be exported as plain nested if/else Python). Ceiling
   is capped (Halite's pure-ML-lite analogs topped out mid-table, ~rank 20/1140, when not
   paired with heuristics) — treat as a guaranteed floor-raiser over the hand-written
   heuristic, not a leaderboard-topping play by itself.

2. **(b) Learned value function scoring the daily planner's portfolio choices — best
   risk-adjusted bet, do second.** Effort: ~1.5-2.5 weeks part-time. Small model (MLP or
   GBT over hand-engineered portfolio/state features) — cheap enough to hand-roll a numpy
   or even pure-python forward pass, so it survives a stdlib-only runner. Only needs to
   run once per "day," not every turn, so it can freely spend from the 60s bank without
   threatening the 1s ceiling on ordinary turns — this is the one insertion point that
   structurally exploits Kaggriculture's specific budget shape. Caps the achievable
   ceiling to "as good as the surrounding heuristic/search planner it's scoring inside
   of," which is a feature (bounded downside) as much as a limit.

3. **(a) Full IL policy cloned from the Daily Top Episodes Dataset — highest ceiling,
   highest risk, stretch goal only.** Effort: 3-4+ weeks part-time realistically — likely
   exceeds solo 4-week capacity to do robustly alongside (b)/(c). Best evidence any
   learned approach has of winning a comparable comp _outright_ (Kore 2022), but Kore's
   actTimeout was 3s (3× Kaggriculture's 1s) and ran inside a full PyTorch-equipped Docker
   image, and no CPU-latency numbers were published for that winning model — so its exact
   transferability to Kaggriculture's tighter, package-uncertain runner is unverified. The
   FLG Lux S2 case is the load-bearing counter-example: a serious, well-resourced,
   CPU-latency-engineered RL/IL effort still needed multi-step action-queue prediction and
   still lost outright to a pure heuristic under a comparable single-core CPU budget. Since
   IL must typically emit an action every turn (unlike (b)'s once-per-day cadence), it
   can't lean on the pooled 60s bank the way (b) can — it's stuck inside the strict 1s
   ceiling on essentially every turn.

## Go/no-go signals

**GO:**

- Week-1 package probe on the actual runner confirms numpy (or better) is present.
- A hand-rolled numpy forward pass of a small net (2-3 layers, <50k params) benchmarks
  comfortably under budget when CPU-throttled locally to ~1 core / Kaggriculture-equivalent
  clock (target well under 1s to leave margin, since 1.6 vCPU is not a full 2 cores).
- The Daily Top Episodes Dataset has enough volume/quality to be useful — Halite's gold
  precedent used ~3,000 curated top matches (out of 100k+ scraped); Kore's winner used
  ~200M timestep-tuples. Anything in the low hundreds of full 720-turn games is plausibly
  workable for (b)/(c); it's thin for a full IL policy (a).
- A trained value function or distilled tree beats the pure-heuristic baseline in
  self-scrimmage on held-out data before further investment.

**NO-GO / kill signals:**

- Package probe shows stdlib-only, no numpy — kills (a) outright and forces (b)/(c) down
  to fully hand-rolled pure-Python arithmetic (still workable for small linear/tree models,
  not for anything CNN/Transformer-shaped).
- Neither a vendored torch/onnxruntime wheel nor numpy fits/works within the 100MiB budget
  — same effective kill as above.
- CPU-throttled local benchmark of even a _minimal_ net exceeds ~500ms/turn — echoes FLG's
  real experience being forced to amortize NN calls across multi-turn action queues just to
  survive a comparable single-core CPU budget; if even a tiny net can't clear this bar,
  drop straight to (c) only.
- Episode dataset turns out sparse (well under ~100 full games) — kills IL cloning (a) for
  lack of data; (b)/(c) remain viable since they can be trained off self-generated
  self-play/search data instead of external replays.
- Two-week checkpoint: if (b) isn't showing a measurable win-rate lift over the heuristic
  baseline in scrimmage by the midpoint, cut losses and ship (c) as the sole learned
  component rather than spending the back half of the 4 weeks chasing (a).

## Bottom line

Layer, don't pick one. Ship (c) first as an unconditional, dependency-safe floor-raiser
(~1 week). Put the main remaining budget into (b) — it's the best risk-adjusted bet because
it matches Kaggriculture's actual budget shape (infrequent, bank-subsidized calls) rather
than fighting it, and degrades gracefully to hand-rolled arithmetic if the runner turns out
to be stdlib-only. Treat (a) — full IL policy cloning, the only approach in the evidence
base with a _clean outright win_ (Kore 2022) — as an opportunistic stretch goal pursued
only after week-1 probes confirm the compute/package budget can support it, never as the
base plan: Kaggriculture's per-turn budget (1s, 1.6 vCPU, unknown packages) is at least as
tight as what sank a well-engineered CPU-latency-optimized RL effort to 4th place behind a
pure heuristic in Lux AI Season 2.
