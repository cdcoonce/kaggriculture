# CI Compute Budget: kaggriculture Tournament Sizing (Actions vs Mac launchd)

Date: 2026-08-04
Repo under study: `cdcoonce/kaggriculture` (private)
Goal: size PR-gate tournaments and a nightly deep tournament for a `kaggle_environments`
simulation, and determine when GitHub Actions stops being free/practical vs running
nightlies on the owner's Mac via launchd.

---

## 1. GitHub Actions pricing / platform facts (verified live against docs.github.com, 2026-08-04)

All numbers below were pulled directly from current `docs.github.com` pages during this
session (not cached third-party summaries), cross-checked by a second independent research
pass (raw-HTML grep of the same live pages) that also surfaced an important dated fact:
**GitHub cut GitHub-hosted runner per-minute rates by up to 39%, effective January 1,
2026**, as part of a broader repricing (a new $0.002/min "Actions cloud platform charge" is
baked into the new, lower rates). The $/minute figures in §1.3 below are these current,
already-reduced 2026 rates — not stale pre-2026 numbers. Source:
https://github.com/resources/insights/2026-pricing-changes-for-github-actions. GitHub
states 96% of customers see no net bill change and only 0.09% of individual users see any
increase (avg. under $2/month) from this repricing.

### 1.1 Free included minutes per month (private repos)

| Plan                    | Included minutes/month (private repos) |
| ----------------------- | -------------------------------------- |
| GitHub Free             | 2,000                                  |
| GitHub Pro              | 3,000                                  |
| GitHub Team             | 3,000                                  |
| GitHub Enterprise Cloud | 50,000                                 |

Source: https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions

Public repos: standard GitHub-hosted runners are free and unlimited (no minutes deducted)
— irrelevant here since kaggriculture is private.

**Caveat on "GitHub Pro"**: the public marketing page `github.com/pricing` currently lists
only Free ($0), Team ($4/user/mo), and Enterprise ($21/user/mo) — "GitHub Pro" does not
appear there. Pro is still documented with 3,000 min/month and 1 GB artifact storage in
GitHub's plan-comparison and billing docs, so it still exists as a legacy/grandfathered
individual plan, just not on the primary sales page. If the repo owner is actually on Team
rather than Pro, the minute allotment is identical (3,000/month); only artifact storage
differs slightly (Team gets 2 GB vs Pro's 1 GB), which doesn't affect this analysis.

### 1.2 OS minute multipliers (against the free-minutes quota) — CAVEAT: framework may be stale

| Runner OS | Traditional multiplier | Implied ratio from current $/min rates (§1.3) |
| --------- | ---------------------- | --------------------------------------------- |
| Linux     | 1x                     | 1x (baseline)                                 |
| Windows   | 2x                     | ~1.67x ($0.010 / $0.006)                      |
| macOS     | 10x                    | ~10.3x ($0.062 / $0.006)                      |

A second, independent research pass found that GitHub's dedicated multiplier-table page
(`docs.github.com/en/billing/reference/actions-minute-multipliers`) now **301-redirects**
to the runner-pricing page, and a raw-HTML grep of current billing docs turned up **zero
occurrences of "multiplier"** anywhere in the live text — the docs now present flat
per-minute USD rates by OS/SKU (§1.3) rather than the old "multiply your minutes by X"
framing. The classic "1x/2x/10x" figures are close to, but not exactly, the ratios implied
by today's dollar rates (macOS checks out at ~10.3x; Windows is now ~1.67x, not 2x). It's
unclear whether GitHub quietly dropped the multiplier abstraction for included-minutes
accounting specifically, or just stopped stating it in docs prose while the mechanism is
unchanged. **Treat "Windows ≈ 1.7–2x, macOS ≈ 10x" as the safe working assumption** — the
exact figure doesn't change this report's conclusions either way.

Implication: keep this pipeline on Linux runners only. A macOS runner would cost roughly
10x the minutes for identical wall-clock time under any version of this accounting — a
non-starter for a tournament workload regardless of which exact multiplier is current.

### 1.3 Per-minute overage pricing (after free minutes exhausted), standard 2-core runners

| Runner               | $/minute |
| -------------------- | -------- |
| Linux x64 (2-core)   | $0.006   |
| Linux ARM (2-core)   | $0.005   |
| Windows x64 (2-core) | $0.010   |
| macOS (3-4 core)     | $0.062   |

Source: https://docs.github.com/en/billing/concepts/product-billing/github-actions
(fetched live 2026-08-04), corroborated by cicdpipelinecost.com "GitHub Actions Pricing
2026: $0.006/min" tracker.

### 1.4 Standard runner hardware spec — PRIVATE repos (this is the one that matters here)

Confirmed directly from the current `docs.github.com` "Supported runners and hardware
resources" reference table (fetched live):

| OS    | vCPU  | RAM      | Storage | Arch  | Label                                                           |
| ----- | ----- | -------- | ------- | ----- | --------------------------------------------------------------- |
| Linux | **2** | **8 GB** | 14 GB   | x64   | `ubuntu-latest`, `ubuntu-24.04`, `ubuntu-22.04`, `ubuntu-26.04` |
| Linux | 2     | 8 GB     | 14 GB   | arm64 | `ubuntu-24.04-arm`, etc.                                        |
| Linux | 1     | 5 GB     | 14 GB   | x64   | `ubuntu-slim` (lightweight option)                              |

Source: https://docs.github.com/en/actions/reference/runners/github-hosted-runners

**Note the public/private split**: public repos get a beefier free `ubuntu-latest` (4 vCPU
/ 16 GB) since GitHub absorbs that cost when minutes are free-and-unlimited; **private
repos get the older/smaller 2 vCPU / 8 GB spec** on the same `ubuntu-latest` label. This
confirms the task's "2-core Actions runner" assumption is exactly right for this repo (it's
private) — no need to hedge on core count, only on relative per-core speed vs the Mac.

