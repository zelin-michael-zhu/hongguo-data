"""Measure how overall-chart depth covers the official AI category ranks."""
import csv
from collections import defaultdict
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "hongguo_breakout_2026-11-21"))
from panel import complete_dates, observed_charts


def main():
    charts, boards = observed_charts()
    days = sorted(complete_dates(boards, 100))
    records = []
    for day in days:
        for sid, row in charts[day].items():
            ai = row.get("ai")
            if ai and ai["rank"] <= 20:
                overall = row.get("hot")
                records.append(dict(date=day.isoformat(), series_id=sid, title=ai["title"].replace("\x00", " "),
                                    ai_rank=ai["rank"], ai_heat=ai["heat"],
                                    overall_rank=overall["rank"] if overall else "",
                                    overall_heat=overall["heat"] if overall else ""))
    with (HERE / "AI榜前二十与综合榜逐日配对.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(sorted(records, key=lambda r: (r["date"], r["ai_rank"])))
    coverage = []
    for ai_depth in (10, 20):
        matches = defaultdict(list)
        for row in records:
            if row["ai_rank"] <= ai_depth:
                matches[row["series_id"]].append(row["overall_rank"] or 101)
        size = sum(len(ranks) for ranks in matches.values())
        assert size == len(days) * ai_depth
        for overall_depth in range(1, 101):
            coverage.append(dict(ai_depth=ai_depth, overall_depth=overall_depth,
                                 complete_days=len(days), ai_title_days=size, ai_titles=len(matches),
                                 covered_title_days=sum(rank <= overall_depth for r in matches.values() for rank in r),
                                 covered_titles=sum(min(ranks) <= overall_depth for ranks in matches.values())))
    with (HERE / "综合榜不同深度的AI覆盖.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage[0]))
        writer.writeheader()
        writer.writerows(coverage)


if __name__ == "__main__":
    main()
