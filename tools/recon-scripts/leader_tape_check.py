"""Registered expression check for the leader-tape slice.

Registration: eval/prereg/2026-09-11-leader-tape-slice1.md. Reads an early-cash ledger
record (tools/recon-scripts/early_cash_ledger.py --out) plus a weed-provenance record
(tools/recon-scripts/weed_provenance.py --out) over the same arms, seeds and build -- in
both, the FIRST arm must be the shipped reference, config {} -- and asks whether each
other arm plays the public leaders' opening tape closely enough for a money gate to test
it.

Every threshold comes from the leaders' measured tape (32 instrumented games, behavior
only; the leaders' source was not read) and was committed before any expression-check
data existed. Each bar is loose enough that an arm which really plays the tape clears
it, and tight enough that the shipped opening fails it:

- C1 herd order (arms whose animal_buy_order puts SHEEP first): mean sheep on the farm at
  the end of day 2 >= 3.5. The leaders own 4 sheep from day 0; shipped reaches 4 on day 7.
- C2 land calendar (arms with ne_land_min_day = N > 0): NE first unlocks on day N or N+1
  on every seed, and SW is unlocked by the end of day 11 on at least 7 of 8 seeds. The
  leaders buy NE on day 6 and SW on day 10, on every seed.
- C3 strawberry fill (every arm): mean NW+NE strawberry tiles at the end of day 9 >= 15,
  and mean strawberry tiles at the end of day 12 >= 27. The leaders stand at ~20 and 36;
  each bar is 75% of theirs. This is the positive mechanism criterion: the last two
  strawberry arms died on fill, not on money.
- C4 survival (every arm): mean strawberry tiles at the end of day 16 >= 0.9 x the day-12
  mean. Strawberry credits yield at ages 9, 11, 13 and 15 and is swept at 16, so a tile
  planted on day 3 or later still stands at the end of day 16 unless it died.
- C5 watering guardrail (every arm): mean plant deaths from missed watering per game
  <= 1.5 x the reference's. A death is a tile the engine turns into a WEED under its
  two-consecutive-unwatered-days rule, counted by weed_provenance.py from the engine's
  own condition.

C5 was re-specified (from total weed tile-days to deaths from missed watering) before any
expression-check data existed; see the registration's amendment history for the engine
rule that made the original measure unmeetable by construction. Both numbers are printed,
so the retired measure stays visible.

Usage:
    uv run python tools/recon-scripts/leader_tape_check.py LEDGER.json --weeds SCAN.json \
        [--out RECORD.json]
"""

import argparse
import json
import math
import statistics

ENGINE = "1.32.7"
SHEEP_DAY = 2
SHEEP_MIN = 3.5
SW_BY_DAY = 11
SW_SEEDS_MIN_FRACTION = 7 / 8
NWNE_DAY = 9
NWNE_MIN = 15.0
FILL_DAY = 12
FILL_MIN = 27.0
SURVIVAL_DAY = 16
SURVIVAL_MIN_RATIO = 0.9
NEGLECT_RATIO_MAX = 1.5
NEGLECT_CATEGORIES = ("established_unwatered", "fresh_planting_unwatered")


def quadrants(row):
    """The unlocked quadrants of an end-of-day row; ``quads`` joins two-letter names."""
    q = row["quads"]
    if len(q) % 2:
        raise ValueError(f"malformed quads field {q!r}")
    return {q[i : i + 2] for i in range(0, len(q), 2)}


def first_unlock(rows, quadrant):
    return next((r["day"] for r in rows if quadrant in quadrants(r)), None)


def end_of_day(rows, day):
    if day >= len(rows) or rows[day]["day"] != day:
        raise ValueError(f"ledger has no end-of-day row for day {day}")
    return rows[day]


