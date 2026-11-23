"""Evaluate daily heat-ranked lists on identical, fully observed entry cohorts."""
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

folder = Path(__file__).resolve().parent
history = folder.parents[1] / "hongguo_free_pilot_2026-11-18" / "history"
one_day = timedelta(days=1)
boards = defaultdict(lambda: defaultdict(dict))
first_entry = {}
with (history / "board_daily.csv").open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        d = date.fromisoformat(row["date"])
        sid = row["id"]
        boards[d][row["board"]][sid] = (int(row["rank"]), int(row["heat"] or -1))
        if row["board"] == "hot":
            first_entry[sid] = min(d, first_entry.get(sid, d))

complete = {d for d, group in boards.items()
            if len(group) == 4 and all({r for r, _ in items.values()} == set(range(1, 101))
                                     for items in group.values())}
origins = sorted(d for d in complete if all(d - i * one_day in complete for i in range(1, 8)))
scored = {d for d in origins if all(d + i * one_day in complete for i in range(1, 4))}
target_dates = {d for d in complete if all(d - i * one_day in scored for i in range(1, 4))}
target_titles = {sid for sid, d in first_entry.items() if d in target_dates}
eligible = {}
for d in origins:
    candidates = {}
    for board in ("real", "ai", "comic"):
        for sid, (rank, heat) in boards[d][board].items():
            if first_entry.get(sid, date.max) <= d:
                continue
            old_heat, old_rank = candidates.get(sid, (-1, 101))
            candidates[sid] = (max(heat, old_heat), min(rank, old_rank))
    eligible[d] = sorted(candidates, key=lambda sid: (-candidates[sid][0], candidates[sid][1], int(sid)))

with (folder / "selected.csv").open(encoding="utf-8-sig") as f:
    reference = defaultdict(list)
    for row in csv.DictReader(f):
        if row["method"] == "published_heat":
            reference[date.fromisoformat(row["date"])].append(row["id"])

def recall_by_lead(daily_lists):
    earliest = {}
    for d, titles in daily_lists.items():
        for sid in titles:
            if sid in target_titles:
                lead = (first_entry[sid] - d).days
                if 1 <= lead <= 3:
                    earliest[sid] = max(earliest.get(sid, 0), lead)
    return {"1_to_3":len(earliest), "2_to_3":sum(v >= 2 for v in earliest.values())}

rows = []
for budget in (3, 5, 10, 20):
    next_allowed = {}
    lists = {}
    for d in origins:
        available = [sid for sid in eligible[d] if next_allowed.get(sid, date.min) <= d]
        taken = available[:budget]
        for sid in taken:
            next_allowed[sid] = d + 3 * one_day
        if d in scored:
            lists[d] = taken
    if budget == 5:
        assert lists == reference, "Five-slot run diverged from previously archived selections."
    rows.append({"titles_per_day":budget, **recall_by_lead(lists)})

output = {"target_dates":len(target_dates),"target_titles":len(target_titles),
          "decision_days":len(scored),"hit_counts_over_same_target_titles":rows,
          "observable_with_no_budget_limit":recall_by_lead({d:eligible[d] for d in scored})}
print(json.dumps(output,ensure_ascii=False,indent=2))
(folder / "review_budget_results.json").write_text(json.dumps(output,ensure_ascii=False,indent=2) + "\n")
