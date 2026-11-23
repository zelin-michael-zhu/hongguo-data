"""Recover explicit season numbers in publicly displayed titles, retaining evidence type."""
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = re.compile(r'第\s*([0-9〇零一二两三四五六七八九十百]+)\s*季')
DIGITS = dict(zip('零一二三四五六七八九',range(10)), 〇=0, 两=2)


def season_number(text):
    if text.isdecimal():
        return int(text)
    if not ('十' in text or '百' in text):
        return int(''.join(str(DIGITS[c]) for c in text))
    total, current = 0, 0
    for c in text:
        if c in DIGITS:
            current = DIGITS[c]
        else:
            total += (current or 1)*{'十':10,'百':100}[c]
            current = 0
    return total+current


def main():
    assert all(season_number(t)==v for t,v in [('十二',12),('二十',20),('二十一',21),('一百零一',101),('３',3)])
    with (HERE/'identity_coverage.csv').open(encoding='utf-8-sig') as f:
        old = {r['series_id']:r for r in csv.DictReader(f)}
    members = []
    slots = defaultdict(list)
    for f in sorted((HERE/'pages').glob('*.json')):
        r = json.loads(f.read_text())
        detail = r['detail']
        group = (detail.get('season_info') or {}).get('series_group_id')
        name = detail.get('series_name','')
        m = MARKER.findall(unicodedata.normalize('NFKC',name))
        if not group or len(m)!=1 or not season_number(m[0]):
            continue
        sid, n = r['series_id'], season_number(m[0])
        prior = old[sid].get('old_sdk_season_index')
        sdk_match = (int(prior)==n) if prior else None
        row = {'series_id':sid,'web_title':name,'website_group_id':group,'title_season_number':n,
               'sdk_season_number_if_available':prior,'sdk_match_if_available':sdk_match,
               'detail_source':r['url'],'collected_at_utc':r['fetched_at_utc']}
        members.append(row)
        slots[(group,n)].append(row)
    for row in members:
        row['catalog_members_at_same_group_position'] = len(slots[(row['website_group_id'],row['title_season_number'])])
    def write(name, rows, fields):
        with (HERE/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    write('explicit_seasons.csv',members,list(members[0]))
    pairs = []
    for (group,n),items in sorted(slots.items()):
        next_items = slots.get((group,n+1),[])
        if len(items)==len(next_items)==1:
            a,b=items[0],next_items[0]
            if a['sdk_match_if_available'] is False or b['sdk_match_if_available'] is False:
                continue
            pairs.append(dict(group_id=group,old_id=a['series_id'],old_title=a['web_title'],old_number=n,
                              new_id=b['series_id'],new_title=b['web_title'],new_number=n+1))
    write('explicit_adjacent_seasons.csv',pairs,['group_id','old_id','old_title','old_number','new_id','new_title','new_number'])
    sdk = Counter('unknown' if r['sdk_match_if_available'] is None else ('agree' if r['sdk_match_if_available'] else 'disagree')
                  for r in members)
    report={'source':'Public official series_group_id and exactly one explicit 第N季 marker in the displayed title.',
            'members':len(members),'groups':len({r['website_group_id'] for r in members}),'crosscheck_with_sdk':sdk,
            'duplicate_group_and_number_slots':sum(len(items)>1 for items in slots.values()),'unique_adjacent_pairs':len(pairs),
            'pair_groups':len({r['group_id'] for r in pairs})}
    (HERE/'explicit_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
