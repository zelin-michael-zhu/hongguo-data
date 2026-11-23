"""Replay fixed five-title monitoring lists from the locally archived Hongguo charts."""
import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
HISTORY = OUT.parents[2] / "outputs/hongguo_free_pilot_2026-11-18/history"
BOARDS = ("ai", "comic", "real", "hot")
DAY = timedelta(days=1)
SLOTS = 5
METHODS = ("category_rank", "published_heat", "two_day_rise", "one_per_category")
def save(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

by_date = defaultdict(lambda: defaultdict(dict))
first_hot = {}
titles = {}
with (HISTORY / "board_daily.csv").open(encoding="utf-8-sig", newline="") as file:
    for row in csv.DictReader(file):
        dt = date.fromisoformat(row["date"])
        board, sid = row["board"], row["id"]
        assert sid not in by_date[dt][board]
        by_date[dt][board][sid] = (int(row["rank"]), int(row["heat"]) if row["heat"] else None)
        if board == "hot":
            first_hot[sid] = min(dt, first_hot.get(sid, dt))
        titles[sid] = row["title"]

complete = {d for d, boards in by_date.items() if all(
    set(rank for rank, heat in boards[b].values()) == set(range(1, 101)) for b in BOARDS)}
origins = sorted(d for d in complete if all(d - j * DAY in complete for j in range(1, 8)))
scored = {d for d in origins if all(d + j * DAY in complete for j in range(1, 4))}
queue = {m:{} for m in METHODS}
selected, risk, distinct_evaluable_entries = [], [], set()
for dt in origins:
    today = by_date[dt]
    past2 = by_date[dt-2*DAY]
    records = {}
    for b in BOARDS[:-1]:
        for sid,(rank,heat) in today[b].items():
            if first_hot.get(sid,date.max) <= dt:
                continue
            row = records.setdefault(sid, {"sid":sid, "title":titles[sid], "ranks":[],
                                             "heats":[], "rises":[]})
            prev = past2[b].get(sid,(101,None))[0]
            row["ranks"].append((rank,b))
            row["rises"].append((prev-rank,b,prev,rank))
            if heat is not None:
                row["heats"].append(heat)
    candidates = []
    for sid,row in records.items():
        best_rank, best_board = min(row["ranks"])
        rise, rise_board, old_rank, new_rank = max(row["rises"])
        heat = max(row["heats"]) if row["heats"] else -1
        days_until = (first_hot[sid]-dt).days if sid in first_hot else None
        info = dict(date=str(dt), id=sid, title=row["title"], category=best_board,
                    best_rank=best_rank, published_heat=heat, capped_rise=rise,
                    rise_board=rise_board, rank_minus_2_capped=old_rank,
                    rank_t_on_rise_board=new_rank,
                    hit=int(days_until is not None and 1 <= days_until <= 3),
                    lead_days=days_until if days_until and 1<=days_until<=3 else "",
                    first_hot_date=str(first_hot[sid]) if sid in first_hot else "")
        if dt in scored:
            risk.append(info.copy())
        candidates.append(info)
    if dt in scored:
        distinct_evaluable_entries.update(sid for sid,first in first_hot.items() if 1 <= (first-dt).days <= 3)
    for method in METHODS:
        # A selection covers today plus the next two decision days. All choices use current or older data.
        pool = [r for r in candidates if dt >= queue[method].get(r["id"], date.min)]
        if method == "category_rank":
            order = sorted(pool,key=lambda r:(r["best_rank"],int(r["id"])))
        elif method == "published_heat":
            order = sorted(pool,key=lambda r:(-r["published_heat"],r["best_rank"],int(r["id"])))
        elif method == "two_day_rise":
            order = sorted(pool,key=lambda r:(-r["capped_rise"],r["best_rank"],int(r["id"])))
        else:
            overall = sorted(pool,key=lambda r:(-r["published_heat"],r["best_rank"],int(r["id"])))
            guaranteed = [next(row for row in overall if row["category"]==b) for b in BOARDS[:-1] if any(row["category"]==b for row in overall)]
            guaranteed_ids = {row["id"] for row in guaranteed}
            order = guaranteed + [row for row in overall if row["id"] not in guaranteed_ids]
        for i,r in enumerate(order[:SLOTS],1):
            queue[method][r["id"]]=dt+3*DAY
            if dt in scored:
                selected.append(dict(method=method,slot=i,**r))

all_target_dates = sorted({dt+i*DAY for dt in scored for i in range(1,4)})
full_opportunities = {d for d in all_target_dates if all(d-i*DAY in scored for i in range(1,4))}
full_entries = {sid for sid in distinct_evaluable_entries if first_hot[sid] in full_opportunities}
observable = {r["id"] for r in risk if r["hit"]}
max_lead = defaultdict(int)
for r in risk:
    if r["hit"] and r["id"] in full_entries:
        max_lead[r["id"]] = max(max_lead[r["id"]], r["lead_days"])
def recent_signals(sid):
    entry = first_hot[sid]
    assert all(entry-j*DAY in complete for j in range(1,8))
    return {j for j in range(1,8) if any(sid in by_date[entry-j*DAY][b] for b in BOARDS[:-1])}
signals7 = {sid:recent_signals(sid) for sid in full_entries}
summary = dict(eligible_decision_days=len(scored),dates=[str(d) for d in sorted(scored)],unique_candidates=len({r["id"] for r in risk}),
               eligible_title_days=len(risk),eligible_positive_title_days=sum(r["hit"] for r in risk),
               missing_heat=sum(r["published_heat"]==-1 for r in risk),
               target_date_count=len(all_target_dates),all_distinct_entries_in_union=len(distinct_evaluable_entries),distinct_possible=len(observable),
               full_opportunities=dict(target_dates=len(full_opportunities),entries=len(full_entries),observable=len(observable&full_entries),max_lead_days=dict(Counter(max_lead[sid] for sid in full_entries)),observable_prior_7=sum(bool(v) for v in signals7.values()),observable_day2_to7=sum(any(j>=2 for j in v) for v in signals7.values()),max_lead_in_prior_7=dict(Counter(max(v or {0}) for v in signals7.values()))),methods={})
for method in METHODS:
    subset=[r for r in selected if r["method"]==method]
    hits=[r for r in subset if r["hit"]]
    assert len(hits)==len({r["id"] for r in hits})
    summary["methods"][method]=dict(slots=len(subset),hits=len(hits),lead_counts=dict(Counter(r["lead_days"] for r in hits)),
                                full_opportunity_hits=sum(r["id"] in full_entries for r in hits),
                                candidates_selected=len({r["id"] for r in subset}),
                                category_hits=dict(Counter(r["category"] for r in hits)),
                                category_slots=dict(Counter(r["category"] for r in subset)))
by_origin=[]
for d in sorted(scored):
    rs=[r for r in risk if r["date"]==str(d)]
    by_origin.append(dict(date=str(d),eligible=len(rs),any_hit=sum(r["hit"] for r in rs),**{m:sum(r["hit"] for r in selected if r["method"]==m and r["date"]==str(d)) for m in METHODS}))
rank_checks = []
for dt in sorted(scored):
    cutoff = max(r["best_rank"] for r in selected if r["method"]=="category_rank" and r["date"]==str(dt))
    other = [r["best_rank"] for r in risk if r["date"]==str(dt) and r["category"]!="real"]
    rank_checks.append(dict(date=str(dt),worst_selected_category_rank=cutoff,best_other_category_rank=min(other)))
summary["first_five_real_not_a_tie_days"] = sum(r["worst_selected_category_rank"]<r["best_other_category_rank"] for r in rank_checks)
save("category_rank_support.csv",rank_checks)
save("selected.csv",selected)
save("candidate_days.csv",risk)
save("by_origin.csv",by_origin)
(OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False))
