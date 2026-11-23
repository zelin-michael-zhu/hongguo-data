"""Join a completed, dated preview snapshot to a pre-selected same-board target."""
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DAY = '2026-11-21'
ZONE = ZoneInfo('Asia/Shanghai')
SCOPES = {'series_review': 'series_review', 'first_episode_comment': 'first_episode'}
LIVE = ROOT / 'snapshots' / DAY


def read(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def save(name, rows):
    target = ROOT / name
    tmp = target.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(target)


def read_publication_time(raw, observed):
    if raw in (None, ''):
        return '', 'missing'
    try:
        stamp = int(raw)
        if stamp <= 0:
            return '', 'invalid'
        t = datetime.fromtimestamp(stamp, ZONE)
    except (ValueError, TypeError, OSError, OverflowError):
        return '', 'invalid'
    return t.isoformat(timespec='seconds'), 'after_capture' if t > observed else 'valid'


def nonnegative(value):
    if value in (None, ''):
        return ''
    try:
        number = float(value)
        if number < 0 or not number.is_integer():
            return ''
        return int(number)
    except (TypeError, ValueError, OverflowError):
        return ''


def main():
    frozen = read('same_board_m0_frozen.csv')
    seed = {(r['board'],r['series_id']):r for r in read('cohort_seed.csv')}
    all_boards = defaultdict(list)
    for b, sid in seed:
        all_boards[sid].append(b)
    expected = {(r['series_id'],scope) for r in frozen for scope in SCOPES}
    pages = {}
    unresolved_errors = []
    for sid,scope in expected:
        path = LIVE / f'{sid}_{scope}.json'
        if not path.exists():
            if (LIVE / 'errors' / path.name).exists():
                unresolved_errors.append(path.name)
            continue
        page = json.loads(path.read_text())
        assert (page['series_id'],page['scope']) == (sid,scope)
        assert page['sampled_at_sh'].startswith(DAY)
        assert page['source'].startswith('https://hongguoduanju.com/')
        assert bool(page['episode_id']) == (scope == 'first_episode_comment')
        pages[sid,scope] = page
    if len(pages) != len(expected):
        raise RuntimeError(f'{len(pages)}/{len(expected)} verified. Unresolved errors: {unresolved_errors}')
    assert len(expected) == 2 * len(set(x['series_id'] for x in frozen)) == 2 * len(frozen)

    chart_at = max(r['chart_snapshot_completed_sh'] for r in seed.values())
    decision = max(p['sampled_at_sh'] for p in pages.values())
    assert chart_at < min(p['sampled_at_sh'] for p in pages.values()) <= decision
    texts, features = [], []
    anomalies = Counter()
    for row in frozen:
        sid, board = row['series_id'], row['board']
        anchor = seed[board,sid]
        assert anchor['rank'] == row['rank'] and row['future_same_board_top20'] == ''
        flat = dict(series_id=sid, title=row['title'], target_board=board, m0_priority=row['priority'],
                    snapshot_date=DAY, chart_snapshot_completed_sh=chart_at, decision_at_sh=decision,
                    rank=anchor['rank'], heat=anchor['heat'], rank_lag1=anchor['rank_lag1'], rank_lag2=anchor['rank_lag2'],
                    same_board_first_observed=anchor['same_board_first_observed'], same_board_age=row['same_board_age'],
                    candidate_boards='|'.join(sorted(all_boards[sid])), prior_or_current_other_board_head=anchor['prior_or_current_other_board_head'])
        for scope, prefix in SCOPES.items():
            page = pages[sid,scope]
            observed = datetime.fromisoformat(page['sampled_at_sh'])
            per_page = []
            positions = []
            for item in page['rows']:
                position = int(item['position'])
                positions.append(position)
                if not isinstance(item['text'],str) or not item['text'].strip():
                    continue
                posted, status = read_publication_time(item['comment_time'], observed)
                likes = nonnegative(item['comment_like_count'])
                if item['comment_like_count'] not in (None,'') and likes == '':
                    anomalies['invalid_like_value'] += 1
                comment = dict(snapshot_date=DAY, series_id=sid, title=row['title'], episode_id=page['episode_id'],
                               scope=scope, display_position=position, text=item['text'],
                               source_comment_id=item['comment_id'], create_time_raw=item['comment_time'],
                               published_at_sh=posted, publication_time_status=status, comment_likes=likes,
                               rating=item['rating'], sampled_at_sh=page['sampled_at_sh'], source_url=page['source'])
                per_page.append(comment)
                anomalies[scope+'_'+status] += 1
            assert positions == list(range(1,len(positions)+1))
            assert nonnegative(page['reported_total']) == '' or nonnegative(page['reported_total']) >= len(per_page)
            texts.extend(per_page)
            flat[prefix+'_sampled_at_sh'] = page['sampled_at_sh']
            flat[prefix+'_reported_total'] = nonnegative(page['reported_total'])
            flat[prefix+'_display_rows'] = len(page['rows'])
            flat[prefix+'_n_text'] = len(per_page)
            flat[prefix+'_n_with_valid_time'] = sum(r['publication_time_status']=='valid' for r in per_page)
            flat[prefix+'_n_published_before_chart_first_observed_day'] = sum(
                r['publication_time_status']=='valid' and r['published_at_sh'][:10]<anchor['same_board_first_observed']
                for r in per_page)
            if scope == 'series_review':
                for k in ('series_like_count','series_favorite_count','rating','rating_count'):
                    flat[k] = page['metrics'].get(k)
            else:
                flat['first_episode_id'] = page['episode_id']
                flat['first_episode_like_count'] = page['metrics'].get('episode_like_count')
        flat.update(forecast_window_start=anchor['forecast_start'],forecast_window_end=anchor['forecast_end'],
                    future_same_board_top20='')
        features.append(flat)
    assert len({(r['series_id'],r['scope'],r['display_position']) for r in texts}) == len(texts)
    assert sum(r['series_review_n_text']+r['first_episode_n_text'] for r in features)==len(texts)
    assert all(r['sampled_at_sh']<=decision for r in texts) and decision[:10]<features[0]['forecast_window_start']
    save('comments_'+DAY+'.csv',texts)
    save('features_'+DAY+'.csv',features)
    out = {
        'date':DAY, 'target': 'fixed same-board first Top20 within 7 calendar days after the decision date',
        'verified_pages':len(pages), 'unique_titles':len(features), 'title_board_pairs':len(seed),
        'chart_complete_sh':chart_at, 'capture_start_sh':min(p['sampled_at_sh'] for p in pages.values()),
        'capture_end_and_decision_sh':decision, 'n_text':len(texts),
        'comment_time_diagnostics': dict(anomalies), 'unresolved_errors':unresolved_errors}
    for scope, pref in SCOPES.items():
        group = [r for r in texts if r['scope']==scope]
        per_n = Counter(r[pref+'_n_text'] for r in features)
        out[scope] = dict(n_text=len(group), per_title_size=dict(sorted(per_n.items())),
                          n_raw_display_rows=sum(r[pref+'_display_rows'] for r in features),
                          reported_total_available=sum(r[pref+'_reported_total']!='' for r in features),
                          titles_with_text=len({r['series_id'] for r in group}),
                          with_source_comment_id=sum(bool(r['source_comment_id']) for r in group),
                          with_like_count=sum(r['comment_likes']!='' for r in group),
                          with_rating=sum(r['rating'] not in (None, '') for r in group),
                          n_published_before_chart_first_observed_day=sum(r[pref+'_n_published_before_chart_first_observed_day'] for r in features))
    out['nonmissing_title_metrics'] = {k:sum(r[k] not in (None,'') for r in features) for k in (
        'rank','heat','rank_lag1','rank_lag2','series_like_count','series_favorite_count','rating','rating_count','first_episode_like_count')}
    entered = {r['series_id']: r['same_board_first_observed'] for r in features}
    counts = {scope:Counter() for scope in SCOPES}
    for r in texts:
        if r['publication_time_status']=='valid' and r['published_at_sh'][:10]>=entered[r['series_id']]:
            counts[r['scope']][r['series_id']]+=1
    sets = [set(n) for n in counts.values()]
    out['published_on_or_after_first_chart_day'] = {
        'titles_with_any':len(set.union(*sets)), 'titles_with_both_sources':len(set.intersection(*sets)),
        'source':{scope:{'texts':sum(n.values()),'titles':len(n),'titles_with_at_least_3':sum(k>=3 for k in n.values())}
                  for scope,n in counts.items()}}
    (ROOT/'batch_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(out,ensure_ascii=False))


if __name__ == '__main__':
    main()
