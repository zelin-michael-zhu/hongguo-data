"""Replay weekly high-rating label decisions from observed public scores."""
import csv
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
INPUT = HERE.parents[1] / "hongguo_free_pilot_2026-11-18/history/drama_daily.csv"
day = timedelta(days=1)
thresholds = [Decimal(x) for x in ("8.5", "8.8", "9.0", "9.2")]
panel = defaultdict(dict)
with INPUT.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        panel[row["id"]][date.fromisoformat(row["date"])] = row
last_date = max(max(history) for history in panel.values())

def score(history, when):
    value = history.get(when, {}).get("rating")
    return Decimal(value) if value else None

def first_observed_upcrossing(history, threshold):
    for when in sorted(history):
        if when + 7 * day > last_date:
            break
        old_score = score(history, when - day)
        new_score = score(history, when)
        if old_score is not None and new_score is not None and old_score < threshold <= new_score:
            return when
    return None

def summarize(events, threshold):
    observed = [row for row in events if all(row[k] is not None for k in ("s1", "s2", "s7"))]
    above = [row for row in observed if row["s7"] >= threshold]
    waiting = [row for row in observed if min(row["s1"], row["s2"]) >= threshold]
    correct_after_wait = sum(row["s7"] >= threshold for row in waiting)
    below = [row for row in observed if row["s7"] < threshold]
    return {
        "candidate_titles": len(events),
        "complete_titles": len(observed),
        "mature_after_7":len(above),
        "below_after_7":len(below),
        "wait_selected":len(waiting),
        "wait_still_above":correct_after_wait,
        "wait_below":len(waiting) - correct_after_wait,
        "missed_mature_if_wait":len(above) - correct_after_wait,
        "below_day7_score_histogram":dict(Counter(str(row["s7"]) for row in below)),
        "distinct_event_days":len({r["date"] for r in observed}),
        "top_event_dates":Counter(r["date"] for r in observed).most_common(3),
    }

all_events, stats = [], {}
for cut in thresholds:
    events = []
    for sid, history in sorted(panel.items()):
        when = first_observed_upcrossing(history, cut)
        if when is None:
            continue
        row = {"id":sid,"title":history[when]["title"],"cut":str(cut),"date":str(when)}
        for offset in (-1,0,1,2,7):
            row[f"s{offset}"] = score(history, when+offset*day)
        events.append(row)
    all_events.extend(events)
    stats[str(cut)] = {"all":summarize(events,cut),
                       "late_nov1_on":summarize([r for r in events if r["date"] >= "2026-11-01"],cut)}
with (HERE / "crossings.csv").open("w", newline="", encoding="utf-8-sig") as f:
    writer=csv.DictWriter(f,fieldnames=list(all_events[0]))
    writer.writeheader()
    writer.writerows(all_events)
(HERE / "results.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding="utf8")
print(json.dumps(stats["9.0"],ensure_ascii=False))
