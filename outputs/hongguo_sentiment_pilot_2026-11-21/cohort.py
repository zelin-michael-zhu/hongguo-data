"""Freeze the 21 November same-board entry cohort and join existing comment captures."""
import csv
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
sys.path.insert(0, str(OUT / 'hongguo_breakout_2026-11-21'))
from panel import observed_charts, read

TARGET = date(2026, 11, 21)
LOCAL = ZoneInfo('Asia/Shanghai')
OLD = OUT / 'hongguo_expansion_2026-11-21'
RAW = OUT / 'hongguo_watchlist_review_2026-11-21/extension/20261121T162219'


def local_time(value):
    return datetime.fromisoformat(value).astimezone(LOCAL).isoformat(timespec='seconds') if value else ''


def write_csv(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build():
    charts, boards = observed_charts()
    assert max(charts) == TARGET
    metadata = {r['series_id']: r for r in read(OLD / 'series_coverage.csv')}
    previews = Counter((r['series_id'], r['scope']) for r in read(OLD / 'reviews_preview.csv') if r['text'].strip())
    manifest = json.loads((RAW / 'manifest.json').read_text())
    at = max(local_time(p['at']) for b in manifest['boards'].values() for p in b['pages'])
    first, past_head = {}, set()
    for day, chart in sorted(charts.items()):
        for sid, entries in chart.items():
            for b, r in entries.items():
                first.setdefault((b,sid), day)
                if r['rank'] <= 20:
                    past_head.add((b,sid))
    seed = []
    for sid, entries in charts[TARGET].items():
        for b, r in entries.items():
            assert boards[TARGET][b] == set(range(1,101))
            key = b,sid
            first_date = first[key]
            chart_age = (TARGET - first_date).days + 1
            if chart_age > 3 or key in past_head:
                continue
            m = metadata.get(sid, {})
            # Keep missing snapshots as missing. An actual page with zero entries has a count of zero.
            sr = local_time(m.get('detail_collected_at_utc'))
            ep = local_time(m.get('first_page_collected_at_utc'))
            assert all(v<=at for v in (sr,ep) if v)
            count_s = previews[sid, 'series_review'] if sr else ''
            count_e = previews[sid, 'first_episode_comment'] if ep else ''
            if m:
                if sr: assert int(m['series_reviews_with_text']) == count_s
                if ep: assert int(m['first_episode_comments_with_text']) == count_e
            ranks = [charts.get(TARGET-timedelta(days=lag),{}).get(sid,{}).get(b,{}).get('rank','') for lag in (2,1)]
            seed.append(dict(board=b, series_id=sid, title=r['title'], same_board_first_observed=first_date.isoformat(),
                             same_board_age=chart_age, rank_lag2=ranks[0], rank_lag1=ranks[1], rank=r['rank'], heat=r['heat'],
                             previous_head_or_current=0, prior_or_current_other_board_head=int(any(
                                 (other, sid) in past_head for other in boards[TARGET] if other != b)),
                             chart_snapshot_completed_sh=at,
                             archived_series_preview_asof_sh=sr, archived_series_preview_n=count_s,
                             archived_first_episode_asof_sh=ep, archived_first_episode_preview_n=count_e,
                             forecast_start='2026-11-22', forecast_end='2026-11-28', future_same_board_top20=''))
    seed.sort(key=lambda r:(r['board'],r['rank'],r['series_id']))
    assert len(seed) == len({(r['board'],r['series_id']) for r in seed})
    write_csv('cohort_seed.csv', seed)
    return seed


if __name__ == '__main__':
    print(build()[0])
