"""Archive published chart pages. Requires the drama-radar repo at commit 9963122."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument("radar_checkout", type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.radar_checkout.resolve()))
from radar.core.http import Fetcher
from radar.sources.hongguo.parse import parse_rank_page
from radar.sources.hongguo.source import BOARDS

zone = ZoneInfo("Asia/Shanghai")
start = dt.datetime.now(zone)
out = Path(__file__).resolve().parent / start.strftime("%Y%m%dT%H%M%S")
out.mkdir()
client = Fetcher("Hongguo-BA-academic-pilot/1.0", 2.0, timeout=12, backoff=())
allowed = ("id", "rank", "title", "fav", "like", "rating", "heat")
manifest = {"started": start.isoformat(), "protocol": "up to 5 public pages/board; no account; same-day published rankings", "boards": {}}
for code, (slug, _) in BOARDS.items():
    records, pages, errors = [], [], []
    for page in range(1, 6):
        url = f"https://hongguoduanju.com/rank/{slug}" + (f"?page={page}" if page > 1 else "")
        try:
            html = client.get(url)
            seen = dt.datetime.now(zone)
            payload = parse_rank_page(html, seen.date().isoformat())
            pages.append({"url": url, "at": seen.isoformat(), "hash": hashlib.sha256(html.encode()).hexdigest(), "label_date": payload["label_date"], "page": payload["current_page"]})
            if payload["current_page"] not in (None, page):
                raise ValueError("unexpected pagination")
            records.extend({k: x.get(k) for k in allowed} for x in payload["items"])
            if page >= (payload["pages"] or 1):
                break
        except Exception as err:
            errors.append({"url": url, "error": str(err)})
            break
    complete = (len(records) == len({x["id"] for x in records}) == 100 and
                {x["rank"] for x in records} == set(range(1, 101)) and
                all(day["label_date"] == start.date().isoformat() for day in pages) and not errors)
    manifest["boards"][code] = {"rows": len(records), "fresh_complete": complete, "pages": pages, "errors": errors}
    (out / (code + ".json")).write_text(json.dumps(records, ensure_ascii=False))
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
print(out.name, {k:(v['rows'],v['fresh_complete']) for k,v in manifest['boards'].items()})
