# eval/ — committed gate-run ledger

Data only, no code. Every gate run appends (eval protocol, issue #4):
identity + verdict (candidate commit + config hash, opponents, gate type,
W/L/T, observed rate, CI bounds, PASS/FAIL, timestamp), the seed manifest,
and per-game rows. Replay JSONs are retained selectively, on demand, for
named matchups only. Schema/naming: Versioning ticket (#9).

A gate run without a ledger entry didn't happen.

## Schema

Every entry under `eval/gates/` is written by `harness.ledger` and stamped
`schema_version: 1`. The version is a documentation stamp, not a dispatch
key — no reader in the repo branches on it. **Bump it only when an existing
key changes meaning or disappears**; purely additive keys (as
`identity.agent_config` was, and as the money block is) do not bump it.

Filename: `{timestamp}-{candidate}-vs-{opponent}-{gate_type}.json`, with `:`
replaced by `_` in the specs.

### Win-rate gate (`write_ledger`, every `gate_type` but `money`)

| block | field | meaning |
|---|---|---|
| `identity` | `candidate`, `candidate_commit`, `opponent`, `gate_type` | what was played, at which commit |
| | `extra_config` | engine configuration overrides, or `null` |
| | `agent_config` | champion `PolicyConfig` overrides, or `null`/absent on pre-`6c47d71` entries |
| `verdict` | `n_games` | `2 * n_seeds` — both seats of every seed |
| | `wins`, `losses`, `ties`, `score`, `rate` | ties score 0.5 |
| | `ci_lower`, `threshold`, `passed` | Wilson lower bound, `passed = ci_lower > threshold` |
| | `any_candidate_crash` | OR across all rows |
| `seed_manifest` | `seed_base`, `n_seeds`, `seeds` | `range(seed_base, seed_base + n_seeds)` |
| `rows` | `seed`, `candidate_seat`, `candidate_money`, `opponent_money`, `outcome`, `candidate_crashed`, `opponent_crashed` | one entry per GAME |

### Money gate (`write_money_ledger`, `gate_type: "money"`)

A superset of the above. `verdict` is still the CANDIDATE arm's **win-rate**
verdict, unchanged in shape and meaning, so the corpus stays homogeneous and
`find_passing_promotion` keeps working. The money PASS/FAIL is
`money_verdict.passed` and nothing else — `gate_type: "money"` never
satisfies the Kaggle submission precondition.

| block | field | meaning |
|---|---|---|
| `identity` | `baseline`, `baseline_agent_config` | the second arm, replayed in the same call over the same seeds |
| | `opponent_digest` | `sha256:<hex>` of the machine-local tape file, or `null` |
| `money_verdict` | `n_seeds`, `alpha`, `threshold` | one observation is one SEED, both seats averaged |
| | `candidate_mean`, `baseline_mean`, `mean_delta`, `median_delta` | seat-averaged money, per seed |
| | `sd_delta`, `stderr`, `skew_delta`, `min_delta`, `df` | dispersion of the paired difference |
| | `t_crit`, `ci_lower_mean` | one-sided 95% Student-t lower bound on the mean |
| | `hl_shift`, `hl_skip`, `hl_exact_alpha`, `ci_lower_hl` | Hodges-Lehmann pseudomedian and its exact distribution-free bound |
| | `ci_lower` | `min(ci_lower_mean, ci_lower_hl)` — the binding leg |
| | `mde_80` | effect this run could have resolved at 80% power; a FAIL means "no effect above this", never "no progress" |
| | `vetoes`, `passed` | `passed = ci_lower > threshold AND vetoes == []` |
| | `opponent_mean_delta`, `min_opponent_money` | market-suppression and dead-opponent diagnostics |
| | `candidate_canary_ran`/`_crashed`, `baseline_canary_ran`/`_crashed` | unshelled crash canary |
| | `min_seeds`, `catastrophic_k`, `candidate_money_floor`, `opponent_money_floor` | veto knobs, recorded so `rerun-ledger` reproduces the same vetoes |
| `per_seed` | `seed`, `candidate_money`, `baseline_money`, `delta` | the paired observations the statistic is computed from |
| `baseline_rows` | same seven keys as `rows` | the baseline arm's per-GAME rows |

## Promotion policy (documented, not enforced in code)

- Screen at `--n-seeds 20` on one seed band; confirm at `--n-seeds 64` on a
  **disjoint** band. Two independent passes drop a truly-zero change's
  false-pass rate to ~5e-5.
- `seed_base` advances monotonically and is never reused across decisions.
  The `seed_manifest` block is the audit trail.
- Multi-tape intersection–union: require `ci_lower > $1,000` on the
  designated primary tape **and** `ci_lower > $0` on every other available
  tape, with `vetoes == []` on all of them. Requiring every component keeps
  familywise error at or below α with no Bonferroni correction, and is the
  direct defense against a "gain" that is really market suppression against
  one frozen script.
- The gate is machine-local by construction: tapes are never committed, and
  `identity.opponent_digest` is what makes a money result citable at all.

## Replays

Replay JSONs live under `eval/replays/`, gitignored by default — every gate
run may produce one, but they are not committed as a matter of course. When
a replay is worth retaining (a named matchup worth re-watching, a bug
repro), the committed `eval/gates/` ledger entry points to it by path and
hash rather than the replay itself being committed.

## Citation law

Any claim about a past matchup or result must cite a committed ledger path
under `eval/gates/`, or it is unciteable. A gate run without a ledger entry
didn't happen, so a result with no ledger entry to point to cannot be
asserted as fact — only reproduced fresh and ledgered.
