"""Construct title entry and seven-day endpoint observations from complete public charts."""
import csv
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / 'hongguo_watchlist_review_2026-11-21'
sys.path.insert(0, str(PRIOR))
from decision_audit import read_panel
from policies import BOARDS, read_rows


def write(name, records):
    with (HERE / name).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=records[0])
        writer.writeheader()
        writer.writerows(records)


def summarize(events):
    result = []
    for window in ('complete', 'endpoints'):
        valid = [e for e in events if window == 'endpoints' or e['complete_window']]
        for sample in ('all', 'first_board_title'):
            seen = set()
            selected = []
            for e in valid:
                key = (e['board'], e['id'])
                if sample == 'all' or key not in seen:
                    selected.append(e)
                seen.add(key)
            for boards, name in [(BOARDS, 'all'), (('ai','comic'), 'ai_comic')] + [((b,), b) for b in BOARDS]:
                board_rows = [e for e in selected if e['board'] in boards]
                for key in ('1', '0', ''):
                    subset = [r for r in board_rows if r['x'] == key]
                    hits = sum(r['y'] for r in subset)
                    result.append(dict(window=window, sample=sample, board=name, x=key,
                                       events=len(subset), day7_in=hits,
                                       share=hits/len(subset) if subset else '',
                                       distinct_titles=len({r['id'] for r in subset}),
                                       distinct_reference_groups=len({r['group_id'] for r in subset if r['group_id']}),
                                       distinct_event_dates=len({r['date'] for r in subset})))
    return result


def main():
    _, days, panels, proxies = read_panel()
    by_title = {key: {r['id']: r for r in rows} for key,rows in panels.items()}
    title_at = {(r['date'],r['id']):r['title_asof'] for r in read_rows(PRIOR / 'identity/asof_groups.csv')}
    day_set = set(days)
    events = []
    checked_dates = Counter()
    for dt in days:
        start = date.fromisoformat(dt)
        window = [(start+timedelta(days=i)).isoformat() for i in range(-1,8)]
        before, after = window[0], window[-1]
        if not {before,after}.issubset(day_set):
            continue
        complete = set(window).issubset(day_set)
        checked_dates[complete] += 1
        for board in BOARDS:
            prev = by_title[before,board]
            current = by_title[dt,board]
            follow = by_title[after,board]
            prev_groups = defaultdict(list)
            prev_names = set()
            for rec in prev.values():
                if rec['group'].startswith('g:'):
                    prev_groups[rec['group']].append(rec)
                prev_names.add(proxies[rec['id']])
            for sid in sorted(current.keys()-prev.keys(), key=lambda sid:current[sid]['rank']):
                entry = current[sid]
                group = entry['group']
                known = group.startswith('g:')
                related = sorted(prev_groups[group],key=lambda r:r['rank'])
                ranks = [by_title[t,board][sid]['rank'] if t in day_set and sid in by_title[t,board] else '' for t in window[1:]]
                events.append(dict(date=dt,board=board,id=sid,
                                   title=title_at.get((dt,sid),entry['title']), group_id=group[2:] if known else '',
                                   rank=entry['rank'],x=str(int(bool(related))) if known else '',
                                   x_title_asof=int(proxies[sid].startswith('t:') and proxies[sid] in prev_names),
                                   y=int(sid in follow),day7_rank=ranks[-1],day7_date=after,
                                   complete_window=int(complete),
                                   prior_related_ids='|'.join(r['id'] for r in related),
                                   prior_related_titles='|'.join(title_at.get((before,r['id']),r['title']) for r in related),
                                   prior_related_ranks='|'.join(str(r['rank']) for r in related),
                                   prior_known_slots=sum(len(rs) for rs in prev_groups.values()),
                                   observed_days_t_to_7='|'.join(t for t in window[1:] if t in day_set),
                                   ranks_t_to_7='|'.join(str(r) for r in ranks)))
    assert len(events) == len({(r['date'],r['board'],r['id']) for r in events})
    assert all(bool(r['day7_rank'])==bool(r['y']) for r in events)
    write('entry_events.csv',events)
    write('entry_summary.csv',summarize(events))
    print(dict(checked_dates))


if __name__=='__main__':
    main()
