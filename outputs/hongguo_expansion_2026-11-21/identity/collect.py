"""Collect anonymised fields served in public /detail HTML, without media requests."""
import csv
import datetime as dt
import gzip
import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent.parent
HIST = OUTPUTS / 'hongguo_free_pilot_2026-11-18'
PAGES = HERE / 'pages'
CACHE_ERRORS = HERE / 'errors'
GAP = 0.42
WORKERS = 3
guard = threading.Lock()
stop = threading.Event()
last_start = 0.0
detail_keys = ('series_name', 'series_id', 'series_intro', 'first_visible_time', 'record_number',
               'series_episode_info', 'episode_cnt', 'accessible_episode_cnt', 'episode_right_text',
               'season_info', 'vid_list', 'tags', 'content_type', 'pay_type',
               'related_album_id', 'is_multi_season', 'season_index', 'related_novel_book_id',
               'novel', 'book_name', 'book_id', 'novel_name', 'novel_author', 'novel_info', 'book_info')
metric_keys = ('rating', 'series_like_count', 'series_favorite_count', 'rating_count',
               'rank_label', 'hot_score_data', 'play_count', 'follow_count', 'subscription_count', 'click_count')
review_keys = ('review_id', 'comment_id', 'create_time', 'content', 'digg_count', 'rating')


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def dump(path, x):
    temp = path.with_suffix('.part')
    temp.write_text(json.dumps(x, ensure_ascii=False, separators=(',', ':')) + '\n')
    temp.replace(path)


def rate_gate():
    global last_start
    with guard:
        time.sleep(max(0, GAP - (time.monotonic() - last_start)))
        if stop.is_set():
            return False
        last_start = time.monotonic()
        return True


def project(html, sid, url, at):
    match = re.search(r'(?:window\.)?_ROUTER_DATA\s*=\s*', html)
    if not match:
        raise ValueError('No public SSR detail state')
    doc = json.JSONDecoder().raw_decode(html, match.end())[0]
    page = doc['loaderData']['detail_page']
    d = page['seriesDetail']
    if str(d.get('series_id')) != sid:
        raise ValueError('Returned detail ID mismatch or missing')
    out = {key:d[key] for key in detail_keys if key in d}
    visible_people = ('nickname', 'sub_title', 'celebrity_id', 'is_label')
    if 'celebrities' in d:
        out['celebrities'] = [{k:c[k] for k in visible_people if k in c} for c in d['celebrities']]
    extra_identity = [k for k in d if re.search(r'book|novel|season|author|copyright|album|adap', k, re.I) and k not in out]
    for key in extra_identity:
        out[key] = d[key]
    social = page.get('seriesSocialInfo') or {}
    metrics = {k:social[k] for k in metric_keys if k in social}
    if 'reviews' in social:
        reviews = social['reviews'] or {}
        metrics['reviews'] = {'total_count': reviews.get('total_count'),
                              'reviews': [{k:r[k] for k in review_keys if k in r} for r in (reviews.get('reviews') or [])]}
    return {'series_id':sid,'url':url,'fetched_at_utc':at,'http_status':200,
            'html_sha256':hashlib.sha256(html.encode('utf-8')).hexdigest(),
            'returned_detail_keys':list(d),'returned_social_keys':list(social),'detail':out,'social':metrics}


def fetch(sid):
    target = PAGES / (sid + '.json')
    if target.exists():
        return 'cached'
    url = 'https://hongguoduanju.com/detail?series_id=' + sid
    attempts = []
    for attempt in range(2):
        if not rate_gate():
            return 'paused'
        at = stamp()
        try:
            req = Request(url, headers={'Accept-Encoding':'gzip'})
            with urlopen(req,timeout=12) as resp:
                payload = resp.read()
                if resp.headers.get('Content-Encoding') == 'gzip':
                    payload = gzip.decompress(payload)
                html = payload.decode()
            dump(target,project(html,sid,url,at))
            (CACHE_ERRORS / (sid + '.json')).unlink(missing_ok=True)
            return 'saved'
        except (HTTPError, URLError, OSError, ValueError, IndexError, KeyError) as exc:
            status = getattr(exc,'code',None)
            attempts.append({'time':at,'status':status,'error':str(exc)[:220]})
            if status in (401,403,429):
                stop.set()
            if stop.is_set() or status in (400,404,410) or isinstance(exc,(ValueError,KeyError,IndexError)):
                break
            if attempt == 0:
                time.sleep(1.0)
    dump(CACHE_ERRORS / (sid + '.json'),{'series_id':sid,'url':url,'attempts':attempts})
    return 'failed'


def main():
    PAGES.mkdir(exist_ok=True)
    CACHE_ERRORS.mkdir(exist_ok=True)
    with (HIST / 'history/catalog.csv').open(encoding='utf-8-sig') as f:
        catalogue = list(csv.DictReader(f))
    with (HIST / 'series_metrics.csv').open(encoding='utf-8-sig') as f:
        previous = {r['series_id'] for r in csv.DictReader(f)}
    ids = [r['id'] for r in catalogue]
    candidate = sorted(catalogue,key=lambda x:hashlib.sha256(('FYP-20261121-'+x['id']).encode()).hexdigest())
    trial = []
    for board in ('hot','real','ai','comic'):
        rows = [r['id'] for r in candidate if board in r['boards_seen'].split('|') and r['id'] not in previous and r['id'] not in trial][:4]
        trial.extend(rows)
    dump(HERE/'sample_ids.json',trial)
    for batch in (trial,[i for i in ids if i not in set(trial)]):
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            jobs = [pool.submit(fetch,i) for i in batch]
            for j in as_completed(jobs):
                j.result()
        if stop.is_set():
            break
    print('saved',len(list(PAGES.glob('*.json'))),'error',len(list(CACHE_ERRORS.glob('*.json'))),'stopped_on_restriction',stop.is_set(),flush=True)


if __name__ == '__main__':
    main()
