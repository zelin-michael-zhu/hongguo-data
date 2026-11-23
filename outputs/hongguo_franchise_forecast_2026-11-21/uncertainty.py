"""Paired, cluster-resampled uncertainty for fixed held-out predictions and the earlier binary contrast."""

import csv
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BOOT = 4000


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def sample_totals(by_cluster):
    sums = np.array(list(by_cluster.values()), dtype=float)
    rng = np.random.default_rng(20261121)
    for start in range(0, BOOT, 200):
        indices = rng.integers(0, len(sums), (min(200, BOOT-start), len(sums)))
        yield sums[indices].sum(axis=1)


def ci_difference(rows, base, comp, cluster):
    groups = defaultdict(lambda: np.zeros(3))
    for r in rows:
        measured = float(r["actual"])
        def loss(model):
            error = float(r[model])-measured
            return abs(error) if r["outcome"] == "days7" else error**2
        groups[r[cluster]] += (loss(base), loss(comp), 1)
    sums = sum(groups.values())
    diffs = np.concatenate([(vals[:,0]-vals[:,1])/vals[:,2] for vals in sample_totals(groups)])
    low, high = np.quantile(diffs,[.025,.975])
    return dict(events=len(rows), clusters=len(groups), clustering=cluster, baseline_loss=sums[0]/sums[2],
                extended_loss=sums[1]/sums[2], improvement=(sums[0]-sums[1])/sums[2], low=low, high=high)


def prediction_audit():
    hrows = read(HERE / "history.csv")
    hindex = {(r["date"],r["board"],r["id"]):r for r in hrows}
    output = []
    for scenario, name in [("all","forecast_oos.csv"),("remove_giant","forecast_no_giant_oos.csv")]:
        pred = read(HERE / name)
        for r in pred:
            h = hindex[r["date"],r["board"],r["id"]]
            assert r["group"] == h["group"]
            for col in ("asof_linked", "asof_season_number", "full_prior7"):
                r[col] = h[col]
        by_outcome = sorted({r["outcome"] for r in pred})
        for outcome in by_outcome:
            subset = [r for r in pred if r["outcome"] == outcome]
            pairs = [("B", "C"), ("B","D"), ("B","E"), ("B","G"), ("G","C"), ("H","I"), ("J","D")]
            for base, comp in ((b,c) for b,c in pairs if b in subset[0] and c in subset[0]):
                groups = {"all":subset}
                if comp=="C" and outcome=="days7" and scenario=="all":
                    groups.update({k:[r for r in subset if r["fold"]==k] for k in sorted({r["fold"] for r in subset})})
                    groups["full_prior7"] = [r for r in subset if r["full_prior7"]=="1"]
                    groups["first_observed"] = [r for r in subset if r["entry_type"]=="first_observed"]
                    groups["reentry"] = [r for r in subset if r["entry_type"]=="reentry"]
                    groups["ai_comic"] = [r for r in subset if r["board"] in ("ai","comic")]
                    groups["ai_season3plus"] = [r for r in subset if r["board"]=="ai" and
                                               float(r["asof_season_number"] or 0)>=3]
                for label, vals in groups.items():
                    if not vals:
                        continue
                    clusters = ("group","date") if label=="all" and comp=="C" else ("group",)
                    for cluster in clusters:
                        output.append(dict(scenario=scenario,outcome=outcome,base=base,comparison=comp,sample=label,
                                           **ci_difference(vals,base,comp,cluster)))
    write("paired_cluster_intervals.csv",output)
    dimensions = read(HERE / "dimension_oos.csv")
    estimates = [dict(outcome="days7",base="G",dimension=col,**ci_difference(dimensions,"G",col,"group"))
                 for col in ("active", "depth", "momentum")]
    write("dimension_intervals.csv", estimates)


def risk_audit():
    events = read(HERE.parent / "hongguo_entry_signal_2026-11-21/entry_events.csv")
    vals = [r for r in events if r["complete_window"]=="1" and r["x"] in ("1","0")]
    result = []
    for cluster in ("group_id","date"):
        groups = defaultdict(lambda: np.zeros(4))
        for r in vals:
            pos = 0 if r["x"]=="1" else 2
            groups[r[cluster]][pos:pos+2] += (float(r["y"]),1)
        diffs=[]
        for b in sample_totals(groups):
            b=b[(b[:,1]>0)&(b[:,3]>0)]
            diffs.extend(b[:,0]/b[:,1]-b[:,2]/b[:,3])
        low, high=np.quantile(diffs,[.025,.975])
        result.append(dict(cluster=cluster,n_events=len(vals),n_clusters=len(groups),
                           risk_difference=40/111-231/649,low=low,high=high))
    write("original_binary_uncertainty.csv",result)


if __name__ == "__main__":
    risk_audit()
    prediction_audit()
