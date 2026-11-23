"""Capture the same public detail-page favorite counter each day for a frozen ID list."""
import argparse
from collections import Counter, defaultdict
import csv
import datetime as dt
from decimal import Decimal
import fcntl
from functools import reduce
from hashlib import sha256
import json
from math import gcd
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
WATCH = HERE / 'favorite_watchlist.csv'
ZONE = ZoneInfo('Asia/Shanghai')
BASELINE = '2026-11-19'
FIELD = 'loaderData.detail_page.seriesSocialInfo.series_favorite_count'
HEADER = ['series_id','title','roles','predecessor_pairs','comparison_pairs']

def read_rows(file):
    with file.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def save_json(path, obj):
    temp = path.with_suffix('.partial')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)

def create_watchlist():
    if WATCH.exists():
        raise SystemExit('The fixed watchlist already exists.')
    source = HERE.parent/'trajectory'
    old = read_rows(source/'candidate_season_pairs.csv')
    donors = read_rows(source/'verified_donors.csv')
    archive = HERE.parents[2]/'outputs/hongguo_free_pilot_2026-11-18/history/drama_daily.csv'
    titles = {r['id']:r['title'] for r in read_rows(archive)}
    amounts = defaultdict(Counter)
    for pair in old:
        amounts[pair['old_id']]['predecessor'] += 1
    for d in donors:
        if d['phase'] == 'observed_event':
            amounts[d['control_id']]['comparison'] += 1
    with WATCH.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for sid, counts in sorted(amounts.items()):
            writer.writerow([sid,titles[sid],'+'.join(sorted(counts)),counts['predecessor'],counts['comparison']])

def normalize(raw):
    if raw is None: return None
    s = str(raw).strip().replace(',','')
    m = re.fullmatch(r'(\d+(?:\.\d+)?)(万|亿)?',s)
    if not m: return None
    value = Decimal(m[1]) * {'万':10000,'亿':100000000,None:1}[m[2]]
    return int(value) if value == int(value) else None

def read_official(sid):
    url = 'https://hongguoduanju.com/detail?series_id='+sid
    with urlopen(Request(url, headers={'User-Agent':'Hongguo-BA-academic-pilot/1.0'}),timeout=12) as response:
        html = response.read()
    obj, _ = json.JSONDecoder().raw_decode(html.decode().split('_ROUTER_DATA = ',1)[1])
    detail = obj['loaderData']['detail_page']
    if str(detail['seriesDetail']['series_id']) != sid: raise ValueError('series_id mismatch')
    return dict(public_fav_display=detail.get('seriesSocialInfo',{}).get('series_favorite_count'),
                url=url,fetched_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                html_sha256=sha256(html).hexdigest(),source='official_html')

def harvest(out, today, watch, limit, complete_baseline):
    state_file = out / 'observations.json'
    fingerprint = sha256(WATCH.read_bytes()).hexdigest()
    state = json.loads(state_file.read_text()) if state_file.exists() else dict(
        local_date=today.isoformat(), timezone=str(ZONE), field=FIELD, watchlist_sha256=fingerprint, entries={})
    if state['watchlist_sha256'] != fingerprint: raise ValueError('The fixed watchlist changed.')
    entries = state['entries']
    reserved = set()
    if today.isoformat() == BASELINE:
        pairs = json.loads((HERE.parent/'identity/independent_candidate_selection.json').read_text())
        reserved = {r[k] for r in pairs for k in ('pre','post')}
        if complete_baseline:
            finished=json.loads((HERE.parent/'identity/official_web_identity.json').read_text())['pages']
            if not reserved.issubset(finished):
                raise ValueError('The shared identity capture is still in progress.')
        companion_file = HERE / 'detail_favorites_companion.json'
        captured = json.loads(companion_file.read_text()) if companion_file.exists() else {}
        for sid, data in captured.items():
            if sid in watch and dt.datetime.fromisoformat(data['fetched_at_utc']).astimezone(ZONE).date()==today:
                entries[sid] = dict(**data, source='same_day_shared_official_html', value=normalize(data['public_fav_display']))
    count = 0
    stopped = None
    for sid in watch:
        if sid in entries or (sid in reserved and not complete_baseline): continue
        if dt.datetime.now(ZONE).date()!=today:
            stopped='local date changed';break
        if limit is not None and count>=limit:
            stopped='explicit URL limit';break
        count+=1
        try:
            rec=read_official(sid)
            if dt.datetime.fromisoformat(rec['fetched_at_utc']).astimezone(ZONE).date()!=today:
                stopped='local date changed during request';break
            if sid in reserved:
                rec['source']='supplemental_official_html_after_identity_audit'
            entries[sid]=dict(**rec,value=normalize(rec['public_fav_display']))
        except (OSError, ValueError, IndexError, KeyError) as err:
            entries[sid]=dict(source='request_error', url='https://hongguoduanju.com/detail?series_id='+sid,
                              fetched_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                              value=None,error=str(err)[:200])
            if isinstance(err,HTTPError) and err.code in (401,403,429):
                stopped='access or rate limit'
        save_json(state_file,state)
        if stopped: break
        time.sleep(1.15)
    save_json(state_file,state)
    rows=[]
    for sid, original in watch.items():
        rec=entries.get(sid,{})
        status=('observed' if rec.get('value') is not None else
                'collection_error' if rec.get('error') else
                'field_missing_or_unparsed' if rec else
                'baseline_identity_page_already_reserved' if sid in reserved else 'pending')
        rows.append({**original,'date_local':today.isoformat(),'status':status,
                     'favorite_display_raw':rec.get('public_fav_display'),'favorites_numeric':rec.get('value'),
                     'fetched_at_utc':rec.get('fetched_at_utc'),'source':rec.get('source'),
                     'url':rec.get('url','https://hongguoduanju.com/detail?series_id='+sid)})
    with (out/'favorites.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys())
        writer.writeheader();writer.writerows(rows)
    valid=[r for r in rows if r['status']=='observed']
    vals=[r['favorites_numeric'] for r in valid]
    counts={role:sum(role in r['roles'] for r in valid) for role in ('predecessor','comparison')}
    summary=dict(date_local=today.isoformat(),watchlist_ids=len(watch),status=dict(Counter(r['status'] for r in rows)),
                 observed_by_role=counts,source=dict(Counter(r['source'] for r in valid)),numeric_values=len(vals),
                 multiples_of_1000=sum(v%1000==0 for v in vals),gcd_of_nonzero_observed_values=reduce(gcd,(v for v in vals if v),0),
                 first_utc=min((r['fetched_at_utc'] for r in valid),default=None),last_utc=max((r['fetched_at_utc'] for r in valid),default=None),
                 observed_granularity_note='Divisibility describes the snapshot. Platform rounding rule and counting population are unverified.',
                 run_stop=stopped)
    save_json(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--initialize-watchlist',action='store_true',help='Generate the fixed historical cohort once, then exit.')
    parser.add_argument('--complete-baseline',action='store_true',help='After the identity audit has finished, collect only missing watchlist counters missed by that audit.')
    parser.add_argument('--limit',type=int,help='Maximum number of new official pages requested in this run.')
    args=parser.parse_args()
    if args.initialize_watchlist:
        create_watchlist()
    else:
        today=dt.datetime.now(ZONE).date()
        out=HERE/'detail_favorites'/today.isoformat()
        out.mkdir(parents=True,exist_ok=True)
        watch={r['series_id']:r for r in read_rows(WATCH)}
        with (out/'.lock').open('a') as guard:
            fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
            harvest(out,today,watch,args.limit,args.complete_baseline)
