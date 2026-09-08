# Pre-registration: demand-aware seasonal controller against public leaders

Date: 2026-09-08
Candidate: flag-gated demand-aware seasonal controller; not implemented here
Baseline: source default at `028309354ad975a818a3aa7d29e39a03e0eb3b6e`
Status: REGISTERED — no run is authorized by this document

## Scope and evidence boundary

The slice may use visible shop roster, exact consumption timing, market inventory and
prices, guaranteed remaining absorption, and bounded public opponent production to
jointly control portfolio, buildings and labor, task budgets, reserve inventory, sale
timing, and endgame. This registration does not implement that controller, alter the
default, run an experiment, create a submission, upload, or merge anything.

The opponent panel is exactly the three immutable public Kaggle versions in
`eval/opponents/public-leaders/panel.json`: Sokolovsky V12 (2883.0), Rayk V11
(2990.4), and Kaito V4 (3090.1). Their notebook bytes and decoded agents are retained
under that directory with SHA-256 enforcement. The three owner namespaces and notebook
version lineages are distinct. All three strategies are replay-derived; this establishes
independent authorship and artifact lineage, not independently invented route ancestry.

## Selection gate

Use seeds 900000–900099, both candidate seats, against every panel opponent: 100
seeds and 200 games per opponent. The candidate advances only if every condition holds:

- aggregate candidate-minus-current-default score-rate uplift is at least 0.15;
- uplift is at least 0.10 against every opponent;
- absolute aggregate candidate score rate is at least 0.25;
- candidate score rate in each seat is strictly greater than 0.15; and
- there are zero candidate crashes and zero candidate fallbacks.

Candidate and default measurements are paired by opponent, seed, and seat. A win scores
1, a tie 0.5, and a loss 0.

## Confirmation gate

Only a full selection pass reaches confirmation. Use fresh seeds 901000–901249,
disjoint from selection, with both seats: 250 seeds and 500 games per opponent. The
candidate passes only if every condition holds:

- aggregate candidate-minus-current-default score-rate uplift is at least 0.15;
- uplift is at least 0.10 against every opponent;
- the stratified paired 95% lower bound on aggregate uplift is strictly greater than
  0.10;
- absolute aggregate candidate score rate is at least 0.30; and
- there are zero candidate crashes and zero candidate fallbacks.

The confidence bound is the 2.5th percentile of 100,000 paired bootstrap replicates,
resampling the 250 paired seed outcomes independently within each opponent × seat
stratum, then weighting all six strata equally. The bootstrap RNG seed is 90202609.

## Integrity rule

Opponent provenance and independence are load-bearing. Any miss closes the whole slice.
After registration there are no threshold revisions, opponent substitutions, seed-band
reuse, extensions, or component salvage. A closed slice may inform a separately proposed
future hypothesis, but no component of this candidate is promoted from a failed result.

## Consequence

A full confirmation pass supports a recommendation to consider source-default promotion.
It does not authorize a default change, submission build, Kaggle upload, or merge; every
such action remains a separate owner decision.
