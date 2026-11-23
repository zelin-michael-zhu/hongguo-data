"""Export the prospective shortlist and evaluate when distinct hits were first flagged."""
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOARD = {"hot": "综合", "real": "真人", "ai": "AI", "comic": "漫剧"}


def read(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_shortlist(panel):
    live = sorted(read("fresh_scores.csv"), key=lambda row: int(row["selected_order"]))
    assert len({row["id"] for row in live}) == len(live) == 26
    results = []
    for place, row in enumerate(live[:10], start=1):
        observed = panel[row["date"], row["id"]]
        assert place == int(row["selected_order"]) and row["y7"] == ""
        assert row["selected_model"] == "rank"
        results.append({
            "名单顺序": place, "决策日": row["date"], "剧名": row["title"], "作品ID": row["id"],
            "官网首次可见日期": row["web_first_visible"], "官网可见第几天": row["web_age"],
            "11月19日最佳榜位": observed["rank_lag2"], "11月20日最佳榜位": observed["rank_lag1"],
            "11月21日最佳榜位": row["rank"], "当日最佳名次所在榜": BOARD[row["board"]],
            "当日所见榜单": "、".join(BOARD[b] for b in observed["boards_today"].split("|")),
            "预测首日": "2026-11-22", "预测末日": "2026-11-28",
        })
    write("11月21日潜力短剧Top10.csv", results)


def audit_discovery(panel):
    for suffix in ("", "daily_refit_"):
        oos = read("fresh_" + suffix + "oos.csv")
        events = defaultdict(list)
        for row in oos:
            if row["y7"] == "1":
                events[row["id"]].append(row)
        results = []
        for sid, rows in sorted(events.items()):
            hit_dates = {panel[row["date"], sid]["observed_hit7"] for row in rows}
            assert len(hit_dates) == 1
            hit_date = date.fromisoformat(hit_dates.pop())
            result = {"id": sid, "title": rows[0]["title"], "first_hit": hit_date.isoformat()}
            for method in ("rank", "state", "trend", "content"):
                picked = [row["date"] for row in rows if int(row["order_" + method]) <= 10]
                first = min(picked) if picked else ""
                result[method + "_first_pick"] = first
                result[method + "_days_ahead"] = (hit_date - date.fromisoformat(first)).days if first else ""
            results.append(result)
        write("fresh_" + suffix + "discovery.csv", results)

        # Equal review workload: a title can consume at most one slot per model
        # during this evaluation. The label is evaluated from that actual selection day.
        daily = defaultdict(list)
        for row in oos:
            daily[row["date"]].append(row)
        first_reviews = []
        for method in ("rank", "state", "trend", "content"):
            reviewed = set()
            for day, rows in sorted(daily.items()):
                ordered = sorted(rows, key=lambda row: int(row["order_" + method]))
                chosen = [row for row in ordered if row["id"] not in reviewed][:10]
                for row in chosen:
                    reviewed.add(row["id"])
                    first_reviews.append({"model": method, "date": day, "id": row["id"],
                                          "title": row["title"], "rank": row["rank"],
                                          "order_before_exclusions": row["order_" + method],
                                          "hit_within_7_days": row["y7"]})
        write("fresh_" + suffix + "first_reviews.csv", first_reviews)


if __name__ == "__main__":
    history = {(row["date"], row["id"]): row for row in read("broad_panel.csv")}
    export_shortlist(history)
    audit_discovery(history)
