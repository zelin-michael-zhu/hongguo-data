"""Retrospective sensitivity: one rank-based slot after two momentum selections."""
from collections import defaultdict
from pathlib import Path
from statistics import median
import csv
import json

OUT=Path(__file__).resolve().parent
with (OUT/'events.csv').open(encoding='utf-8-sig') as f:
    events=list(csv.DictReader(f))
groups=defaultdict(list)
for row in events:
    if row['future3_calendar_complete']!='True':
        continue
    for name in ['pre_2day_change','prior_best_rank','prev_fav','delta3','return3']:
        row[name]=int(row[name]) if row[name] else None
    groups[row['date']].append(row)

def rank(row):
    return row['prior_best_rank'],row['id']

def ordered(row,key):
    score=row[key]
    return score is None, -(score or 0),*rank(row)

records=[]
for day,group in sorted(groups.items()):
    rating=sorted(group,key=rank)
    growth=sorted(group,key=lambda row:ordered(row,'pre_2day_change'))
    stock=sorted(group,key=lambda row:ordered(row,'prev_fav'))
    first=growth[:2]
    hybrid=(first+[r for r in rating if r['id'] not in {x['id'] for x in first}])[:3]
    portfolios={'rank':rating[:3],'growth':growth[:3],'stock':stock[:3],'hybrid':hybrid}
    observed=[r for r in group if r['delta3'] is not None]
    max_gain=max((r['delta3'] for r in observed),default=None)
    winners={r['id'] for r in observed if r['delta3']==max_gain}
    all_known=len(group)==len(observed)
    shared=all(r['delta3'] is not None for rr in portfolios.values() for r in rr)
    for method,rs in portfolios.items():
        stocks={r['id'] for r in rs}
        known=[r for r in rs if r['delta3'] is not None]
        missing=[r for r in observed if r['id'] not in stocks]
        max_miss=max((r['delta3'] for r in missing),default=None)
        records.append(dict(date=day,rule=method,candidates=len(group),outcomes_known=len(observed),all_candidates_complete=all_known,joint_complete=shared,
                            ids='|'.join(r['id'] for r in rs),n=len(rs),return_hits=sum(r['return3'] for r in rs),
                            delta3=sum(r['delta3'] for r in known) if len(known)==len(rs) else None,covered_daily_biggest=int(bool(winners&stocks)) if all_known else None,
                            largest_unselected_net=max_miss if all_known else None))
def write(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write('hybrid_by_day.csv',records)
summary={}
for start in ['2026-10-13','2026-11-05']:
    chosen=[r for r in records if r['date']>=start and r['joint_complete']]
    byday={r['date']:r['delta3'] for r in chosen if r['rule']=='hybrid'}
    sub={}
    for method in portfolios:
        select=[r for r in chosen if r['rule']==method]
        diffs=[byday[r['date']]-r['delta3'] for r in select]
        full=[r for r in select if r['all_candidates_complete']]
        sub[method]=dict(days=len(select),slots=sum(r['n'] for r in select),growth_sum=sum(r['delta3'] for r in select),median_daily_growth=median(r['delta3'] for r in select),returns=sum(r['return_hits'] for r in select),
                         hybrid_wdl=[sum(x>0 for x in diffs),sum(x==0 for x in diffs),sum(x<0 for x in diffs)],
                         all_candidate_complete_days=len(full),covered_daily_biggest=sum(r['covered_daily_biggest'] for r in full),
                         worst_missed=max((r['largest_unselected_net'] for r in full),default=None))
    summary[start]=sub
(OUT/'hybrid_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(summary)
