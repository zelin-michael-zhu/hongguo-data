"""Evaluate pre-entry discovery of Top20 groups on contiguous, jointly complete slates."""
import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
BOARDS = ('hot','real','ai','comic')
BUDGETS = (10,20,30,50)
HORIZONS = (3,7)
WASHOUT = 7
POLICIES = ('original','cap1','cap2','aggregate','dynamic','mmr')
DAY = timedelta(days=1)


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def write_csv(name, rows):
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


def ratio(x,y):
    return round(x/y,6) if y else ''


def average(items):
    return round(mean(items),4) if items else ''


def get_slates():
    groups={}
    for r in read_csv(OUTPUTS/'hongguo_expansion_2026-11-21/identity/identity_coverage.csv'):
        sid=r['series_id']
        gid=r['series_group_id'] or r['old_sdk_album_id']
        groups[sid]='g:'+gid if gid else 'i:'+sid
    slates=defaultdict(dict)
    for r in read_csv(OUTPUTS/'hongguo_free_pilot_2026-11-18/history/board_daily.csv'):
        slot=slates[date.fromisoformat(r['date']), r['board']]
        rank=int(r['rank'])
        assert rank not in slot
        slot[rank]=(r['id'],groups[r['id']],r['title'])
    all_ranks=set(range(1,101))
    days=sorted(d for d in {k[0] for k in slates} if all(slates[d,b].keys()==all_ranks for b in BOARDS))
    assert len(days)==35
    slates={k:v for k,v in slates.items() if k[0] in days}
    return days,slates


def history(days, d, lag):
    prior=[d-DAY*i for i in range(1,lag+1)]
    return prior if all(x in days for x in prior) else []


def prep_events():
    days,slates=get_slates()
    ranks={}
    names={}
    for (d,b),s in slates.items():
        groups={}
        for r in sorted(s):
            _,g,n=s[r]
            if g not in groups:
                groups[g]=r
                names[d,b,g]=n
        ranks[d,b]=groups
    head={(d,b):{g for g,r in m.items() if r<=20} for (d,b),m in ranks.items()}
    events=[]
    for d in days:
        prior=history(days,d,WASHOUT)
        if not prior:
            continue
        for b in BOARDS:
            previous=set.union(*(head[t,b] for t in prior))
            for g in sorted(head[d,b]-previous,key=lambda g:ranks[d,b][g]):
                rows=[ranks[t,b].get(g) for t in prior]
                events.append(dict(day=d,board=b,group=g,entry_rank=ranks[d,b][g],example_entry_title=names[d,b,g],
                                   best_prior_3d_rank=min((r for r in rows[:3] if r is not None),default=''),
                                   best_prior_7d_rank=min((r for r in rows if r is not None),default=''),
                                   detected_group_id=int(g.startswith('g:'))))
    write_csv('top20_episode_registry.csv',events)
    return days,slates,ranks,head,events


def load_policies(days,slates):
    lists=defaultdict(list)
    path=HERE.parent/'policies/watchlists.csv'
    for row in read_csv(path):
        d=date.fromisoformat(row['date'])
        b,k,p=row['board'],int(row['k']),row['policy']
        if k not in BUDGETS or p not in POLICIES:
            continue
        slot=slates[d,b][int(row['rank'])]
        assert (row['id'],row['group'])==slot[:2], (d,b,k,p,row,slot)
        lists[d,b,k,p].append(row['group'])
    assert all(len(lists[d,b,k,p])==k for d in days for b in BOARDS for k in BUDGETS for p in POLICIES)
    return {k:set(v) for k,v in lists.items()}


def earliest(lookup,t,b,k,p,g,h):
    return max((i for i in range(1,h+1) if g in lookup[t-DAY*i,b,k,p]),default=0)


