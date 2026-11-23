"""Reproduce first-episode duration comparisons using the saved Hongguo pages."""
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "hongguo_expansion_2026-11-21"
TARGET_DAY = "2026-11-21"
BEIJING = ZoneInfo("Asia/Shanghai")


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def first_episode_sample():
    identity = {r["series_id"]: r for r in read(SOURCE / "identity/identity_coverage.csv")}
    episodes = {
        r["series_id"]: r["episode_id"]
        for r in read(SOURCE / "episode_index.csv") if r["episode_position"] == "1"
    }
    sample = {}
    for row in read(SOURCE / "series_coverage.csv"):
        series_id = row["series_id"]
        record = identity[series_id]
        if "ai" not in record["catalog_boards"].split("|") or not row["first_episode_duration_seconds"]:
            continue
        assert row["first_page_status"] == "ok"
        observed = datetime.fromisoformat(row["first_page_collected_at_utc"])
        assert observed.astimezone(BEIJING).date().isoformat() == TARGET_DAY
        first_visible = datetime.fromtimestamp(int(record["first_visible_time"]), timezone.utc)
        assert observed > first_visible
        assert row["first_episode_id"] == episodes[series_id]
        sample[series_id] = dict(
            series_id=series_id, title=row["catalog_title"], group_id=record["series_group_id"],
            boards=record["catalog_boards"], episode_id=row["first_episode_id"],
            captured_at=observed.isoformat(), website_first_visible_at=first_visible.isoformat(),
            website_age_days=(observed - first_visible).total_seconds() / 86400,
            duration=float(row["first_episode_duration_seconds"]),
            comments=int(row["first_episode_comments_total"]), likes=int(row["first_episode_likes"]),
        )
    return sample


def season_pairs(sample):
    pairs = []
    for source in read(SOURCE / "identity/explicit_adjacent_seasons.csv"):
        old, new = (sample.get(source[f"{side}_id"]) for side in ("old", "new"))
        if old is None or new is None:
            continue
        assert old["group_id"] == new["group_id"] == source["group_id"]
        older_time, newer_time = (
            datetime.fromisoformat(row["website_first_visible_at"]) for row in (old, new)
        )
        old_snap, new_snap = (datetime.fromisoformat(row["captured_at"]) for row in (old, new))
        long, short = sorted((old, new), key=lambda row: row["duration"], reverse=True)
        pairs.append(dict(
            group_id=source["group_id"], old_number=source["old_number"], new_number=source["new_number"],
            long_id=long["series_id"], long_title=long["title"].replace("\0", ""),
            short_id=short["series_id"], short_title=short["title"].replace("\0", ""),
            long_captured_at=long["captured_at"], short_captured_at=short["captured_at"],
            long_website_first_visible=long["website_first_visible_at"],
            short_website_first_visible=short["website_first_visible_at"],
            long_website_age_days=long["website_age_days"], short_website_age_days=short["website_age_days"],
            long_duration=long["duration"], short_duration=short["duration"],
            long_comments=long["comments"], short_comments=short["comments"],
            long_likes=long["likes"], short_likes=short["likes"],
            duration_gap=long["duration"]-short["duration"],
            first_visible_gap_days=(newer_time - older_time).total_seconds() / 86400,
            snapshot_gap_seconds=abs((new_snap-old_snap).total_seconds()),
        ))
    return pairs


def model(row, field, paired=False):
    if not paired:
        return [1., np.log(row["duration"]), np.log1p(row["website_age_days"]), np.log1p(row[field])]
    return [1., np.log(row["long_duration"]/row["short_duration"]),
            np.log1p(row["long_website_age_days"]) - np.log1p(row["short_website_age_days"]),
            np.log1p(row[f"long_{field}"]) - np.log1p(row[f"short_{field}"])]


