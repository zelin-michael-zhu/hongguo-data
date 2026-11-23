"""Check episode identity and the review preview on ordinary public HTML pages."""
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, build_opener


OUT = Path(__file__).resolve().parent
OLD = OUT.parent / 'hongguo_expansion_2026-11-21'
SITE = 'https://hongguoduanju.com'
SAMPLE = ['7706759303633308696', '7684955951031389209', '7701304930841136190']


def allowed(url):
    loc = urlsplit(url)
    return loc.netloc == 'hongguoduanju.com' and re.fullmatch(
        r'/(?:robots\.txt|detail|player/\d+)', loc.path)


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Redirect outside the public series and landing page sample.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def get(opener, path):
    url = SITE + path
    assert allowed(url)
    with opener.open(url, timeout=20) as response:
        text = response.read().decode('utf-8')
        return text, {'url': response.geturl(), 'http_status': response.status,
                      'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
                      'html_sha256': hashlib.sha256(text.encode()).hexdigest()}


def inspect(opener, sid, channel):
    series = channel == 'series_review'
    body, source = get(opener, ('/detail?series_id=' if series else '/player/') + sid)
    router = re.search(r'_ROUTER_DATA\s*=\s*', body)
    data = json.JSONDecoder().raw_decode(body[router.end():])[0]['loaderData']
    social = 'seriesSocialInfo' if series else 'episodeSocialInfo'
    page = next(v for v in data.values() if isinstance(v, dict) and social in v)
    detail = page['seriesDetail']
    assert str(detail['series_id']) == sid
    ids = [str(v) for v in detail['vid_list']]
    if not series:
        assert str(page['vid']) == ids[0]
    preview = page[social]['reviews']
    cards = preview['reviews']
    evidence = dict(source, channel=channel, series_id=sid, title=detail['series_name'],
                    bound_episode_id='' if series else ids[0],
                    response_keys=sorted(preview),
                    received_nonempty_texts=sum(bool(r.get('content')) for r in cards),
                    reported_total=int(preview['total_count']),
                    with_creation_time=sum(r.get('create_time') is not None for r in cards),
                    with_like_count=sum(r.get('digg_count') is not None for r in cards),
                    with_stable_id_field=sum(bool(r.get('id') or r.get('comment_id') or r.get('review_id')) for r in cards),
                    with_episode_id_field=sum(bool(r.get('episode_id') or r.get('vid')) for r in cards))
    observed = {(r['content'].strip(), str(r['create_time'])) for r in cards if r.get('content')}
    return ids, observed, evidence


def main():
    opener = build_opener(PublicRedirect())
    rules, source = get(opener, '/robots.txt')
    source['text'] = rules
    assert any(line.strip().lower() == 'disallow: /player/*/*' for line in rules.splitlines())
    (OUT/'episode_probe_robots.json').write_text(json.dumps(source, ensure_ascii=False, indent=2))
    with (OLD/'episode_index.csv').open(encoding='utf-8-sig') as f:
        ids_in_index = {sid: {} for sid in SAMPLE}
        for row in csv.DictReader(f):
            if row['series_id'] in ids_in_index:
                ids_in_index[row['series_id']][int(row['episode_position'])] = row['episode_id']
    with (OLD/'comments/comment_previews.csv').open(encoding='utf-8-sig') as f:
        previous = list(csv.DictReader(f))
    pages, positions = [], []
    for sid in SAMPLE:
        ids, series_text, series = inspect(opener, sid, 'series_review')
        time.sleep(0.65)
        first_ids, first_text, first = inspect(opener, sid, 'episode_1')
        assert ids == first_ids
        first['distinct_text_overlap_with_series_preview'] = len({t for t, _ in series_text} & {t for t, _ in first_text})
        for scope, observed, envelope in [('series_review', series_text, series),
                                         ('default_episode_comment', first_text, first)]:
            old_rows = [r for r in previous if r['series_id'] == sid and r['scope'] == scope]
            old_keys = {(r['content'].strip(), r['create_time']) for r in old_rows}
            envelope['earlier_capture'] = old_rows[0]['sampled_at']
            envelope['earlier_unique_text_time'] = len(old_keys)
            envelope['common_unique_text_time'] = len(old_keys & observed)
            envelope['now_unique_text_time'] = len(observed)
        pages.extend([series, first])
        for n in (1, 2, 10, (len(ids)+1)//2, len(ids)):
            vid = ids[n-1]
            assert vid == ids_in_index[sid][n]
            positions.append(dict(series_id=sid, title=series['title'], number=n,
                                  episodes=len(ids), episode_id=vid, index_matches_current_detail=1,
                                  result='verified_first_episode_text' if n==1 else 'ID_only_no_detail_fetch_robots_disallow',
                                  verified_text_count=first['received_nonempty_texts'] if n==1 else '',
                                  verified_reported_total=first['reported_total'] if n==1 else ''))
        time.sleep(0.65)
    (OUT/'episode_probe_pages.json').write_text(json.dumps(pages, ensure_ascii=False, indent=2))
    with (OUT/'episode_probe_positions.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=positions[0])
        writer.writeheader()
        writer.writerows(positions)


if __name__ == '__main__':
    main()
