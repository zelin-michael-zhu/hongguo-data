"""Compare episode engagement within verified consecutive seasons."""
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median

import numpy as np

from first_episode_duration import SOURCE, first_episode_sample, read, save, season_pairs


def orient_pairs():
    out = []
    catalog = {r["series_id"]: r for r in read(SOURCE / "series_coverage.csv")}
    for pair in season_pairs(first_episode_sample()):
        old, new = sorted(("long", "short"),
                          key=lambda side: datetime.fromisoformat(pair[side + "_website_first_visible"]))
        assert pair["first_visible_gap_days"] > 0
        row = {k: pair[k] for k in ("group_id", "old_number", "new_number", "duration_gap",
                                    "first_visible_gap_days", "snapshot_gap_seconds")}
        for label, side in (("older", old), ("newer", new)):
            for field in ("id", "title", "duration", "comments", "likes", "website_age_days"):
                row[f"{label}_{field}"] = pair[f"{side}_{field}"]
            sid = row[f"{label}_id"]
            metrics = catalog[sid]
            captured = datetime.fromisoformat(metrics["first_page_collected_at_utc"])
            detail = datetime.fromisoformat(metrics["detail_collected_at_utc"])
            assert abs((captured - detail).total_seconds()) < 600
            row[f"{label}_favorites"] = int(metrics["web_series_favorite"])
            row[f"{label}_per1000likes"] = 1000 * row[f"{label}_comments"] / row[f"{label}_likes"]
        out.append(row)
    return out


def delta(row, feature):
    return np.log(row[f"newer_{feature}"]) - np.log(row[f"older_{feature}"])


def counts(name, rows):
    # Keep equal-duration pairs in the archive but exclude them from sign comparisons.
    chosen = [r for r in rows if r["duration_gap"] > 0]
    signs = np.array([np.sign(delta(r, "duration")) for r in chosen])
    values = {k: signs * np.array([delta(r, k) for r in chosen])
              for k in ("comments", "likes", "per1000likes")}
    return dict(scope=name, pairs=len(chosen), groups=len({r["group_id"] for r in chosen}),
                longer_is_newer=int(sum(signs > 0)),
                **{f"longer_higher_{k}": int(sum(v > 0)) for k, v in values.items()},
                **{f"median_longer_change_{k}_pct": round(100 * float(np.expm1(median(v))), 2)
                   for k, v in values.items()})


def model(name, rows, field, extra=(), use_intercept=True):
    inputs = np.array([[delta(r, "duration"), delta(r, "website_age_days"),
                        *[delta(r, item) for item in extra]] for r in rows])
    x = np.column_stack((inputs, np.ones(len(rows)))) if use_intercept else inputs
    y = np.array([delta(r, field) for r in rows])
    clusters = defaultdict(list)
    for index, row in enumerate(rows):
        clusters[row["group_id"]].append(index)
    groups = list(clusters.values())
    assert np.linalg.matrix_rank(x) == x.shape[1]

    def calculate(indices):
        return float(100 * np.expm1(np.linalg.lstsq(x[indices], y[indices], rcond=None)[0][0] * np.log(2)))

    rng = np.random.default_rng(20261122)
    sampled = (np.asarray([i for g in js for i in groups[g]])
               for js in rng.integers(len(groups), size=(4000, len(groups))))
    estimates = [calculate(index) for index in sampled if np.linalg.matrix_rank(x[index]) == x.shape[1]]
    low, high = np.percentile(estimates, [2.5, 97.5])
    return dict(scope=name, outcome=field, covariates="website_age_days" + "".join("+" + v for v in extra),
                later_season_intercept=use_intercept, pairs=len(rows), series=len(groups),
                pct_for_2x_duration=round(calculate(np.arange(len(rows))), 2),
                bootstrap_low=round(float(low), 2), bootstrap_high=round(float(high), 2),
                bootstrap_draws=len(estimates))


def main():
    rows = orient_pairs()
    biggest = Counter(r["group_id"] for r in rows).most_common(1)[0][0]
    comparisons = [
        ("全部", rows),
        ("官网首见差至多7天", [r for r in rows if r["first_visible_gap_days"] <= 7]),
        ("官网首见差至多14天", [r for r in rows if r["first_visible_gap_days"] <= 14]),
        ("去掉最多配对的系列", [r for r in rows if r["group_id"] != biggest]),
    ]
    results = [counts(name, group) for name, group in comparisons]
    results.extend([
        counts("仅时长差至少10秒", [r for r in rows if r["duration_gap"] >= 10]),
        counts("两季首集点赞数相差不超过20%（对称）",
               [r for r in rows if abs(delta(r, "likes")) <= np.log(1.2)]),
        counts("较新一季首集更长", [r for r in rows if delta(r, "duration") > 0]),
        counts("较早一季首集更长", [r for r in rows if delta(r, "duration") < 0]),
    ])
    models = []
    for name, group in comparisons:
        models.extend(model(name, group, k) for k in ("comments", "likes", "per1000likes"))
        models.append(model(name, group, "comments", extra=("likes",)))
        models.append(model(name, group, "comments", extra=("favorites",)))
    models.extend(model("全部", rows, field, use_intercept=False)
                  for field in ("comments", "likes", "per1000likes"))
    save("首集曝光讨论_前后季明细.csv", rows)
    save("首集曝光讨论_方向核对.csv", results)
    save("首集曝光讨论_配对模型.csv", models)
    for row in results:
        print(row)
    for row in models:
        print(row)


if __name__ == "__main__":
    main()
