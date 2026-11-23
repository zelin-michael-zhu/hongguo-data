"""Replay fixed-size, calendar-day editorial tracking lists using archived Hongguo charts."""
import csv
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
HISTORY = OUTPUTS / "hongguo_free_pilot_2026-11-18" / "history"
PAIR_FILE = OUTPUTS / "hongguo_topic_implementation_2026-11-19" / "identity" / "pair_identity.csv"
K = 10
CUTOFFS = (10,12,15,20)
LATE_START, LATE_END = date(2026,11,5), date(2026,11,14)


def read(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def write(name, rows):
    with (HERE/name).open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

charts = defaultdict(dict)
for r in read(HISTORY/"board_daily.csv"):
    key = r["board"], date.fromisoformat(r["date"])
    rank=int(r["rank"])
    assert rank not in charts[key]
    charts[key][rank] = (r["id"],r["title"])
charts={key:[rows[n] for n in range(1,101)] for key,rows in charts.items()
        if set(rows)==set(range(1,101)) and len({v[0] for v in rows.values()})==100}
units = {}
for r in read(PAIR_FILE):
    assert r["old_html_group"]==r["new_html_group"]
    for id_key in ("old_id","new_id"):
        sid=r[id_key]
        assert sid not in units or units[sid]==r["old_html_group"]
        units[sid]=r["old_html_group"]
checks=[]
duplicates=[]
for (board,day), chart in sorted(charts.items()):
    for size in (10,20):
        selected=set()
        for rank,(sid,title) in enumerate(chart[:size],1):
            gid=units.get(sid)
            if gid and gid in selected:
                duplicates.append({"board":board,"date":day,"size":size,"rank":rank,"id":sid,"title":title,"group_id":gid})
            if gid:
                selected.add(gid)
        covered=sum(sid in units for sid,title in chart[:size])
        checks.append({"board":board,"date":day,"size":size,"confirmed_duplicate_slots":covered-len(selected),"resolved_title_rows":covered})
write("season_slots.csv",checks)
write("season_collisions.csv",duplicates)

day_rows=[]
selections=[]
for board in sorted({key[0] for key in charts}):
    last_day=None
    last_lists={}
    for key in sorted(key for key in charts if key[0]==board):
        day=key[1]
        chart=charts[key]
        ranks={sid:i for i,(sid,title) in enumerate(chart,1)}
        names=dict(chart)
        first=last_day is None or last_day+timedelta(days=1)!=day
        next3=[charts.get((board,day+timedelta(days=i))) for i in (1,2,3)]
        next_top = {sid for sid,_ in next3[0][:K]} if next3[0] else None
        future_counts=None
        if all(next3):
            future_counts=Counter(sid for later in next3 for sid,_ in later[:K])
        for limit in CUTOFFS:
            prior = set() if first else last_lists[limit]
            kept={sid for sid in prior if ranks.get(sid,101)<=limit}
            ordered=[sid for sid,_ in chart if sid not in kept]
            chosen=kept | set(ordered[:K-len(kept)])
            assert len(chosen)==K
            entrants=chosen-prior
            day_rows.append(dict(board=board,date=day.isoformat(),cutoff=limit,first=int(first),
                                switches=len(entrants) if not first else "",
                                next_top10=sum(sid in next_top for sid in chosen) if next_top is not None else "",
                                two_of_three=sum(future_counts[sid]>=2 for sid in chosen) if future_counts is not None else "",
                                gross_future_slots=sum(future_counts[sid] for sid in chosen) if future_counts is not None else ""))
            for sid in sorted(chosen,key=ranks.get):
                selections.append(dict(board=board,date=day.isoformat(),cutoff=limit,id=sid,title=names[sid],rank=ranks[sid],
                                        first=int(first),new=int(sid in entrants) if not first else "",
                                        next_top10=int(sid in next_top) if next_top is not None else "",
                                        future_top10_days=future_counts[sid] if future_counts is not None else ""))
            last_lists[limit]=chosen
        last_day=day
write("daily_policy.csv",day_rows)
write("selected_titles.csv",selections)
summary=[]
for span in ("all","late"):
    for board_scope in ["all"]+sorted({key[0] for key in charts}):
        for limit in CUTOFFS:
            pool=[r for r in day_rows if r["cutoff"]==limit and not r["first"] and (board_scope=="all" or r["board"]==board_scope)
                  and (span=="all" or LATE_START.isoformat()<=r["date"]<=LATE_END.isoformat())]
            for label in ("next_top10","two_of_three"):
                eligible=[r for r in pool if r[label]!=""]
                summary.append(dict(span=span,board=board_scope,cutoff=limit,label=label,denominator_board_days=len(eligible),
                                    portfolio_slots=K*len(eligible),switches=sum(r["switches"] for r in eligible),hits=sum(r[label] for r in eligible)))
write("policy_summary.csv",summary)
print(json.dumps([r for r in summary if r['board']=='all' and r['cutoff'] in {10,15}],ensure_ascii=False,indent=2))

# Alternate editorial objective, cumulative net favorites after list selection.
fav = {(r["id"],r["date"]):int(r["fav"]) for r in read(HISTORY/"drama_daily.csv") if r["fav"]!=""}
portfolios=defaultdict(dict)
for r in selections:
    key=(r["date"],r["board"])
    portfolios[key].setdefault(r["cutoff"],[]).append(r)
favorite_rows=[]
for (when,board), policies in sorted(portfolios.items()):
    if policies[10][0]["first"]:continue
    if policies[10][0]["future_top10_days"]=="":continue
    later=(date.fromisoformat(when)+timedelta(days=3)).isoformat()
    # For direct policy comparisons use a shared board-day only if all portfolios can be measured.
    both_endpoints={sid for policy in policies.values() for item in policy
                    if (sid:=item['id'],when) in fav and (sid,later) in fav}
    complete=all(item['id'] in both_endpoints for policy in policies.values() for item in policy)
    for limit,items in policies.items():
        observed=[item['id'] for item in items if item['id'] in both_endpoints]
        favorite_rows.append(dict(date=when,board=board,cutoff=limit,observed=len(observed),all_policies_complete=int(complete),
                                  selected_net_favorites=sum(fav[sid,later]-fav[sid,when] for sid in observed) if len(observed)==K else ""))
write('favorite_outcomes.csv',favorite_rows)
for span in ('all','late'):
    pool=[r for r in favorite_rows if (span=='all' or LATE_START.isoformat()<=r['date']<=LATE_END.isoformat()) and r['all_policies_complete']]
    print(span,'complete for all',len(pool)//len(CUTOFFS),{c:sum(r['selected_net_favorites'] for r in pool if r['cutoff']==c) for c in CUTOFFS})
