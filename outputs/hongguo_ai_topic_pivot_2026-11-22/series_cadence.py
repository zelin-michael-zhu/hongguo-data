"""Replay first-visible date gaps for already observed adjacent Hongguo seasons.

The sample is conditioned on both seasons appearing in the saved catalogue.
Historical medians use only pairs whose later season was visible by the replay origin.
The timestamps come from the public detail pages, not from production records.
"""

import csv
from datetime import date, datetime
from pathlib import Path
from statistics import mean, median
from zoneinfo import ZoneInfo


HERE = Path(__file__).resolve().parent
IDENTITY = HERE.parent / "hongguo_expansion_2026-11-21" / "identity"
SHANGHAI = ZoneInfo("Asia/Shanghai")
MIN_OTHER_PAIRS = 10


def read(name):
    with (IDENTITY / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def season_pairs():
    details = {row["series_id"]: row for row in read("identity_coverage.csv")}
    pairs = []
    for pair in read("explicit_adjacent_seasons.csv"):
        earlier = details[pair["old_id"]]
        later = details[pair["new_id"]]
        origin, observed = (
            datetime.fromtimestamp(int(row["first_visible_time"]), SHANGHAI)
            for row in (earlier, later)
        )
        if origin >= observed:
            continue
        pairs.append(
            {
                "group_id": pair["group_id"],
                "earlier_title": pair["old_title"],
                "later_title": pair["new_title"],
                "earlier_id": pair["old_id"],
                "later_id": pair["new_id"],
                "origin_time": origin,
                "observed_time": observed,
                "observed_gap_days": (observed.date() - origin.date()).days,
                "earlier_catalogue_boards": earlier["catalog_boards"],
                "later_catalogue_boards": later["catalog_boards"],
            }
        )
    return sorted(pairs, key=lambda pair: (pair["origin_time"], pair["earlier_id"]))


def replay(pairs, exclude_same_day=False):
    if exclude_same_day:
        pairs = [pair for pair in pairs if pair["observed_gap_days"] != 0]
    results = []
    for pair in pairs:
        past = [earlier for earlier in pairs if earlier["observed_time"] <= pair["origin_time"]]
        others = [
            earlier["observed_gap_days"] for earlier in past
            if earlier["group_id"] != pair["group_id"]
        ]
        own = [
            earlier["observed_gap_days"] for earlier in past
            if earlier["group_id"] == pair["group_id"]
        ]
        if not own or len(others) < MIN_OTHER_PAIRS:
            continue
        baseline, history = median(others), median(own)
        results.append(
            {
                **pair,
                "prior_other_pairs": len(others),
                "prior_own_pairs": len(own),
                "other_series_median_days": baseline,
                "own_series_median_days": history,
                "other_series_abs_error": abs(pair["observed_gap_days"] - baseline),
                "own_series_abs_error": abs(pair["observed_gap_days"] - history),
            }
        )
    return results


def summary(pairs):
    return {
        "pairs": len(pairs),
        "series": len({pair["group_id"] for pair in pairs}),
        "later_in_ai_catalogue": sum("ai" in pair["later_catalogue_boards"].split("|") for pair in pairs),
        "later_in_comic_catalogue": sum("comic" in pair["later_catalogue_boards"].split("|") for pair in pairs),
    }


def both_in_board(pairs, board):
    return [
        pair for pair in pairs
        if all(
            board in pair[f"{role}_catalogue_boards"].split("|")
            for role in ("earlier", "later")
        )
    ]


def main():
    pairs = season_pairs()
    tested = replay(pairs)
    print("Source:", summary(pairs))
    path = HERE / "相邻季首次可见_时序比较.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(tested[0]))
        writer.writeheader()
        writer.writerows(tested)
    for label, rows in (
        ("All replayed", tested),
        ("Origin on or after October 13", [r for r in tested if r["origin_time"].date() >= date(2026, 10, 13)]),
        ("Excluding same-day pairs", replay(pairs, exclude_same_day=True)),
        ("Only pairs with both seasons in the AI catalogue", replay(both_in_board(pairs, "ai"))),
        ("Only pairs with both seasons in the comic catalogue", replay(both_in_board(pairs, "comic"))),
    ):
        print(
            label,
            {
                **summary(rows),
                "other_series_mae_days": round(mean(r["other_series_abs_error"] for r in rows), 3) if rows else None,
                "own_series_mae_days": round(mean(r["own_series_abs_error"] for r in rows), 3) if rows else None,
                "own_series_strictly_closer": sum(r["own_series_abs_error"] < r["other_series_abs_error"] for r in rows),
            },
        )


if __name__ == "__main__":
    main()
