"""Record the public first-episode landing page for catalogued series. HTML only."""
import concurrent.futures
import csv
import gzip
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parent
CATALOG = OUT.parents[1] / 'hongguo_free_pilot_2026-11-18/history/catalog.csv'
PAGES = OUT / 'pages'
ERRORS = OUT / 'errors'
PAGE_MARKER = re.compile(r'\b_ROUTER_DATA\s*=\s*')
gate = threading.Lock()
restricted = threading.Event()
next_request = 0.0


def store(path, record):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def fetch(series_id):
    global next_request
    path = PAGES / f'{series_id}.json'
    if path.exists() or restricted.is_set():
        return
    url = f'https://hongguoduanju.com/player/{series_id}'
    for attempt in range(2):
        with gate:
            if restricted.is_set():
                return
            time.sleep(max(0, next_request - time.monotonic()))
            next_request = time.monotonic() + 0.54
        now = datetime.now(timezone.utc).isoformat()
        try:
            req = Request(url, headers={'Accept': 'text/html', 'Accept-Encoding': 'gzip'})
            with urlopen(req, timeout=18) as response:
                body = response.read()
                if response.headers.get('Content-Encoding') == 'gzip':
                    body = gzip.decompress(body)
            html = body.decode('utf-8')
            marker = PAGE_MARKER.search(html)
            if not marker:
                raise ValueError('HTML missing page data')
            data = json.JSONDecoder().raw_decode(html[marker.end():].lstrip())[0]['loaderData']
            page = next((v for v in data.values() if isinstance(v, dict) and 'seriesDetail' in v), {})
            detail = page.get('seriesDetail') or {}
            ids = [str(v) for v in detail.get('vid_list', [])]
            episode_id = str(page.get('vid') or '')
            if str(detail.get('series_id')) != series_id or not ids or episode_id != ids[0]:
                raise ValueError('Unverified series or first episode')
            interaction = page.get('episodeSocialInfo') or {}
            reviews = interaction.get('reviews') or {}
            public_seo = page.get('publicVideoSeo') or {}
            series_social = page.get('seriesSocialInfo') or {}
            metric_names = ('play_count','series_play_cnt','series_play_count','follow_count','series_follow_count')
            metrics = {k: v for obj in (detail, series_social, page) for k,v in obj.items() if k in metric_names}
            record = {
                'series_id': series_id, 'title': detail.get('series_name'), 'episode_id': episode_id,
                'source_url': url, 'collected_at_utc': now, 'episode_number': 1,
                'episode_like_count': interaction.get('episode_like_count'), 'comment_total_reported': reviews.get('total_count'),
                'comments': [{k:v for k,v in c.items() if k in ('content','create_time','digg_count','rating','comment_id')}
                             for c in reviews.get('reviews', []) if isinstance(c,dict)],
                'duration_seconds': public_seo.get('durationSeconds') if str(public_seo.get('itemId'))==episode_id else None,
                'raw_series_metrics_if_present': metrics,
                'series_social_keys': sorted(series_social), 'episode_social_keys': sorted(interaction),
            }
            store(path, record)
            (ERRORS / path.name).unlink(missing_ok=True)
            return
        except Exception as exc:
            status = exc.code if isinstance(exc, HTTPError) else None
            if status in (401, 403, 429):
                restricted.set()
            if attempt == 0 and not restricted.is_set() and (status is None or status >= 500):
                time.sleep(2)
                continue
            store(ERRORS / path.name, {'series_id': series_id, 'url': url, 'time_utc':now,
                                      'http_status':status,'reason':str(exc)[:200]})
            return


if __name__ == '__main__':
    PAGES.mkdir(exist_ok=True)
    ERRORS.mkdir(exist_ok=True)
    with CATALOG.open(encoding='utf-8-sig') as file:
        ids = [row['id'] for row in csv.DictReader(file)]
    sample = json.loads((OUT.parent / 'identity/sample_ids.json').read_text())
    ordered = list(dict.fromkeys(sample + ids))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(fetch, ordered))
    print('verified',len(list(PAGES.glob('*.json'))),'errors',len(list(ERRORS.glob('*.json'))),'source restricted',restricted.is_set())
