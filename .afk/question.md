# Issue #23 (meta-clone economy core) — observations parked, NOT fixed in this slice

**Status: the slice is complete and the full gate is green.** This file is
advisory, not an escalation — nothing here blocked the implementation.

Recorded rather than fixed, per the no-opportunistic-fixes convention. None of
these block an acceptance criterion; all three want a human decision because
they touch the pinned pacing spec or slice 2's contract.

## 1. The issue body contradicts itself on feed-stock wheat (needs a decision before slice 2)

The issue asks for BOTH:

- "**Feed-stock buying:** `BUY_PRODUCT` WHEAT only ... (In this slice the bought
  wheat simply accumulates in inventory; slice 2 consumes it.)"
- "**Selling:** ... Sell wheat/melon/strawberry price-blind at those windows."

These cannot both hold. `BUY_PRODUCT` lands wheat in the shed, and a price-blind
`["SELL", "WHEAT", 99999]` at hours 19-23 empties the shed the same evening, so
end-of-episode shed WHEAT is 0 on every seed measured. The engine quotes buys at
post-buy inventory, so the round trip nets ~zero money — there is no leak, but
nothing accumulates either.

This slice implemented both literally (both are AC-tested behaviours) and
corrected the module docstring, which previously asserted the accumulation that
does not happen. **Slice 2 cannot rely on a standing feed stock as written.**
The fix belongs in slice 2 (hold a feed floor back from the sell loop, sized to
the herd) or in a spec correction here; either way it is a human call, not an
implementer's.

## 2. `need_at` hides unwatered plants from HARVEST once the wind-down water budget is spent

`meta_clone.py`, `need_at`: an unwatered PLANT returns `"WATER" if approved else
None`. On days 27-29, after the 8-op cap is spent, every still-unwatered tile
becomes invisible to harvesting too, and idle units fall through to `PASS`.
Melons planted day 15 ripen on day 27 and expire on day 28, so those are
dropped. The pinned episode reallocates those turns to harvest/sell rather than
idling.

Deliberately left alone: no AC covers days 27-29 harvest yield, and changing it
would move the wind-down behaviour the ACs *do* pin. Worth a slice of its own if
the fixture's late-game money matters to the rig.

## 3. Market-list truncation is load-bearing but undocumented

`maxMarketOrdersPerTurn` is 10. On days >= 12 the 12 HIRE orders fill hour 0's
list and push SELL/BUY_SEED to hour 1. It works today (hires self-correct across
turns, sells still land inside the 0-1 window), but a daily hire count above ~10
would silently starve everything ordered after the HIREs. Not a defect at the
pinned numbers; a hazard for anyone editing `HIRE_SCHEDULE`.

## 4. Plant-table fidelity is close but not exact (money-limited, not tile-limited)

After moving to a shared tile pool, per-day plantings match `PLANT_SCHEDULE`
exactly except for 1-2 tiles on a handful of days (typically `d9 WHEAT 2/3`,
`d11 STRAWBERRY 6/7`), which are seed-money limited on the day, not blocked by
tile supply. No AC covers per-day counts; noted so the next reader does not
mistake it for a pool-sizing bug.
