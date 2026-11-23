"""Measure a fixed-length shortlist using only candidates in the observed top 100."""
import csv
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

OUT = Path(__file__).resolve().parent
BASE = OUT.parent


def load(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(name, rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run():
    identities = load(BASE/'hongguo_expansion_2026-11-21/identity/identity_coverage.csv')
    keys = {r['series_id']:r['series_group_id'] or r['old_sdk_album_id'] for r in identities}
    def family(row):
        key=keys[row['id']]
        return 'season:'+key if key else 'title:'+row['id']
    entries=defaultdict(list)
    for row in load(BASE/'hongguo_free_pilot_2026-11-18/history/board_daily.csv'):
        row['rank']=int(row['rank'])
        entries[row['date'],row['board']].append(row)
    days=sorted({d for d,b in entries})
    boards=('hot','real','ai','comic')
    valid={d for d in days if all({r['rank'] for r in entries[d,b]}==set(range(1,101))
                                  and len(entries[d,b])==100 for b in boards)}
    assert len(valid)==35
    scenarios=[]
    turns=[]
    for day in sorted(valid):
        yesterday=(date.fromisoformat(day)-timedelta(days=1)).isoformat()
        for board in boards:
            rows=sorted(entries[day,board],key=lambda r:r['rank'])
            assert len(set(r['id'] for r in rows))==100
            for k in (10,20,50,100):
                original=rows[:k]
                original_families=set(map(family,original))
                if yesterday in valid:
                    prior=sorted(entries[yesterday,board],key=lambda r:r['rank'])[:k]
                    previous_ids={r['id'] for r in prior}
                    previous_families=set(map(family,prior))
                    entrants=[r for r in original if r['id'] not in previous_ids]
                    known=[r for r in entrants if keys[r['id']]]
                    already_present=sum(family(r) in previous_families for r in known)
                    turns.append(dict(date=day,board=board,k=k,entering_ids=len(entrants),
                                      entering_with_official_group=len(known),entering_ids_with_group_on_prior_day=already_present))
                if k==100:
                    continue
                for cap in (1,2):
                    selected=[]
                    counts=Counter()
                    for row in rows:
                        fid=family(row)
                        if counts[fid]<cap:
                            selected.append(row)
                            counts[fid]+=1
                        if len(selected)==k:
                            break
                    assert len(selected)==k
                    replaced=sum(r['rank']>k for r in selected)
                    gained=len(counts)-len(original_families)
                    scenarios.append(dict(date=day,board=board,k=k,cap=cap,
                                          baseline_distinct=len(original_families),after_distinct=len(counts),
                                          extra_families=gained,replacements=replaced,deepest_original_rank=selected[-1]['rank'],
                                          incoming=' | '.join(r['title'] for r in selected if r['rank']>k)))
    save('同系列限额逐日演算.csv',scenarios)
    save('隔日入榜逐日核验.csv',turns)
    summary=[]
    for b in boards:
        for k in (10,20,50):
            for cap in (1,2):
                sub=[r for r in scenarios if (r['board'],r['k'],r['cap'])==(b,k,cap)]
                summary.append(dict(board=b,k=k,cap=cap,board_days=len(sub),
                                    mean_distinct_original=round(mean(r['baseline_distinct'] for r in sub),4),
                                    mean_families_gained=round(mean(r['extra_families'] for r in sub),4),
                                    mean_replaced=round(mean(r['replacements'] for r in sub),4),
                                    max_deepest_original_rank=max(r['deepest_original_rank'] for r in sub)))
    save('同系列限额汇总.csv',summary)
    summary=[]
    for b in boards:
        for k in (10,20,50,100):
            sub=[r for r in turns if (r['board'],r['k'])==(b,k)]
            d=sum(r['entering_ids'] for r in sub)
            n=sum(r['entering_ids_with_group_on_prior_day'] for r in sub)
            summary.append(dict(board=b,k=k,consecutive_day_pairs=len(sub),entering_ids=d,
                                known_group_entrants=sum(r['entering_with_official_group'] for r in sub),
                                confirmed_group_already_present=n,share_of_entering_ids=round(n/d,4) if d else ''))
    save('隔日入榜汇总.csv',summary)


if __name__=='__main__':
    run()
