"""Make historical selections without the later website group ID; score frozen event labels."""
import sys
from collections import defaultdict

from replay import BOARDS, BUDGETS, HERE, HORIZONS, POLICIES, earliest, prep_events, read_csv, write_csv

sys.path.insert(0,str(HERE.parent/'policies'))
from policies import select_orders


def main():
    days,slates,ranks,head,events=prep_events()
    asof_rows=read_csv(HERE.parent/'identity/asof_groups.csv')
    proxy={(r['date'],r['id']):r['group'] for r in asof_rows}
    assert all(r['first_list_date']<=r['date'] for r in asof_rows)
    picked={}
    for (d,b),slots in slates.items():
        public=[dict(rank=i,id=sid,group=proxy[d.isoformat(),sid]) for i,(sid,_,_) in slots.items()]
        orders=select_orders(public)
        later_group={sid:g for sid,g,n in slots.values()}
        for k in BUDGETS:
            for p in POLICIES:
                items=orders[p][:k]
                assert len(items)==k
                picked[d,b,k,p]={later_group[x['id']] for x in items}
    output=[]
    for e in events:
        t,b,g=e['day'],e['board'],e['group']
        for k in BUDGETS:
            for h in HORIZONS:
                orig=earliest(picked,t,b,k,'original',g,h)
                for p in POLICIES:
                    lead=earliest(picked,t,b,k,p,g,h)
                    output.append(dict(day=t,board=b,group=g,k=k,horizon=h,policy=p,earliest_days_before=lead,
                                       original_days_before=orig,candidate=int(e[f'best_prior_{h}d_rank']!='')))
    grouped=defaultdict(list)
    for r in output:
        for b in (r['board'],'all_boards'):
            grouped[b,r['k'],r['horizon'],r['policy']].append(r)
    rows=[]
    for (b,k,h,p),rs in sorted(grouped.items()):
        hits=[r for r in rs if r['earliest_days_before']]
        rows.append(dict(board=b,k=k,horizon=h,policy=p,all_events=len(rs),reachable=sum(r['candidate'] for r in rs),
                         captured=len(hits),policy_only=sum(not r['original_days_before'] for r in hits),
                         baseline_only=sum(r['original_days_before']>0 and r['earliest_days_before']==0 for r in rs),
                         both_with_policy_earlier=sum(r['earliest_days_before']>r['original_days_before']>0 for r in rs),
                         both_with_policy_later=sum(r['original_days_before']>r['earliest_days_before']>0 for r in rs)))
    write_csv('asof_event_summary.csv',rows)


if __name__=='__main__':
    main()
