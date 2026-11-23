"""Audit playback count fields on public default player pages without loading media."""
import gzip
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from first_episode_duration import HERE, SOURCE, read, save


ROUTER = re.compile(r"\b_ROUTER_DATA\s*=\s*")
STRUCTURED = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S)
COUNT = re.compile(
    r"(?:play|watch|view|impress|expos).*?(?:count|cnt|num|uv|pv|total)|"
    r"(?:count|cnt|num|total).*?(?:play|watch|view|impress|expos)|"
    r"^(?:userinteractioncount|interactionstatistic|playvv|viewvv|playviews|viewcounts|plays|views|vv|播放量|播放次数|观看次数)$",
    re.I,
)


def count_paths(obj, prefix):
    if isinstance(obj, list):
        for value in obj:
            yield from count_paths(value, prefix + "[]")
    elif isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}"
            if COUNT.search(key):
                yield path
            yield from count_paths(value, path)


def examine(series_id, episode_id):
    url = f"https://hongguoduanju.com/player/{series_id}"
    row = {
        "series_id": series_id, "expected_first_episode_id": episode_id, "source": url,
        "status": "", "http_status": "", "collected_at_utc": "", "first_episode_id_verified": False,
        "episode_social_fields": "", "comment_count": "", "like_count": "", "candidate_count_fields": "",
    }
    row["collected_at_utc"] = datetime.now(timezone.utc).isoformat()
    try:
        request = Request(url, headers={"Accept": "text/html", "Accept-Encoding": "gzip"})
        with urlopen(request, timeout=12) as response:
            row["http_status"] = response.status
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
    except HTTPError as exc:
        row.update(http_status=exc.code, status="HTTP error")
        return row
    except (TimeoutError, URLError) as exc:
        row["status"] = f"Request error: {type(exc).__name__}"
        return row

    try:
        html = body.decode("utf-8")
        marker = ROUTER.search(html)
        if marker is None:
            raise ValueError("Page data absent")
        data = json.JSONDecoder().raw_decode(html[marker.end():].lstrip())[0]["loaderData"]
        page = next(v for v in data.values() if isinstance(v, dict) and "seriesDetail" in v)
        detail = page["seriesDetail"]
        verified = str(detail["series_id"]) == series_id and (
            str(page["vid"]) == str(detail["vid_list"][0]) == episode_id
        )
        row["first_episode_id_verified"] = verified
        if not verified:
            row["status"] = "First-episode ID mismatch"
            return row
        social = page.get("episodeSocialInfo") or {}
        row["episode_social_fields"] = "|".join(sorted(social))
        row["comment_count"] = (social.get("reviews") or {}).get("total_count")
        row["like_count"] = social.get("episode_like_count")
        candidates = set(count_paths(data, "loaderData"))
        for match in STRUCTURED.finditer(html):
            candidates.update(count_paths(json.loads(match[1]), "jsonld"))
        row["candidate_count_fields"] = "|".join(sorted(candidates))
        row["status"] = "Count field review needed" if candidates else "No playback count fields"
    except (ValueError, KeyError, IndexError, StopIteration, TypeError) as exc:
        row["status"] = f"Page parse error: {type(exc).__name__}"
    return row


def main():
    pairs = read(HERE / "首集曝光讨论_前后季明细.csv")
    ids = sorted({row[f"{side}_id"] for row in pairs for side in ("older", "newer")})
    episode_ids = {
        row["series_id"]: row["episode_id"]
        for row in read(SOURCE / "episode_index.csv") if row["episode_position"] == "1"
    }
    assert len(pairs) == 42 and len(ids) == 66
    audited = {}
    for series_id in ids:
        checked = examine(series_id, episode_ids[series_id])
        audited[series_id] = checked
        print(series_id, checked["status"], checked["candidate_count_fields"], flush=True)
        if checked["http_status"] in (401, 403, 429):
            break
        time.sleep(0.8)

    save("首集播放量_逐集网页核查.csv", list(audited.values()))
    print(Counter(row["status"] for row in audited.values()), flush=True)


if __name__ == "__main__":
    main()
