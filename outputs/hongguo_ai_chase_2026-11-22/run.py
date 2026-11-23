"""Reproduce the AI-board replay and the blinded comment measurements."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
PILOT = OUTPUTS / "hongguo_sentiment_pilot_2026-11-21"
sys.path.insert(0, str(PILOT))
sys.path.insert(0, str(OUTPUTS / "hongguo_franchise_forecast_2026-11-21"))
from forecast import binary_scores, logistic, preprocess
from rank_baseline import observed_charts
from audit import read_samples

DECISION = "2026-11-21"
TEST_DATES = ("2026-11-02", "2026-11-14")
SCOPES = {"first_episode_comment": "episode", "series_review": "series"}
KEY = ("series_id", "scope", "display_position")
FIELDS = ("quality_positive", "chase_intent", "recommend", "quit_intent",
          "production_criticism", "self_declared_promo")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def number(row, key):
    value = row.get(key)
    return float(value) if value not in (None, "") else np.nan


def labels(path):
    contents = read(path)
    keyed = {tuple(row[k] for k in KEY): {k: int(row[k]) for k in FIELDS} for row in contents}
    assert len(keyed) == len(contents) and all(v in (0, 1) for row in keyed.values() for v in row.values())
    return keyed


def historical_baseline(live):
    charts, _ = observed_charts()
    archive = OUTPUTS / "hongguo_free_pilot_2026-11-18/history/drama_daily.csv"
    observations = {(row["date"], row["id"]): row for row in read(archive)}
    own = {(row["date"], row["id"]): row for row in
           read(OUTPUTS / "hongguo_franchise_forecast_2026-11-21/own.csv") if row["board"] == "ai"}
    historical = [row for row in read(PILOT / "same_board_historical_labeled.csv")
                  if row["board"] == "ai"]
    archived_text = read_samples()
    archived_keys = {(day, row["sid"]) for day, rows in archived_text.items() for row in rows}
    assert len({(r["date"], r["series_id"]) for r in historical}) == len(historical)

    def vector(row, is_live=False):
        day = row["snapshot_date"] if is_live else row["date"]
        sid = row["series_id"]
        dt = date.fromisoformat(day)
        current = own[day, sid]
        review = number(row, "series_review_reported_total") if is_live else number(
            observations.get((day, sid), {}), "review_count")
        lags = [charts.get(dt - timedelta(days=lag), {}).get(sid, {}).get("ai", {}).get("rank")
                for lag in (1, 2)]
        return [int(row["rank"]), int(row["same_board_age"]),
                *[np.log1p(number(current, k)) for k in ("heat", "likes", "favorites")],
                number(current, "rating"), np.log1p(review),
                *[lag - int(row["rank"]) if lag is not None else np.nan for lag in lags]]

    def scores(train, holdout, is_live=False):
        x, z = preprocess(np.asarray([vector(r) for r in train]),
                          np.asarray([vector(r, is_live) for r in holdout]))
        y = np.array([int(r["future_same_board_top20"]) for r in train])
        penalty = 10 * np.eye(x.shape[1])
        penalty[0, 0] = 0
        beta = logistic(x, y, penalty)
        return 1 / (1 + np.exp(-np.clip(z @ beta, -35, 35)))

    def priority(day, group, fit, is_live=False):
        ordered = sorted(group, key=lambda r: (int(r["rank"]), r["series_id"]))
        probs = scores(fit, ordered, is_live)
        positions = {row["series_id"]: i for i, (row, _) in enumerate(
            sorted(zip(ordered, probs), key=lambda pair: (-pair[1], int(pair[0]["rank"]), pair[0]["series_id"])), 1)}
        return [
            dict(date=day, series_id=r["series_id"], title=r["title"], current_rank=r["rank"],
                 chart_age=r["same_board_age"], rank_model_position=i, metrics_model_position=positions[r["series_id"]],
                 metrics_model_score=round(float(score), 6), future_same_board_top20=r["future_same_board_top20"],
                 training_rows=len(fit), training_positives=sum(q["future_same_board_top20"] == "1" for q in fit))
            for i, (r, score) in enumerate(zip(ordered, probs), 1)
        ]

    oos = []
    for day in sorted({r["date"] for r in historical if TEST_DATES[0] <= r["date"] <= TEST_DATES[1]}):
        cut = date.fromisoformat(day)
        fit = [r for r in historical if date.fromisoformat(r["date"]) + timedelta(days=7) < cut]
        actual = [r for r in historical if r["date"] == day]
        assert {r["series_id"] for r in fit}.isdisjoint(r["series_id"] for r in actual)
        if len({r["future_same_board_top20"] for r in fit}) == 2:
            oos.extend(priority(day, actual, fit))
    live_order = priority(DECISION, live, historical, is_live=True)
    assert all(r["future_same_board_top20"] == "" for r in live_order)
    write("历史数值基准逐日回测.csv", oos)
    write("11月21日两种数值基准.csv", live_order)

    y = np.array([int(r["future_same_board_top20"]) for r in oos])
    oos_by_date = defaultdict(list)
    rank_by_date = defaultdict(list)
    for row in oos:
        oos_by_date[row["date"]].append(row)
    for row in sorted(historical, key=lambda r: (r["date"], int(r["rank"]), r["series_id"])):
        rank_by_date[row["date"]].append(row)
    daily = []
    for day, group in sorted(rank_by_date.items()):
        top5 = group[:5]
        numeric = [r for r in oos_by_date[day] if r["metrics_model_position"] <= 5]
        daily.append(dict(date=day, candidates=len(group), positives=sum(int(r["future_same_board_top20"]) for r in group),
                          rank_slots=len(top5), rank_hits=sum(int(r["future_same_board_top20"]) for r in top5),
                          numeric_slots=len(numeric) if numeric else "",
                          numeric_hits=sum(int(r["future_same_board_top20"]) for r in numeric) if numeric else ""))
    write("历次复盘按日汇总.csv", daily)
    comparisons = {}
    for model, values in (("rank", [-int(r["current_rank"]) for r in oos]),
                          ("metrics", [r["metrics_model_score"] for r in oos])):
        auc, ap, _, _ = binary_scores(y, np.array(values))
        outcome = {"ap": ap, "auc": auc}
        for k in (5, 10):
            selected = [r for r in oos if r[f"{model}_model_position"] <= k]
            hits = [r for r in selected if r["future_same_board_top20"] == "1"]
            outcome[f"top{k}"] = dict(slots=len(selected), hits=len(hits),
                                     unique_titles=len({r["series_id"] for r in selected}),
                                     unique_hit_titles=len({r["series_id"] for r in hits}))
        comparisons[model] = outcome
    return dict(labeled_rows=len(historical), labeled_titles=len({r["series_id"] for r in historical}),
                labeled_positive_rows=sum(int(r["future_same_board_top20"]) for r in historical),
                labeled_positive_titles=len({r["series_id"] for r in historical if r["future_same_board_top20"] == "1"}),
                all_rank_days=len(daily), all_rank_slots=sum(r["rank_slots"] for r in daily),
                all_rank_hits=sum(r["rank_hits"] for r in daily),
                oos_rows=len(oos), oos_titles=len({r["series_id"] for r in oos}),
                oos_dates=sorted({r["date"] for r in oos}), oos_positive_rows=int(y.sum()),
                historical_text_archive_dates=sorted(archived_text),
                matched_historical_text_and_label_rows=sum(
                    (r["date"], r["series_id"]) in archived_keys for r in historical),
                comparisons=comparisons)


def reliability(primary, second):
    results = {}
    for field in FIELDS:
        pairs = Counter((primary[key][field], row[field]) for key, row in second.items())
        a, b, c, d = (pairs[0, 0], pairs[0, 1], pairs[1, 0], pairs[1, 1])
        n = a + b + c + d
        expected = ((c + d) * (b + d) + (a + b) * (a + c)) / (n * n)
        results[field] = dict(n=n, both_yes=d, both_no=a, only_primary=c, only_second=b,
                              agreement=(a + d) / n,
                              kappa=((a + d) / n - expected) / (1 - expected) if expected < 1 else None)
    return results


def comment_analysis(live):
    idset = {r["series_id"] for r in live}
    source = [r for r in read(PILOT / "comments_2026-11-21.csv") if r["series_id"] in idset]
    primary = labels(HERE / "labels_a.csv")
    second_half = labels(HERE / "labels_b.csv")
    assert primary.keys().isdisjoint(second_half)
    primary.update(second_half)
    qa = labels(HERE / "labels_qa.csv")
    decision = {r["series_id"]: datetime.fromisoformat(r["decision_at_sh"]) for r in live}
    coded = []
    for row in source:
        key = tuple(row[k] for k in KEY)
        assert row["publication_time_status"] == "valid"
        assert datetime.fromisoformat(row["published_at_sh"]) <= datetime.fromisoformat(
            row["sampled_at_sh"]) <= decision[row["series_id"]]
        coded.append({**{k: row[k] for k in KEY}, "text": row["text"],
                      "sampled_at_sh": row["sampled_at_sh"], **primary[key]})
    assert {tuple(r[k] for k in KEY) for r in source} == primary.keys()
    assert len(source) == len(primary) and qa.keys() <= primary.keys()
    write("逐条评论编码.csv", coded)
    by_title = defaultdict(list)
    for item in coded:
        by_title[item["series_id"]].append(item)
    features = []
    for row in live:
        sid = row["series_id"]
        feature = {k: row[k] for k in ("series_id", "title", "rank", "same_board_age", "decision_at_sh",
                                        "forecast_window_start", "forecast_window_end", "future_same_board_top20")}
        feature["title"] = feature["title"].replace("\x00", " ")
        for scope, prefix in SCOPES.items():
            subset = [r for r in by_title[sid] if r["scope"] == scope]
            clean = [r for r in subset if not r["self_declared_promo"]]
            assert subset
            feature[f"{prefix}_n"] = len(subset)
            feature[f"{prefix}_nonpromo_n"] = len(clean)
            for name in FIELDS:
                feature[f"{prefix}_{name}"] = sum(r[name] for r in subset)
            feature[f"{prefix}_chase_share_nonpromo"] = round(sum(r["chase_intent"] for r in clean) / len(clean), 6) if clean else ""
            feature[f"{prefix}_positive_share_nonpromo"] = round(sum(r["quality_positive"] for r in clean) / len(clean), 6) if clean else ""
        features.append(feature)
    write("AI榜22部逐剧信号.csv", features)

    summary = {}
    for scope, prefix in SCOPES.items():
        rows = [r for r in coded if r["scope"] == scope]
        clean = [r for r in rows if not r["self_declared_promo"]]
        summary[prefix] = dict(n=len(rows), nonpromo_n=len(clean),
                               totals={k: sum(r[k] for r in rows) for k in FIELDS},
                               clean_positive=sum(r["quality_positive"] for r in clean),
                               clean_chase=sum(r["chase_intent"] for r in clean),
                               clean_chase_without_positive=sum(r["chase_intent"] and not r["quality_positive"] for r in clean),
                               titles_with_chase=len({r["series_id"] for r in clean if r["chase_intent"]}))
    diff = [r["series_chase_share_nonpromo"] - r["episode_chase_share_nonpromo"] for r in features]
    start = {row["series_id"]: row["same_board_first_observed"] for row in live}
    return dict(live_titles=len(live), valid_text=len(coded),
                text_outcome_pairs=sum(r["future_same_board_top20"] != "" for r in live),
                text_published_before_chart_first_seen=sum(r["published_at_sh"][:10] < start[r["series_id"]] for r in source),
                paired_series_higher=sum(x>0 for x in diff), paired_equal=sum(x==0 for x in diff),
                paired_episode_higher=sum(x<0 for x in diff), paired_median_difference=median(diff),
                channels=summary, reliability=reliability(primary, qa))


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--baseline-only", action="store_true")
    opts = cli.parse_args()
    live = sorted((r for r in read(PILOT / "features_2026-11-21.csv") if r["target_board"] == "ai"),
                  key=lambda r: (int(r["rank"]), r["series_id"]))
    seed = {r["series_id"] for r in read(PILOT / "cohort_seed.csv") if r["board"] == "ai"}
    assert seed == {r["series_id"] for r in live} and len(seed) == len(live)
    counts = historical_baseline(live)
    if not opts.baseline_only:
        counts.update(comment_analysis(live))
    (HERE / "结果核验.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
