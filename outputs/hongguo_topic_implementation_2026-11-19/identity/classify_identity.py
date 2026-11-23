"""Reconcile the two frozen public surfaces without reading engagement outcomes."""
from pathlib import Path
import csv
from collections import Counter
from datetime import date, datetime
import hashlib
import json
from statistics import median
from zoneinfo import ZoneInfo

DIR = Path(__file__).resolve().parent
def read_json(name):
    return json.loads((DIR / name).read_text())
def write_csv(name, rows):
    with (DIR / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
def shown_time(value):
    return datetime.fromtimestamp(int(value), ZoneInfo("Asia/Shanghai")) if value and int(value) > 0 else None
def same_nonblank(*values):
    return bool(values[0]) and len(set(values)) == 1
def short_key(pair):
    return hashlib.sha256((pair["pre"] + ":" + pair["post"]).encode()).hexdigest()[:12]

pairs = read_json("independent_candidate_selection.json")
cache = read_json("public_season_metadata.json")
raw = cache["details"]
web = read_json("official_web_identity.json")
with (DIR / "synopsis_first_pass.csv").open(encoding="utf-8-sig") as f:
    notes = {(r["pre"], r["post"]): r for r in csv.DictReader(f)}
rows, blinded = [], []
for pair in pairs:
    a, b = [raw.get(pair[k], {}) for k in ("pre", "post")]
    w1, w2 = [web["pages"].get(pair[k], {}) for k in ("pre", "post")]
    webgroups = [(w.get("season_info") or {}).get("series_group_id") for w in (w1, w2)]
    a1, a2 = a.get("related_album_id"), b.get("related_album_id")
    n1, n2 = a.get("season_index"), b.get("season_index")
    adjacent = (isinstance(n1, int) and isinstance(n2, int) and n2 == n1+1
                and n1 == pair["prev_order"] and n2 == pair["next_order"])
    sdk_ok = same_nonblank(a1, a2) and adjacent and all(x.get("is_multi_season") is True for x in (a,b))
    webpage_ok = same_nonblank(a1, a2, *webgroups)
    conflict = any(x and y and x != y for x,y in zip((a1,a2), webgroups))
    if conflict:
        level = "cross_surface_conflict"
    elif sdk_ok and webpage_ok:
        level = "app_adjacent_and_web_same_group"
    elif sdk_ok:
        level = "app_adjacent_only"
    elif same_nonblank(*webgroups):
        level = "web_group_order_unconfirmed"
    else:
        level = "unverified"
    time_a, time_b = [shown_time(w.get("first_visible_time")) for w in (w1,w2)]
    lag = (date.fromisoformat(pair["event"])-time_b.date()).days if time_b else None
    rec1, rec2 = w1.get("record_number"), w2.get("record_number")
    note = notes[(pair["pre"],pair["post"])]
    exact = bool(a.get("description")) and a.get("description") == b.get("description")
    if note["code"] == "R":
        assert exact
    key = short_key(pair)
    rows.append(dict(blind_id=key,family=pair["family"],old_id=pair["pre"],new_id=pair["post"],
        old_title=a.get("title"),new_title=b.get("title"),event_date=pair["event"],identity_status=level,
        identity_confirmed=int(sdk_ok and not conflict),old_app_album_id=a1,new_app_album_id=a2,
        old_platform_order=n1,new_platform_order=n2,old_html_group=webgroups[0],new_html_group=webgroups[1],
        old_content_type=a.get("content_type"),new_content_type=b.get("content_type"),
        same_nonempty_book_id=int(same_nonblank(a.get("related_novel_book_id"),b.get("related_novel_book_id"))),
        old_web_first_visible_shanghai=time_a.isoformat() if time_a else "",
        new_web_first_visible_shanghai=time_b.isoformat() if time_b else "", lag_to_archive_first_seen_days=lag,
        old_record_number=rec1,new_record_number=rec2,record_numbers_status=("same" if rec1==rec2 else "different") if rec1 and rec2 else "missing",
        synopsis_code=note["code"],synopsis_note=note["agent_note"],production_split_reissue_status="undetermined",
        old_detail_url=a.get("source_page"),new_detail_url=b.get("source_page"),old_app_retrieved_utc=a.get("time"),
        new_app_retrieved_utc=b.get("time"),old_html_retrieved_utc=w1.get("fetched_at_utc"),new_html_retrieved_utc=w2.get("fetched_at_utc")))
    blinded.append({"blind_id":key,"older_title":a.get("title"),"later_title":b.get("title"),"older_synopsis":a.get("description"),"later_synopsis":b.get("description"),"coder_category":"","supporting_detail":""})
write_csv("pair_identity.csv",rows)
write_csv("blind_coding_sheet.csv",sorted(blinded,key=lambda x:x["blind_id"]))
lags=[r["lag_to_archive_first_seen_days"] for r in rows if r["lag_to_archive_first_seen_days"] is not None]
stats = {"pairs":len(rows),"platform_titles_returned":len(raw),"families":len({x["family"] for x in rows}),
         "event_dates":len({x["event_date"] for x in rows}), "html_pages":len(web["pages"]), "html_failures":web["failures"],
         "identity_evidence_levels":dict(Counter(x["identity_status"] for x in rows)), "distinct_record_number_comparison":dict(Counter(x["record_numbers_status"] for x in rows)),
         "lag_days_distribution":dict(sorted(Counter(lags).items())), "median_lag":median(lags) if lags else None,
         "synopsis_categories":dict(Counter(x["synopsis_code"] for x in rows)),"positive_case_families":len({x["family"] for x in rows if x["synopsis_code"]=="E"}),
         "same_book_confirmed_pairs":sum(x["same_nonempty_book_id"] for x in rows),"content_type_titles":dict(Counter(x.get("content_type") for x in raw.values())),
         "alternate_album_directory_error_codes":dict(Counter(x["code"] for x in cache["failures"] if x["stage"]=="album_error"))}
(DIR/"identity_summary.json").write_text(json.dumps(stats,indent=2,ensure_ascii=False)+"\n")
print(json.dumps(stats, ensure_ascii=False))
