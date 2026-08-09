# Issue #30 — one AC's premise is factually false in the current working tree

## What the issue says

> The `5d0aa0f` digest above also matches the CURRENT working-tree
> `dist/MANIFEST.txt`, since HEAD is only a few non-agent commits past it —
> so that one entry is independently checkable with a plain file read.

And the corresponding AC:

> `packages/harness/tests/test_submissions.py` asserts ... that the entry
> for `5d0aa0f` equals the digest parsed from the committed
> `dist/MANIFEST.txt` in the working tree — the one digest reachable
> without git.

## What I found

They don't match, and the mismatch is legitimate (not a stale-bundle bug):

- `git show 5d0aa0f:dist/MANIFEST.txt` → digest
  `186273e5ff393ada6fe73382f45b3e95bae93807179603ff306567af52fdffeb`
  (matches the table exactly — table transcription is correct).
- Current working-tree `dist/MANIFEST.txt` → digest
  `cd12dfe0a8b14caa539770c7b41f6872cae7504dc522b3f49d6b052109421d23`.
- `uv run pytest tests/test_bundle.py -q` passes — the committed working-tree
  bundle IS fresh (a correct rebuild of current `packages/agent` source), so
  this isn't a stale-dist problem.
- The divergence is explained by `git log --oneline -- dist/MANIFEST.txt`:
  commit `b9533d8` ("AFK: implement issue #22", merged into this branch's
  history) touched `packages/agent/src/agent/{constants,plan,policy}.py`
  *after* `5d0aa0f`, which changed the bundle digest. So HEAD is not "a few
  non-agent commits past" `5d0aa0f` — a concurrent slice landed an agent
  change in between, and the working tree now reflects that newer source.

## What I did

- Backfilled all five `eval/submissions/sub-*.json` entries with the table's
  values verbatim, including `bundle_sha256 =
  186273e5ff393ada6fe73382f45b3e95bae93807179603ff306567af52fdffeb` for
  `sub-55358390` (the `5d0aa0f` entry) — per the explicit "transcribe
  verbatim, do not re-derive" instruction, since that value is confirmed
  correct against git history.
- `packages/harness/tests/test_submissions.py` asserts every non-null
  `bundle_sha256` across the five backfilled entries is well-formed (64
  lowercase hex chars), with a teeth-check that corrupting one char goes
  red.
- I did **not** add the specific assertion comparing the `5d0aa0f` entry
  against the live working-tree `dist/MANIFEST.txt`, because as written it
  would assert a currently-false equality and fail on this branch (and
  would keep failing/reappearing on `main` too, since every future
  agent-touching commit moves the working-tree digest further from the
  frozen `5d0aa0f` value — the check's premise doesn't hold once the repo
  has advanced past that commit, which it already has).

## Question for the human

Was the intent for that comparison to hold only transiently (at the moment
this correction was written, before issue #22 landed), or should the AC be
reworded — e.g. compare against `git show 5d0aa0f:dist/MANIFEST.txt` once
git becomes available again, or drop the cross-check and rely solely on the
hex-format + verbatim-transcription guarantees? I left the assertion out
rather than land a test that's red today, or one that encodes a comparison
against a moving target.
