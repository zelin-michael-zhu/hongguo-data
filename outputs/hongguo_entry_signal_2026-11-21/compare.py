"""Paired descriptive comparisons and a chronological incremental-prediction check."""

import csv
from collections import Counter
from pathlib import Path
from statistics import mean

import numpy as np

HERE = Path(__file__).resolve().parent


def write_table(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def compare_neighbors(rows, radius):
    controls = [r for r in rows if r["x"] == 0]
    paired = []
    for r in rows:
        if r["x"] != 1:
            continue
        candidates = [s for s in controls if s["board"] == r["board"] and s["date"] == r["date"]
                      and s["group_id"] != r["group_id"] and abs(s["rank"] - r["rank"]) <= radius]
        if not candidates:
            continue
        gap = min(abs(s["rank"] - r["rank"]) for s in candidates)
        nearest = [s for s in candidates if abs(s["rank"] - r["rank"]) == gap]
        paired.append(dict(radius=radius, board=r["board"], date=r["date"], id=r["id"],
                           group=r["group_id"], rank=r["rank"], y=r["y"], closest_ranks=gap,
                           control_ids="|".join(s["id"] for s in nearest),
                           control_y=mean(s["y"] for s in nearest)))
    return paired


def probabilities(train, test, predictor):
    # Normalize entry rank in units of about one SD over the 1..100 positions.
    # Board-specific initial rank slopes; fixed L2 penalty, selected without test outcomes.
    def design(rows):
        matrix = []
        for r in rows:
            rank = (r["rank"] - 50.5) / 29
            boards = [float(r["board"] == b) for b in ("real", "ai", "comic")]
            row = [1., rank, *boards, *(rank * x for x in boards)]
            if predictor:
                row.append(r[predictor])
            matrix.append(row)
        return np.array(matrix)
    x = design(train)
    y = np.array([r["y"] for r in train])
    beta = np.zeros(x.shape[1])
    penalty = np.eye(len(beta))
    penalty[0, 0] = 0
    for _ in range(100):
        p = 1 / (1 + np.exp(-(x @ beta)))
        gradient = x.T @ (p - y) + penalty @ beta
        hessian = x.T @ ((p * (1 - p))[:, None] * x) + penalty
        step = np.linalg.solve(hessian, gradient)
        beta -= step
        if np.max(np.abs(step)) < 1e-9:
            break
    return 1 / (1 + np.exp(-(design(test) @ beta)))


def main():
    with (HERE / "entry_events.csv").open(encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["complete_window"] == "1" and r["x"] in ("0","1")]
    for r in rows:
        for key in ("rank", "x", "x_title_asof", "y"):
            r[key] = int(r[key])
    pairs = []
    for radius in (5, 10):
        group = compare_neighbors(rows, radius)
        pairs.extend(group)
        print("Matched",radius,len(group),round(mean(r["y"] for r in group),4),
              round(mean(r["control_y"] for r in group),4))
    write_table("same_day_pairs.csv", pairs)
    train = [r for r in rows if r["date"] < "2026-11-01"]
    test = [r for r in rows if r["date"] >= "2026-11-01"]
    assert max(r["day7_date"] for r in train) < min(r["date"] for r in test)
    actual = np.array([r["y"] for r in test])
    summary = []
    for predictor in (None, "x", "x_title_asof"):
        predicted = probabilities(train, test, predictor)
        summary.append(dict(added_predictor=predictor or "none", train_n=len(train), test_n=len(test),
                            train_last_event=max(r["date"] for r in train),
                            test_first_event=min(r["date"] for r in test),
                            test_last_event=max(r["date"] for r in test),
                            brier=np.mean((predicted-actual)**2), average_prediction=np.mean(predicted),
                            observed_rate=np.mean(actual)))
    write_table("time_split.csv", summary)
    for item in summary:
        print(item)
    print("Counts",Counter((r["x"],r["y"]) for r in rows))


if __name__ == "__main__":
    main()