def measure(rows, scan):
    if any("weed" not in r for r in rows):
        raise ValueError(
            "ledger rows lack 'weed': regenerate with early_cash_ledger.py at or after the"
            " commit that added this checker"
        )
    odd = [c for c in scan["births_by_category"] if c.startswith(("UNEXPECTED", "OTHER"))]
    if odd:
        raise ValueError(f"weed scan has unexplained births {odd}: the classification is not validated here")
    by_quadrant = end_of_day(rows, NWNE_DAY)["strawberry_by_quadrant"]
    return {
        "sheep": end_of_day(rows, SHEEP_DAY)["sheep"],
        "ne_unlock_day": first_unlock(rows, "NE"),
        "sw_unlock_day": first_unlock(rows, "SW"),
        "nw_ne_strawberry": by_quadrant.get("NW", 0) + by_quadrant.get("NE", 0),
        "fill": end_of_day(rows, FILL_DAY)["strawberry"],
        "survival": end_of_day(rows, SURVIVAL_DAY)["strawberry"],
        "weed_tile_days": sum(r["weed"] for r in rows),
        "neglect_deaths": sum(scan["births_by_category"].get(c, 0) for c in NEGLECT_CATEGORIES),
    }


def check(cfg, seeds, ref_seeds):
    """Every criterion that applies to one arm, as [(name, passed, detail)]."""

    def mean(key, population=seeds):
        return statistics.fmean(s[key] for s in population)

    out = []
    order = cfg.get("animal_buy_order")
    if order and order[0] == "SHEEP":
        v = mean("sheep")
        out.append(
            ("C1_herd_order", v >= SHEEP_MIN, f"mean sheep end of day {SHEEP_DAY} {v:.2f} (needs >= {SHEEP_MIN})")
        )
    n = cfg.get("ne_land_min_day", 0)
    if n > 0:
        ne = [s["ne_unlock_day"] for s in seeds]
        sw_ok = sum(1 for s in seeds if s["sw_unlock_day"] is not None and s["sw_unlock_day"] <= SW_BY_DAY)
        need = math.ceil(SW_SEEDS_MIN_FRACTION * len(seeds))
        ok = all(d in (n, n + 1) for d in ne) and sw_ok >= need
        out.append(
            (
                "C2_land_calendar",
                ok,
                f"NE unlock days {ne} (needs all in {n}-{n + 1}); SW by day {SW_BY_DAY} on"
                f" {sw_ok}/{len(seeds)} seeds (needs >= {need})",
            )
        )
    nwne, fill = mean("nw_ne_strawberry"), mean("fill")
    out.append(
        (
            "C3_strawberry_fill",
            nwne >= NWNE_MIN and fill >= FILL_MIN,
            f"NW+NE end of day {NWNE_DAY} {nwne:.1f} (needs >= {NWNE_MIN:g}); all quadrants end of"
            f" day {FILL_DAY} {fill:.1f} (needs >= {FILL_MIN:g})",
        )
    )
    late = mean("survival")
    out.append(
        (
            "C4_survival",
            fill > 0 and late >= SURVIVAL_MIN_RATIO * fill,
            f"end of day {SURVIVAL_DAY} {late:.1f} (needs >= {SURVIVAL_MIN_RATIO} x {fill:.1f} ="
            f" {SURVIVAL_MIN_RATIO * fill:.1f})",
        )
    )
    deaths, ref_deaths = mean("neglect_deaths"), mean("neglect_deaths", ref_seeds)
    out.append(
        (
            "C5_watering_guardrail",
            deaths <= NEGLECT_RATIO_MAX * ref_deaths,
            f"missed-water deaths {deaths:.1f}/game (needs <= {NEGLECT_RATIO_MAX} x {ref_deaths:.1f} ="
            f" {NEGLECT_RATIO_MAX * ref_deaths:.1f})",
        )
    )
    return out


