"""Freeze a stratified list, then read one public detail preview per title."""
from pathlib import Path
import argparse
import csv
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = Path(__file__).resolve().parent
PILOT = BASE.parents[1] / 'hongguo_free_pilot_2026-11-18'
SHANGHAI = timezone(timedelta(hours=8))
SEED = 'hg-info-choice-v1-20261119'
SENSITIVE = re.compile(r'(?:1[3-9][0-9]{9}|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})')

def read_rows(file):
    with file.open(encoding='utf-8-sig',newline='') as handle:
        return list(csv.DictReader(handle))

def write_rows(file,rows):
    with file.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)

def freeze():
    selected = {x['id'] for x in json.loads((PILOT/'selected_series.json').read_text())}
    daily = [r for r in read_rows(PILOT/'history/drama_daily.csv') if r['date']=='2026-11-17' and r['id'] not in selected]
    by = {}
    for r in daily:
        group = 'hot' if r['rank_hot'] else ('category_only' if any(r['rank_'+k] for k in ['real','comic','ai']) else 'tracked_off_board')
        by.setdefault(group, []).append(r)
    ordered = []
    for group, items in sorted(by.items()):
        key=lambda r: hashlib.sha256((SEED+'|'+r['id']).encode()).hexdigest()
        for r in sorted(items,key=key)[:10]:
            ordered.append({'series_id':r['id'],'stratum':group,'frame_date':r['date'],'frame_title':r['title'],'hash':key(r),'stratum_size':len(items)})
    path = BASE/'frozen_30.csv'
    if path.exists():
        assert [r['series_id'] for r in read_rows(path)]==[r['series_id'] for r in ordered]
    else: write_rows(path,ordered)
    return ordered

def pull(sid):
    date = datetime.now(SHANGHAI).isoformat(timespec='seconds')
    url='https://hongguoduanju.com/detail?series_id='+sid
    request = Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; University research; public page sample)'})
    with urlopen(request,timeout=10) as response:
        html = response.read().decode('utf-8')
    mark=html.index('_ROUTER_DATA')
    start=html.index('{',html.index('=',mark))
    obj,_=json.JSONDecoder().raw_decode(html[start:])
    page=next(x for x in obj['loaderData'].values() if isinstance(x,dict) and str(x.get('seriesDetail',{}).get('series_id'))==sid)
    detail=page['seriesDetail'];social=page.get('seriesSocialInfo') or {}; reviews=social.get('reviews') or {}
    rows=[]
    for i,r in enumerate(reviews.get('reviews') or [],1):
        if not r.get('content'):continue
        rows.append({'source_position':i,'text':SENSITIVE.sub('[redacted]',r['content']),'review_rating':r.get('rating'),'digg_count':r.get('digg_count'),'create_time':r.get('create_time')})
    return {'series_id':sid,'status':'ok','sample_time':date,'url':url,'title':detail.get('series_name'),'synopsis':detail.get('series_intro'),'tags':detail.get('tags'),'episode_count':detail.get('episode_cnt'),'cast':[c.get('name') or c.get('nickname') or c.get('celebrity_name') for c in detail.get('celebrities') or [] if isinstance(c,dict)],'display_rating':social.get('rating'),'rating_count':social.get('rating_count'),'source_review_total':reviews.get('total_count'),'reviews':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--collect',action='store_true');parser.add_argument('--calibrate',action='store_true');args=parser.parse_args()
    cohort=freeze()
    if args.collect and args.calibrate:
        parser.error('Choose one capture folder per run.')
    if args.collect or args.calibrate:
        source=BASE/('calibration_today' if args.calibrate else 'sanitized_captures');source.mkdir(exist_ok=True)
        if args.calibrate:
            cohort=[{'series_id':r['id']} for r in json.loads((PILOT/'selected_series.json').read_text())]
        for row in cohort:
            sid=row['series_id'];p=source/(sid+'.json')
            if p.exists():continue
            try:
                obj=pull(sid)
            except (HTTPError,URLError,TimeoutError,ValueError,StopIteration,KeyError) as err:
                stop=isinstance(err,HTTPError) and err.code in (401,403,429)
                obj={'series_id':sid,'status':'failed','sample_time':datetime.now(SHANGHAI).isoformat(),'error_type':type(err).__name__,'error':str(err)[:180]}
                p.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
                if stop:print('stopped on access or rate limit',flush=True);break
            p.write_text(json.dumps(obj,ensure_ascii=False,indent=2));print(sid,obj['status'],len(obj.get('reviews',[])),flush=True)
            time.sleep(1.5)
