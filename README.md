# kaggriculture

Agent + improvement system for the [Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)
Kaggle simulation competition (final submission 2026-09-30).

- **Strategy:** [docs/strategy.md](docs/strategy.md) · engine/economy ground truth in [docs/recon/](docs/recon/)
- **Decisions:** the [blueprint map](https://github.com/cdcoonce/kaggriculture/issues/1) — design
  decisions live in its tickets, never re-litigated in code review
- **Layout:** uv workspace — `packages/agent` ships to Kaggle (Python 3.11, stdlib+numpy only,
  enforced); `packages/harness` is home infrastructure (zoo, gates, ledger, parity)
- **Build:** `python build.py` → deterministic `dist/submission.tar.gz` (committed; CI fails on stale)
- **Test:** `uv run pytest` (fast set) · `uv run pytest -m slow` (episode-playing suites)