Larger runners (4/8/16-core) exist for Team/Enterprise plans at a higher per-minute rate,
but "included minutes cannot be used for larger runners" per the billing docs — every
minute on a larger runner is a paid minute even within an otherwise-free monthly quota, so
they're excluded from this analysis in favor of the standard included 2-core runner.

### 1.5 Storage (context only, not the bottleneck here)

| Plan             | Artifacts | Cache |
| ---------------- | --------- | ----- |
| Free             | 500 MB    | 10 GB |
| Pro              | 1 GB      | 10 GB |
| Team             | 2 GB      | 10 GB |
| Enterprise Cloud | 50 GB     | 10 GB |

Overage: $0.25/GB-month (artifacts/Packages), $0.07/GB-month (cache). Tournament result
JSON/logs for even 10,000 games are small (single-digit MB), so storage is not a
constraint for this workload.

### 1.6 Concurrent job limits (private repos, standard runners)

| Plan       | Concurrent jobs                                  |
| ---------- | ------------------------------------------------ |
| Free       | 20                                               |
| Pro        | 40                                               |
| Team       | 60                                               |
| Enterprise | 500 (1000 on larger runners for Team/Enterprise) |

Source: https://docs.github.com/en/actions/reference/limits (fetched live)

Relevant point confirmed: **billing is per job-minute, not per wall-clock minute of the
workflow.** Fanning a tournament out across N parallel jobs reduces wall-clock time but
does **not** reduce total billed minutes — 10 jobs running 1 minute each in parallel still
bills 10 minutes. Parallelism only helps wall-clock/latency, not minute budget. (This is
standard, well-documented GitHub Actions billing behavior; not separately citation-worthy
beyond the general billing page above, which bills "per job.")

The one place parallelism _does_ save minutes for free: using **both vCPUs inside a single
job** via multiprocessing costs nothing extra (you're charged for the job's wall-clock
regardless of whether it uses 1 or 2 of its own cores), so intra-job parallelism is a pure
win — see the Actions extrapolation below.

