# Public-leader opponent panel

Three public Kaggle notebooks by other competitors, retained here as **fixed**
opponents for this repository's local evaluation harness.

## These files are not ours

Copyright in everything under this directory remains with the upstream authors
named below. The repository-root `LICENSE` copyright line does not cover them.
See the root [`NOTICE`](../../../NOTICE) file.

## Attribution

| Author | Notebook | Version | License | Source |
|---|---|---|---|---|
| Andrey Naymushin (@andrewsokolovsky) | kaggriculture-breaking-the-tie | v12 (`341994976`) | Apache-2.0 | [notebook](https://www.kaggle.com/code/andrewsokolovsky/kaggriculture-breaking-the-tie/notebook?scriptVersionId=341994976) |
| Rayk Kretzschmar (@raykkretzschmar) | kaggriculture-rank-your-agent | v11 (`341319585`) | Apache-2.0 | [notebook](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-rank-your-agent?scriptVersionId=341319585) |
| Kaito Fukami (@kaitofukami) | 25-27-strict-future-v27-midgame-meta-reset | v4 (`341355723`) | Apache-2.0 | [notebook](https://www.kaggle.com/code/kaitofukami/25-27-strict-future-v27-midgame-meta-reset?scriptVersionId=341355723) |

## License verification

Each upstream license was checked directly at its source URL on **2026-09-12**. All
three Kaggle notebook pages state: "This Notebook has been released under the
Apache 2.0 open source license."

This matters because `panel.json` records a `license` field and
`tests/test_public_leader_provenance.py` asserts against that same field — that
assertion confirms the record is internally consistent, **not** that it matches
upstream. The date above is the record of the external check.

## Integrity, and why nothing here is edited

Both the `notebook.ipynb` and the extracted `main.py` for each opponent are
sha256-pinned in `panel.json`. The pins exist to prove these are byte-identical to
what was retrieved from upstream, so **no attribution header is added to the files
themselves** — doing so would break the pin and destroy the very guarantee it
provides. Attribution lives here and in the root `NOTICE` instead, which is what
Apache-2.0 §4(d) prescribes.

`main.py` is extracted from its notebook for direct import by the harness. The
agent logic is unmodified; the extraction is the only change, and it is what the
`decoded_agent_sha256` pin covers.

## Freshness

These are snapshots, not mirrors. Upstream authors may have published newer
versions. The pinned `scriptVersionId` is the exact version evaluated here.
