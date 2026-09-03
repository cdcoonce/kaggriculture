# What a month of careful evaluation failed to measure

Kaggriculture is a two-player farming economy. Each match runs 720 turns, thirty
in-game days, and whoever holds more coins at the end wins. I spent August
building an agent for it and a fairly heavy evaluation harness around that
agent: paired-seed money gates, Wilson bounds on win rate, committed JSON
ledgers for every gate run, frozen copies of past agents to gate against, and
pre-registered experiments with kill criteria, the results that would make me
stop, fixed before any seed was burned.

The harness worked. Every gate I ran was correctly specified and correctly
read. On 2026-08-28 it told me, across four opponents at sixty-four paired
seeds each, that a change was worth about fifteen thousand coins a match, and
a pre-registered control came back stronger still. Then I ran it against my
own shipped agent, the version already sitting on the leaderboard, and it
lost 44 games to 456.

This is a writeup about that gap, because it turned out to be the most useful
thing the season produced.

## The agent, and where it actually loses

The shipped agent runs a wheat rush. It plants the cheap fast crop across most
of the board, keeps a small melon satellite, runs six cows and four sheep, and
sells with a price-aware floor so it doesn't dump into a crashed market.
Against the scripted opponents in my test pool it banks somewhere between
eighty-five and a hundred thousand coins and wins every game, with two
exceptions. A scripted clone of the ladder's common build holds it to
seventy-two thousand coins and takes a quarter of the games off it. The
second exception gets the rest of this section.

I had ported a published competitor solution into the test pool as a replay
of its 720-turn action plan, with three repair passes so it reacts to the
live board instead of replaying blind.
It beat my agent 200 games to nil, banking $114,862 against my $64,041.

To find out why, I wrapped both agents in a recorder and replayed seven
matches. The same shape shows up in every one:

```
mean money gap (mine minus theirs)
  d16  +9,644    d20  -142    d24  -26,909    d28  -43,071

late-game earning rate, days 21-29
  mine  +2,474/day      theirs  +7,607/day      (3.1x)
```

I lead all seven games at day 16 and trail all seven at the end. Day 20 is
the crossover (ahead in four of the seven, dead even on average), and from
there the last third is a rout. That was not what I expected, and it is not
a tuning problem.

Their action plan explains it. They buy 37 strawberry seeds between day 3 and
day 10, and those tiles then produce 20 to 37 units a day, every day, from day
16 through day 29. Three hundred units of output from one early purchase.
They buy eight cows by day 8 and put 320 milk on the market. My agent sells
about 550 wheat, a crop that destroys its own tile at harvest and consumes
the labor that would otherwise be working the back half of the game.

Their economy is standing assets bought early. Mine is throughput. Throughput
wins the opening and runs out of hands by day 20.

## The part where careful work measured nothing

Strawberry was the obvious lever, so I went after it. I had already written a
pre-registration for it, with predictions and kill criteria fixed in advance,
and I followed it.

The first attempt found that the strawberry seed line was funded ahead of the
wheat seed line, so a $100 seed was bought before a $10 one and the early game
starved. I fixed the ordering, capped the strawberry spend at a share of
available cash, and measured. Both kill criteria fired. I recorded the
negative and stopped.

The second attempt found something better. The agent is two halves: a planner
that decides what seed money buys, and a dispatcher that assigns labor to
tiles each turn. The dispatcher had a fallback the planner did not know
about: plant wheat on any idle strawberry tile once the day's strawberry cap
is spent. The planner computed wheat's seed target over a tile set with the
strawberry zone subtracted out, so the dispatcher stood ready to plant ground
the planner refused to buy seed for, and the fallback fired against an empty
shed. At the largest zone size the planner saw exactly zero plantable
wheat tiles for thirteen days while twenty-one tiles sat empty, and the farm
ran on under two hundred coins because nothing was producing.

I fixed it, and the gates came back strong. Against four replay tapes the
change was worth about fifteen thousand coins with lower bounds between ten
and fourteen thousand. One kill criterion did fire: the opponent was losing
more money than my registered band allowed. Both players sell into one
shared market, so a gain that shows up as the opponent's loss can be
redirected revenue rather than new production, and the band existed to catch
exactly that. So I registered a follow-up test with its
decision points derived from the observed transfer before running it, and ran
the change against an opponent that takes no market action at all and finishes
every match holding its untouched opening stake. There is no revenue to take
from an opponent like that, so a gain against it is production by
construction.

It came back at +25,838 coins with a lower bound of +23,542, and every one of
the 32 paired seeds improved. The transfer hypothesis was refuted by its own
sign: my gain was largest against the one opponent with nothing to take, and
smaller against the four that compete in the market, which is backwards from
what taking revenue would produce.

Every one of those numbers is real. I would run all of those gates again.

