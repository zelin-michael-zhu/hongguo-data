"""Offline shortlist rules for a fixed pool of visible positions. Python standard library."""
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean


OUT = Path(__file__).resolve().parent
BASE = OUT.parents[1]
BOARDS = ('hot', 'real', 'ai', 'comic')
KS = (10, 20, 30, 50)
RULES = ('original', 'cap1', 'cap2', 'aggregate', 'dynamic', 'mmr')


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_rows(name, rows):
    path = OUT / name
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    temp.replace(path)


def select_orders(rows):
    """Return full selection order for each rule. Input ranks remain in their original 1–100 scale."""
    ranked = sorted(rows, key=lambda r: r['rank'])
    counts = Counter()
    head = Counter(r['group'] for r in ranked if r['rank'] <= 20)
    first = {}
    group_score = Counter()
    capped_one, capped_two, adaptive = [], [], []
    for r in ranked:
        group = r['group']
        group_score[group] += 1 / r['rank']
        counts[group] += 1
        if counts[group] == 1:
            capped_one.append(r)
            first[group] = r
        if counts[group] <= 2:
            capped_two.append(r)
        if counts[group] <= max(1, min(3, head[group])):
            adaptive.append(r)
    ordered_groups = sorted(first, key=lambda g: (-group_score[g], first[g]['rank']))

    # With binary group similarity, 396*(0.8*q - 0.2*similarity)/0.8
    # is proportional to 4*(100-rank) - 99*similarity. Use the integer score.
    candidates = ranked.copy()
    seen = set()
    mmr = []
    while candidates:
        best = max(range(len(candidates)), key=lambda i: (
            4*(100-candidates[i]['rank']) - 99*(candidates[i]['group'] in seen),
            -candidates[i]['rank']))
        choice = candidates.pop(best)
        seen.add(choice['group'])
        mmr.append(choice)
    return dict(original=ranked, cap1=capped_one, cap2=capped_two,
                aggregate=[first[g] for g in ordered_groups], dynamic=adaptive, mmr=mmr)


def select(rows, k):
    return {rule: ordered[:k] for rule, ordered in select_orders(rows).items()}


def load_panels():
    fields = read_rows(BASE / 'hongguo_expansion_2026-11-21/identity/identity_coverage.csv')
    groups = {}
    for r in fields:
        official = r['series_group_id'] or r['old_sdk_album_id']
        groups[r['series_id']] = 'g:'+official if official else 'i:'+r['series_id']
    panels = defaultdict(list)
    path = BASE / 'hongguo_free_pilot_2026-11-18/history/board_daily.csv'
    for r in read_rows(path):
        r['rank'] = int(r['rank'])
        r['group'] = groups[r['id']]
        panels[r['date'], r['board']].append(r)
    all_days = sorted({day for day, _ in panels})
    expected = set(range(1,101))
    days = [day for day in all_days if all(len(panels[day,b]) == 100 and
            {r['rank'] for r in panels[day,b]} == expected and
            len({r['id'] for r in panels[day,b]}) == 100 for b in BOARDS)]
    assert len(days) == 35
    return days, {(day, b):panels[day,b] for day in days for b in BOARDS}


def utc_day_back(day, n):
    return (date.fromisoformat(day) - timedelta(days=n)).isoformat()


def utility(rows):
    return sum(1/math.log2(1+r['rank']) for r in rows)


def coverage_price_regions(summary):
    """Upper envelope of six lines: rank-retention points plus specified price per series."""
    import itertools
    result=[]
    for b in BOARDS:
        for k in KS:
            rules=[r for r in summary if r['board']==b and r['k']==k]
            cuts={0.0}
            for a,c in itertools.combinations(rules,2):
                difference=a['coverage']-c['coverage']
                if abs(difference)>1e-12:
                    crossing=100*(c['rank_retention']-a['rank_retention'])/difference
                    if crossing>1e-10:
                        cuts.add(round(crossing,10))
            bounds=sorted(cuts)+[math.inf]
            intervals=[]
            for left,right in zip(bounds,bounds[1:]):
                mid=(left+right)/2 if math.isfinite(right) else left+1
                scores={r['policy']:100*r['rank_retention']+mid*r['coverage'] for r in rules}
                best=max(scores.values())
                ties='|'.join(p for p in RULES if abs(scores[p]-best)<1e-9)
                if intervals and intervals[-1][2]==ties:
                    intervals[-1]=(intervals[-1][0],right,ties)
                else:
                    intervals.append((left,right,ties))
            for left,right,ties in intervals:
                result.append(dict(board=b,k=k,from_weight=left,to_weight=right if math.isfinite(right) else '',
                                   rule_with_max_toy_score=ties))
    return result