def event_scores(events,lists,days):
    details=[]
    for e in events:
        t,b,g=e['day'],e['board'],e['group']
        for h in HORIZONS:
            reachable=int(e[f'best_prior_{h}d_rank']!='')
            for k in BUDGETS:
                original=earliest(lists,t,b,k,'original',g,h)
                for policy in POLICIES:
                    lead=earliest(lists,t,b,k,policy,g,h)
                    assert not (lead and not reachable)
                    details.append(dict(episode_day=t,board=b,group=g,example_entry_title=e['example_entry_title'],
                                        entry_rank=e['entry_rank'],horizon=h,k=k,policy=policy,candidate_before_entry=reachable,
                                        captured=int(lead>0),lead_if_captured=lead or '',
                                        original_lead_if_captured=original or '',
                                        paired_lead_gain=lead-original if lead and original else ''))
    write_csv('event_by_policy.csv',details)
    groups=defaultdict(list)
    for r in details:
        b=r['board']; period='early_block' if r['episode_day'].month==10 else 'later_block'
        for label in ('all',period):
            for name in (b,'all_boards'):
                groups[label,name,r['horizon'],r['k'],r['policy']].append(r)
    scores=[]
    eligible=[d for d in days if history(days,d,WASHOUT)]
    for (period,b,h,k,p),rows in sorted(groups.items()):
        successes=sum(r['captured'] for r in rows)
        reachable=sum(r['candidate_before_entry'] for r in rows)
        baseline_only=sum(not r['captured'] and bool(r['original_lead_if_captured']) for r in rows)
        policy_only=sum(r['captured'] and not r['original_lead_if_captured'] for r in rows)
        paired=[r['paired_lead_gain'] for r in rows if r['paired_lead_gain']!='']
        n_dates=sum(period=='all' or (d.month==10)==(period=='early_block') for d in eligible)
        scores.append(dict(period=period,board=b,horizon=h,k=k,policy=p,n_entry_calendar_days=n_dates,
                           board_group_date_episodes=len(rows),distinct_groups=len({r['group'] for r in rows}),
                           reachable_episodes=reachable,outside_candidate_pool=len(rows)-reachable,
                           captured_episodes=successes,end_to_end_recall=ratio(successes,len(rows)),
                           reachable_recall=ratio(successes,reachable),baseline_only=baseline_only,policy_only=policy_only,
                           both_capture=len(paired),neither=len(rows)-baseline_only-policy_only-len(paired),
                           mean_lead_if_captured=average([r['lead_if_captured'] for r in rows if r['captured']]),
                           paired_earlier=sum(d>0 for d in paired),paired_later=sum(d<0 for d in paired),
                           paired_equal=sum(d==0 for d in paired),paired_mean_lead_gain=average(paired),
                           paired_median_lead_gain=median(paired) if paired else ''))
    write_csv('event_summary.csv',scores)


def opportunities(days,ranks,head,events,lists):
    lookup=defaultdict(set)
    for e in events:
        lookup[e['day'],e['board']].add(e['group'])
    panel=[]
    for t in days:
        if not history(days,t,WASHOUT-1):
            continue
        for h in HORIZONS:
            future=[t+i*DAY for i in range(1,h+1)]
            if not all(d in days for d in future):
                continue
            for b in BOARDS:
                target=set.union(*(lookup[d,b] for d in future))-head[t,b]
                available=target & ranks[t,b].keys()
                for k in BUDGETS:
                    for p in POLICIES:
                        alerts=lists[t,b,k,p]-head[t,b]
                        hits=len(target & alerts)
                        panel.append(dict(date=t,board=b,horizon=h,k=k,policy=p,all_future_groups=len(target),
                                          future_groups_in_todays_100=len(available),selected_nonhead_groups=len(alerts),
                                          captured_future_groups=hits))
    write_csv('decision_date_outcomes.csv',panel)
    aggregates=defaultdict(Counter)
    for r in panel:
        for b in (r['board'],'all_boards'):
            a=aggregates[b,r['horizon'],r['k'],r['policy']]
            for field in ('all_future_groups','future_groups_in_todays_100','selected_nonhead_groups','captured_future_groups'):
                a[field]+=r[field]
            a['board_days']+=1
    scores=[]
    for (b,h,k,p),a in sorted(aggregates.items()):
        hits=a['captured_future_groups']
        scores.append(dict(board=b,horizon=h,k=k,policy=p,**a,
                           recall_from_all_future=ratio(hits,a['all_future_groups']),
                           recall_from_candidate_pool=ratio(hits,a['future_groups_in_todays_100']),
                           yield_per_selected_nonhead_group=ratio(hits,a['selected_nonhead_groups'])))
    write_csv('decision_date_summary.csv',scores)


if __name__=='__main__':
    days,slates,ranks,head,events=prep_events()
    print('Events from seven-day washout:',len(events),Counter(e['board'] for e in events))
    policies=load_policies(days,slates)
    event_scores(events,policies,days)
    opportunities(days,ranks,head,events,policies)
