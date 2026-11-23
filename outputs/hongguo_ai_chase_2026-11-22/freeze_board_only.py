"""Freeze 21 November predictions using only AI chart positions and published heat."""
import csv
from datetime import date, timedelta
import hashlib
from io import StringIO

import numpy as np

from run import DECISION, HERE, PILOT, logistic, observed_charts, preprocess, read


def fit_scores(charts, train, holdout):
    def vector(row):
        day = date.fromisoformat(row["date"])
        sid = row["series_id"]
        observed = charts[day][sid]["ai"]
        rank = int(row["rank"])
        assert observed["rank"] == rank
        lags = [charts.get(day - timedelta(days=lag), {}).get(sid, {}).get("ai", {}).get("rank")
                for lag in (1, 2)]
        heat = np.log1p(observed["heat"]) if observed["heat"] is not None else np.nan
        return [rank, int(row["same_board_age"]), heat,
                *[lag - rank if lag is not None else np.nan for lag in lags]]

    x, z = preprocess(np.asarray([vector(r) for r in train]), np.asarray([vector(r) for r in holdout]))
    y = np.asarray([int(r["future_same_board_top20"]) for r in train])
    penalty = 10 * np.eye(x.shape[1])
    penalty[0, 0] = 0
    beta = logistic(x, y, penalty)
    return 1 / (1 + np.exp(-np.clip(z @ beta, -35, 35)))


def main():
    charts, _ = observed_charts()
    day = date.fromisoformat(DECISION)
    train = [r for r in read(PILOT / "same_board_historical_labeled.csv")
             if r["board"] == "ai" and date.fromisoformat(r["date"]) + timedelta(days=7) <= day]
    live = [{**r, "date": r["snapshot_date"]} for r in read(PILOT / "features_2026-11-21.csv")
            if r["target_board"] == "ai" and r["snapshot_date"] == DECISION]
    assert len(train) == 424 and len(live) == 22
    assert {r["series_id"] for r in train}.isdisjoint(r["series_id"] for r in live)
    paired = sorted(zip(live, fit_scores(charts, train, live)),
                    key=lambda pair: (-pair[1], int(pair[0]["rank"]), pair[0]["series_id"]))
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(("series_id", "board_only_score", "board_only_order"))
    for order, (row, score) in enumerate(paired, 1):
        writer.writerow((row["series_id"], f"{score:.10f}", order))
    output = HERE / "board_only_baseline.csv"
    data = buffer.getvalue().encode("utf-8-sig")
    try:
        with output.open("xb") as handle:
            handle.write(data)
    except FileExistsError:
        if output.read_bytes() != data:
            raise RuntimeError("Board-only baseline already frozen with different scores")
    print(f"22 frozen chart-only scores from 424 mature training rows. SHA-256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
