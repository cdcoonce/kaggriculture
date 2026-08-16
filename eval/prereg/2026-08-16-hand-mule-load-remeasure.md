# Pre-registration — `hand_mule_load` 9 → 20, re-measured on the post-melon-fix champion

Written **before** the run, at commit `2b762f4`+ (melon fix `bdadb15` in HEAD).

## Why the existing evidence cannot answer the question

Four ledgered runs exist for this arm. They are insufficient **and** stale.

**Insufficient.** Under the intersection-union rule, barnyard-719 at n=64 (band
603000) returns `ci_lower` -1,781 against a $0 bar, which ends promotion
regardless of thunder. metac95-720 and mirror-719 were never run for this arm at
all. Pooling the two thunder confirms (bands 592000 + 603000, n=128) gives mean
+2,669, `ci_lower` **+662** — short of the $1,000 primary bar.

That is a **power** failure, not a measured absence: barnyard's mean is *positive*
(+1,513), and at that mean and sd it needs n ~ 674 for 80% power at the $0 bar.
Failing to detect is not detecting an absence.

**Stale.** `git` reports that `dca001c` and `ad97540`, the commits those runs were
measured at, are **not ancestors of HEAD** and no branch contains them. They also
predate `bdadb15`, which changed what units do all game: 27.1% of HARVEST fires
were dead, with units parked re-issuing them, and now none are. `hand_mule_load`
governs shed round-trip cadence, so its value is a function of exactly the labour
pattern that just changed. The old numbers describe an agent that no longer
exists.

## Design (locked before launch)

Config-only A/B, so no frozen incumbent is required: candidate `champion` with
`{"hand_mule_load": 20}` against baseline `champion` at defaults, both at HEAD,
one code version differing by one `PolicyConfig` argument.

Band **650000**, disjoint from every band burned to date (through 640023).

**Barnyard runs first and alone**, because it is the tape that ends promotion and
the tape least correlated with the others (per-seed delta r = +0.19 against
thunder, versus thunder~mirror r = +0.96 — the four tapes are closer to 2.5
independent measurements than four).

| order | tape | threshold | n | condition |
|---|---|---|---|---|
| 1 | barnyard-719 | > $0 | 512 | always |
| 2 | thunder-719 | > $1,000 | 512 | only if barnyard `ci_lower` > 0 |
| 3 | metac95-720 | > $0 | 256 | only if 1 and 2 pass |
| 4 | mirror-719 | > $0 | 256 | only if 1 and 2 pass |

n=512 gives se ~ 620 at the sd this arm has shown historically (13-16k), or
se ~ 350 if its dispersion drops to the 7-8k the melon arm showed. At the
historical sd and the historical barnyard mean (+1,513) that yields `ci_lower`
~ +490: a pass, but a thin one. **This is stated in advance so that a near-miss
is read as the predicted outcome of a small effect, not as bad luck deserving
another band.**

**No tape gets additional seeds after its result is seen.** If barnyard fails,
the answer is "not promotable at n=512 on the current champion, interval
attached" — and specifically **not** "labor does not convert to money", the
inference `ad97540` made and `cf71c5e` retracted.

## Decision rule

Unchanged from `eval/README.md`: `ci_lower > 1000` on thunder and `> 0` on every
other tape, `vetoes == []` everywhere, and `skew_delta` read on each — any tape
that only just clears while `skew_delta < -1.0` is reported inconclusive.

## Standing hazard, learned the hard way this session

The gate resolves `champion` from the **live working tree** and builds a fresh
worker pool per arm, so editing `packages/agent/**` mid-run can hand the two arms
different code. A confirm launched at 21:25:28Z was discarded for this. No agent
source is edited while these runs are in flight.
