"""Compare published season intervals using the previous day's observed episode count."""
import csv
import statistics
from datetime import date, timedelta
from pathlib import Path

here = Path(__file__).resolve().parent
source = here.parent / "hongguo_topic_implementation_2026-11-19/identity/pair_identity.csv"
history = here.parent / "hongguo_free_pilot_2026-11-18/history/drama_daily.csv"

def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

episodes = {(r["id"],r["date"]):r["episodes"] for r in read(history)}
rows = []
for p in read(source):
    assert p["identity_confirmed"] == "1"
    old_date = date.fromisoformat(p["old_web_first_visible_shanghai"][:10])
    new_date = date.fromisoformat(p["new_web_first_visible_shanghai"][:10])
    observation = new_date - timedelta(days=1)
    gap = (new_date-old_date).days
    count = int(episodes[p["old_id"], observation.isoformat()])
    rows.append(dict(family=p["family"], previous_id=p["old_id"], previous_title=p["old_title"],
                     next_id=p["new_id"], next_title=p["new_title"], previous_first_web_date=old_date,
                     next_first_web_date=new_date, count_snapshot_date=observation,
                     episodes_listed_in_previous=count, gap_calendar_days=gap,
                     episodes_per_day=count/gap, previous_url=p["old_detail_url"], next_url=p["new_detail_url"]))
with (here/"相邻季间隔.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(len(rows),statistics.median(r["gap_calendar_days"] for r in rows),
      statistics.median(r["episodes_per_day"] for r in rows))
for r in rows:
    if (r["episodes_listed_in_previous"],r["gap_calendar_days"]) in {(208,5),(209,37)}:
        print(r["previous_title"],r["next_title"],r["previous_first_web_date"],r["next_first_web_date"],r["count_snapshot_date"])