def main():
    ap = argparse.ArgumentParser(description="leader-tape expression check")
    ap.add_argument("ledger", help="an early_cash_ledger.py --out record")
    ap.add_argument("--weeds", required=True, help="a weed_provenance.py --out record over the same arms and seeds")
    ap.add_argument("--out", help="write the verdict record here")
    a = ap.parse_args()
    with open(a.ledger) as fh:
        record = json.load(fh)
    with open(a.weeds) as fh:
        weeds = json.load(fh)
    ident, wident = record["identity"], weeds["identity"]
    if ident["engine"] != ENGINE:
        raise SystemExit(f"ABORT: engine {ident['engine']}; the check requires {ENGINE}")
    if ident["packages_dirty"] or wident["packages_dirty"]:
        raise SystemExit("ABORT: a record ran on a dirty packages/ tree")
    for field in ("git_sha", "engine", "opponent", "arms", "seeds"):
        if ident[field] != wident[field]:
            raise SystemExit(f"ABORT: the ledger and the weed scan disagree on {field}")
    arms = ident["arms"]
    ref = next(iter(arms))
    if arms[ref] != {}:
        raise SystemExit(f"ABORT: the first arm ({ref}) must be the shipped reference, config {{}}")
    games, wgames = record["games"], weeds["games"]
    seeds = sorted(games)
    if sorted(wgames) != seeds:
        raise SystemExit("ABORT: the ledger and the weed scan cover different seeds")
    measures = {arm: [measure(games[s][arm]["rows"], wgames[s][arm]) for s in seeds] for arm in arms}

    print(
        f"{len(seeds)} seeds {seeds[0]}..{seeds[-1]} vs {ident['opponent']};"
        f" tree {ident['git_sha'][:7]}; reference {ref}"
    )
    print(
        f"{'arm':<14}{'sheep@2':>8}{'NE day':>14}{'SW day':>14}{'NW+NE@9':>8}{'@12':>6}{'@16':>6}"
        f"{'deaths':>8}{'weed t-d':>9}"
    )
    for arm in arms:
        m = measures[arm]

        def days(key, rows=m):
            vals = [99 if s[key] is None else s[key] for s in rows]
            return f"{min(vals)}-{max(vals)}"

        print(
            f"{arm:<14}{statistics.fmean(s['sheep'] for s in m):>8.2f}{days('ne_unlock_day'):>14}"
            f"{days('sw_unlock_day'):>14}{statistics.fmean(s['nw_ne_strawberry'] for s in m):>8.1f}"
            f"{statistics.fmean(s['fill'] for s in m):>6.1f}{statistics.fmean(s['survival'] for s in m):>6.1f}"
            f"{statistics.fmean(s['neglect_deaths'] for s in m):>8.1f}"
            f"{statistics.fmean(s['weed_tile_days'] for s in m):>9.1f}"
        )
    print("(weed t-d = total weed tile-days, the retired C5 measure: reported, not gating)")

    print("\nEXPRESSION CHECK (registered criteria):")
    verdicts = {}
    for arm, cfg in arms.items():
        if arm == ref:
            continue
        results = check(cfg, measures[arm], measures[ref])
        passed = all(ok for _, ok, _ in results)
        verdicts[arm] = {
            "pass": passed,
            "criteria": {name: {"pass": ok, "detail": detail} for name, ok, detail in results},
        }
        print(f"  {arm}: {'PASS' if passed else 'FAIL'}")
        for name, ok, detail in results:
            print(f"    {name}: {'ok' if ok else 'FAIL'} | {detail}")
    print("ALL ARMS PASS" if all(v["pass"] for v in verdicts.values()) else "NOT ALL ARMS PASS")

    if a.out:
        with open(a.out, "w") as fh:
            json.dump(
                {
                    "identity": {
                        **ident,
                        "checker": "tools/recon-scripts/leader_tape_check.py",
                        "ledger": a.ledger,
                        "weed_scan": a.weeds,
                    },
                    "measures": {arm: dict(zip(seeds, measures[arm])) for arm in arms},
                    "verdicts": verdicts,
                },
                fh,
                indent=1,
            )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