def run():
    days, panels = load_panels()
    watchlists, metrics, stress = [], [], []
    history = {}
    for day in days:
        for b in BOARDS:
            orders = select_orders(panels[day,b])
            for k in (*KS, 100):
                baseline = orders['original'][:k]
                baseline_mass = utility(baseline)
                topm = {r['id'] for r in baseline[:min(k,20)]}
                for rule in RULES:
                    rows = orders[rule][:k]
                    ids = {r['id'] for r in rows}
                    grps = {r['group'] for r in rows}
                    assert len(ids) == len(rows)
                    complete = len(rows) == k
                    deepest = max(r['rank'] for r in rows)
                    # Full candidate-pool scans and the deepest selected item are distinct.
                    if rule in ('aggregate','mmr'):
                        input_depth = 100
                    elif complete:
                        input_depth = max(deepest,20) if rule=='dynamic' else deepest
                    else:
                        input_depth = 100
                    stress.append(dict(date=day,board=b,k=k,policy=rule,selected=len(rows),
                                       filled=int(complete),unfilled=k-len(rows),
                                       deepest_selected_rank=deepest,input_inspection_depth=input_depth,
                                       refill_needs_beyond_100=int(not complete),
                                       refill_depth_lower_bound_when_unfilled=101 if not complete else ''))
                    if k==100:
                        continue
                    assert complete
                    for pos,r in enumerate(rows,1):
                        watchlists.append(dict(date=day,board=b,k=k,policy=rule,selection_order=pos,
                                               rank=r['rank'],id=r['id'],group=r['group']))
                    previous = history.get((utc_day_back(day,1), b,k,rule))
                    history7 = [history.get((utc_day_back(day,i), b,k,rule)) for i in range(1,8)]
                    unseen = None
                    if all(h is not None for h in history7):
                        seen = set().union(*(h[1] for h in history7))
                        unseen = len(grps-seen)
                    history[day,b,k,rule]=(ids,grps)
                    rank_mass = utility(rows)
                    head_keep = len(ids & topm)
                    metrics.append(dict(date=day,board=b,k=k,policy=rule,coverage=len(grps),
                                        rank_utility=rank_mass,rank_retention=rank_mass/baseline_mass,
                                        top_m=min(k,20),top_m_retained_count=head_keep,
                                        top_m_retention=head_keep/len(topm),
                                        new_vs_own_prior_7_complete_days=unseen,
                                        item_turnover=None if previous is None else len(ids-previous[0]),
                                        family_turnover=None if previous is None else len(grps-previous[1]),
                                        n_vs_original_replaced=len(ids-{r['id'] for r in baseline}),
                                        deepest_selected_rank=deepest))
    write_rows('watchlists.csv',watchlists)
    write_rows('daily_metrics.csv',metrics)
    write_rows('depth_diagnostics.csv',stress)
    cols=('coverage','rank_utility','rank_retention','top_m_retained_count','top_m_retention',
          'new_vs_own_prior_7_complete_days','item_turnover','family_turnover','n_vs_original_replaced')
    summary=[]
    stress_summary=[]
    for b in BOARDS:
        for k in (*KS,100):
            for p in RULES:
                sr=[r for r in stress if (r['board'],r['k'],r['policy'])==(b,k,p)]
                stress_summary.append(dict(board=b,k=k,policy=p,days=len(sr),
                                           n_unfilled=sum(1-r['filled'] for r in sr),
                                           fraction_unfilled=mean(1-r['filled'] for r in sr),
                                           max_deepest_selection=max(r['deepest_selected_rank'] for r in sr),
                                           max_input_depth=max(r['input_inspection_depth'] for r in sr),
                                           mean_unfilled_slots=mean(r['unfilled'] for r in sr)))
                if k==100:
                    continue
                dr=[r for r in metrics if (r['board'],r['k'],r['policy'])==(b,k,p)]
                values={c:[r[c] for r in dr if r[c] is not None] for c in cols}
                result=dict(board=b,k=k,policy=p,days=len(dr),turnover_days=len(values['item_turnover']),
                            prior_seven_days_complete=len(values['new_vs_own_prior_7_complete_days']))
                result.update({key:mean(vals) for key,vals in values.items()})
                summary.append(result)
    write_rows('summary.csv',summary)
    write_rows('depth_summary.csv',stress_summary)
    write_rows('coverage_tradeoff_regions.csv',coverage_price_regions(summary))
    # Check K=50 cap2 against independently published pilot.
    prior=read_rows(BASE/'hongguo_three_pilots_2026-11-21/同系列限额汇总.csv')
    for row in prior:
        a=next(x for x in summary if x['board']==row['board'] and x['k']==int(row['k']) and x['policy']=='cap'+row['cap'])
        base=next(x for x in summary if x['board']==row['board'] and x['k']==int(row['k']) and x['policy']=='original')
        assert abs((a['coverage']-base['coverage'])-float(row['mean_families_gained']))<0.000051
    print(json.dumps(dict(days=len(days),lists=len(metrics),item_rows=len(watchlists),
                          incomplete_lists_at_K_to_50=sum(1-r['filled'] for r in stress if r['k']!=100),
                          incomplete_stress_K100=sum(1-r['filled'] for r in stress if r['k']==100))))


if __name__=='__main__':
    run()
