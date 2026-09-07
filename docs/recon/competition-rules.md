# Competition rules — verbatim, with an empirical confirmation

Retrieved 2026-09-07 from the live Kaggle Overview > Evaluation tab
(<https://www.kaggle.com/competitions/kaggriculture/overview/evaluation>),
rendered in a browser. Everything in the "Verbatim" sections below is quoted
prose from that page, not paraphrase. This file exists because
`docs/recon/rules-format.md` (2026-08-04) recorded the same rules as *summary
with section citations*, and three separate notes flagged the resulting
ambiguity as unresolved and blocking an upload decision.

## Verbatim — submission tracking

> Each day your team is able to submit up to 5 agents (bots) to the competition.
> Each submission will play Episodes (games) against other bots on the ladder
> that have a similar skill rating. Over time, skill ratings will go up with wins
> or down with losses, and even out with ties. To reduce the number of bots
> playing and ensure high-quality matching, only the latest 2 submissions are
> tracked. The latest 2 submissions are also used for final leaderboard
> evaluation.

> Every bot submitted will continue to play episodes until the end of the
> competition, with newer bots playing a much more frequent number of episodes.
> On the leaderboard, only your best-scoring bot will be shown, but you can track
> the progress of all of your submissions on your Submissions page.

## Verbatim — what the rating responds to

> Winning the match (having the most coins in the bank at the end of 720 turns)
> increases your skill rating, while losing decreases it.
> The amount your rating changes depends on the rating difference between you and
> your opponent. Beating a highly-rated agent will boost your rating more than
> beating a lower-rated one.
> Ties will generally pull ratings closer together.
> The actual coin difference in a match does not affect the rating change—only
> the win, loss, or tie outcome matters.

## Verbatim — final evaluation

> At the submission deadline, additional submissions will be locked. Games will
> continue to run for approximately two weeks to continue to reduce uncertainty,
> especially for new agents. A final Bradley-Terry tournament will be run on
> those episodes to produce the final leaderboard.

## Verbatim — timeline

> September 23, 2026 - Entry Deadline.
> September 23, 2026 - Team Merger Deadline.
> September 30, 2026 - Final Submission Deadline.
> October 1, 2026 to (approx) October 15, 2026 - We will continue to run games,
> or until the leaderboard has reached convergence. At the conclusion of this
> period, the leaderboard is final.

## Empirical confirmation — the rule is chronological, and our own history proves it

The page says "latest 2" without saying explicitly that "latest" is by upload
time across ALL submissions. Our own episode history settles it, because a
submission that falls out of the tracked pair **stops accumulating episodes**.

Predicted: each upload drops whichever submission was, at that moment, the
third-newest. Tested against `kaggle competitions episodes <id>`:

| submission | predicted to stop when | predicted time | last episode observed | |
|---|---|---|---|---|
| M1 55309517 | M2b uploads | 2026-08-08 18:58 | 2026-08-08 17:03 | match |
| M2a 55334684 | M2c uploads | 2026-08-12 16:52 | 2026-08-12 16:34 | match |
| M2b 55358390 | M3a uploads | 2026-08-13 02:13 | 2026-08-12 23:27 | match |
| M2c 55463561 | M3b uploads | 2026-08-26 03:25 | 2026-08-26 02:13 | match |

Four for four. Every last episode lands shortly *before* the next upload, which
is what a matchmaking cutover looks like (the final episode is created before the
new bot enters the pool). Meanwhile M3a and M3b — the current pair — both played
episodes on 2026-09-06.

## Corrections to the existing record

1. **"Same-line eviction" is not a Kaggle mechanic.** It is this repo's own
   lineage bookkeeping vocabulary (`eval/submissions/README.md` defines "Lines").
   Eviction is chronological and line-agnostic. The three vault notes flagging
   this as an unresolved contradiction can be closed.

2. **`eval/submissions/sub-55784368.json` annotates M3b as "[evicts 55471731]"
   (M3a). That is factually wrong.** When M3b uploaded on 08-26 the tracked pair
   was [M3a 08-13, M2c 08-12], so M3b's upload dropped **M2c (55463561)**. M3a is
   still tracked today. The ledger row is left as written (append-only); this
   note is the correction.

3. **`docs/recon/rules-format.md:109` — "Final submissions selectable for
   judging: up to 2" — is a misreading.** The live page describes an automatic
   mechanic ("only the latest 2 submissions are tracked"), with no selection UI.
   Nothing is chosen at the deadline; the last two uploads *are* the entry.

4. **Cross-era ratings are not comparable.** M2a shows 585.5, higher than M3a's
   543.6, which invites the conclusion that M3a regressed. It did not: M2a
   stopped playing on 2026-08-12 against a ~1,500-team field and its rating is
   frozen at that date. The field is 7,927 teams as of 2026-09-07. Only the
   tracked pair keeps playing, so only the tracked pair carries a current rating.

## Consequences for upload strategy

- The final entry is **whatever our last two uploads are** on 2026-09-30. There
  is nothing to select and nothing to protect except the ordering of uploads.
- Our tracked pair today is [M3a 543.6, M3b 657.2]. **Exactly one upload is free**
  — it drops M3a, our weaker slot. A second upload starts dropping M3b.
- Because the board shows only the best-scoring tracked bot, a single upload
  **cannot lower our displayed score**: M3b stays tracked either way. The
  exposure is confined to the final Bradley-Terry tournament, which uses both.
- 5 uploads/day. Episode rate for a tracked bot is ~13/day (M3b: 146 episodes
  over 11 days), and newer bots play more often, so a bot uploaded on the
  2026-09-30 deadline still accumulates roughly 200 episodes before Oct 15 —
  about what M3b needed to converge (flat from n=57 to n=140).
- **The ladder is therefore a usable measurement instrument, not just a
  scoreboard.** An uploaded candidate returns a rating against the real field,
  which is the actual objective — unlike any offline proxy in `eval/`.

## Live state at retrieval (2026-09-07)

Team "Charles Coonce" (16664096): rank **4,513 / 7,927**, score **657.2**,
SubmissionCount 2. Leaderboard SubmissionCount distribution: 6,663 teams at 2,
861 at 1, none above 2 — consistent with the tracked-pair cap applying to
everyone. Rank-50 bar 2,652.8; rank-10 bar 2,796.2.

Per-submission scores (`kaggle competitions submissions kaggriculture`):
M3b 657.2 · M3a 543.6 · M2c 546.3 · M2b 577.5 · M2a 585.5 · M1 508.0 ·
chassis 429.4 · M0a 273.1. Only the first two are current.
