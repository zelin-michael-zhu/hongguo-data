"""Compare Hongguo's displayed title rating with ratings on its public review cards."""
import csv
from collections import defaultdict
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "hongguo_expansion_2026-11-21"


def read(name):
    with (SOURCE / name).open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rounded(value):
    return round(float(value), 8)


def input_rows():
    catalog = {
        row["series_id"]: row["catalog_boards"]
        for row in read("identity/identity_coverage.csv")
        if "ai" in row["catalog_boards"].split("|")
    }
    works = {
        row["series_id"]: row for row in read("series_coverage.csv")
        if row["series_id"] in catalog and row["series_rating"]
    }
    reviews = defaultdict(list)
    for row in read("reviews_preview.csv"):
        if row["series_id"] in works and row["scope"] == "series_review" and row["rating"]:
            reviews[row["series_id"]].append(row)
    for sid, cards in sorted(reviews.items()):
        cards.sort(key=lambda row: int(row["display_position"]))
        works_row = works[sid]
        ratings = [Fraction(row["rating"]) for row in cards]
        assert len({row["display_position"] for row in cards}) == len(cards)
        assert all(row["collected_at_utc"] == works_row["detail_collected_at_utc"] for row in cards)
        assert all(0 <= rate <= 10 for rate in ratings)
        yield {
            "series_id": sid, "title": works_row["catalog_title"],
            "catalog_boards": catalog[sid], "detail_collected_at_utc": works_row["detail_collected_at_utc"],
            "title_rating": Fraction(works_row["series_rating"]),
            "title_rating_count": int(works_row["series_rating_count"]),
            "cards": ratings, "url": cards[0]["source_url"],
        }


def compare(rows, scope, card_count=None):
    pairs = [(row["title_rating"], mean(row["cards"][:card_count])) for row in rows]
    gaps = [preview - title for title, preview in pairs]
    separated = [
        (left[0] - right[0], left[1] - right[1])
        for left, right in combinations(pairs, 2)
        if abs(left[0] - right[0]) >= Fraction(1, 2)
    ]
    return {
        "scope": scope, "cards_used": card_count or "all_visible", "titles": len(rows),
        "mean_preview_minus_title": rounded(mean(gaps)),
        "median_preview_minus_title": rounded(median(gaps)),
        "mean_abs_gap": rounded(mean(abs(gap) for gap in gaps)),
        "at_least_1_point_above": sum(gap >= 1 for gap in gaps),
        "at_least_1_point_below": sum(gap <= -1 for gap in gaps),
        "pairs_at_least_half_point_apart_on_title": len(separated),
        "pairs_preview_reversed": sum(left * right < 0 for left, right in separated),
        "pairs_preview_tied": sum(right == 0 for _, right in separated),
    }


def main():
    rows = list(input_rows())
    nine = [row for row in rows if len(row["cards"]) == 9]
    high_count = [row for row in nine if row["title_rating_count"] >= 1000]
    summaries = [compare(rows, "all_paired")]
    for scope, group in (("same_nine_card_titles", nine), ("same_nine_card_titles_raters_ge_1000", high_count)):
        summaries.extend(compare(group, scope, n) for n in (1, 3, 5, 9))
    write("剧评与作品评分_汇总.csv", summaries)

    thresholds = []
    for threshold in map(Fraction, ("8", "8.5", "9")):
        pairs = [(row["title_rating"] >= threshold, mean(row["cards"]) >= threshold) for row in rows]
        thresholds.append({
            "rating_threshold": float(threshold), "titles": len(pairs),
            "page_score_and_review_mean_meet": pairs.count((True, True)),
            "page_score_only_meets": pairs.count((True, False)),
            "review_mean_only_meets": pairs.count((False, True)),
            "neither_meets": pairs.count((False, False)),
        })
    write("剧评与作品评分_阈值.csv", thresholds)
    details = []
    for row in rows:
        card_mean = mean(row["cards"])
        details.append({
            **{k: row[k] for k in ("series_id", "title", "catalog_boards", "detail_collected_at_utc")},
            "title_rating": float(row["title_rating"]), "title_rating_count": row["title_rating_count"],
            "review_card_count": len(row["cards"]),
            "review_card_ratings_by_display_position": "|".join(str(rating) for rating in row["cards"]),
            "review_card_mean": rounded(card_mean),
            "review_minus_title": rounded(card_mean - row["title_rating"]), "url": row["url"],
        })
    write("剧评与作品评分_逐剧.csv", details)
    print(summaries[0])


if __name__ == "__main__":
    main()
