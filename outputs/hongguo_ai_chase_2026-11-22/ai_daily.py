"""Archive the public Hongguo AI chart, preserve cohort previews, or label a cohort."""

import argparse
import csv
import fcntl
import hashlib
from html.parser import HTMLParser
import json
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / "hongguo_sentiment_pilot_2026-11-21"
DAILY = HERE / "daily"
sys.path.insert(0, str(PILOT))
from daily_snapshot import csv_bytes, freeze, verified_chart
from capture_previews import collect
from cohort import LOCAL, RAW, TARGET, observed_charts, read

FIRST_COHORT = TARGET
URL = "https://hongguoduanju.com/rank/hot-ai-drama"
TOP100 = set(range(1, 101))
TOP20 = set(range(1, 21))
SCOPES = ("series_review", "first_episode_comment")
# The date label advances before the ranks may refresh. In the 22 November
# midnight probe all 100 ranks matched the previous afternoon's archive.
EARLIEST_ARCHIVE_HOUR = 12
FIELDS = ("priority", "date", "board", "series_id", "title", "rank", "same_board_age",
          "same_board_first_observed", "forecast_eligible", "rank_lag2", "rank_lag1", "heat",
          "likes", "favorites", "rating", "chart_snapshot_completed_sh", "forecast_start", "forecast_end",
          "future_same_board_top20")


