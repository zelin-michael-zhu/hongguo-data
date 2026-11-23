"""Time-purged forecast of a title's first observed entry into any Hongguo top 20."""

import csv
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hongguo_franchise_forecast_2026-11-21"))
from forecast import logistic, preprocess, binary_scores

FOLDS = (
    ("2026-11-02", "2026-11-06"),
    ("2026-11-10", "2026-11-11"),
    ("2026-11-12", "2026-11-14"),
)
FRESH_FOLDS = (
    ("2026-11-02", "2026-11-06"),
    ("2026-11-07", "2026-11-11"),
    ("2026-11-12", "2026-11-14"),
)
MODELS = ("rank", "state", "trend", "content")
LIVE = "2026-11-21"
RIDGE = 10.0
GENRES = (
    "tag_romance",
    "tag_urban",
    "tag_historical",
    "tag_action",
    "tag_fantasy",
    "tag_family",
    "tag_suspense",
    "tag_rebirth",
)


def read(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields=None):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields if fields else rows[0])
        w.writeheader()
        w.writerows(rows)


def val(r, key):
    return np.nan if r.get(key, "") == "" else float(r[key])


def features(rows, model):
    result = []
    for r in rows:
        vec = [int(r["rank"])]
        if model != "rank":
            vec += [r["board"] == b for b in ("real", "ai", "comic")]
            vec += [int(r["age"])]
        if model in ("trend", "content"):
            vec += [
                val(r, k)
                for k in (
                    "rank_gain2",
                    "days_seen3",
                    "up_steps",
                    "heat_growth2",
                    "heat_accel",
                    "cross_boards",
                )
            ]
            vec += [np.log1p(val(r, "heat"))]
        if model == "content":
            vec += [
                np.log1p(val(r, k))
                for k in ("episodes", "season_number", "prior_sibling_count7")
            ]
            vec += [val(r, k) for k in (*GENRES, "theme_share")]
        result.append(vec)
    return np.array(result, float)


def fit_predict(train, test, model):
    x, z = preprocess(features(train, model), features(test, model))
    y = np.array([int(r["y7"]) for r in train])
    reg = RIDGE * np.eye(x.shape[1])
    reg[0, 0] = 0.0
    beta = logistic(x, y, reg)
    if model == "rank" and x.shape[1] > 1 and beta[1] > 0:
        # Current rank is the fixed operational ordering. An unsupported reversed relation
        # can only flatten its probability estimates, not reverse that ordering.
        return np.full(len(test), y.mean())
    return 1 / (1 + np.exp(-np.clip(z @ beta, -35, 35)))


def predict(train, test, fold):
    assert train and test and {r["id"] for r in train}.isdisjoint(r["id"] for r in test)
    output = [
        dict(
            date=r["date"],
            id=r["id"],
            title=r["title"],
            board=r["board"],
            rank=r["rank"],
            age=r["age"],
            rank_lag2=r["rank_lag2"],
            rank_gain2=r["rank_gain2"],
            days_seen3=r["days_seen3"],
            cross_boards=r["cross_boards"],
            heat_growth2=r["heat_growth2"],
            first_date=r["first_date"],
            web_age=r["web_age"],
            web_first_visible=r["web_first_visible"],
            fold=fold,
            y7=r["y7"],
        )
        for r in test
    ]
    for model in MODELS:
        probabilities = fit_predict(train, test, model)
        groups = defaultdict(list)
        for p, r in zip(probabilities, output):
            r["score_" + model] = float(p)
            groups[r["date"]].append(r)
        for dayrows in groups.values():
            ordered = sorted(
                dayrows, key=lambda r: (-r["score_" + model], int(r["rank"]), r["id"])
            )
            if model == "rank":
                assert [r["id"] for r in ordered] == [
                    r["id"]
                    for r in sorted(dayrows, key=lambda r: (int(r["rank"]), r["id"]))
                ]
            for order, r in enumerate(ordered, 1):
                r["order_" + model] = order
    return output


def metrics(rows, model, capacity=10):
    y = np.array([int(r["y7"]) for r in rows])
    scores = np.array([r["score_" + model] for r in rows])
    probability_auc, probability_ap, _, _ = binary_scores(y, scores)
    if model == "rank":
        # The operational baseline orders raw rank, even when a fold has no support
        # for a monotone probability slope. Keep ordering and calibration separate.
        auc, ap, _, _ = binary_scores(y, -np.array([int(r["rank"]) for r in rows]))
    else:
        auc, ap = probability_auc, probability_ap
    selected = [r for r in rows if r["order_" + model] <= capacity]
    successes = [r for r in selected if r["y7"] == "1"]
    return dict(
        model=model,
        n=len(rows),
        titles=len({r["id"] for r in rows}),
        positives=int(y.sum()),
        positive_titles=len({r["id"] for r in rows if r["y7"] == "1"}),
        days=len({r["date"] for r in rows}),
        hits=len(successes),
        picks=len(selected),
        precision=len(successes) / len(selected),
        recall=len(successes) / int(y.sum()) if y.sum() else "",
        brier=float(np.mean((y - scores) ** 2)),
        ap=ap,
        auc=auc,
        probability_ap=probability_ap,
        probability_auc=probability_auc,
        observed=float(y.mean()),
        mean_probability=float(scores.mean()),
        unique_selected=len({r["id"] for r in selected}),
        unique_hits=len({r["id"] for r in successes}),
    )


