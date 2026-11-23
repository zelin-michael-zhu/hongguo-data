"""Check public series and default-player HTML for three new catalogue titles."""
import csv
from datetime import datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler
from zoneinfo import ZoneInfo

OUT = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
SAMPLE = {
    "7706759303633308696": "ai",
    "7684955951031389209": "real",
    "7701304930841136190": "comic",
}
PRIVATE = re.compile(r'(?:1[3-9][0-9]{9}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})')


class PublicPageRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        path = urlsplit(newurl)
        if path.netloc != "hongguoduanju.com" or (
            path.path != "/detail" and
            re.fullmatch(r"/player/[0-9]+", path.path) is None
        ):
            raise RuntimeError("Redirect leaves the supported public page paths.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class EpisodeLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.target = None
        self.anchor = ""
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.target = dict(attrs).get("href") or ""
            self.anchor = ""

    def handle_data(self, content):
        if self.target:
            self.anchor += content

    def handle_endtag(self, tag):
        if tag == "a" and self.target is not None:
            if self.anchor.isdecimal() and self.target.startswith("/player/"):
                self.links[self.anchor] = self.target
            self.target = None


def collect():
    opener = build_opener(PublicPageRedirect())
    pages, records = [], []
    for series_id, board in SAMPLE.items():
        for scope, path in [
            ("series_review", "/detail?series_id="),
            ("default_episode_comment", "/player/"),
        ]:
            url = "https://hongguoduanju.com" + path + series_id
            with opener.open(url, timeout=14) as response:
                html = response.read().decode()
                status = response.status
            start = html.index("{", html.index("=", html.index("_ROUTER_DATA")))
            router = json.JSONDecoder().raw_decode(html[start:])[0]
            key = "seriesSocialInfo" if scope == "series_review" else "episodeSocialInfo"
            page = next(v for v in router["loaderData"].values()
                        if isinstance(v, dict) and key in v)
            detail = page["seriesDetail"]
            assert str(detail["series_id"]) == series_id
            social = page[key]["reviews"]
            comments = social.get("reviews") or []
            sampled = datetime.now(ZONE).isoformat(timespec="seconds")
            episode_id = str(page["vid"]) if scope == "default_episode_comment" else ""
            pages.append({
                "series_id": series_id, "title": detail["series_name"], "board": board,
                "scope": scope, "episode_id": episode_id, "url": url, "http_status": status,
                "sampled_at": sampled, "preview_length": len(comments),
                "reported_total": social.get("total_count"), "envelope_keys": sorted(social),
                "platform_comment_id_present": any(
                    set(obj) & {"id", "review_id", "comment_id"} for obj in comments),
            })
            if scope == "series_review":
                parser = EpisodeLinks()
                parser.feed(html)
                pages[-1]["episode_navigation_in_detail"] = parser.links
            for position, obj in enumerate(comments, 1):
                records.append({
                    "series_id": series_id, "scope": scope, "episode_id": episode_id,
                    "source_position": position, "content": PRIVATE.sub("[redacted]", obj["content"]),
                    "create_time": obj.get("create_time"), "digg_count": obj.get("digg_count"),
                    "rating": obj.get("rating"), "sampled_at": sampled, "url": url,
                })
            time.sleep(0.55)
    (OUT / "page_checks.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2))
    with (OUT / "comment_previews.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)
    for page in pages:
        print(page["series_id"], page["scope"], page["preview_length"], page["reported_total"])


if __name__ == "__main__":
    collect()
