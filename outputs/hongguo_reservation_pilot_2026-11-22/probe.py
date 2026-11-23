"""Audit public Hongguo reservation-to-release matches and seven-day coverage."""
import csv
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = "https://hongguoduanju.com"
SHANGHAI = ZoneInfo("Asia/Shanghai")
SOURCE = (HERE.parent / "hongguo_research_review_2026-11-19/evidence/raw"
          / "official_website_headers_2026-11-19.json")
HISTORY = HERE.parent / "hongguo_free_pilot_2026-11-18/history"
PREVIEW_ARCHIVE = HERE.parent / "hongguo_sentiment_pilot_2026-11-21/snapshots"
ROUTER = re.compile(r"\b_ROUTER_DATA\s*=\s*")
ARCHIVED_ROW = re.compile(
    r"^1\. (\d+)\n\n## (.+?)\n\n([\d.]+[万亿]?期待)\n\n"
    r"([\d.]+[万亿]?人预约)([^\n]*)\n\n([^\n]+)\n\n(.+?)\n\n预约正片",
    re.M | re.S,
)


def now():
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def number(value, suffix):
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)(万|亿)?" + suffix, value or "")
    if match:
        scale = {None: 1, "万": 10_000, "亿": 100_000_000}[match[2]]
        return int(Decimal(match[1]) * scale)
    return None


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def save_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def request(url):
    time.sleep(0.55)
    req = Request(url, headers={"Accept": "text/html", "User-Agent": "Hongguo-BA-academic-pilot/1.0"})
    with urlopen(req, timeout=14) as response:
        if response.geturl() != url:
            raise ValueError(f"Unexpected redirect for {url}")
        raw = response.read()
    html = raw.decode("utf-8")
    match = ROUTER.search(html)
    if not match:
        raise ValueError(f"Public data marker absent on {url}")
    return json.JSONDecoder().raw_decode(html[match.end():].lstrip())[0]["loaderData"], {
        "source_url": url, "sampled_at_sh": now(), "html_sha256": hashlib.sha256(raw).hexdigest()
    }


def rank_chart(slug):
    rows, pages = [], []
    for idx in range(1, 6):
        url = f"{ROOT}/rank/{slug}" + ("" if idx == 1 else f"?page={idx}")
        data, snapshot = request(url)
        page = data[f"rank_{slug}/page"]
        content = page["content"]
        label = page["updatedText"]
        items = content["rankList"]
        cap = range(20 * (idx - 1) + 1, 20 * idx + 1)
        if (page["pageNum"] != idx or content["pagination"]["totalPages"] != 5
                or [item["rank"] for item in items] != list(cap)):
            raise ValueError(f"Unexpected page numbering or coverage for {url}")
        day = datetime.fromisoformat(snapshot["sampled_at_sh"])
        if slug == "new-drama" and not label.startswith(f"{day.month}月{day.day}日已更新"):
            raise ValueError(f"Unexpected new chart date label for {url}: {label}")
        pages.append(dict(snapshot, page=idx, page_label=label))
        rows.extend(dict(item, **snapshot, page_label=label) for item in items)
    if len({str(row["seriesId"]) for row in rows}) != 100:
        raise ValueError(f"Duplicated series IDs across pages for {slug}")
    return {"rows": rows, "pages": pages}


def archived_reservations():
    capture = json.loads(SOURCE.read_text(encoding="utf-8"))["structuredContent"]["value"]
    chart = next(row for row in capture if row["url"] == f"{ROOT}/rank/subscribe-drama")
    blocks = [m.groups() for m in ARCHIVED_ROW.finditer(chart["read"])]
    if [int(row[0]) for row in blocks] != list(range(1, 21)):
        raise ValueError("Historical capture does not reproduce ranks 1 through 20")
    return [{
        "date": "2026-11-19", "sampled_at_sh": "", "source_url": chart["url"],
        "rank": int(rank), "seriesId": "", "title": title, "primaryMetricText": expected,
        "subscribeText": reservations, "expectedPublishText": schedule,
        "tags": tag.split(" · "), "description": summary,
    } for rank, title, expected, reservations, schedule, tag, summary in blocks]


