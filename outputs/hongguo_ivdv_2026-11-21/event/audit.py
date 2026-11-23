"""Audit sample coverage around a sequel's public website first-visibility date."""
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parents[1]
IDENTITY = OUTPUTS / 'hongguo_expansion_2026-11-21/identity'
HISTORY = OUTPUTS / 'hongguo_free_pilot_2026-11-18/history'
EXT = OUTPUTS / 'hongguo_watchlist_review_2026-11-21/extension'
START, END = date(2026, 10, 13), date(2026, 11, 21)
SHANGHAI = ZoneInfo('Asia/Shanghai')
KEYS = ('like', 'fav', 'heat')
D = timedelta(days=1)


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as fh:
        return list(csv.DictReader(fh))


def save(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def archive_tail(directory, ids):
    """Optional regeneration of the pinned 3-day extract; no network required."""
    result = []
    for src in json.loads((EXT/'sources.json').read_text())[:3]:
        raw = (directory / (src['day'] + '.json')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == src['sha256']
        snapshot = json.loads(raw)
        for sid, item in snapshot['items'].items():
            if sid in ids:
                result.append(dict(date=src['day'], id=sid,
                                   **{k:item.get(k) for k in KEYS},
                                   first_visible=item.get('first_visible')))
    save(HERE/'archived_extra_days.csv', result)


def main():
    pairs = {(r['old_id'],r['new_id']):dict(r, support='official_group+numbered_titles')
             for r in read(IDENTITY/'explicit_adjacent_seasons.csv')}
    checked = read(OUTPUTS/'hongguo_topic_implementation_2026-11-19/identity/pair_identity.csv')
    for s in checked:
        assert s['identity_confirmed'] == '1'
        key = s['old_id'],s['new_id']
        if key not in pairs:
            pairs[key] = dict(old_id=s['old_id'],new_id=s['new_id'],old_title=s['old_title'],
                              new_title=s['new_title'],old_number=s['old_platform_order'],
                              new_number=s['new_platform_order'],group_id=s['new_html_group'])
        pairs[key]['support'] = 'official_group+SDK_order' + ('+numbered_titles' if 'support' in pairs[key] else '')
    ids = {t for pair in pairs for t in pair}
    if len(sys.argv) > 1:
        archive_tail(Path(sys.argv[1]), ids)
    web = {r['series_id']:r for r in read(IDENTITY/'identity_coverage.csv')}
    def official_date(sid):
        return datetime.fromtimestamp(int(web[sid]['first_visible_time']), SHANGHAI).date()
    source_days = sorted({d['date'] for d in read(HISTORY/'drama_daily.csv')})
    rank = defaultdict(set)
    for path in (HISTORY/'board_daily.csv', EXT/'new_rank_days.csv'):
        for r in read(path):
            rank[r['id']].add(date.fromisoformat(r['date']))
    panel = {}
    raw_dates = defaultdict(set)
    rows = read(HISTORY/'drama_daily.csv')
    offset_board_rows = sum(not any(r[f'rank_{b}'] for b in ('hot','ai','real','comic')) for r in rows)
    all_rows = rows + read(HERE/'archived_extra_days.csv')
    for r in all_rows:
        if r['id'] not in ids:
            continue
        day = date.fromisoformat(r['date'])
        panel[r['id'],day] = {k:int(r[k]) if r[k]!='' else None for k in KEYS}
        if r.get('first_visible'):
            raw_dates[r['id']].add(r['first_visible'])
    # Nov 21: bulk collection queried the historical roster including off-chart shows.
    for sid in ids:
        r = web[sid]
        if r['web_status'] == 'ok' or r['web_at_utc']:
            assert datetime.fromisoformat(r['web_at_utc']).astimezone(SHANGHAI).date()==END
            panel[sid,END] = {k:int(r[source]) if r[source] else None for k,source in
                              [('like','like_display'),('fav','favorite_display'),('heat','heat')]}
    # Add the already-visible first seasons to the series event chronology, too.
    siblings = defaultdict(dict)
    for a in pairs.values():
        for key in ('new_id','old_id'):
            sid = a[key]
            siblings[a['group_id']][sid] = official_date(sid)
    for a in read(IDENTITY/'explicit_seasons.csv'):
        sid = a['series_id']
        siblings[a['website_group_id']][sid] = official_date(sid)
    results = []
    for r in pairs.values():
        old, new = r['old_id'],r['new_id']
        day = official_date(new)
        old_day = official_date(old)
        both = lambda n: all(panel.get((old,day+n*D),{}).get(k) is not None for k in ('like','fav'))
        row = dict(**r, old_visible=old_day,new_visible=day,new_archive_visible='|'.join(sorted(raw_dates[new])),
                   old_url=web[old]['web_url'],new_url=web[new]['web_url'],
                   new_first_observed_chart=min(rank[new]) if rank[new] else '',
                   in_window=int(START<=day<=END),older_precedes_new=int(old_day<day),
                   calendar_window=int(START<=day-8*D and day+7*D<=END),
                   complete_prior_differences=sum(both(n-1) and both(n) for n in range(-7,0)),
                   complete_post_differences=sum(both(n-1) and both(n) for n in range(1,8)),
                   full_like_fav=int(all(both(n) for n in range(-8,8))),
                   full_heat=int(all(panel.get((old,day+n*D),{}).get('heat') is not None for n in range(-8,8))),
                   offchart_old_metric_days=sum(both(n) and (day+n*D not in rank[old]) for n in range(-8,8)),
                   other_known_same_group_7d=sum(k!=new and abs((v-day).days)<=7 for k,v in siblings[r['group_id']].items()),
                   other_known_same_group_14d=sum(k!=new and abs((v-day).days)<=14 for k,v in siblings[r['group_id']].items()))
        if row['full_like_fav']:
            for k in ('like','fav'):
                prev = panel[old,day-D][k]-panel[old,day-8*D][k]
                after = panel[old,day+7*D][k]-panel[old,day][k]
                row[k+'_prior_net'],row[k+'_post_net']=prev,after
        else:
            for k in ('like','fav'):
                row[k+'_prior_net'],row[k+'_post_net']='',''
        results.append(row)
    results.sort(key=lambda r:(r['new_visible'],r['group_id'],r['new_number']))
    save(HERE/'event_coverage.csv',results)
    def counts(seq):
        return {'events':len(seq),'groups':len({r['group_id'] for r in seq})}
    valid = [r for r in results if r['in_window'] and r['older_precedes_new']]
    full = [r for r in valid if r['full_like_fav']]
    # A deliberately narrow support check among other observed, later-treated pairs.
    # Future dates establish eligibility retrospectively; pre-event outcomes are not fabricated.
    controls = []
    for e in full:
        day = e['new_visible']
        treated_old = e['old_id']
        for c in results:
            old = c['old_id']
            if c['group_id'] == e['group_id'] or c['new_visible'] <= day+7*D:
                continue
            if abs((official_date(treated_old)-official_date(old)).days)>7 or official_date(old)>=day-8*D:
                continue
            if any(sid != old and abs((v-day).days)<=7 for sid,v in siblings[c['group_id']].items()):
                continue
            if not all(all(panel.get((old,day+n*D),{}).get(k) is not None for k in ('like','fav'))
                       for n in range(-8,8)):
                continue
            controls.append(dict(event_new_id=e['new_id'],event_group=e['group_id'],event_date=day,
                                 treated_old_id=treated_old,control_old_id=old,
                                 control_group=c['group_id'],control_sequel_visible=c['new_visible'],
                                 treated_old_age=(day-official_date(treated_old)).days,
                                 control_old_age=(day-official_date(old)).days))
    if controls:
        save(HERE/'potential_controls.csv',controls)
    print(json.dumps({'pairs':counts(results),'within':counts([r for r in results if r['in_window']]),
          'chronological_in_window':counts(valid),'eligible_by_calendar':counts([r for r in valid if r['calendar_window']]),
          'full_net_like_fav':counts(full),'eligible_sample_controls':{'supported_events':len({c['event_new_id'] for c in controls}), 'supported_groups':len({c['event_group'] for c in controls}),'possible_comparisons':len(controls)},'full_through_nov20':counts([r for r in full if r['new_visible']+7*D<END]),
          'full_like_fav_heat':counts([r for r in full if r['full_heat']]),
          'full_old_at_least_one_day_offchart':counts([r for r in full if r['offchart_old_metric_days']>0]),
          'full_with_no_other_7d':counts([r for r in full if not r['other_known_same_group_7d']]),
          'full_with_no_other_14d':counts([r for r in full if not r['other_known_same_group_14d']]),
          'historical_visible_dates_agree':sum(r['new_archive_visible']==str(r['new_visible']) for r in results),
          'old_daily_rows':len(rows),'old_offchart_rows':offset_board_rows,'source_days_old':len(source_days),
          'within_but_first_chart_earlier':sum(bool(r['new_first_observed_chart']) and r['new_first_observed_chart']<r['new_visible'] for r in valid),
          'within_but_first_chart_different':sum(bool(r['new_first_observed_chart']) and r['new_first_observed_chart']!=r['new_visible'] for r in valid),
          'old_does_not_precede_new':[(r['old_title'],r['new_title']) for r in results if not r['older_precedes_new']]},
        indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
