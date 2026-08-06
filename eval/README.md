# eval/ — committed gate-run ledger

Data only, no code. Every gate run appends (eval protocol, issue #4):
identity + verdict (candidate commit + config hash, opponents, gate type,
W/L/T, observed rate, CI bounds, PASS/FAIL, timestamp), the seed manifest,
and per-game rows. Replay JSONs are retained selectively, on demand, for
named matchups only. Schema/naming: Versioning ticket (#9).

A gate run without a ledger entry didn't happen.