def load_panel(fresh=False):
    prefix = "broad_" if fresh else ""
    panel = read(prefix + "panel.csv")
    metadata = read(prefix + "content.csv")
    content = {(r["date"], r["id"]): r for r in metadata}
    assert len(content) == len(metadata) == len(panel)
    for r in panel:
        c = content[(r["date"], r["id"])]
        for k in (
            *GENRES,
            "episodes",
            "season_number",
            "prior_sibling_count7",
            "theme_share",
            "web_age",
            "web_first_visible",
        ):
            r[k] = c.get(k, "")
    return panel


def train_date_limit(start, live):
    latest = date.fromisoformat(start) - timedelta(days=7)
    return (latest if live else latest - timedelta(days=1)).isoformat()


def fresh_panel():
    from panel import observed_charts, complete_dates

    _, boards = observed_charts()
    covered = complete_dates(boards, 20)
    rows = load_panel(fresh=True)
    keep = []
    issues = []
    for r in rows:
        if not r["web_first_visible"]:
            continue
        first = date.fromisoformat(r["web_first_visible"])
        if r["first_date"] > r["date"] or r["first_date"] < r["web_first_visible"]:
            issues.append(
                {
                    k: r[k]
                    for k in (
                        "date",
                        "id",
                        "title",
                        "first_date",
                        "web_first_visible",
                        "web_age",
                    )
                }
            )
            continue
        if int(r["web_age"]) not in range(3, 8):
            continue
        if all(first - timedelta(days=i) in covered for i in range(1, 8)):
            keep.append(r)
    write(
        "fresh_date_conflicts.csv",
        issues,
        ("date", "id", "title", "first_date", "web_first_visible", "web_age"),
    )
    horizons = []
    for h in (7, 14, 30):
        k = "y" + str(h)
        labeled = [r for r in keep if r[k] != ""]
        days = sorted({r["date"] for r in labeled})
        eligible_days = [
            d
            for d in days
            if any(
                date.fromisoformat(r["date"]) + timedelta(days=h)
                < date.fromisoformat(d)
                for r in labeled
            )
        ]
        fit_with_positive = [
            d
            for d in eligible_days
            if any(
                r[k] == "1"
                and date.fromisoformat(r["date"]) + timedelta(days=h)
                < date.fromisoformat(d)
                for r in labeled
            )
        ]
        horizons.append(
            dict(
                horizon=h,
                rows=len(labeled),
                titles=len({r["id"] for r in labeled}),
                positive_rows=sum(r[k] == "1" for r in labeled),
                positive_titles=len({r["id"] for r in labeled if r[k] == "1"}),
                origin_days=len(days),
                origin_days_with_previous_labels=len(eligible_days),
                origin_days_with_previous_positive_labels=len(fit_with_positive),
                live_count=sum(r["date"] == LIVE for r in keep),
            )
        )
    write("fresh_horizon_support.csv", horizons)
    return keep


def check_daily_refitting(rows):
    """Test every fresh-title origin with mature outcomes and both classes for training."""
    predictions = []
    for day in sorted({row["date"] for row in rows if row["y7"] != ""}):
        cutoff = train_date_limit(day, live=False)
        train = [row for row in rows if row["y7"] != "" and row["date"] <= cutoff]
        if {row["y7"] for row in train} != {"0", "1"}:
            continue
        test = [row for row in rows if row["date"] == day and row["y7"] != ""]
        predictions.extend(predict(train, test, day))
    write("fresh_daily_refit_oos.csv", predictions)
    evaluations = []
    for day in sorted({row["date"] for row in predictions}):
        daily_rows = [row for row in predictions if row["date"] == day]
        evaluations.extend(
            dict(date=day, **metrics(daily_rows, model)) for model in MODELS
        )
    evaluations.extend(
        dict(date="pooled", **metrics(predictions, model)) for model in MODELS
    )
    write("fresh_daily_refit_eval.csv", evaluations)


def write_case_examples(oos, rows):
    """Verify two illustrative same-board comparisons against the actual future charts."""
    from panel import observed_charts

    chart, _ = observed_charts()
    panel = {(row["date"], row["id"]): row for row in rows}
    scores = {(row["date"], row["id"]): row for row in oos}
    cases = [
        ("2026-11-10", "7703172063460084798"),
        ("2026-11-10", "7704150431571643454"),
        ("2026-11-13", "7704887964689501209"),
        ("2026-11-13", "7705824595416190014"),
    ]
    output = []
    for key in cases:
        row = scores[key]
        item = {
            k: row[k]
            for k in (
                "date",
                "id",
                "title",
                "board",
                "rank",
                "web_age",
                "age",
                "order_rank",
                "order_trend",
                "y7",
            )
        }
        if row["y7"] == "1":
            hit = panel[key]["observed_hit7"]
            ranks = chart[date.fromisoformat(hit)][row["id"]]
            best = min(ranks, key=lambda b: ranks[b]["rank"])
            item.update(first_hit=hit, hit_board=best, hit_rank=ranks[best]["rank"])
        else:
            item.update(first_hit="", hit_board="", hit_rank="")
        output.append(item)
    write("fresh_examples.csv", output)


