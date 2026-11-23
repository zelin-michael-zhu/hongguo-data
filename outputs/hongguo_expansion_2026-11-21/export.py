"""Export anonymously sampled public text, complete enumerations and explicit missingness."""
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'hongguo_free_pilot_2026-11-18'


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as source:
        return list(csv.DictReader(source))


def read_cached(folder, sid):
    path = ROOT / folder / (sid + '.json')
    return json.loads(path.read_text()) if path.exists() else {}


def status(folder, sid, page):
    if page:
        return 'ok'
    error = read_cached(folder + '/errors', sid)
    if not error:
        return 'not_checked'
    attempts = error.get('attempts') or []
    code = attempts[-1].get('status') if attempts else error.get('http_status')
    return f'HTTP {code}' if code else 'no_verified_record'


def as_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def present(x):
    return x is not None and x != ''


SERIES = ['series_id','catalog_title','detail_status','detail_collected_at_utc','detail_episode_count',
          'listed_episode_ids','enumeration_reconciled','preview_accessible_episode_count','series_group_id',
          'official_record_number','web_series_like','web_series_favorite','web_heat_score','series_rating',
          'series_rating_count','series_reviews_total','series_reviews_with_text','first_page_status',
          'first_episode_id','first_page_collected_at_utc','first_episode_likes','first_episode_comments_total',
          'first_episode_comments_with_text','first_episode_duration_seconds',
          'historical_sdk_play_count','historical_sdk_follow_count','historical_sdk_collected_at']
INDEX = ['series_id','episode_position','episode_id','source_url','detail_collected_at_utc']
REVIEWS = ['series_id','episode_id','scope','display_position','text','create_time_raw','digg_count','rating',
           'source_comment_id','source_total_reported','source_url','collected_at_utc']


def writer(file, fields):
    rows = csv.DictWriter(file, fieldnames=fields)
    rows.writeheader()
    return rows


def emit_text(rows, sid, eid, scope, items, total, url, stamp):
    n = 0
    for i, r in enumerate(items, 1):
        if not isinstance(r.get('content'), str) or not r['content'].strip():
            continue
        rows.writerow(dict(zip(REVIEWS, [sid,eid,scope,i,r['content'],r.get('create_time'),r.get('digg_count'),
                          r.get('rating'),r.get('comment_id') or r.get('review_id'),total,url,stamp])))
        n += 1
    return n


