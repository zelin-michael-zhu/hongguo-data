"""Fixed-horizon follow-up after an observed exit from all four archived boards."""
from pathlib import Path
from datetime import date,timedelta
import csv, json, statistics
from collections import defaultdict,Counter

OUT=Path(__file__).resolve().parent
HIST=OUT.parents[1]/'hongguo_free_pilot_2026-11-18/history'
def read(name):
    with (HIST/name).open(encoding='utf-8-sig',newline='') as fp:return list(csv.DictReader(fp))
def dt(s):return date.fromisoformat(s)
def dump(name,records):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as fp:
        w=csv.DictWriter(fp,fieldnames=list(records[0])); w.writeheader();w.writerows(records)
days=defaultdict(lambda:defaultdict(dict))
for r in read('board_daily.csv'):
    days[dt(r['date'])][r['board']][r['id']]=int(r['rank'])
complete={d for d,bs in days.items() if set(bs)=={'hot','ai','comic','real'} and all(len(x)==100 and set(x.values())==set(range(1,101)) for x in bs.values())}
def union(d):
    return set().union(*(set(v) for v in days[d].values()))
titles={}; fav={}
for r in read('drama_daily.csv'):
    titles[r['id']]=r['title']
    if r['fav']!='':fav[dt(r['date']),r['id']]=int(r['fav'])
def lag(a,b):
    if a is None or b is None:return None
    return a-b
one=timedelta(days=1)
rows=[]; all_by_day=defaultdict(list)
for d in sorted(complete):
    prev=d-one
    if prev not in complete:continue
    for sid in sorted(union(prev)-union(d)):
        ranks={b:v[sid] for b,v in days[prev].items() if sid in v}
        row=dict(date=d.isoformat(),id=sid,title=titles[sid],prior_boards='|'.join(sorted(ranks)),prior_best_rank=min(ranks.values()),pre_2day_change=lag(fav.get((prev,sid)),fav.get((d-3*one,sid))),fav0=fav.get((d,sid)),prev_fav=fav.get((prev,sid)))
        for h in (3,7):
            dates=[d+i*one for i in range(1,h+1)]
            row[f'future{h}_calendar_complete']=all(k in complete for k in dates)
            row[f'fav{h}']=fav.get((d+h*one,sid))
            row[f'delta{h}']=lag(row[f'fav{h}'],row['fav0'])
            row[f'return{h}']=int(any(sid in union(k) for k in dates)) if row[f'future{h}_calendar_complete'] else None
        rows.append(row);all_by_day[d].append(row)
dump('events.csv',rows)
summary={}
for h in (3,7):
    eligible=[r for r in rows if r[f'future{h}_calendar_complete']]
    known=[r for r in eligible if r[f'delta{h}'] is not None]
    sub={}
    for label,pred in [('all',lambda r:True),('returned',lambda r:r[f'return{h}']==1),('never_returned',lambda r:r[f'return{h}']==0)]:
        group=[r for r in known if pred(r)]; vals=[r[f'delta{h}'] for r in group]
        sub[label]=dict(n=len(group),unique=len({r['id'] for r in group}),median=statistics.median(vals) if vals else None,net_pos=sum(v>0 for v in vals),net_ge10000=sum(v>=10000 for v in vals),net_neg=sum(v<0 for v in vals))
    summary[str(h)]=dict(eligible=len(eligible),unique=len({r['id'] for r in eligible}),n_days=len({r['date'] for r in eligible}),have_endpoints=len(known),returning=sum(r[f'return{h}'] for r in eligible),sub=sub)
# Freeze decisions from the currently observable board exits. Growth score looks backwards two intervals to day -1.
# Keep events with missing prior increments in the list; fill after scored events in order of the rank baseline.
# Workload is an illustration: exactly min(3,n_exits) reviews per usable date.
cells=[]
for d,candidates in all_by_day.items():
    if not candidates[0]['future3_calendar_complete']: continue
    def rankkey(r):return (r['prior_best_rank'],r['id'])
    simple=sorted(candidates,key=rankkey)[:3]
    momentum=sorted(candidates,key=lambda r:(r['pre_2day_change'] is None,-(r['pre_2day_change'] or 0),*rankkey(r)))[:3]
    stock=sorted(candidates,key=lambda r:(r['prev_fav'] is None,-(r['prev_fav'] or 0),*rankkey(r)))[:3]
    for name,ss in [('prior_rank',simple),('prior_2d_favorite_growth',momentum),('prior_favorite_stock',stock)]:
        cells.append(dict(date=d.isoformat(),rule=name,n_candidates=len(candidates),n_usable_pre=sum(r['pre_2day_change'] is not None for r in candidates),slots=len(ss),returns3=sum(r['return3'] for r in ss),known_growth3=sum(r['delta3'] is not None for r in ss),sum_delta3=sum(r['delta3'] if r['delta3'] is not None else 0 for r in ss) if all(r['delta3'] is not None for r in ss) else None,overlap=len({r['id'] for r in simple}&{r['id'] for r in momentum}),selection='|'.join(r['id'] for r in ss)))
dump('policy_by_day.csv',cells)
summary['source']={'event_rows':len(rows),'unique':len({r['id'] for r in rows}),'complete_chart_days':len(complete),'adjacent_complete_day_pairs':len(all_by_day),'single_board_exits':sum(sum(len(set(days[d-one][b])-set(v)) for b,v in days[d].items()) for d in complete if d-one in complete)}
summary['policy']={}
for name in ['prior_rank','prior_2d_favorite_growth']:
    a=[r for r in cells if r['rule']==name]; paired_dates={r['date'] for r in a if r['sum_delta3'] is not None}&{r['date'] for r in cells if r['rule'] in {'prior_2d_favorite_growth','prior_rank'}-{name} and r['sum_delta3'] is not None}
    summary['policy'][name]=dict(slots=sum(r['slots'] for r in a),days=len(a),returns=sum(r['returns3'] for r in a),overlap=sum(r['overlap'] for r in a),paired_complete_days=len(paired_dates),sum_growth_paired_dates=sum(r['sum_delta3'] for r in a if r['date'] in paired_dates))
groups=defaultdict(dict)
for c in cells:groups[c['date']][c['rule']]=c
sensitivity={}
for baseline in ('prior_rank','prior_favorite_stock'):
    for start in ('2026-10-13','2026-11-05'):
        dates=[k for k,v in groups.items() if k>=start and v[baseline]['sum_delta3'] is not None and v['prior_2d_favorite_growth']['sum_delta3'] is not None]
        b=[groups[k][baseline]['sum_delta3'] for k in dates]
        m=[groups[k]['prior_2d_favorite_growth']['sum_delta3'] for k in dates]
        dif=[i-j for i,j in zip(m,b)]
        sensitivity[baseline+'_'+start]=dict(days=len(dates),baseline=sum(b),momentum=sum(m),wins=sum(v>0 for v in dif),ties=sum(v==0 for v in dif),losses=sum(v<0 for v in dif),median_daily_difference=statistics.median(dif),leave_one_out_sums=[sum(dif)-max(dif),sum(dif)-min(dif)])
summary['sensitivity']=sensitivity
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False))