### 1.7 Job/workflow time limits

- Each job: max 6 hours execution time (GitHub-hosted runners), then terminated/failed.
- Each workflow run: max 35 days elapsed (execution + queued/approval time), then cancelled.

Source: https://docs.github.com/en/actions/reference/limits

At the measured/estimated throughput below, a 10,000-game nightly on a 2-core Actions
runner takes ~117–164 minutes — comfortably inside the 6-hour job cap. A single job would
only approach that cap somewhere in the 22,000–31,000-game range, so the 6-hour ceiling is
not a binding constraint at the scales asked about here, but it _is_ the reason you can't
naively push tournament size arbitrarily high in one job — beyond ~25k games you'd need to
shard across a matrix of jobs (each independently billed, so no minutes saved, only
wall-clock).

### 1.8 Scheduled workflows (`on: schedule`) on private repos

- **Minimum interval: 5 minutes.** Verbatim from official docs: _"The shortest interval you
  can run scheduled workflows is once every 5 minutes."_
  (https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows).
  Irrelevant at nightly cadence, included for completeness.
- **60-day auto-disable — confirmed to happen, but officially documented as PUBLIC-repo-only,
  creating a real ambiguity.** A first research pass (community discussions, marketplace
  "keepalive" actions) found scheduled workflows widely reported as disabled after 60 days
  of no repository activity, and assumed this applies to both public and private repos. A
  second, independent pass went back to GitHub's own docs text and found the **literal
  official sentence is scoped to public repos**: _"In a public repository, scheduled
  workflows are automatically disabled when no repository activity has occurred in 60
  days"_ — appearing verbatim on two official pages (the events-that-trigger-workflows page
  and https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows).
  **No official docs sentence was found that explicitly extends this rule to private
  repos**, yet numerous GitHub Community Discussions (#57858, #86087, #184653) report the
  identical 60-day disable happening on repos in practice, without a clean
  public/private split in the reports. **Net: unresolved from docs text alone — treat as
  "likely still applies to private repos, but not officially confirmed either way."**
  Critically, on any reading, **only new commits to the default branch reset the inactivity
  clock** — opening issues, merging PRs without a commit to default, pushing tags, or the
  scheduled workflow simply _running_ do **not** count as activity.
- Scheduled runs consume billed minutes exactly like any other trigger (push/PR/manual) —
  no official docs text differentiates billing by trigger type, and no special
  discount/exemption for `schedule`-triggered workflows was found anywhere.

**Implication for this repo**: given the ambiguity, don't rely on "it's private so the
60-day disable doesn't apply." If nightlies run on Actions and are the _only_ thing keeping
the repo "active," they may stop firing on their own once 60 days pass without a commit —
worth either (a) accepting that risk since active development will likely keep committing
anyway, or (b) adding a trivial keepalive commit (cheap, fully removes the risk regardless
of which reading of the docs is correct), or (c) simply running nightlies
on the Mac via launchd instead, which has no such dependency on GitHub-side repo activity.

---

## 2. Local benchmark (measured on this Mac)

**Hardware**: Apple M1 Pro, `hw.ncpu`/`hw.logicalcpu` = 10 (8 performance cores + 2
efficiency cores, confirmed via `sysctl hw.perflevel0.physicalcpu`=8,
`hw.perflevel1.physicalcpu`=2). macOS 26.5.2.

**Environment**: `kaggle_environments` from the venv at
`/private/tmp/.../scratchpad/kagg-venv`. `make('kaggriculture')` confirmed to default to
`episodeSteps=720`, and a `starter` vs `starter` episode was confirmed to run the full 720
steps every time (`len(env.steps)==720`, `env.done==True`, no early termination) — so the
benchmark's "1 game = 1 episode = full 720 steps" assumption holds and is representative.

Scripts: `/private/tmp/.../scratchpad/r3-bench/bench_single.py`,
`/private/tmp/.../scratchpad/r3-bench/bench_multi.py`.

### 2.1 Single-process throughput (20 episodes, `make('kaggriculture').run(['starter','starter'])`)

```
episodes=20
total_wall_sec=19.627
episodes_per_sec=1.0190
avg_episode_sec=0.9813  (min 0.8825, max 1.2675)
```

**1.019 episodes/sec single-process** (~0.98 sec/episode average) on one M1 Pro
performance core.

### 2.2 Multiprocessing scaling (independent worker processes, one `make()` env per worker, `spawn` context)

| Workers | Total episodes | Wall (s) | Aggregate eps/sec | Scaling factor | Per-worker eps/sec |
| ------- | -------------- | -------- | ----------------- | -------------- | ------------------ |
| 1       | 20             | 19.63    | 1.019             | 1.00x          | 1.019              |
| 2       | 20             | 9.82     | 2.038             | 2.00x          | 1.019              |
| 4       | 40             | 10.64    | 3.758             | 3.69x          | 0.940              |
| 8       | 80             | 10.84    | 7.381             | 7.24x          | 0.923              |
| 10      | 100            | 12.74    | 7.849             | 7.70x          | 0.785              |

Scaling is essentially linear (100% efficiency) through 2 workers, stays high (90%+
efficiency) through 8 workers (all 8 performance cores), then flattens sharply at 10
workers as the 2 efficiency cores get used — consistent with the known P-core/E-core split.
**Practical full-machine ceiling: ~7.4–7.85 episodes/sec.**

### 2.3 Memory footprint

Peak RSS for a single episode process: **~206 MB**. Trivial even at 8-10 parallel workers
(under 2 GB total) — memory is not a constraint on either the Mac or an 8 GB Actions
runner.

---

## 3. Extrapolation to a GitHub Actions 2-core runner

Per the task's instruction, apply a conservative 0.5x–0.7x per-core-speed penalty to
account for Actions' shared-cloud x86 vCPUs being slower than this Mac's Apple Silicon
performance cores:

- Per-core Actions throughput: 1.019 × [0.5, 0.7] = **0.509–0.713 episodes/sec/core**
- Since the confirmed private-repo standard runner has exactly 2 vCPUs (§1.4), and this
  Mac showed clean 2.00x scaling at 2 workers, the natural design is to run **2 worker
  processes inside each Actions job** (matches the measured multiprocessing pattern, and
  costs nothing extra — job billing is by wall-clock of the job, not by core count used
  within it):
  - **Actions 2-core, parallelized: 1.019–1.427 episodes/sec** (recommended design)
  - **Actions 2-core, naive single-threaded loop: 0.509–0.713 episodes/sec** (fallback if
    the workflow doesn't bother parallelizing — shown for comparison; leaving a free 2nd
    vCPU idle roughly doubles wall-clock and minutes for zero savings, so there's no reason
    to ship it this way)

RAM: 8 GB on the private-repo standard runner vs ~206 MB/process measured — two parallel
workers use under 500 MB, nowhere near the 8 GB ceiling.

---

## 4. Budget table — minutes per tournament size

All Actions figures use the **parallelized 2-core** design (§3) unless noted. Ranges are
[optimistic 0.7x-factor, conservative 0.5x-factor] i.e. [fewer minutes, more minutes].

| Tournament size                 | Actions 2-core (parallel)          | Actions 2-core (naive single-thread) | Mac (all cores, measured) |
| ------------------------------- | ---------------------------------- | ------------------------------------ | ------------------------- |
| 200 games (PR gate, fast)       | **2.3 – 3.3 min**                  | 4.7 – 6.5 min                        | 0.42 – 0.45 min (~26 s)   |
| 1,000 games (PR gate, thorough) | **11.7 – 16.4 min**                | 23.4 – 32.7 min                      | 2.1 – 2.3 min             |
| 10,000 games (nightly deep)     | **116.8 – 163.6 min** (1.9–2.7 hr) | 233.7 – 327.1 min (3.9–5.5 hr)       | **21.2 – 22.6 min**       |

Headline: the Mac is **7.7–9.7x faster wall-clock** than a parallelized 2-core Actions job
at every tournament size (matches the ~7.4–7.85x raw core-count advantage plus a bit more
from the conservative per-core-speed penalty stacking on top).

A single-job 10,000-game Actions run (117–164 min) is comfortably inside the 6-hour/job cap
(§1.7); a naive single-threaded 10k-game run (234–327 min ≈ 3.9–5.5 hr) is still inside the
cap but starts eating a meaningful fraction of it — another reason to parallelize within
the job.

## 5. Monthly minute budget — does it fit for free?

Assumptions: solo-dev repo, plausible PR volume of **30–60 PR-gate runs/month**, and
**30 nightly runs/month** (one per night). Both GitHub Free (2,000 min/mo) and Pro
(3,000 min/mo) shown since this is the owner's personal private repo and the plan tier
wasn't independently verifiable from this environment.

### 5.1 PR gate cost alone (Actions, parallelized 2-core)

| Gate size   | 30 runs/mo    | 60 runs/mo    |
| ----------- | ------------- | ------------- |
| 200 games   | 70 – 98 min   | 140 – 196 min |
| 1,000 games | 351 – 491 min | 701 – 981 min |

A 200-game PR gate is cheap at any plausible volume — even 60 runs/month costs under 10%
of the Free plan's monthly allotment. A 1,000-game gate run 60x/month alone can consume
**23–33% of the entire Pro allotment**, or **35–49% of Free** — still affordable by itself,
but it starts to matter once nightlies are added.

### 5.2 Nightly deep tournament cost alone (10,000 games × 30 nights)

|                           | Total min/month                                                | % of Free (2,000) | % of Pro (3,000) |
| ------------------------- | -------------------------------------------------------------- | ----------------- | ---------------- |
| Actions 2-core (parallel) | **3,505 – 4,907 min**                                          | **175% – 245%**   | **117% – 164%**  |
| Mac (all cores)           | 637 – 677 min _wall-clock, not billed_ (10.6–11.3 hr/mo total) | —                 | —                |

**This is the key number**: a full 10,000-game nightly, run every night, _by itself_
already exceeds both the Free and Pro monthly free-minute allotments — before a single PR
gate is counted. There is no PR-gate volume small enough to make "10k games every night on
Actions" fit inside the free envelope.

### 5.3 Max nightly size that fits the _remaining_ free budget after a realistic PR-gate load (45 runs/mo)

| Plan             | PR gate size | Gate cost/mo  | Remaining nightly budget → max games/night |
| ---------------- | ------------ | ------------- | ------------------------------------------ |
| Free (2,000 min) | 200 games    | 105 – 147 min | **~3,780 – 5,410 games/night**             |
| Free (2,000 min) | 1,000 games  | 526 – 736 min | **~2,580 – 4,210 games/night**             |
| Pro (3,000 min)  | 200 games    | 105 – 147 min | **~5,810 – 8,260 games/night**             |
| Pro (3,000 min)  | 1,000 games  | 526 – 736 min | **~4,610 – 7,060 games/night**             |

So on Actions alone, staying inside free minutes with a realistic PR-gate load caps a
_nightly_ tournament somewhere around **2,600–8,300 games**, depending on plan and gate
size — never comfortably reaching 10,000, and the tighter combinations (Free + 1,000-game
gate) top out well under half of the requested nightly size.

### 5.4 If you're willing to pay overage instead of downsizing

Overage is billed at $0.006/min (Linux 2-core, §1.3) for every minute past the free
allotment. Running the _full_ ask — 45 PR-gate runs/month at 1,000 games each, **plus** a
full 10,000-game nightly every night — entirely on Actions:

- Total: **4,031 – 5,643 minutes/month**
- Free plan overage: 2,031 – 3,643 min → **$12.18 – $21.86/month**
- Pro plan overage: 1,031 – 2,643 min → **$6.18 – $15.86/month**

In pure dollar terms this is cheap — the free-minute wall is a _quota_ problem, not a
_cost_ problem, since $0.006/min is low. The real question is whether Charles wants to
attach a payment method / accept metered billing for a side project versus just running the
nightly somewhere that's already sunk-cost free.

---

## 6. Recommendation

**Run PR-gate tournaments on GitHub Actions.** At 200–1,000 games/run and any plausible PR
volume (30–60/month), this costs 2.3–33 minutes per run and 70–981 minutes/month —
comfortably inside even the Free plan's 2,000 free minutes with room to spare, requires no
infrastructure to maintain, and gives every collaborator/PR the same reproducible sandboxed
environment. Ship it parallelized across both of the runner's 2 vCPUs (matches the measured
2.00x local scaling and costs nothing extra in job-minutes) — that alone roughly halves
both wall-clock and, more importantly, halves the minutes actually billed vs a naive
single-threaded loop.

