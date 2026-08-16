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
| | `n_regressed` | seeds strictly WORSE than baseline. **Recorded diagnostic — it does not gate** |
| | `t_crit`, `ci_lower_mean`, `ci_lower` | one-sided 95% Student-t lower bound on the mean. `ci_lower` IS this bound — it is the whole criterion |
| | `hl_shift`, `hl_skip`, `hl_exact_alpha`, `ci_lower_hl` | Hodges-Lehmann pseudomedian and its exact distribution-free bound. **Recorded diagnostic — it does not gate** |
| | `tail_quantile` | the `catastrophic_tail_quantile`-th LINEAR-INTERPOLATED quantile of the per-seed differences; drives `catastrophic_tail`. Not exactly "the worst-off `catastrophic_tail_quantile` fraction of seeds" — interpolation puts the true fraction slightly under the nominal quantile at small `n` (13.1% of seeds at `n=8`, rising to 14.8% at `n=64` for the default 0.15) |
| | `mde_80` | how far ABOVE `threshold` a per-seed effect must be for this run to clear the bound ~80% of the time, at the `sd_delta` observed. Not a bound, and silent about the lower tail — an improvement of any size can still PASS with `blockers` non-empty |
| | `vetoes` | the RUN is invalid (exit 2): `too_few_seeds`, `degenerate_dispersion`, `candidate_crash`, `baseline_crash`, `opponent_crash`, `candidate_degenerate`, `baseline_degenerate`, `opponent_degenerate`, `canary_crash` |
| | `blockers` | **Recorded diagnostic — it does not gate.** `catastrophic_tail` (the `catastrophic_tail_quantile` quantile of the per-seed differences sits below `-catastrophic_tail_floor`) is computed and printed as a WARNING by the CLI, on every exit code, but never changes PASS/FAIL/INVALID. Three successive attempts to gate on a loss-tail guard were each shown to refuse arbitrarily large TRUE gains; see `harness.stats.MoneyVerdict` |
| | `passed` | `ci_lower > threshold AND vetoes == []`. `blockers` is NOT part of this — see the limitation below |
| | `opponent_mean_delta`, `min_opponent_money` | market-suppression and dead-opponent diagnostics |
| | `candidate_canary_ran`/`_crashed`, `baseline_canary_ran`/`_crashed` | unshelled crash canary |
| | `min_seeds`, `catastrophic_tail_quantile`, `catastrophic_tail_floor`, `candidate_money_floor`, `opponent_money_floor`, `degenerate_seed_fraction` | veto and diagnostic knobs, recorded so `rerun-ledger` reproduces the same verdict |
| | `per_seed` (top-level, not inside `money_verdict`) | `seed`, `candidate_money`, `baseline_money`, `delta` — the paired observations the statistic is computed from |
| | `baseline_rows` (top-level) | same seven keys as `rows` — the baseline arm's per-GAME rows |

Bounds that are not finite (`ci_lower*`, `mde_80` under `too_few_seeds`) are
written as JSON `null`, never as the non-standard `-Infinity` literal.

## Reading a money verdict: the EXPECTED-money limitation

`money_verdict.passed` promotes on the MEAN paired difference and nothing
else. A candidate that is worse on most seeds still PASSES if a minority of
seeds pays for the majority's gain — `blockers` names that shape, it does not
stop it.

This is deliberate, not an oversight, while the agent is far behind the
frontier: the measured champion banks ~$37k per seed against a ~$123k
opponent, so ANY mean-money gain moves it toward the ~$70k threshold where
games start being winnable at all, and refusing a real gain for being
unevenly distributed would cost progress the agent cannot yet afford. The
proxy stops being valid near parity, where "worse for most seeds" is exactly
the failure a promotion gate exists to catch. An operator is expected to read
`n_regressed` and `tail_quantile` (and `blockers` itself) before promoting a
PASS — not to treat `passed` alone as the promotion decision.

**Known Type-I leak, stated rather than hidden**: the t bound's one-sided
level is not 0.05 on a strongly left-skewed per-seed difference. Measured
with the true mean pinned at the threshold and the worst real paired sd
($9,495), the realized level is 0.0494 on a normal null and 0.0492 on a
Laplace null — but 0.0753 at skew -1.75 and 0.1196 at skew -6.2. This is
accepted, not fixed: the real arms measured so far sit at skew +0.117 and
-0.054, so the leak lives at shapes nothing here has produced yet. Read
`skew_delta` on any run whose bound only just clears the threshold.

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
  one frozen script. `blockers` is not part of this check — it is not a
  gate — but an operator should still read `n_regressed` / `tail_quantile` on
  each tape by hand before promoting (see the limitation above).
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
