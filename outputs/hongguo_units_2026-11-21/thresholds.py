"""Classify entrants into a board's top K by their observable prior-day top-100 presence."""

import csv
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hongguo_watchlist_review_2026-11-21"))
from decision_audit import read_panel


def main():
    _, days, panels, _ = read_panel()
    totals = Counter()
    comparisons = Counter()
    for day in days:
        previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        for board in ("hot", "real", "ai", "comic"):
            if (previous, board) not in panels:
                continue
            prior_titles = {r["id"]: r for r in panels[previous, board]}
            prior_groups = {r["group"] for r in prior_titles.values() if r["group"].startswith("g:")}
            for k in (20, 50, 100):
                comparisons[board, k] += 1
                for row in panels[day, board]:
                    if row["rank"] > k:
                        continue
                    old = prior_titles.get(row["id"])
                    if old and old["rank"] <= k:
                        continue
                    if old:
                        category = "same_title_in_previous_top100_below_k"
                    elif row["group"] in prior_groups:
                        category = "another_title_in_confirmed_franchise_in_previous_top100"
                    else:
                        category = "no_confirmed_previous_top100_link"
                    totals[board, k, category] += 1
    keys = ("same_title_in_previous_top100_below_k",
            "another_title_in_confirmed_franchise_in_previous_top100",
            "no_confirmed_previous_top100_link")
    with (HERE / "threshold_entries.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("board", "depth", "day_pairs", "entering_titles", *keys))
        writer.writeheader()
        for (board, k), pairs in sorted(comparisons.items()):
            assert pairs == 37
            counts = {key: totals[board, k, key] for key in keys}
            writer.writerow(dict(board=board, depth=k, day_pairs=pairs, entering_titles=sum(counts.values()), **counts))


if __name__ == "__main__":
    main()
