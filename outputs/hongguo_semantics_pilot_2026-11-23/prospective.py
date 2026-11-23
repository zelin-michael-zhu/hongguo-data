"""Register future visible-preview features before outcomes, then compare matched forecasts."""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from zoneinfo import ZoneInfo

import numpy as np
from labels import HERE, DIMENSIONS, TAGS, read, validated

OUTPUTS = HERE.parent
DAILY = OUTPUTS / "hongguo_ai_chase_2026-11-22" / "daily"
SNAPSHOTS = OUTPUTS / "hongguo_sentiment_pilot_2026-11-21" / "snapshots"
FUTURE = HERE / "prospective"
RULES = HERE / "三维评论标注口径.md"
PROTOCOL = HERE / "semantics_protocol.json"
ZONE = ZoneInfo("Asia/Shanghai")
HORIZON = 7
MIN_TRAIN_ROWS = 30
MIN_TRAIN_DATES = 4
MIN_EXAMPLES_PER_CLASS = 5
RIDGE = 10
SCOPES = ("first_episode_comment", "series_review")
sys.path.insert(0, str(OUTPUTS / "hongguo_franchise_forecast_2026-11-21"))
from forecast import binary_scores, logistic, preprocess


def now():
    return datetime.now(ZONE)


def json_string(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_once(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        scratch = Path(handle.name)
        try:
            handle.write(body.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
            try:
                os.link(scratch, path)
            except FileExistsError:
                if path.read_bytes() != body.encode("utf-8"):
                    raise ValueError(f"Frozen file already differs: {path}")
        finally:
            scratch.unlink()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def hashes():
    paths = (Path(__file__).resolve(), RULES, HERE / "labels.py",
             OUTPUTS / "hongguo_franchise_forecast_2026-11-21" / "forecast.py")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def lock():
    if not PROTOCOL.exists():
        write_once(PROTOCOL, json_string({
            "registered_at_sh": now().isoformat(timespec="seconds"), "sha256": hashes(),
            "primary_metric": "Brier score", "horizon_days": HORIZON, "outcome": "future_same_AI_board_top20",
            "training_min_rows": MIN_TRAIN_ROWS, "training_min_dates": MIN_TRAIN_DATES,
            "training_min_per_class": MIN_EXAMPLES_PER_CLASS, "ridge": RIDGE,
        }))
    verify()


def verify():
    protocol = load(PROTOCOL)
    if protocol["sha256"] != hashes():
        raise ValueError("Frozen annotation or analysis rules changed")
    return datetime.fromisoformat(protocol["registered_at_sh"])


def rows_csv(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def prepare(day, frozen_at):
    source = DAILY / day
    folder = FUTURE / day
    manifest = folder / "manifest.json"
    if manifest.exists():
        print(manifest)
        return
    batch = load(source / "batch.json")
    cutoff = datetime.fromisoformat(batch["decision_at"])
    if cutoff.date().isoformat() != day or not frozen_at < cutoff <= now() or now().date().isoformat() != day:
        raise ValueError("New cohorts need a same-day, post-protocol decision snapshot")
    seen = {r["series_id"] for r in read(HERE / "11月21日_标注索引.csv")}
    for earlier in sorted(FUTURE.glob("????-??-??/manifest.json")):
        if earlier.parent.name < day:
            seen.update(item["series_id"] for item in load(earlier)["titles"])
    titles = [r for r in read(source / "cohort.csv") if r["forecast_eligible"] == "1" and r["series_id"] not in seen]
    texts = []
    for title in titles:
        sid = title["series_id"]
        for scope in SCOPES:
            path = SNAPSHOTS / day / f"{sid}_{scope}.json"
            page = load(path)
            sampled = datetime.fromisoformat(page["sampled_at_sh"])
            if (scope != page["scope"] or sid != page["series_id"]
                    or not datetime.fromisoformat(title["chart_snapshot_completed_sh"]) <= sampled <= cutoff):
                raise ValueError(f"Out-of-window or mismatched source: {path}")
            if scope == "series_review":
                title["series_review_total"] = page["reported_total"]
            for review in page["rows"]:
                raw = str(review.get("comment_time") or "")
                if review["text"].strip() and raw.isdecimal() and 0 < int(raw) <= sampled.timestamp():
                    texts.append(dict(series_id=sid, scope=scope, position=review["position"], text=review["text"]))
    texts.sort(key=lambda r: hashlib.sha256(f"{day}|{r['series_id']}|{r['scope']}|{r['position']}".encode()).hexdigest())
    for index, row in enumerate(texts, 1):
        row["row_id"] = index
    write_once(folder / "blind.csv", rows_csv(({"row_id": r["row_id"], "text": r["text"]} for r in texts),
                                               ("row_id", "text")))
    write_once(manifest, json_string({"date": day, "data_at": cutoff.isoformat(), "titles": titles,
                                      "rows": [{k: v for k, v in r.items() if k != "text"} for r in texts]}))
    print(json_string({"manifest": str(manifest), "titles": len(titles), "texts": len(texts)}), end="")


def outcome(day, as_of):
    pairs = set()
    for lag in range(1, HORIZON + 1):
        dt = (date.fromisoformat(day) + timedelta(days=lag)).isoformat()
        chart = DAILY / dt / "chart.json"
        if dt > as_of or not chart.exists():
            return None
        board = load(chart)
        entries = board["records"]
        if (board["date"] != dt or len(entries) != 100 or {int(r["rank"]) for r in entries} != set(range(1, 101))
                or len({str(r["id"]) for r in entries}) != 100):
            return None
        pairs.update(str(r["id"]) for r in entries if int(r["rank"]) <= 20)
    return pairs


def vectors(row, use_semantics):
    f = lambda key: float(row[key]) if row.get(key) not in ("", None) else np.nan
    values = [f("rank"), f("same_board_age"), f("rank_lag1"), f("rank_lag2"), f("rating"),
              *[np.log1p(f(key)) for key in ("heat", "likes", "favorites", "series_review_total")],
              row["positive_share"]]
    if use_semantics:
        values.extend(row[key] for key in DIMENSIONS)
    return values


def forecasts(day, features):
    train = []
    dates = set()
    for path in sorted(FUTURE.glob("????-??-??/registered.json")):
        prior = load(path)
        dt = prior["date"]
        target = outcome(dt, (date.fromisoformat(day) - timedelta(days=1)).isoformat()) if dt < day else None
        if target is None or not prior["features"]:
            continue
        dates.add(dt)
        train.extend((row, int(row["series_id"] in target)) for row in prior["features"])
    if {r["series_id"] for r in features} & {r["series_id"] for r, _ in train}:
        raise ValueError("Forecast titles leaked into training")
    info = {"training_dates": len(dates), "training_rows": len(train), "training_hits": sum(y for _, y in train)}
    y = np.array([y for _, y in train])
    if (not features or len(dates) < MIN_TRAIN_DATES or len(train) < MIN_TRAIN_ROWS
            or min(info["training_hits"], len(train) - info["training_hits"]) < MIN_EXAMPLES_PER_CLASS):
        return info, []
    preds = {}
    for key, use_semantics in (("positive", False), ("semantics", True)):
        x, z = preprocess(np.array([vectors(row, use_semantics) for row, _ in train]),
                          np.array([vectors(row, use_semantics) for row in features]))
        penalty = RIDGE * np.eye(x.shape[1])
        penalty[0, 0] = 0
        beta = logistic(x, y, penalty)
        preds[key] = 1 / (1 + np.exp(-np.clip(z @ beta, -35, 35)))
    return info, [{"series_id": row["series_id"], **{key: float(vals[i]) for key, vals in preds.items()}}
                  for i, row in enumerate(features)]


def register(day):
    folder = FUTURE / day
    record = folder / "registered.json"
    if record.exists():
        print(record)
        return
    if now().date().isoformat() != day:
        raise ValueError("Registration must finish on the forecast day")
    manifest = load(folder / "manifest.json")
    expected = {r["row_id"] for r in manifest["rows"]}
    tags = validated(folder / "labels.json", expected) if expected else {tag: set() for tag in TAGS}
    by_title = defaultdict(set)
    for row in manifest["rows"]:
        if row["row_id"] not in tags["promo"]:
            by_title[row["series_id"]].add(row["row_id"])
    features = []
    for row in manifest["titles"]:
        ids = by_title[row["series_id"]]
        if not ids:
            continue
        counts = {tag: len(ids & values) for tag, values in tags.items()}
        features.append({**row, "audience_preview_n": len(ids),
                         "positive_share": counts["overall_positive"] / len(ids),
                         **{key: (counts[pos] - counts[neg]) / len(ids) for key, (pos, neg) in DIMENSIONS.items()}})
    info, predictions = forecasts(day, features)
    registered = now()
    if registered.date().isoformat() != day:
        raise ValueError("Registration crossed the forecast-day boundary")
    write_once(record, json_string({"date": day, "registered_at_sh": registered.isoformat(),
                                    "features": features, "training": info, "predictions": predictions}))
    print(json_string({"date": day, "feature_rows": len(features), "prediction_rows": len(predictions), **info}), end="")


def review():
    result = []
    not_ready = []
    today = now().date().isoformat()
    registered = [load(path) for path in sorted(FUTURE.glob("????-??-??/registered.json"))]
    for batch in registered:
        if not batch["predictions"]:
            continue
        target = outcome(batch["date"], today)
        if target is None:
            not_ready.append(batch["date"])
            continue
        result.extend(dict(row, date=batch["date"], actual=int(row["series_id"] in target))
                      for row in batch["predictions"])
    score = {}
    if result:
        y = np.array([row["actual"] for row in result])
        for key in ("positive", "semantics"):
            p = np.array([row[key] for row in result])
            _, ap, _, _ = binary_scores(y, p)
            score[key] = {"brier": float(np.mean((y - p) ** 2)), "average_precision": float(ap) if ap != "" else None}
    summary = dict(registered_dates=len(registered), registered_titles=sum(len(x["features"]) for x in registered),
                   evaluated_dates=len({row["date"] for row in result}), evaluated_titles=len(result),
                   future_window_pending_or_incomplete=not_ready, hits=sum(row["actual"] for row in result),
                   scores=score, per_date_n=dict(Counter(row["date"] for row in result)), predictions=result)
    FUTURE.mkdir(exist_ok=True)
    temp = FUTURE / ".validation.tmp"
    temp.write_text(json_string(summary), encoding="utf-8")
    temp.replace(FUTURE / "validation.json")
    print(json_string({k: v for k, v in summary.items() if k != "predictions"}), end="")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("freeze", "prepare", "register", "review"))
    args = ap.parse_args()
    if args.action == "freeze":
        lock()
    else:
        frozen_at = verify()
        if args.action == "prepare":
            prepare(now().date().isoformat(), frozen_at)
        elif args.action == "register":
            register(now().date().isoformat())
        else:
            review()


if __name__ == "__main__":
    main()
