"""Snapshot public review previews for a dated cohort. Retain observed text, not user profiles."""
import argparse
import csv
import gzip
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo

HOME_URL = "https://hongguoduanju.com"
ZONE = ZoneInfo("Asia/Shanghai")
ROOT = Path(__file__).resolve().parent
ROUTER = re.compile(r"\b_ROUTER_DATA\s*=\s*")
CONTACTS = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


class PageRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = urlsplit(newurl)
        if url.scheme != "https" or url.netloc != "hongguoduanju.com" or not (
            url.path == "/detail" or re.fullmatch(r"/player/\d+", url.path)
        ):
            raise ValueError("redirect outside a public series or default player page")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def snapshot(opener, sid, scope):
    first = scope == "first_episode_comment"
    url = HOME_URL + ("/player/" if first else "/detail?series_id=") + sid
    req = Request(url, headers={"Accept": "text/html", "Accept-Encoding": "gzip",
                                "User-Agent": "Hongguo-BA-academic-pilot/1.0"})
    with opener.open(req, timeout=14) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    captured = datetime.now(ZONE).isoformat(timespec="seconds")
    html = body.decode()
    match = ROUTER.search(html)
    if match is None:
        raise ValueError("missing public page data")
    state = json.JSONDecoder().raw_decode(html[match.end():].lstrip())[0]["loaderData"]
    key = "episodeSocialInfo" if first else "seriesSocialInfo"
    page = next((v for v in state.values() if isinstance(v, dict) and key in v), {})
    detail = page.get("seriesDetail", {})
    if str(detail.get("series_id")) != sid:
        raise ValueError("wrong or missing series ID")
    eid = str(page["vid"]) if first else ""
    if first and eid != str(detail["vid_list"][0]):
        raise ValueError("wrong first episode")
    social = page[key]
    listing = social["reviews"]
    rows = listing["reviews"]
    if not isinstance(rows, list):
        raise ValueError("review list unavailable")
    metrics = {k: social[k] for k in
               ("series_like_count", "series_favorite_count", "rating", "rating_count", "episode_like_count")
               if k in social}
    data = []
    for position, row in enumerate(rows, 1):
        raw = row.get("content") or ""
        data.append({"position": position, "text": CONTACTS.sub("[已隐藏]", raw),
                     "comment_time": row.get("create_time"), "comment_like_count": row.get("digg_count"),
                     "rating": row.get("rating"), "comment_id": row.get("review_id") or row.get("comment_id")})
    return {"series_id": sid, "episode_id": eid, "title": detail.get("series_name"), "scope": scope,
            "sampled_at_sh": captured, "source": url, "sha256": hashlib.sha256(body).hexdigest(),
            "reported_total": listing.get("total_count"), "metrics": metrics, "rows": data}


def save(path, record):
    temp = path.with_suffix(".part")
    temp.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def collect(seed, day):
    if day != datetime.now(ZONE).date().isoformat():
        raise ValueError("Backdating a new public snapshot is unsupported")
    with seed.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows or any(r["chart_snapshot_completed_sh"][:10] != day for r in rows):
        raise ValueError("cohort and capture dates differ")
    ids = sorted({row["series_id"] for row in rows})
    if not all(s.isdecimal() for s in ids):
        raise ValueError("malformed series ID")
    dest = ROOT / "snapshots" / day
    dest.mkdir(parents=True, exist_ok=True)
    opener = build_opener(PageRedirect())
    for sid in ids:
        for scope in ("series_review", "first_episode_comment"):
            path = dest / f"{sid}_{scope}.json"
            if path.exists():
                continue
            time.sleep(0.55)
            if datetime.now(ZONE).date().isoformat() != day:
                raise ValueError("date changed during capture")
            try:
                record = snapshot(opener, sid, scope)
                if record["sampled_at_sh"][:10] != day:
                    raise ValueError("snapshot taken after midnight")
                save(path, record)
            except (HTTPError, URLError, ValueError, KeyError, IndexError, OSError) as error:
                status = getattr(error, "code", None)
                failed = dest / "errors"
                failed.mkdir(exist_ok=True)
                save(failed / path.name, {"sampled_at_sh": datetime.now(ZONE).isoformat(),
                                          "series_id": sid, "scope": scope, "error": str(error)})
                if status in (401, 403, 429):
                    raise
    print(len(list(dest.glob("*.json"))), "verified public pages", flush=True)


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("cohort", type=Path)
    cli.add_argument("--day", default=datetime.now(ZONE).date().isoformat())
    args = cli.parse_args()
    collect(args.cohort, args.day)
