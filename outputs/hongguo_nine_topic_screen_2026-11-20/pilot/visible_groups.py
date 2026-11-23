"""Count observed titles, verified season groups and exact synopsis reuse in chart archives."""
import csv
import json
from collections import defaultdict, Counter
from itertools import combinations
from statistics import median
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HISTORY = ROOT / "outputs/hongguo_free_pilot_2026-11-18/history"
IDENTITY = ROOT / "outputs/hongguo_topic_implementation_2026-11-19/identity"
def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))

catalog = {r["id"]: r for r in read_csv(HISTORY / "catalog.csv")}
positions = defaultdict(lambda: defaultdict(list))
for r in read_csv(HISTORY / "board_daily.csv"):
    positions[r["date"]][r["board"]].append((int(r["rank"]),r["id"]))
codes = ["ai","real","comic","hot"]
complete = {d for d,day in positions.items() if all(sorted(k for k,v in day[c]) == list(range(1,101)) for c in codes)}
cohorts = {c: {v for d in complete for _,v in positions[d][c]} for c in codes}
verified = {}
for r in read_csv(IDENTITY / "pair_identity.csv"):
    if r["identity_confirmed"]!="1":
        continue
    assert r["old_html_group"]==r["new_html_group"]==r["old_app_album_id"]==r["new_app_album_id"]
    for role in ("old","new"):
        v=r[f"{role}_id"]
        assert v not in verified or verified[v] == r["old_html_group"]
        verified[v]=r["old_html_group"]
def groups(ids):
    return len({("verified",verified[sid]) if sid in verified else ("unresolved",sid) for sid in ids})
def by_board(ids):
    exact=defaultdict(list)
    for sid in sorted(ids):
        s="".join(catalog[sid]["synopsis"].split())
        if s: exact[s].append(sid)
    return {"unique_title_ids":len(ids),"verified_season_ids":len(set(verified)&ids),"known_groups":len({verified[v] for v in ids if v in verified}),"max_groups_after_known_merges":groups(ids),"nonblank_synopses":sum(map(len,exact.values())),"unique_exact_nonblank_synopses":len(exact),"duplicate_synopsis_clusters":sum(len(v)>1 for v in exact.values()),"nonblank_detail_tags":sum(bool(catalog[v]["detail_tags"]) for v in ids),"unique_distinct_detail_tags":len({t for v in ids for t in catalog[v]["detail_tags"].split("|") if t})}
summary={"catalog_titles":len(catalog),"catalog_nonblank_synopsis":sum(bool(r["synopsis"].strip()) for r in catalog.values()),"date_count":len(positions),"complete_date_count":len(complete),"complete_date_span":[min(complete),max(complete)],"incomplete_dates":sorted(set(positions)-complete),"boards":{c:by_board(s) for c,s in cohorts.items()},"union":by_board(set.union(*cohorts.values())),"cross_board_overlap_over_period":{f"{c}|{e}":len(cohorts[c]&cohorts[e]) for c,e in combinations(codes,2)}}
for code, ids in cohorts.items():
    labels = [catalog[sid]["detail_tags"].split("|") for sid in ids if catalog[sid]["detail_tags"]]
    summary["boards"][code]["median_detail_tags_per_labeled_id"] = median(map(len, labels))
    summary["boards"][code]["top_ten_labeled_terms"] = Counter(tag for tags in labels for tag in tags).most_common(10)
summary["cross_board_same_day_overlap_seats"]={f"{c}|{e}":sum(len({v for _,v in positions[d][c]} & {v for _,v in positions[d][e]}) for d in complete) for c,e in combinations(codes,2)}
groups_examples = defaultdict(list)
for sid in cohorts["ai"] | cohorts["comic"]:
    if sid in verified and catalog[sid]["synopsis"].strip():
        groups_examples["".join(catalog[sid]["synopsis"].split())].append(sid)
examples=[]
for s,ids in sorted(groups_examples.items(),key=lambda x:-len(x[1])):
    if len(ids)>1:
        examples.append({"titles":[catalog[v]["title"] for v in sorted(ids)],"ids":sorted(ids),"same_verified_group":len({verified[v] for v in ids})==1 and all(v in verified for v in ids),"synopsis_excerpt":s[:55]})
summary["exact_synopsis_examples_known_seasons"]=examples[:6]
summary["catalog_columns"]=list(next(iter(catalog.values())).keys())
file=ROOT/'outputs/hongguo_tool_probe_2026-11-18/hongguo_data_catalog_sample.json'
probe=json.loads(file.read_text())
summary["separate_sitemap_sample"]={"sample_size":len(probe),"columns":list(probe[0]),"new_at_values":[r.get('new_at') for r in probe]}
(HERE / "visible_groups.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False)[:6250])
