"""Replay an untrained, same-board rank-only rule and freeze its 21 November choices."""
from collections import defaultdict
from datetime import date, timedelta

from cohort import TARGET, build, observed_charts, write_csv

WEEK = 7
TIE = ('hot', 'real', 'ai', 'comic')


def replay(charts=None, coverage=None):
    if charts is None:
        charts, coverage = observed_charts()
    complete100 = {board: {day for day, b in coverage.items() if set(range(1, 101)) <= b[board]} for board in TIE}
    complete20 = {board: {day for day, b in coverage.items() if set(range(1, 21)) <= b[board]} for board in TIE}
    cumulative_head = set()
    first = {}
    history = defaultdict(list)
    for day, chart in sorted(charts.items()):
        for sid, entries in chart.items():
            for board, r in entries.items():
                key = board, sid
                first.setdefault(key, day)
                if r['rank'] <= 20:
                    cumulative_head.add(key)
                age = (day - first[key]).days + 1
                if age > 3 or key in cumulative_head or day not in complete100[board]:
                    continue
                # Require a week of complete chart observations before accepting an observed entry.
                if not all(first[key] - timedelta(days=k) in complete100[board] for k in range(1, WEEK+1)):
                    continue
                future = [day + timedelta(days=k) for k in range(1, WEEK+1)]
                known = all(when in complete20[board] for when in future)
                label = int(any(charts[when].get(sid, {}).get(board, {}).get('rank',101) <= 20
                                for when in future)) if known else ''
                history[day].append({'date':day.isoformat(), 'board': board, 'series_id':sid,
                                     'title':r['title'], 'rank':r['rank'], 'same_board_age':age,
                                     'future_same_board_top20':label})
    return history


def distinct_priorities(pairs):
    result, seen = [], set()
    for r in sorted(pairs,key=lambda r:(int(r['rank']), TIE.index(r['board']),r['series_id'])):
        if r['series_id'] in seen:
            continue
        seen.add(r['series_id'])
        result.append({'priority':len(result)+1, **r})
    return result


def main():
    daily = replay()
    seed = build()
    assert {(r['board'],r['series_id']) for r in seed} == {(r['board'],r['series_id']) for r in daily[TARGET]}
    history = [r for rows in daily.values() for r in rows if r['future_same_board_top20'] != '']
    write_csv('same_board_historical_labeled.csv', history)
    write_csv('same_board_m0_frozen.csv', distinct_priorities(daily[TARGET]))
    tested = []
    for d, rows in sorted(daily.items()):
        if date(2026,11,2) <= d <= date(2026,11,14):
            assert all(r['future_same_board_top20'] != '' for r in rows)
            tested.extend(distinct_priorities(rows))
    write_csv('same_board_m0_replay.csv', tested)
    picks = [r for r in tested if r['priority']<=10]
    print('all labeled pairs-days/titles/success rows:', len(history),len({r['series_id'] for r in history}),sum(r['future_same_board_top20'] for r in history))
    print('replay title-days/titles/positives/picks/picked positives:',len(tested),len({r['series_id'] for r in tested}),sum(r['future_same_board_top20'] for r in tested),len(picks),sum(r['future_same_board_top20'] for r in picks))


if __name__ == '__main__':
    main()
