"""Check public card metadata and cover availability, without requesting video or user data."""
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
ARCHIVE = OUTPUTS / "hongguo_expansion_2026-11-21/identity/pages"
BOARD = OUTPUTS / "hongguo_free_pilot_2026-11-18/history/board_daily.csv"
RANK_ROLES = {
    "6": "anchor_season_1", "27": "anchor_season_2", "1": "anchor_season_11",
    "14": "alternative_preview", "26": "alternative_preview",
    "7": "fixed_target", "8": "fixed_target", "23": "fixed_target",
}


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def verify_live(url, sid):
    with urlopen(url, timeout=12) as resp:
        html = resp.read().decode()
    marker = re.search(r"(?:window\.)?_ROUTER_DATA\s*=\s*", html)
    payload, _ = json.JSONDecoder().raw_decode(html, marker.end())
    d = payload["loaderData"]["detail_page"]["seriesDetail"]
    assert str(d["series_id"]) == sid
    cover = d["series_cover"]
    # Read just a signature to verify that a real cover decodes as an image format.
    req = Request(cover, headers={"Range": "bytes=0-31"})
    with urlopen(req, timeout=12) as resp:
        header = resp.read(32)
        image_type = resp.headers.get_content_type()
        assert image_type.startswith("image/")
        assert header.startswith((b"\xff\xd8\xff", b"\x89PNG", b"RIFF", b"GIF8")) or b"ftyp" in header
        code = resp.status
    return d, cover, image_type, code, header.hex()


def main():
    with BOARD.open(encoding="utf-8-sig") as f:
        chart = [r for r in csv.DictReader(f) if r["board"] == "ai" and
                 r["date"] == "2026-11-16" and r["rank"] in RANK_ROLES]
    cards = []
    for r in chart:
        sid = r["id"]
        archive = json.loads((ARCHIVE / (sid + ".json")).read_text())
        detail, cover, image_type, status, signature = verify_live(archive["url"], sid)
        group = detail["season_info"]["series_group_id"]
        assert str(group) == archive["detail"]["season_info"]["series_group_id"]
        cards.append(dict(role=RANK_ROLES[r["rank"]], series_id=sid, group_id=group, title=detail["series_name"],
                          date=r["date"], board=r["board"], rank=r["rank"], detail_url=archive["url"],
                          synopsis_chars=len(detail["series_intro"].strip()), episode_text=detail["episode_right_text"],
                          cover_url=cover, cover_status=status, cover_mime=image_type, cover_signature=signature,
                          verified_utc=datetime.now(timezone.utc).isoformat(timespec="seconds")))
        sleep(.45)
    anchor = [r for r in cards if r["role"].startswith("anchor")]
    assert len(cards) == 8 and len(anchor) == 3 and len({r["group_id"] for r in anchor}) == 1
    assert len({r["group_id"] for r in cards}) == 6 and all(r["synopsis_chars"] for r in cards)
    write("real_cards.csv", cards)
    counts = Counter()
    titled = []
    for p in sorted(ARCHIVE.glob("*.json")):
        record = json.loads(p.read_text())
        d = record["detail"]
        counts["detail_pages"] += 1
        counts["display_all_n_episodes"] += int(bool(re.fullmatch(r"全\d+集", d.get("episode_right_text", ""))))
        counts[f"series_status_{d.get('series_episode_info', {}).get('series_status')}"] += 1
        if "完结" in d["series_name"]:
            titled.append(dict(id=p.stem, title=d["series_name"], url=record["url"],
                               episode_text=d.get("episode_right_text")))
        counts["tag_explicit_ai"] += int(any("AI" in str(tag).upper() or "人工智能" in str(tag)
                                             for tag in d.get("tags", [])))
        counts["status_text_says_finished"] += int("完结" in d.get("episode_right_text", ""))
    write("explicit_titles.csv", titled)
    (HERE / "field_counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2))
    print("cards",len(cards),"groups",len({r["group_id"] for r in cards}),"MIME",
          dict(Counter(r["cover_mime"] for r in cards)),dict(counts))


if __name__ == "__main__":
    main()
