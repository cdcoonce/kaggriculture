# eval/submissions/ — committed Kaggle upload ledger

Data only, no code. Every Kaggle upload appends a `sub-<submission_id>.json`
entry (issue #10, #21, #30): the Kaggle submission ID, the candidate commit
SHA it was built from, its line, the bundle digest, the `sub-<id>` tag that
names it, the upload timestamp, an artifact reference, and a free-text note.

A submission without a ledger entry didn't happen.

## Schema

Each entry is a JSON object, one field per `harness.submissions.SubmissionRecord`
attribute:

| field            | type          | meaning                                                                 |
| ---------------- | ------------- | ------------------------------------------------------------------------ |
| `schema_version` | `int`         | ledger schema version (currently `1`)                                    |
| `submission_id`  | `str`         | the Kaggle submission ID                                                 |
| `candidate_sha`  | `str \| null` | commit the bundle was built from; `null` if none (e.g. the pre-`build.py` probe) |
| `line`           | `str`         | lineage tag — see "Lines" below                                          |
| `bundle_sha256`  | `str \| null` | sha256 digest of `dist/submission.tar.gz` at `candidate_sha`; `null` if no bundle existed |
| `tag`            | `str \| null` | the `sub-<id>` git tag naming this SHA, as a plain string field — a populated `tag` does not imply the git tag has been created |
| `uploaded_at`    | `str`         | ISO-8601 UTC upload timestamp                                            |
| `artifact_ref`   | `str \| null` | `git:<sha>:dist/submission.tar.gz` — the bundle is deterministic and pinned to source at every commit, so the committed tar.gz at that SHA IS the artifact |
| `note`           | `str \| null` | free-text context                                                        |

## The `sub-<id>` tag convention

Every submission built from a bundle is named by a local git tag,
`sub-<submission_id>`, pointing at `candidate_sha`. The tag is how a
submission is looked up from the commit graph without touching Kaggle. A
`tag` field with no corresponding git tag on disk is a valid, expected state
for entries backfilled before the tag was created — the ledger entry is the
source of truth; the tag is a convenience pointer into git history.

## Lines

- **Line A** — the champion lineage: chassis v1 → M1 → M2a → M2b, each
  submission evicting its predecessor's older slot per same-line discipline.
- **probe** — the retired M0a pipeline-proof line: a bare `main.py` upload
  before `build.py` existed, used to confirm the Kaggle submission pipeline
  worked at all. Not part of Line A.

There is no Line B yet.
