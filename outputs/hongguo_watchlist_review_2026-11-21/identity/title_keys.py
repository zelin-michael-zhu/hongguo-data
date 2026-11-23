"""Replay series linkage using only titles found in dated archive observations."""
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / 'hongguo_free_pilot_2026-11-18/history'
SEASON = re.compile(r'第\s*([0-9零〇一二两三四五六七八九十百]+)\s*季\s*[。！？!？?）)]*\s*$')


def explicit_key(title, sid):
    title = unicodedata.normalize('NFKC', title or '')
    match = SEASON.search(title)
    if match and len(re.findall(r'第\s*[0-9零〇一二两三四五六七八九十百]+\s*季', title)) == 1:
        stem = title[:match.start()].strip().strip('，,。.：:、！!？?（）()【】[]《》·—- ').strip()
        stem = ''.join(ch for ch in stem if not ch.isspace())
        if len(stem) >= 2:
            return 't:' + stem
    return 'i:' + sid


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    board=read(DATA/'board_daily.csv')
    daily={(r['date'],r['id']):r['title'] for r in read(DATA/'drama_daily.csv')}
    by_day_id=defaultdict(list)
    for r in board:
        by_day_id[r['date'],r['id']].append(r)
    out=[]
    first={}
    for (date,sid),rows in sorted(by_day_id.items()):
        title=daily.get((date,sid),'')
        current=explicit_key(title,sid)
        if sid not in first:
            first[sid]=(date,current)
        first_date,frozen=first[sid]
        out.append(dict(date=date,id=sid,title_asof=title,group=frozen,group_from_today_title=current,
                        first_list_date=first_date,title_disagrees_catalog=int(bool(title) and title!=rows[0]['title'])))
    write(HERE/'asof_groups.csv',out)


if __name__=='__main__':
    main()
