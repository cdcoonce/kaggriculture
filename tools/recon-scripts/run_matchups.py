import time, json, statistics
from kaggle_environments import make

SEEDS = [1, 2, 3, 4, 5]
MATCHUPS = [
    ("starter", "random"),
    ("starter", "pass"),
    ("starter", "starter"),
]

results = {}

for a, b in MATCHUPS:
    key = f"{a}_vs_{b}"
    rows = []
    for seed in SEEDS:
        t0 = time.time()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run([a, b])
        dt = time.time() - t0
        final = env.steps[-1]
        m0 = final[0].reward
        m1 = final[1].reward
        if m0 > m1:
            wlt = "P0_WIN"
        elif m1 > m0:
            wlt = "P1_WIN"
        else:
            wlt = "TIE"
        rows.append({"seed": seed, "money0": m0, "money1": m1, "wlt": wlt, "seconds": dt})
        print(f"{key} seed={seed} money0={m0} money1={m1} wlt={wlt} t={dt:.2f}s")
    results[key] = rows

with open("matchup_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n=== SUMMARY ===")
for key, rows in results.items():
    m0s = [r["money0"] for r in rows]
    m1s = [r["money1"] for r in rows]
    ts = [r["seconds"] for r in rows]
    p0w = sum(1 for r in rows if r["wlt"] == "P0_WIN")
    p1w = sum(1 for r in rows if r["wlt"] == "P1_WIN")
    tie = sum(1 for r in rows if r["wlt"] == "TIE")
    print(f"{key}: P0(mean/min/max)={statistics.mean(m0s):.0f}/{min(m0s):.0f}/{max(m0s):.0f} "
          f"P1(mean/min/max)={statistics.mean(m1s):.0f}/{min(m1s):.0f}/{max(m1s):.0f} "
          f"W/L/T(P0 perspective)={p0w}/{p1w}/{tie} mean_seconds={statistics.mean(ts):.2f}")