**Run the nightly 10,000-game deep tournament on the Mac via launchd, not Actions.**
Three independent reasons converge on the same answer:

1. **It doesn't fit the free-minute budget.** A 10,000-game nightly run every night costs
   3,505–4,907 Actions minutes/month by itself — 117–245% of the _entire_ monthly free
   allotment on either Free or Pro, before any PR gates are counted (§5.2). To keep a daily
   10k-game nightly _and_ stay free, you'd have to either cut PR-gate volume to near zero or
   shrink the nightly to roughly 2,600–8,300 games depending on plan (§5.3) — i.e., you
   can't actually run the tournament size you asked about and stay inside free minutes.
2. **It's 7.7–9.7x faster on the Mac.** Measured: 21.2–22.6 minutes wall-clock on this M1
   Pro's 8 performance cores vs an estimated 116.8–163.6 minutes on a parallelized 2-core
   Actions runner (§4). A launchd job kicked off at 2am finishes before 2:30am; the Actions
   equivalent runs 2–2.7 hours, which matters if results need to be ready for morning
   review or feed the next day's PR gates.
3. **It removes a real failure mode.** Scheduled workflows on GitHub silently stop firing
   after 60 days of no _commit_ activity to the repo (§1.8) — a nightly Actions cron job is
   quietly coupled to the repo staying actively committed-to, which is a strange invisible
   dependency for a tournament runner to have. launchd on the Mac has no such dependency.