def status(series_id):
    url = f"{ROOT}/player/{series_id}"
    result = {"series_id": series_id, "source_url": url, "sampled_at_sh": "", "http_status": "",
              "status": "", "title": "", "first_visible_at_metadata": "",
              "episodes": "", "first_episode_id": "", "favorite_count": ""}
    try:
        data, receipt = request(url)
        result.update(receipt, http_status=200)
        page = next(v for v in data.values() if isinstance(v, dict) and "seriesDetail" in v)
        detail = page["seriesDetail"]
        vid = str(page.get("vid") or "")
        ids = detail.get("vid_list") or []
        seo = page.get("publicVideoSeo") or {}
        if str(detail["series_id"]) != series_id:
            raise ValueError("Returned series ID differs")
        released = bool(ids and vid and str(ids[0]) == vid
                        and str(seo.get("itemId")) == vid and seo.get("available"))
        if metadata := detail.get("first_visible_time"):
            result["first_visible_at_metadata"] = datetime.fromtimestamp(int(metadata), SHANGHAI).isoformat()
        result.update(status="public_first_episode" if released else "first_episode_unverified",
                      title=detail.get("series_name") or "", episodes=detail.get("episode_cnt", ""),
                      first_episode_id=vid, description=detail.get("series_intro") or "",
                      site_season_group_id=str((detail.get("season_info") or {}).get("series_group_id") or ""),
                      favorite_count=(page.get("seriesSocialInfo") or {}).get("series_favorite_count", ""))
    except HTTPError as exc:
        result.update(http_status=exc.code, status=f"HTTP {exc.code}", sampled_at_sh=now())
    except (URLError, TimeoutError, ValueError, TypeError, KeyError, StopIteration) as exc:
        result.update(status=f"{type(exc).__name__}: {exc}", sampled_at_sh=now())
    return result


def title_group(title):
    if re.search(r"第[一1][季期部]", title):
        return "explicit_first"
    if re.search(r"第[二三四五六七八九十百零两0-9]+[季期部]|续季", title):
        return "explicit_sequel"
    return "unverified"


def join_rows(old, live, new, checks):
    historical = read_csv(HISTORY / "catalog.csv")
    history_ids = {item["id"] for item in historical}
    history_titles = {normalized(item["title"]) for item in historical}
    new_by_id = {str(item["seriesId"]): item for item in new}
    title_index = {}
    for item in new:
        title_index.setdefault(normalized(item["title"]), []).append(item)
    results = []
    for record in old + live:
        sid = str(record["seriesId"])
        title = record["title"]
        candidates = title_index.get(normalized(title), [])
        match = new_by_id.get(sid)
        method = "same_id" if match else ""
        if not sid and len(candidates) == 1:
            target = candidates[0]
            intro = normalized(record["description"])
            target_intro = normalized(target["description"])
            if len(intro) >= 35 and target_intro.startswith(intro[:35]):
                match, method = target, "title_and_synopsis"
        if match:
            target_id = str(match["seriesId"])
        elif checks.get(sid, {}).get("status") == "public_first_episode":
            target_id, method = sid, "same_id_player"
        else:
            target_id = ""
        player = checks.get(target_id or sid, {})
        feature_time = record.get("sampled_at_sh", "")
        observed = record.get("date") or feature_time[:10]
        verified_at = player.get("sampled_at_sh", "") if target_id else ""
        results.append({
            "reservation_snapshot_date": observed, "reservation_sampled_at_sh": feature_time,
            "reservation_rank": record["rank"], "title": title, "reservation_series_id": sid,
            "format": record["tags"][0] if record["tags"] else "",
            "season_group_label": title_group(title),
            "expected_value_display": record["primaryMetricText"],
            "expected_value": number(record["primaryMetricText"], "期待"),
            "reservations_display": record["subscribeText"],
            "reservations": number(record["subscribeText"], "人预约"),
            "expected_release_display": record["expectedPublishText"],
            "old_catalog_id_match": bool(sid and sid in history_ids),
            "old_catalog_title_match": normalized(title) in history_titles,
            "current_new_chart_title_hits": len(candidates),
            "match_method": method, "matched_series_id": target_id,
            "first_episode_verified": player.get("status") == "public_first_episode",
            "player_checked_at_sh": verified_at or player.get("sampled_at_sh", ""),
            "player_check_status": player.get("status", ""),
            "player_first_visible_metadata_sh": player.get("first_visible_at_metadata", ""),
            "favorites_at_player_check": player.get("favorite_count", "") if target_id else "",
            "verified_launch_day": "", "favorite_d0": "", "favorite_d7": "",
            "week1_favorite_gain": "", "source_url": record.get("source_url", ""),
        })
    return results


