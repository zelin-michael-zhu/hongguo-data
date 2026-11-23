"""Join panel rows to dated, public Hongguo metadata; never backfill a past prediction."""
import argparse
import csv
import hashlib
import json
import sys
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
PREV = OUT / "hongguo_watchlist_review_2026-11-21"
sys.path.insert(0, str(OUT / "hongguo_expansion_2026-11-21/identity"))
sys.path.insert(0, str(PREV / "identity"))
from explicit_seasons import MARKER, season_number
from title_keys import explicit_key

SH = ZoneInfo("Asia/Shanghai")
THEMES = {
    "romance": ("爱情", "恋爱", "甜宠", "婚恋", "先婚后爱", "暗恋"),
    "urban": ("都市", "现代"),
    "historical": ("古风", "古代", "古装", "宫廷", "架空"),
    "action": ("动作", "打斗", "武侠", "武术"),
    "fantasy": ("玄幻", "奇幻", "修仙", "仙侠", "异能", "神魔"),
    "family": ("家庭", "亲情", "萌宝", "育儿", "婆媳"),
    "suspense": ("悬疑", "探案", "推理", "刑侦"),
    "rebirth": ("重生", "穿越", "穿书"),
}


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def last_day_details(last, timestamp):
    # Only consider local pages whose actual capture timestamp is on/before the prediction.
    result = {}
    for p in (OUT / "hongguo_expansion_2026-11-21/identity/pages").glob("*.json"):
        page = json.loads(p.read_text())
        capture = datetime.fromisoformat(page["fetched_at_utc"]).astimezone(SH)
        if capture.date().isoformat() != last or capture > timestamp:
            continue
        detail = page["detail"]
        published = detail.get("first_visible_time")
        visible = datetime.fromtimestamp(int(published), SH).date().isoformat() if published else ""
        result[p.stem] = dict(title=detail.get("series_name"), episodes=detail.get("episode_cnt"),
                              tags=detail.get("tags") or [], first_visible=visible)
    return result


def assemble(archive, panel_path):
    wanted = defaultdict(list)
    for r in read(panel_path):
        wanted[r["date"]].append(r)
    extension = PREV / "extension"
    final = json.loads((extension / "sources.json").read_text())[-1]
    last = final["day"]
    final_dir = (extension / final["source"]).parent
    manifest = json.loads((final_dir / "manifest.json").read_text())
    # Individual final-board pages were collected at slightly different times.
    last_at = max(datetime.fromisoformat(v["at"]) for b in manifest["boards"].values() for v in b["pages"])
    final_details = last_day_details(last, last_at)
    cache, frozen, chart_dates, rows = {}, {}, defaultdict(set), []
    days = sorted(p.stem for p in archive.glob("*.json") if "2026-10-13" <= p.stem < last) + [last]
    for day in days:
        if day == last:
            boards = {p.stem:json.loads(p.read_text()) for p in final_dir.glob("*.json") if p.stem!="manifest"}
            names = {str(r["id"]):r["title"] for board in boards.values() for r in board}
            details = final_details
        else:
            snap = json.loads((archive / (day+".json")).read_text())
            assert snap["date"] == day and not snap["stale"]
            details = snap["items"]
            boards = {b:r["items"] for b,r in snap["boards"].items()}
            names = {str(r["id"]):details.get(str(r["id"]),{}).get("title","")
                     for board in boards.values() for r in board}
        for sid,v in details.items():
            tags = v.get("tags") or []
            detailed = v.get("detail_tags") or []
            if not all(isinstance(t,str) for t in tags+detailed):
                raise ValueError("unexpected tag schema")
            # Tag vocabulary audit uses the same card-level tags across all dates.
            values = dict(episodes=v.get("episodes"), first_visible=v.get("first_visible"),
                          tags=tags, featured_tag=tags[0] if tags else "")
            for k,val in values.items():
                if val not in (None,"",[]):
                    cache.setdefault(sid,{})[k] = (val,day)
        for sid,name in names.items():
            frozen.setdefault(sid,explicit_key(name,sid))
        cutoff=(date.fromisoformat(day)-timedelta(days=7)).isoformat()
        prior_ids=set().union(*(ids for d,ids in chart_dates.items() if cutoff<=d<day))
        recent=defaultdict(set)
        for sid in prior_ids:
            recent[frozen[sid]].add(sid)
        for r in wanted[day]:
            sid=r["id"]
            fields=cache.get(sid,{})
            val=lambda k,default:fields.get(k,(default,""))[0]
            tags=val("tags",[]); first=val("first_visible","")
            age=(date.fromisoformat(day)-date.fromisoformat(first)).days+1 if first else ""
            tag=val("featured_tag","")
            peers=[cache.get(str(v["id"]),{}).get("featured_tag",("", ""))[0] for v in boards[r["board"]] if str(v["id"])!=sid]
            valid=[t for t in peers if t]
            marks=MARKER.findall(unicodedata.normalize("NFKC",r["title"]))
            key=frozen[sid]
            row=dict(date=day,id=sid,episodes=val("episodes",""),web_first_visible=first,web_age=age,
                     episode_date=fields.get("episodes",("",""))[1],tags_date=fields.get("tags",("",""))[1],
                     season_number=season_number(marks[0]) if len(marks)==1 else "",tag_count=len(tags) if tags else "",
                     prior_sibling_count7=len(recent[key]-{sid}) if key.startswith("t:") else "",
                     theme_share=sum(t==tag for t in valid)/len(valid) if tag and valid else "",
                     featured_tag=tag,tags="|".join(tags),peers_with_tag=len(valid))
            for theme,markers in THEMES.items():
                row["tag_"+theme]=int(any(m in t for m in markers for t in tags)) if tags else ""
            assert all(v[1]<=day for v in fields.values())
            rows.append(row)
        chart_dates[day].update(names)
    return rows


def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--archive-dir",type=Path)
    arg.add_argument("--broad",action="store_true",help="Join all observed chart ages to allow selection by website age.")
    args=arg.parse_args()
    archive=args.archive_dir or next(Path(tempfile.gettempdir()).glob("hongguo_watchlist_archive_*/radar/data/snapshots/hongguo"))
    source_checks = read(OUT / "hongguo_franchise_forecast_2026-11-21/own_source_checks.csv")
    for source in source_checks:
        if "2026-10-13" <= source["date"] <= "2026-11-20":
            snapshot = archive / (source["date"] + ".json")
            if hashlib.sha256(snapshot.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError(f"Archive digest changed: {snapshot}")
    panel=HERE/("broad_panel.csv" if args.broad else "panel.csv")
    rows=assemble(archive,panel)
    assert len(rows)==len({(r["date"],r["id"]) for r in rows})==len(read(panel))
    with (HERE/("broad_content.csv" if args.broad else "content.csv")).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)


if __name__=="__main__":
    main()