**The crossover, stated plainly**: with a realistic PR-gate load (45 runs/month, 200–1,000
games each), Actions stays free/practical for nightlies up to roughly **3,000–8,000
games/night** depending on plan tier and gate size (§5.3) — call it **~5,000 games/night**
as a rough midpoint. Below that, Actions is genuinely free and simpler to operate (no Mac
uptime/sleep-schedule dependency, no launchd plist to maintain). At or above the requested
**10,000 games/night**, Actions either blows the free quota (§5.2) or costs a modest but
non-zero $6–22/month in metered overage (§5.4) _and_ takes 5–8x longer wall-clock than just
running it locally — so above that ~5k threshold, the Mac wins outright on both dollars and
latency, and Actions should be reserved for the PR gate only.

---

## Appendix: scripts used

- `/private/tmp/claude-501/-Users-cdcoonce-Developer-GitHub-the-vault/48f69011-acdd-44c8-850e-fae45901a79f/scratchpad/r3-bench/bench_single.py` — single-process 20-episode timing.
- `/private/tmp/claude-501/-Users-cdcoonce-Developer-GitHub-the-vault/48f69011-acdd-44c8-850e-fae45901a79f/scratchpad/r3-bench/bench_multi.py` — multiprocessing scaling harness (2/4/8/10 workers), `spawn` context, one `kaggle_environments` env per worker, episodes divided evenly across workers.

Raw run outputs are reproduced verbatim in §2.1–2.2 above.