Then I ran the change against my own shipped agent, the one on the
leaderboard, and it lost 44 to 456.

## Why none of it could have caught the problem

Every money gate in that chain compared the new code at a given strawberry zone
size against a frozen copy of the old code at the same zone size. That is the
correct way to price a code change, because otherwise you price the knob and
the code change together and credit the sum to the code.

It also means both arms were standing inside a configuration that nothing had
validated. The comparison can answer "is my fix good," and it cannot answer
"should this feature be on." I never asked the second question. Turning
strawberry on costs far more than my fix recovered, at every zone size I
tested: 0 wins in 200 at the small zone, 3 in 200 at the medium one, 44 in 500
at the large one.

The signal was in every ledger I wrote. Against the passive opponent, my
frozen baseline banked $70,394 and my fixed version banked $96,232, while the
shipped agent takes $99,010 off that same opponent. The number that mattered
was sitting in the same row as the number I was celebrating. I read deltas for
a week and never once put the absolute next to what was already live.

What makes this worth writing down is that the rigor made the wrong answer
stronger. A pre-registered experiment with a fixed threshold, a refuted
alternative hypothesis, and a control opponent chosen for a specific
mechanical reason is a very convincing object. It was also measuring inside
the wrong universe the entire time, and none of its machinery could tell.
The rigor did not cause the mistake. It armored it.

The rule, which costs one gate run: **before opening a pre-registration on a
change behind a non-default setting, run that setting against the shipped
default first.** It is the only comparison that can kill the configuration,
and it has to happen before you build anything on top of it. And because
this whole piece is about not trusting myself to remember things, the
durable form of the rule is not a habit. It belongs in the harness, as the
mandatory first arm of any gate on a non-default configuration.

## Four smaller traps from the same month

**Compare against the broken arm, not the off switch.** When a fix removes a
blocker, there are three arms and not two: feature off, feature on and blocked,
feature on and fixed. I set my occupancy bar, a mean count of standing
crops, against the blocked arm before measuring. It missed by 0.3 and I
killed the change. Against the off arm it would have cleared comfortably,
and the honest reading would have been hidden:
fixing the blocker made the metric slightly worse, because the blocked version
had been buying its score by starving the competing crop.

**A guard inherited from another experiment guards its mechanism, not yours.**
The kill criterion that fired above deserves a second pass, because handling
it honestly was a near thing. The opponent-suppression band came from a
pre-registration about crop displacement, which should not move wheat
supply. I applied it to a change whose entire mechanism is planting more
wheat. A wheat-selling opponent
cannot keep its revenue flat when you double your wheat, so the band forbade
the mechanism rather than the artifact. The trap is the timing: that argument
is correct, and it only occurred to me after the veto fired, which is exactly
when I least deserved to be believed. Recording it as a hypothesis and testing
it separately was the only move that stayed honest.

**The diagnosis you need is usually in a closed pull request.** I spent a day
diagnosing the zone geometry problem. A pull request closed weeks earlier had
it already, with the same arithmetic: under the two starting quadrants there
are 49 tiles, and 8 melon plus 10 pasture plus 31 strawberry is 49, so wheat
gets none. My own project notes listed that pull request as a parked negative.
I never opened it, because `gh pr list` shows open ones by default and a
negative reads like an absence of information. It is the opposite. You only
write a negative up carefully when you understood why, so the closed ones hold
the sharpest statement of the constraint.

**A conclusion without its instrument is a memory, not a measurement.** The
day-by-day decomposition above originally came from a quick instrumented run
I never committed. The conclusions went into a document, the script did not,
and I trusted the document for a week. Rebuilding the probe as a committed
script was supposed to be housekeeping. The purchase counts and sale totals
reproduced exactly; the mid-game money series did not, under any of nineteen
sampling conventions I tried, and whatever convention produced the original
numbers is gone because I never wrote it down. The figures above are from
the committed run. They cost me the tidiest sentence in the essay, because
the honest crossover is day 20, not "the first two thirds." I caught it only
by tracing every number in this piece to a committed ledger before
publishing, which is this essay's own argument, applied to the essay.

## Where it ended

I descoped on 2026-08-29, nine days ahead of my own checkpoint. The agent
sits at an Elo-style ladder rating of 664 against a top-ten bar of 2811, and
the last twenty ladder games ran 7 wins and 13 losses with a negative money
margin. The lever I had is measured dead, and I did not have a second one
ready. The diagnosis behind the lever may even be right, because their
economy really is standing assets bought early. What the season killed was
my route to that economy, not the read on theirs.

I got a working agent, an evaluation harness I trust more than the agent, and
one finding I will carry into every project after this: a frozen baseline is a
mirror. It shows you your change, faithfully, and it will never show you that
you are standing in the wrong room. The check that catches it is one more
frozen comparison, aimed at whatever is actually live, and it only works if
it runs first.