def matched_favorites(matches, players):
    observations = []
    for match in matches:
        sid = match["matched_series_id"]
        if not match["first_episode_verified"]:
            continue
        sampled = players[sid]
        items = [("default_player", sampled["sampled_at_sh"], sampled["favorite_count"], sampled["source_url"])]
        for path in sorted(PREVIEW_ARCHIVE.glob(f"????-??-??/{sid}_series_review.json")):
            preview = json.loads(path.read_text(encoding="utf-8"))
            if preview["series_id"] != sid or preview["scope"] != "series_review":
                raise ValueError(f"Archived detail identity mismatch for {sid}")
            items.append(("series_detail", preview["sampled_at_sh"],
                          preview["metrics"].get("series_favorite_count"), preview["source"]))
        for scope, observed_at, count, url in sorted(items, key=lambda row: row[1]):
            if str(count).isdecimal():
                observations.append(dict(series_id=sid, title=match["title"], sampled_at_sh=observed_at,
                                         page_kind=scope, favorite_count=int(count), source_url=url))
    return observations


def main():
    old = archived_reservations()
    charts = []
    for slug, filename in (("subscribe-drama", "预约榜_当日快照.json"), ("new-drama", "新剧榜_当日快照.json")):
        path = HERE / filename
        if path.exists():
            chart = json.loads(path.read_text(encoding="utf-8"))
        else:
            chart = rank_chart(slug)
            save_json(path, chart)
        charts.append(chart)
    reservation, new = charts
    print("Archived reservation:", len(old), "live reservation/new:", len(reservation["rows"]), len(new["rows"]), flush=True)
    initial = join_rows(old, reservation["rows"], new["rows"], {})
    all_ids = list(dict.fromkeys(
        [r["matched_series_id"] for r in initial if r["matched_series_id"]]
        + [str(r["seriesId"]) for r in reservation["rows"]]
    ))
    checked_path = HERE / "官方正片核查.json"
    saved = json.loads(checked_path.read_text(encoding="utf-8")) if checked_path.exists() else []
    checks = {row["series_id"]: row for row in saved}
    for sid in all_ids:
        existing = checks.get(sid)
        if existing and existing["http_status"] in (200, 404):
            continue
        row = status(sid)
        if not row["http_status"] or row["http_status"] in (500, 502, 503, 504):
            time.sleep(2)
            row = status(sid)
        checks[sid] = row
        if row["http_status"] in (401, 403, 429):
            print("Public request restricted:", sid, row["status"], flush=True)
            break
        if len(checks) % 25 == 0:
            print("Player checks:", len(checks), flush=True)
    save_json(checked_path, list(checks.values()))
    output = join_rows(old, reservation["rows"], new["rows"], checks)
    save_csv(HERE / "预约到正片_逐剧覆盖.csv", output)
    if observations := matched_favorites(output, checks):
        save_csv(HERE / "已配对作品_收藏时间点.csv", observations)
    print("Player checks:", Counter(row["status"] for row in checks.values()), flush=True)
    print("Confirmed matches:", [(row["title"], row["matched_series_id"]) for row in output
                                 if row["matched_series_id"]], flush=True)


if __name__ == "__main__":
    main()
