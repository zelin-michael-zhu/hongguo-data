"""Audit ties at the boundary of a daily top-ten review list."""

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path


evidence = Path(__file__).resolve().parent
archive = evidence.parents[1] / "hongguo_free_pilot_2026-11-18" / "history" / "drama_daily.csv"
with archive.open(encoding="utf-8-sig", newline="") as file:
    favorites = {
        (date.fromisoformat(row["date"]), row["id"]): int(row["fav"])
        for row in csv.DictReader(file)
        if row["fav"]
    }

daily_changes = defaultdict(list)
for (day, title_id), current in favorites.items():
    previous = favorites.get((day - timedelta(days=1), title_id))
    if previous is not None:
        daily_changes[day].append(current - previous)

records = []
for day, changes in sorted(daily_changes.items()):
    if len(changes) < 10:
        continue
    cutoff = sorted(changes, reverse=True)[9]
    above = sum(change > cutoff for change in changes)
    tied = changes.count(cutoff)
    records.append({
        "date": day.isoformat(), "eligible": len(changes), "cutoff": cutoff,
        "above": above, "tied": tied, "places_left": 10 - above, "ambiguous": above + tied > 10,
    })

(evidence / "top10_favorite_change_ties.json").write_text(json.dumps(records, indent=2))