def estimate(rows, field, paired, age_adjusted):
    variables = np.asarray([model(r, field, paired) for r in rows])
    if paired:
        # First differences already absorb shared series levels. A zero difference
        # in both observed inputs maps to a zero predicted difference.
        columns = [1, 2] if age_adjusted else [1]
    else:
        columns = [0, 1, 2] if age_adjusted else [0, 1]
    x, y = variables[:, columns], variables[:, -1]
    group_rows = defaultdict(list)
    for index, row in enumerate(rows):
        group = row["group_id"] or row["series_id"]
        group_rows[group].append(index)
    clusters = list(group_rows.values())

    def coef(indices):
        return np.linalg.lstsq(x[indices], y[indices], rcond=None)[0][columns.index(1)]

    def percentage(slope):
        return 100 * np.expm1(slope * np.log(2))

    rng = np.random.default_rng(20261122)
    replicates = [
        percentage(coef([i for c in groups for i in clusters[c]]))
        for groups in rng.integers(0, len(clusters), (1000, len(clusters)))
    ]
    low, high = np.percentile(replicates, [2.5, 97.5])
    return dict(
        outcome=field, n=len(rows), groups=len(clusters), age_adjusted=age_adjusted,
        percentage_change_for_2x_duration=round(float(percentage(coef(list(range(len(rows)))))), 2),
        bootstrap_low=round(float(low), 2), bootstrap_high=round(float(high), 2),
    )


def main():
    sample = first_episode_sample()
    pairs = season_pairs(sample)
    save("首集时长与互动_相邻季对照.csv", pairs)
    sorted_rows = sorted(sample.values(), key=lambda row: row["duration"])
    quartiles = []
    for index, segment in enumerate(np.array_split(sorted_rows, 4), start=1):
        quartiles.append(dict(
            quartile=index, n=len(segment), duration_min=min(r["duration"] for r in segment),
            duration_max=max(r["duration"] for r in segment), duration_median=median(r["duration"] for r in segment),
            median_comments=median(r["comments"] for r in segment), median_likes=median(r["likes"] for r in segment),
            median_website_age_days=median(r["website_age_days"] for r in segment),
        ))
    save("首集时长与互动_四分位.csv", quartiles)
    matched_ids = {row[f"{side}_id"] for row in pairs for side in ("long", "short")}
    estimates = [
        dict(sample=label, **estimate(rows, field, False, age_adjusted))
        for label, rows in (
            ("ever_ai_archived", list(sample.values())),
            ("ever_ai_archived_duration_at_most_five_minutes",
             [row for row in sample.values() if row["duration"] <= 300]),
            ("paired_titles_cross_section", [sample[series_id] for series_id in sorted(matched_ids)]),
        )
        for field in ("comments", "likes") for age_adjusted in (False, True)
    ]
    estimates.extend(dict(sample="confirmed_adjacent_seasons_positive_gap", **estimate(
        [r for r in pairs if r["first_visible_gap_days"] > 0], field, True, age_adjusted
    )) for field in ("comments", "likes") for age_adjusted in (False, True))
    save("首集时长与互动_对数模型.csv", estimates)
    counts = []
    for available_gap in (None, 7, 14):
        for duration_gap in (0, 10, 20):
            filtered = [row for row in pairs if row["duration_gap"] >= duration_gap
                        and (available_gap is None or 0 < row["first_visible_gap_days"] <= available_gap)]
            different = [row for row in filtered if row["duration_gap"] > 0]
            counts.append(dict(
                max_first_visible_gap_days="all" if available_gap is None else available_gap,
                min_duration_gap_seconds=duration_gap, pairs=len(filtered),
                groups=len({r["group_id"] for r in filtered}),
                equal_duration=len(filtered)-len(different),
                longer_first_episode_more_comments=sum(r["long_comments"] > r["short_comments"] for r in different),
                longer_first_episode_more_likes=sum(r["long_likes"] > r["short_likes"] for r in different),
                equal_comments=sum(r["long_comments"] == r["short_comments"] for r in different),
                equal_likes=sum(r["long_likes"] == r["short_likes"] for r in different),
            ))
    save("首集时长与互动_配对敏感性.csv", counts)
    print("AI-titles / confirmed adjacent pairs:", len(sample), len(pairs))
    print("Snapshot separation seconds min / median / max", min(r["snapshot_gap_seconds"] for r in pairs),
          median(r["snapshot_gap_seconds"] for r in pairs), max(r["snapshot_gap_seconds"] for r in pairs))
    print("Nonpositive season date gaps:", sum(r["first_visible_gap_days"] <= 0 for r in pairs))
    print("Estimates", *estimates, sep="\n")
    print("Pair sensitivity", *counts, sep="\n")


if __name__ == "__main__":
    main()
