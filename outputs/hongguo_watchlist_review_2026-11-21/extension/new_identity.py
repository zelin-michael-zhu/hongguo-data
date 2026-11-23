"""Read only identity-relevant metadata from public series detail HTML; no media."""
import csv
import datetime as dt
import gzip
import json
import re
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]
OLD=OUT/'hongguo_expansion_2026-11-21/identity'
cache=HERE/'identity_checks'
lock=threading.Lock()
stop=threading.Event()
next_time=0.0


def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def get(s):
    global next_time
    loc=cache/(s+'.json')
    if loc.exists():return json.loads(loc.read_text())
    url='https://hongguoduanju.com/detail?series_id='+s
    for attempt in range(2):
        with lock:
            time.sleep(max(0,next_time-time.monotonic()))
            next_time=time.monotonic()+0.42
        now=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        record=dict(id=s,group_id='',status='not_attempted',title='',checked_at_utc=now,source_url=url)
        if stop.is_set():return record
        try:
            with urlopen(Request(url,headers={'Accept-Encoding':'gzip'}),timeout=14) as resp:
                data=resp.read()
                if resp.headers.get('Content-Encoding')=='gzip':data=gzip.decompress(data)
            html=data.decode()
            match=re.search(r'(?:window\.)?_ROUTER_DATA\s*=\s*',html)
            if not match:raise ValueError('no details')
            d=json.JSONDecoder().raw_decode(html,match.end())[0]['loaderData']['detail_page']['seriesDetail']
            if str(d['series_id'])!=s:raise ValueError('ID mismatch')
            group=str((d.get('season_info') or {}).get('series_group_id','') or '')
            record.update(group_id=group,status='ok_group' if group else 'ok_no_public_group',title=d['series_name'])
            break
        except (HTTPError,OSError,KeyError,TypeError,ValueError) as exc:
            code=getattr(exc,'code',None)
            record.update(status=('http_'+str(code)) if code else 'failed_'+type(exc).__name__)
            if code in (401,403,429):stop.set()
            if stop.is_set() or code in (404,410) or attempt==1:break
    loc.write_text(json.dumps(record,ensure_ascii=False))
    return record


def main():
    cache.mkdir(exist_ok=True)
    roster=read(OLD/'identity_coverage.csv')
    ids={r['id'] for r in read(HERE/'new_rank_days.csv')}-{r['series_id'] for r in roster}
    with ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(get,sorted(ids)))
    historical={r['series_group_id'] or r['old_sdk_album_id'] for r in roster}-{''}
    for row in rows:
        row['in_prior_known_group']=int(row['group_id'] in historical) if row['group_id'] else ''
    with (HERE/'new_identity.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(ids=len(ids),status_counts=Counter(r['status'] for r in rows),
                 previously_known_group=sum(r['in_prior_known_group']==1 for r in rows),
                 distinct_groups=len({r['group_id'] for r in rows}-{''}))
    (HERE/'new_identity_summary.json').write_text(json.dumps(summary,indent=2))
    print(summary)


if __name__=='__main__':main()
