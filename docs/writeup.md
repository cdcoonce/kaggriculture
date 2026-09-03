# What a month of careful evaluation failed to measure

Kaggriculture is a two-player farming economy. Each match runs 720 turns, thirty
in-game days, and whoever holds more coins at the end wins. I spent August
building an agent for it and a fairly heavy evaluation harness around that
agent: paired-seed money gates, Wilson bounds on win rate, committed JSON
ledgers for every gate run, frozen copies of past agents to gate against, and
pre-registered experiments with kill criteria fixed before any seed was burned.

The harness worked. Every gate I ran was correctly specified and correctly
read. On 2026-08-28 it told me, across four opponents at sixty-four paired
seeds each, that a change was worth about fifteen thousand coins a match, and
a pre-registered control came back stronger still. Then I ran the agent
against the version already on the leaderboard and it lost 44 games to 456.

This is a writeup about that gap, because it turned out to be the most useful
thing the season produced.

## The agent, and where it actually loses

The shipped agent runs a wheat rush. It plants the cheap fast crop across most
of the board, keeps a small melon satellite, runs six cows and four sheep, and
sells with a price-aware floor so it doesn't dump into a crashed market.
Against the scripted opponents in my test pool it banks somewhere between
eighty-five and a hundred thousand coins and wins every game, with one
exception short of the ported competitor below: a clone of the observed
ladder meta holds it to seventy-two thousand and takes a quarter of the
games off it.

The interesting opponent was different. I had ported a published competitor
solution into the test pool as a replay of its 720-turn action plan, with
three repair passes so it reacts to the live board instead of replaying blind.
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
the crossover — still ahead in four of the seven, dead even on average —
and from there the last third is a rout. That was not what I expected, and
it is not a tuning problem.

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

The second attempt found something better. The dispatcher already plants wheat
on an idle strawberry tile once the daily strawberry cap is spent. The planner
did not know that, because it computed wheat's seed target over a tile set with
the strawberry zone subtracted out. So the dispatcher was willing to plant
ground the planner refused to buy seed for, and the fallthrough fired against
an empty shed. At the largest zone size the planner saw exactly zero plantable
wheat tiles for thirteen days while twenty-one tiles sat empty, and the farm
ran on under two hundred coins because nothing was producing.

I fixed it, and the gates came back strong. Against four replay tapes the
change was worth about fifteen thousand coins with lower bounds between ten
and fourteen thousand. One kill criterion did fire: the opponent was losing
more money than my registered band allowed, which is the signature of taking
revenue rather than producing it. So I registered a follow-up test with its
decision points derived from the observed transfer before running it, and ran
the change against an opponent that takes no market action at all and finishes
every match holding its untouched opening stake. There is no revenue to take
from an opponent like that, so a gain against it is production by
construction.

It came back at +25,838 coins with a lower bound of +23,542, and every one of
the 32 paired seeds improved. The transfer hypothesis was refuted by its own
sign: my gain was largest with no opponent present and shrank as competition
rose, which is the opposite of what taking revenue would do.

Every one of those numbers is real. I would run all of those gates again.

Then I ran the change against the agent on the leaderboard, and it lost
44 to 456.

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

What makes this worth writing down is that the rigor made it worse. A
pre-registered experiment with a fixed threshold, a refuted alternative
hypothesis, and a control opponent chosen for a specific mechanical reason is
a very convincing object. It was also measuring inside the wrong universe the
entire time, and none of its machinery could tell.

The rule I'd give myself, which costs eleven minutes: **before opening a
pre-registration on a change behind a non-default setting, run that setting
against the shipped default first.** It is the only comparison that can kill
the configuration, and it has to happen before you build anything on top of it.

## Three smaller traps, all of the same family

**Compare against the broken arm, not the off switch.** When a fix removes a
blocker, there are three arms and not two: feature off, feature on and blocked,
feature on and fixed. I set my occupancy bar against the blocked arm before
measuring. It missed by 0.3 and I killed the change. Against the off arm it
would have cleared comfortably, and the honest reading would have been hidden:
fixing the blocker made the metric slightly worse, because the blocked version
had been buying its score by starving the competing crop.

**A guard inherited from another experiment guards its mechanism, not yours.**
The opponent-suppression band that fired above came from a pre-registration
about crop displacement, which should not move wheat supply. I applied it to a
change whose entire mechanism is planting more wheat. A wheat-selling opponent
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

## Where it ended

I descoped on 2026-08-29, nine days ahead of my own checkpoint. The agent sits
at a rating of 664 against a top-ten bar of 2811, and the last twenty ladder
games ran 7 and 13 with a negative margin. The lever I had is measured dead
and I did not have a second one ready.

I got a working agent, an evaluation harness I trust more than the agent, and
one finding I will carry into every project after this: a frozen baseline is a
mirror. It shows you your change, faithfully, and it will never show you that
you are standing in the wrong room.
