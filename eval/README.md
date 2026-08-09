# eval/ — committed gate-run ledger

Data only, no code. Every gate run appends (eval protocol, issue #4):
identity + verdict (candidate commit + config hash, opponents, gate type,
W/L/T, observed rate, CI bounds, PASS/FAIL, timestamp), the seed manifest,
and per-game rows. Replay JSONs are retained selectively, on demand, for
named matchups only. Schema/naming: Versioning ticket (#9).

A gate run without a ledger entry didn't happen.

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