class AIRankParser(HTMLParser):
    """Recognize AI ranking records by their published titles and displayed rank badges."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.records = []
        self.item = None
        self.parts = []
        self.capture = None
        self.in_pagination = False
        self.current_page = None
        self.ai_list_seen = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "ol" and attrs.get("aria-label") == "AI剧热播榜":
            self.ai_list_seen = True
        if tag == "nav" and attrs.get("aria-label") == "榜单分页":
            self.in_pagination = True
        if self.in_pagination and attrs.get("aria-current") == "page":
            self.capture = (tag, "page", [])
        if tag == "article":
            label = attrs.get("aria-labelledby") or ""
            if re.fullmatch(r"rank-title-[0-9]+", label):
                self.item = {"id": label.removeprefix("rank-title-")}
                self.parts = []
        if self.item is not None:
            if attrs.get("id") == "rank-title-" + self.item["id"]:
                self.capture = (tag, "title", [])
            if "badge-number" in (attrs.get("class") or ""):
                self.capture = (tag, "rank", [])

    def handle_data(self, data):
        if self.item is not None:
            self.parts.append(data)
        if self.capture is not None:
            self.capture[2].append(data)

    def handle_endtag(self, tag):
        if self.capture and tag == self.capture[0]:
            _, field, parts = self.capture
            text = " ".join("".join(parts).split())
            if field == "page":
                self.current_page = int(text)
            else:
                self.item[field] = int(text) if field == "rank" else text
            self.capture = None
        if tag == "nav":
            self.in_pagination = False
        if tag == "article" and self.item is not None:
            if not self.item.get("title") or "rank" not in self.item:
                raise ValueError("Official chart entry has no title or rank")
            full_text = "".join(self.parts)
            for field, label in (("heat", "热度"), ("like", "点赞"), ("fav", "收藏")):
                match = re.search(r"(\d+(?:\.\d+)?)\s*(万|亿)?\s*" + label, full_text)
                self.item[field] = round(float(match[1]) * {"万": 10_000, "亿": 100_000_000, None: 1}[match[2]]) if match else None
            rating = re.search(r"评分\s*(\d+(?:\.\d+)?)", full_text)
            self.item["rating"] = float(rating[1]) if rating else None
            self.records.append(self.item)
            self.item = None


def rank_set(records):
    return {int(r["rank"]) for r in records}


def download_chart(day):
    pages, records = [], []
    for page in range(1, 6):
        if page > 1:
            time.sleep(0.6)
        url = URL if page == 1 else f"{URL}?page={page}"
        request = Request(url, headers={"Accept": "text/html", "User-Agent": "Hongguo-BA-academic-pilot/1.0"})
        with urlopen(request, timeout=15) as response:
            if response.geturl() != url:
                raise ValueError(f"Unexpected redirect from {url}")
            raw = response.read()
        observed = datetime.now(LOCAL)
        html = raw.decode()
        labels = {(int(month), int(number)) for month, number in
                  re.findall(r"(\d{1,2})月(\d{1,2})日已更新", html)}
        if observed.date() != day or labels != {(day.month, day.day)}:
            raise ValueError(f"AI chart page {page} has labels {sorted(labels)} on requested date {day}")
        parser = AIRankParser()
        parser.feed(html)
        parser.close()
        if not parser.ai_list_seen or parser.current_page != page:
            raise ValueError(f"AI chart page {page} has an unexpected board or pagination marker")
        expected = set(range((page - 1) * 20 + 1, page * 20 + 1))
        if len(parser.records) != 20 or rank_set(parser.records) != expected:
            raise ValueError(f"AI chart page {page} is incomplete")
        pages.append(dict(url=url, at=observed.isoformat(), label_date=day.isoformat(),
                          sha256=hashlib.sha256(raw).hexdigest(), page=page))
        records.extend(parser.records)
    if len({r["id"] for r in records}) != 100:
        raise ValueError("AI chart contains repeated work IDs")
    return dict(date=day.isoformat(), completed_at=pages[-1]["at"], pages=pages, records=records)


def load_chart(path):
    chart = json.loads(path.read_text())
    records = chart["records"]
    observed = datetime.fromisoformat(chart["completed_at"])
    day = date.fromisoformat(path.parent.name)
    if (chart["date"] != day.isoformat() or observed.tzinfo is None
            or observed.astimezone(LOCAL).date() != day
            or observed.astimezone(LOCAL).hour < EARLIEST_ARCHIVE_HOUR or len(records) != 100
            or not all(str(r["id"]).isdecimal() and r["title"] for r in records)
            or len({str(r["id"]) for r in records}) != 100 or rank_set(records) != TOP100):
        raise ValueError(f"Invalid complete AI chart archive {path}")
    return chart


def chart_for(day, folder, offline):
    path = folder / "chart.json"
    if path.exists():
        return load_chart(path)
    if day == FIRST_COHORT:
        archive = verified_chart(RAW, day)
        pages = archive["manifest"]["boards"]["ai"]["pages"]
        payload = dict(date=day.isoformat(), completed_at=pages[-1]["at"],
                       pages=pages, records=archive["boards"]["ai"])
    elif not offline and day == datetime.now(LOCAL).date():
        if datetime.now(LOCAL).hour < EARLIEST_ARCHIVE_HOUR:
            raise ValueError(f"AI chart collection opens at {EARLIEST_ARCHIVE_HOUR}:00 Asia/Shanghai")
        payload = download_chart(day)
    else:
        raise ValueError(f"No same-day AI chart archive for {day}")
    freeze(path, json.dumps(payload, ensure_ascii=False, indent=2).encode())
    return load_chart(path)


def history(through):
    archived, _ = observed_charts()
    days = {day: {sid: info["ai"] for sid, info in titles.items() if "ai" in info}
            for day, titles in archived.items() if day <= through}
    for path in DAILY.glob("????-??-??/chart.json"):
        day = date.fromisoformat(path.parent.name)
        if day > through:
            continue
        records = {str(r["id"]): r for r in load_chart(path)["records"]}
        if day in days and {sid: r["rank"] for sid, r in days[day].items()} != {
                sid: r["rank"] for sid, r in records.items()}:
            raise ValueError(f"Baseline and AI chart archives do not agree on {day}")
        days[day] = records
    return days


def candidates(day, chart, days):
    current = days[day]
    captured_at = chart["completed_at"]
    complete = {d for d, records in days.items() if rank_set(records.values()) == TOP100}
    first, ever_top20 = {}, set()
    for d, records in sorted(days.items()):
        for sid, work in records.items():
            first.setdefault(sid, d)
            if work["rank"] <= 20:
                ever_top20.add(sid)
    result = []
    for sid, row in sorted(current.items(), key=lambda item: item[1]["rank"]):
        age = (day - first[sid]).days + 1
        if age > 3:
            continue
        if any(first[sid] + timedelta(days=offset) not in complete for offset in range(-7, age)):
            continue
        eligible = sid not in ever_top20
        if day == FIRST_COHORT and not eligible:
            continue
        lags = [days.get(day-timedelta(days=lag), {}).get(sid, {}).get("rank", "") for lag in (2, 1)]
        result.append(dict(priority=len(result)+1, date=day.isoformat(), board="ai", series_id=sid,
                           title=row["title"], rank=row["rank"], same_board_age=age,
                           same_board_first_observed=first[sid].isoformat(), forecast_eligible=int(eligible),
                           rank_lag2=lags[0], rank_lag1=lags[1], heat=row.get("heat"), likes=row.get("like"),
                           favorites=row.get("fav"), rating=row.get("rating"),
                           chart_snapshot_completed_sh=captured_at, forecast_start=day+timedelta(days=1),
                           forecast_end=day+timedelta(days=7), future_same_board_top20=""))
    if day == FIRST_COHORT:
        reference = [(r["series_id"], int(r["rank"]), int(r["same_board_age"]))
                     for r in read(PILOT / "features_2026-11-21.csv") if r["target_board"] == "ai"]
        if [(r["series_id"], r["rank"], r["same_board_age"]) for r in result] != reference:
            raise ValueError("Reconstructed AI cohort differs from the 21 November analysis cohort")
    return result


def capture_cohort(day, folder, offline):
    chart = chart_for(day, folder, offline)
    rows = candidates(day, chart, history(day))
    target = folder / "cohort.csv"
    freeze(target, csv_bytes(rows, FIELDS))
    if rows and not offline and day == datetime.now(LOCAL).date():
        collect(target, day.isoformat())

    stamps, missing = [], []
    chart_at = datetime.fromisoformat(chart["completed_at"])
    for row in rows:
        sid = row["series_id"]
        for scope in SCOPES:
            path = PILOT / "snapshots" / day.isoformat() / f"{sid}_{scope}.json"
            if not path.exists():
                missing.append((sid, scope))
                continue
            preview = json.loads(path.read_text())
            stamp = datetime.fromisoformat(preview["sampled_at_sh"])
            if (stamp.tzinfo is None or stamp.astimezone(LOCAL).date() != day or stamp < chart_at
                    or preview["series_id"] != sid or preview["scope"] != scope):
                raise ValueError(f"Invalid capture identity or time in {path}")
            stamps.append(stamp)
    n_eligible = sum(r["forecast_eligible"] for r in rows)
    print(f"{day}: AI chart 100, recent works {len(rows)}, forecast-eligible {n_eligible}, "
          f"verified pages {len(stamps)}/{2*len(rows)}")
    if missing:
        raise ValueError(f"{len(missing)} public previews are missing; rerun this decision date if still today")
    summary = dict(date=day.isoformat(), chart_items=len(chart["records"]), chart_completed_at=chart["completed_at"],
                   recent_works=len(rows), forecast_eligible_works=n_eligible, verified_pages=len(stamps),
                   first_preview_at=min(stamps).isoformat() if stamps else None,
                   decision_at=max(stamps).isoformat() if stamps else chart["completed_at"])
    freeze(folder / "batch.json", json.dumps(summary, ensure_ascii=False, indent=2).encode())


def label_cohort(day, folder):
    target = folder / "cohort.csv"
    if not target.exists():
        raise ValueError(f"No frozen AI cohort for {day}")
    horizon = [day+timedelta(days=i) for i in range(1, 8)]
    if horizon[-1] > datetime.now(LOCAL).date():
        raise ValueError(f"The seven-day window ends {horizon[-1]}")
    days = history(horizon[-1])
    if missing := [d.isoformat() for d in horizon if not TOP20 <= rank_set(days.get(d, {}).values())]:
        raise ValueError("Official AI Top 20 snapshots are missing for " + ", ".join(missing))
    result = []
    for row in read(target):
        if row["forecast_eligible"] != "1":
            continue
        sid = row["series_id"]
        ranks = [days[d].get(sid, {}).get("rank", 101) for d in horizon]
        first_hit = next((d.isoformat() for d, rank in zip(horizon, ranks) if rank <= 20), "")
        result.append(dict(date=day.isoformat(), series_id=sid, board="ai", title=row["title"],
                           first_hit_date=first_hit, future_same_board_top20=int(bool(first_hit))))
    fields = ("date", "series_id", "board", "title", "first_hit_date", "future_same_board_top20")
    freeze(folder / "labels_7d.csv", csv_bytes(result, fields))
    print(f"{day}: {len(result)} verified seven-day labels, "
          f"{sum(r['future_same_board_top20'] for r in result)} hits")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--day", type=date.fromisoformat, default=None)
    choice.add_argument("--labels-for", type=date.fromisoformat)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    day = args.labels_for or args.day or datetime.now(LOCAL).date()
    folder = DAILY / day.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.labels_for:
                label_cohort(day, folder)
            else:
                capture_cohort(day, folder, args.offline)
        except (ValueError, OSError) as exc:
            parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
