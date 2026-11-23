"""Common-denominator replay of group and individual-title events and robustness checks."""
import csv
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'policies'))
sys.path.insert(0,str(HERE/'identity'))
from policies import BOARDS, KS, RULES, load_panels, read_rows, select_orders, utility
from title_keys import explicit_key


def save(name, rows):
    with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def earlier(day, n):
    return (date.fromisoformat(day)-timedelta(days=n)).isoformat()


def read_panel():
    days, panels = load_panels()
    all_proxy = read_rows(HERE/'identity/asof_groups.csv')
    proxy = {r['id']:r['group'] for r in all_proxy}
    roster = read_rows(HERE.parent/'hongguo_expansion_2026-11-21/identity/identity_coverage.csv')
    retrospective = {r['series_id']:('g:'+(r['series_group_id'] or r['old_sdk_album_id'])
                     if r['series_group_id'] or r['old_sdk_album_id'] else 'i:'+r['series_id']) for r in roster}
    extension = read_rows(HERE/'extension/new_rank_days.csv')
    additional = read_rows(HERE/'extension/new_identity.csv')
    assert {r['id'] for r in additional} == {r['id'] for r in extension} - set(retrospective)
    for entry in additional:
        assert entry['status'] in ('ok_group', 'ok_no_public_group')
        sid = entry['id']
        retrospective[sid] = 'g:'+entry['group_id'] if entry['group_id'] else 'i:'+sid
    for r in sorted(extension,key=lambda x:(x['date'],x['id'],x['board'])):
        sid=r['id']
        proxy.setdefault(sid,explicit_key(r['title'],sid))
        r.update(rank=int(r['rank']),group=retrospective[sid])
        panels.setdefault((r['date'],r['board']),[]).append(r)
    dates=sorted(set(days)|{r['date'] for r in extension})
    for (d,b),rows in panels.items():
        assert len({r['id'] for r in rows})==100
        assert {r['rank'] for r in rows}==set(range(1,101))
    assert len(dates)==39 and all(r['id'] in proxy for rows in panels.values() for r in rows)
    return days,dates,panels,proxy


def sensitivity_groups(days,panels):
    records=[]
    for b in BOARDS:
        costs=Counter(); names={}
        for day in days:
            groups=Counter(r['group'] for r in panels[day,b])
            for r in sorted(panels[day,b],key=lambda x:x['rank']):
                names.setdefault(r['group'],r['title'])
            costs.update({g:n-1 for g,n in groups.items() if n>1})
        for i,(g,n) in enumerate(sorted(costs.items(),key=lambda v:(-v[1],v[0]))[:3],1):
            records.append(dict(board=b,order=i,group=g,example=names[g],extra_slots_over_35d=n))
    return records


def evaluate(days, panels, proxies, board, scenario, asof, removed, period, eval_days):
    head={}; selections={};metrics=[];events=[]
    for day in days:
        rows=[dict(r,truth=r['group']) for r in panels[day,board] if r['group']!=removed]
        if asof:
            for r in rows:r['group']=proxies[r['id']]
        orders=select_orders(rows)
        head[day,'group']={r['truth'] for r in rows if r['rank']<=20}
        head[day,'title']={r['id'] for r in rows if r['rank']<=20}
        for k in KS:
            base_utility=utility(orders['original'][:k])
            for rule in RULES:
                chosen=orders[rule][:k]
                assert len(chosen)==k
                selected={r['id'] for r in chosen}
                groups={r['truth'] for r in chosen}
                selections[day,k,rule]={'group':groups,'title':selected}
                px=selections.get((earlier(day,1),k,rule))
                if day in eval_days:
                    metrics.append((day,k,rule,len(groups),utility(chosen)/base_utility,
                                    len(selected-px['title']) if px else None))
        prior=[earlier(day,i) for i in range(1,8)]
        if day not in eval_days or not all((d,'group') in head for d in prior):
            continue
        for entity in ('group','title'):
            new=head[day,entity]-set.union(*(head[d,entity] for d in prior))
            for value in sorted(new):
                for k in KS:
                    hits={}
                    for rule in RULES:
                        hits[rule]=max((i for i,d in enumerate(prior,1) if value in selections[d,k,rule][entity]),default=0)
                    events.append(dict(date=day,board=board,entity=entity,event_key=value,k=k,**hits))
    results=[]
    for k in KS:
        for rule in RULES:
            rows=[r for r in metrics if (r[1],r[2])==(k,rule)]
            out=dict(period=period,scenario=scenario,board=board,removed=removed,k=k,policy=rule,
                     slate_days=len(rows),coverage=mean(r[3] for r in rows),rank_retention=mean(r[4] for r in rows),
                     daily_new_title_ids=mean(r[5] for r in rows if r[5] is not None))
            for entity in ('group','title'):
                ev=[r for r in events if r['k']==k and r['entity']==entity]
                out[entity+'_events']=len(ev)
                out[entity+'_hits']=sum(bool(r[rule]) for r in ev)
                out[entity+'_gained']=sum(r[rule]>0 and not r['original'] for r in ev)
                out[entity+'_missed']=sum(r['original']>0 and not r[rule] for r in ev)
                out[entity+'_earlier']=sum(r[rule]>r['original']>0 for r in ev)
                out[entity+'_later']=sum(r['original']>r[rule]>0 for r in ev)
            results.append(out)
    return results,events


def mark_frontier(rows):
    buckets=defaultdict(list)
    for r in rows:
        buckets[r['period'],r['scenario'],r['board'],r['k']].append(r)
    def vector(r):
        return (r['coverage'],r['rank_retention'],-r['daily_new_title_ids'],r['group_hits'])
    def dominates(q,r):
        pairs=list(zip(vector(q),vector(r)))
        return all(a>=b-1e-10 for a,b in pairs) and any(a>b+1e-10 for a,b in pairs)
    for candidates in buckets.values():
        for r in candidates:
            r['dominated_by']='|'.join(q['policy'] for q in candidates if dominates(q,r))
            r['on_empirical_four_objective_frontier']=int(not r['dominated_by'])


def main():
    original,extended,panels,proxy=read_panel()
    omitted=sensitivity_groups(original,panels)
    save('removed_groups.csv',omitted)
    results=[]; event_rows=[]
    last_four=set(extended)-set(original)
    for b in BOARDS:
        for scenario,excluded,asof in [('retrospective','',False),('asof_title','',True)]+[
                ('remove_'+str(g['order']),g['group'],False) for g in omitted if g['board']==b]:
            out,ev=evaluate(original,panels,proxy,b,scenario,asof,excluded,'35d',set(original))
            results.extend(out)
            if scenario in ('retrospective','asof_title'):
                event_rows.extend(dict(period='35d',scenario=scenario,**r) for r in ev)
        out,ev=evaluate(extended,panels,proxy,b,'asof_title',True,'','extension4',last_four)
        results.extend(out)
        event_rows.extend(dict(period='extension4',scenario='asof_title',**r) for r in ev)
    mark_frontier(results)
    save('policy_robustness_and_pareto.csv',results)
    save('family_and_title_entry_events.csv',event_rows)
    other=read_rows(HERE/'future/event_summary.csv')
    reference={(r['board'],int(r['k']),r['policy']):int(r['captured_episodes']) for r in other
               if r['period']=='all' and r['board'] in BOARDS and r['horizon']=='7'}
    assert len(reference)==len(BOARDS)*len(KS)*len(RULES)
    for r in results:
        if r['period']=='35d' and r['scenario']=='retrospective':
            assert r['group_hits']==reference[r['board'],r['k'],r['policy']]


if __name__=='__main__':
    main()