def main(warmup=7, fresh=False):
    prefix = (
        "fresh_"
        if fresh
        else "" if warmup == 7 else "sensitivity_warmup" + str(warmup) + "_"
    )
    rows = (
        fresh_panel()
        if fresh
        else [r for r in load_panel() if int(r["prior_consecutive_complete"]) >= warmup]
    )
    assert len({(r["date"], r["id"]) for r in rows}) == len(rows)
    oos = []
    scope = []
    evaluations = []
    scheme = FRESH_FOLDS if fresh else FOLDS
    for start, end in (*scheme, (LIVE, LIVE)):
        live = start == LIVE
        fold = "live" if live else start + "_" + end
        cutoff = train_date_limit(start, live)
        train = [r for r in rows if r["y7"] != "" and r["date"] <= cutoff]
        test = [
            r for r in rows if start <= r["date"] <= end and (live or r["y7"] != "")
        ]
        scope.append(
            dict(
                fold=fold,
                train_dates=len({r["date"] for r in train}),
                train=len(train),
                train_titles=len({r["id"] for r in train}),
                train_positive=sum(r["y7"] == "1" for r in train),
                train_positive_titles=len({r["id"] for r in train if r["y7"] == "1"}),
                latest_train_origin=max(r["date"] for r in train),
                latest_train_outcome=(
                    date.fromisoformat(max(r["date"] for r in train))
                    + timedelta(days=7)
                ).isoformat(),
                test=len(test),
                test_days=len({r["date"] for r in test}),
            )
        )
        predicted = predict(train, test, fold)
        if live:
            live_rows = predicted
        else:
            oos.extend(predicted)
            evaluations.extend(dict(fold=fold, **metrics(predicted, m)) for m in MODELS)
    evaluations.extend(dict(fold="pooled", **metrics(oos, m)) for m in MODELS)
    lookup = {(r["fold"], r["model"]): r for r in evaluations}
    folds = [a + "_" + b for a, b in scheme]
    eligible = ["rank"]
    for m in MODELS[1:]:
        delta = [lookup[f, m]["hits"] - lookup[f, "rank"]["hits"] for f in folds]
        if (
            min(delta) >= 0
            and sum(d > 0 for d in delta) >= 2
            and lookup["pooled", m]["brier"] < lookup["pooled", "rank"]["brier"]
            and lookup["pooled", m]["ap"] > lookup["pooled", "rank"]["ap"]
        ):
            eligible.append(m)
    chosen = sorted(
        eligible,
        key=lambda m: (
            -lookup["pooled", m]["hits"],
            lookup["pooled", m]["brier"],
            MODELS.index(m),
        ),
    )[0]
    daily = []
    for day in sorted({r["date"] for r in oos}):
        daily.extend(
            dict(date=day, **metrics([r for r in oos if r["date"] == day], m))
            for m in MODELS
        )
    for r in live_rows:
        r["selected_model"] = chosen
        r["selected_order"] = r["order_" + chosen]
    write(prefix + "oos.csv", oos)
    write(prefix + "eval.csv", evaluations)
    write(prefix + "daily_eval.csv", daily)
    write(prefix + "scores.csv", sorted(live_rows, key=lambda r: r["selected_order"]))
    write(prefix + "folds.csv", scope)
    if fresh:
        check_daily_refitting(rows)
        write_case_examples(oos, rows)
        subgroup_results = []
        for name, lower, upper in (
            ("first_2_chart_days", 1, 2),
            ("chart_day_3_to_7", 3, 7),
        ):
            subset = [r for r in oos if lower <= int(r["age"]) <= upper]
            for m in MODELS:
                subgroup_results.append(
                    dict(
                        chart_age=name,
                        missing_rank_gain2=sum(r["rank_gain2"] == "" for r in subset),
                        **metrics(subset, m)
                    )
                )
        write("fresh_chart_age_eval.csv", subgroup_results)
        capacities = [
            dict(daily_capacity=k, **metrics(oos, model, k))
            for k in (5, 10, 20)
            for model in MODELS
        ]
        write("fresh_capacity_eval.csv", capacities)
    print(
        json.dumps(
            {
                "scope": prefix,
                "warmup": warmup,
                "chosen": chosen,
                "folds": scope,
                "models": [r for r in evaluations if r["fold"] == "pooled"],
            },
            ensure_ascii=False,
            default=float,
        )
    )


if __name__ == "__main__":
    if "--fresh-only" not in sys.argv:
        main()
        main(3)
    main(fresh=True)