def export():
    catalog = read_csv(OLD/'history/catalog.csv')
    previous = {r['series_id']:r for r in read_csv(OLD/'series_metrics.csv')}
    old_episodes = read_csv(OLD/'episodes.csv')
    stats = Counter()
    detail_statuses = Counter()
    first_statuses = Counter()
    seen_episode = set()
    by_group = Counter()
    raw_play_fields_found = Counter()
    old_positions = {(r['series_id'],r['episode_id']):int(r['episode_number']) for r in old_episodes}
    first_success_ids = set()
    all_detail_keys,all_social_keys = Counter(),Counter()
    with (ROOT/'series_coverage.csv').open('w',encoding='utf-8-sig',newline='') as s, \
         (ROOT/'episode_index.csv').open('w',encoding='utf-8-sig',newline='') as e, \
         (ROOT/'reviews_preview.csv').open('w',encoding='utf-8-sig',newline='') as t:
        series_out = writer(s,SERIES)
        episode_out = writer(e,INDEX)
        reviews_out = writer(t,REVIEWS)
        for c in catalog:
            sid = c['id']
            old = previous.get(sid,{})
            dpage = read_cached('identity/pages',sid)
            fpage = read_cached('first_episodes/pages',sid)
            ds = status('identity',sid,dpage)
            fs = status('first_episodes',sid,fpage)
            detail_statuses[ds] += 1
            first_statuses[fs] += 1
            if dpage:
                all_detail_keys.update(dpage['returned_detail_keys'])
                all_social_keys.update(dpage['returned_social_keys'])
            detail = dpage.get('detail',{})
            social = dpage.get('social',{})
            rev = social.get('reviews',{})
            gids = (detail.get('season_info') or {}).get('series_group_id')
            if present(gids):
                by_group[gids] += 1
            ids = list(map(str,detail.get('vid_list') or []))
            n = as_int(detail.get('episode_cnt'))
            archive_n = as_int(c.get('episodes'))
            if dpage and n is not None and archive_n is not None:
                stats['same_episode_count_as_old_catalogue'] += n == archive_n
                stats['changed_episode_count_since_old_catalogue'] += n != archive_n
            reconciled = bool(dpage and n is not None and n>0 and len(ids)==n and
                              len(set(ids))==n and all(v.isdigit() for v in ids))
            stats['enumerations_match_count'] += reconciled
            for i, eid in enumerate(ids, 1):
                episode_out.writerow(dict(zip(INDEX,[sid,i,eid,dpage['url'],dpage['fetched_at_utc']])))
                seen_episode.add(eid)
                if (sid,eid) in old_positions:
                    stats['paired_old_episode_ids'] += 1
                    stats['same_position_as_sdk'] += (old_positions[sid,eid]==i)
            stats['episode_index_rows'] += len(ids)
            # A client-facing series count and a website first-episode count have different denominators.
            sr = emit_text(reviews_out,sid,'','series_review',rev.get('reviews') or [],rev.get('total_count'),
                           dpage.get('url'),dpage.get('fetched_at_utc'))
            fr = emit_text(reviews_out,sid,fpage.get('episode_id'),'first_episode_comment',fpage.get('comments') or [],
                           fpage.get('comment_total_reported'),fpage.get('source_url'),fpage.get('collected_at_utc'))
            for scope,num,total,page in [('series_reviews',sr,rev.get('total_count'),dpage),
                                          ('first_comments',fr,fpage.get('comment_total_reported'),fpage)]:
                if page:
                    stats[scope+'_text_rows'] += num
                    stats[scope+'_pages_with_text'] += num>0
                    if as_int(total) is not None:
                        stats[scope+'_pages_with_total'] += 1
                        stats[scope+'_total_sum'] += as_int(total)
                        stats[scope+'_pages_count_equal'] += num==as_int(total)
            if fpage:
                first_success_ids.add(sid)
                stats['first_with_duration'] += present(fpage.get('duration_seconds'))
                stats['first_with_likes'] += present(fpage.get('episode_like_count'))
                raw_play_fields_found.update(fpage.get('raw_series_metrics_if_present',{}).keys())
                if ids:
                    stats['first_detail_overlaps'] += 1
                    stats['first_ids_cross_checked'] += str(fpage['episode_id']) == ids[0]
            for k in ('series_favorite_count','series_like_count','click_count','play_count','follow_count','subscription_count'):
                stats['detail_nonempty_'+k] += present(social.get(k))
            row = [sid,c['title'],ds,dpage.get('fetched_at_utc'),n,len(ids) if dpage else None,
                   int(reconciled) if dpage else None,detail.get('accessible_episode_cnt'),gids,detail.get('record_number'),
                   social.get('series_like_count'),social.get('series_favorite_count'),(social.get('hot_score_data') or {}).get('score'),
                   social.get('rating'),social.get('rating_count'),rev.get('total_count'),sr if dpage else None,
                   fs,fpage.get('episode_id'),fpage.get('collected_at_utc'),fpage.get('episode_like_count'),
                   fpage.get('comment_total_reported'),fr if fpage else None,fpage.get('duration_seconds'),
                   old.get('play_count'),old.get('follow_count'),old.get('collected_at')]
            series_out.writerow(dict(zip(SERIES,row)))
    stats.update({'catalog_ids':len(catalog),'distinct_episode_ids':len(seen_episode),'website_group_members':sum(by_group.values()),
                  'website_group_ids':len(by_group),'website_groups_with_multiple_catalog_members':sum(x>1 for x in by_group.values()),
                  'historical_sdk_series':len(previous),'historical_sdk_episode_rows':len(old_episodes),
                  'new_first_episode_titles_outside_old_five':len(first_success_ids-set(previous))})
    summary = {'counts':stats,'detail_status':detail_statuses,'first_episode_status':first_statuses,
               'detail_returned_keys':all_detail_keys,'social_returned_keys':all_social_keys,
               'first_raw_play_follow_fields':raw_play_fields_found}
    (ROOT/'coverage_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    export()
