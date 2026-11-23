"""Build one row per still-eligible title/decision date from frozen daily Hongguo charts."""

import csv
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent
BOARDS = ("hot", "real", "ai", "comic")
STEP = timedelta(days=1)


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def write(name, rows):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as dest:
        writer = csv.DictWriter(dest, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def observed_charts():
    original = OUTPUT / "hongguo_free_pilot_2026-11-18/history"
    later = OUTPUT / "hongguo_watchlist_review_2026-11-21/extension"
    same_day_titles = {(r["date"],r["id"]):r["title"] for r in read(original/"drama_daily.csv")}
    own = {(r["date"],r["board"],r["id"]):r for r in read(OUTPUT/"hongguo_franchise_forecast_2026-11-21/own.csv")}
    by_title = defaultdict(lambda:defaultdict(dict))
    by_board = defaultdict(lambda:defaultdict(set))
    for source in (original/"board_daily.csv", later/"new_rank_days.csv"):
        for row in read(source):
            ds, b, sid, rank = row["date"], row["board"], row["id"], int(row["rank"])
            d=date.fromisoformat(ds)
            assert rank not in by_board[d][b] and b not in by_title[d][sid]
            title = same_day_titles[ds,sid] if source.parent==original else row["title"]
            heat = own[ds,b,sid]["heat"]
            by_title[d][sid][b] = dict(title=title,rank=rank,heat=float(heat) if heat else None)
            by_board[d][b].add(rank)
    return by_title, by_board


def complete_dates(boards, cutoff):
    required=set(range(1,cutoff+1))
    return {d for d,bs in boards.items() if all(required.issubset(bs[b]) for b in BOARDS)}


def gain(recent, earlier):
    return earlier - recent if earlier is not None and recent is not None else ""


def log_heat(row):
    if row and row["heat"] is not None:
        return math.log1p(row["heat"])
    return None


def make_rows(by_title,boards,min_age=3,max_age=7):
    all_dates=sorted(by_title)
    complete=complete_dates(boards,100)
    outputs=[]
    history=defaultdict(dict)
    prior_best={}
    first={}
    head=set()
    for d in all_dates:
        today=by_title[d]
        for sid, choices in today.items():
            best_key=min(choices,key=lambda b:(choices[b]["rank"], BOARDS.index(b)))
            best=choices[best_key]["rank"]
            first.setdefault(sid,d)
            age=(d-first[sid]).days+1
            if best<=20:
                head.add(sid)
            if d in complete and min_age<=age<=max_age and sid not in head:
                hist=history[sid]
                dates3=[d-2*STEP,d-STEP,d]
                series3=[hist.get(day) if day!=d else (best_key,best) for day in dates3]
                lag2 = series3[0][1] if series3[0] else None
                ranks=[r[1] for r in series3 if r]
                rank1=series3[1][1] if series3[1] else None
                adjacent=[(a[1],b[1]) for a,b in zip(series3,series3[1:]) if a and b]
                heat3=[log_heat(by_title.get(day,{}).get(sid,{}).get(best_key)) for day in dates3]
                if heat3[0] is not None and heat3[2] is not None:
                    heat_growth2=heat3[2]-heat3[0]
                else:
                    heat_growth2=""
                nearby=[first[sid]-i*STEP for i in range(1,8)]
                warm=sum(day in complete for day in nearby)
                consecutive=0
                while first[sid]-(consecutive+1)*STEP in complete:
                    consecutive+=1
                observed_before_head=[h[1] for h in hist.values()]
                row=dict(date=d.isoformat(),id=sid,title=choices[best_key]["title"],board=best_key,
                         rank=best,age=age,first_date=first[sid].isoformat(),
                         warmup_complete_days=warm,prior_consecutive_complete=consecutive,
                         main_eligible=int(warm==7),rank_lag2=lag2 if lag2 is not None else "",
                         rank_lag1=rank1 if rank1 is not None else "",rank_gain2=gain(best,lag2),
                         days_seen3=len(ranks),up_steps=sum(b<a for a,b in adjacent),
                         compared_steps3=len(adjacent),heat=choices[best_key]["heat"] if choices[best_key]["heat"] is not None else "",
                         heat_growth2=heat_growth2,
                         heat_accel=heat3[2]-2*heat3[1]+heat3[0] if all(v is not None for v in heat3) else "",
                         cross_boards=len(choices),boards_today="|".join(b for b in BOARDS if b in choices),
                         peak_rank_prior=min(observed_before_head) if observed_before_head else "",
                         peak_rank_through_today=min(best,prior_best.get(sid,best)),
                         prior3_complete=sum(t in complete for t in dates3),
                         days_seen_since_first=len(hist)+1,
                         chart_switch_2d=int(series3[0][0]!=best_key) if series3[0] else "",
                         rank_range3=max(ranks)-min(ranks),
                         heat_basis_board=best_key)
                outputs.append(row)
            prior_best[sid]=min(best,prior_best.get(sid,best))
            history[sid][d]=(best_key,best)
    return outputs


def add_labels(outputs,by_title,boards):
    seen={cut: {d:{sid for sid,bs in titles.items() if any(r["rank"]<=cut for r in bs.values())}
                for d,titles in by_title.items()} for cut in (10,20)}
    coverage={cut:complete_dates(boards,cut) for cut in seen}
    for row in outputs:
        d=date.fromisoformat(row["date"])
        sid=row["id"]
        for horizon in (7,14,30):
            after=[d+i*STEP for i in range(1,horizon+1)]
            for cut,prefix in ((20,"y"),(10,"top10_")):
                complete=all(t in coverage[cut] for t in after)
                first_hit=next((t.isoformat() for t in after if sid in seen[cut].get(t,())), "")
                row[prefix+str(horizon)]=int(bool(first_hit)) if complete else ""
                if cut==20:
                    row["observed_hit"+str(horizon)]=first_hit
                    row["observed_future_days"+str(horizon)]=sum(t in coverage[cut] for t in after)


def main():
    charts, boards=observed_charts()
    rows=make_rows(charts,boards)
    # Truncating the archive must not change the historical risk set or features.
    for cut in (date(2026,10,28), date(2026,11,12)):
        prefix=make_rows({d:v for d,v in charts.items() if d<=cut}, {d:v for d,v in boards.items() if d<=cut})
        assert prefix==[r for r in rows if date.fromisoformat(r["date"])<=cut]
    add_labels(rows,charts,boards)
    assert len(rows)==len({(r["date"],r["id"]) for r in rows})
    assert all(r["rank"]>20 and r["peak_rank_through_today"]>20 for r in rows)
    rows.sort(key=lambda r:(r["date"],r["rank"],r["id"]))
    write("panel.csv",rows)
    report=[]
    for minimum in (0,3,7):
        selected=[r for r in rows if r["prior_consecutive_complete"]>=minimum]
        for h in (7,14,30):
            labeled=[r for r in selected if r["y"+str(h)]!=""]
            report.append(dict(prior_complete_days_required=minimum,horizon=h,
                               rows=len(selected),titles=len({r["id"] for r in selected}),
                               labeled=len(labeled),positive=sum(r["y"+str(h)] for r in labeled),
                               labeled_titles=len({r["id"] for r in labeled}),
                               positive_titles=len({r["id"] for r in labeled if r["y"+str(h)]}),
                               label_origin_dates=len({r["date"] for r in labeled}),
                               live_count=sum(r["date"]==max(boards).isoformat() for r in selected)))
    write("horizon_support.csv",report)
    dated=[]
    main_rows=[r for r in rows if r["main_eligible"]]
    for h in (7,14,30):
        key="y"+str(h)
        usable=[r for r in main_rows if r[key]!=""]
        for origin in sorted({r["date"] for r in usable}):
            date_rows=[r for r in usable if r["date"]==origin]
            fit=[r for r in usable if date.fromisoformat(r["date"])+h*STEP<date.fromisoformat(origin)]
            dated.append(dict(horizon=h,origin=origin,events=len(date_rows),future_positive=sum(r[key] for r in date_rows),
                              labeled_rows_mature_before_origin=len(fit),
                              mature_positive_rows=sum(r[key] for r in fit),
                              mature_unique_positive_titles=len({r["id"] for r in fit if r[key]})))
    write("origin_support.csv",dated)
    print(json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    main()
