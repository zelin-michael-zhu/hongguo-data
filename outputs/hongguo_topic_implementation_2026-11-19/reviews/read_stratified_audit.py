"""Print card and outcome-blind text for two deterministic positions per title."""
from pathlib import Path
import csv,hashlib,json,sys
B=Path(__file__).resolve().parent
cohort=list(csv.DictReader((B/'frozen_30.csv').open(encoding='utf-8-sig')))
def selected(sid,rows):
    return sorted(sorted(rows,key=lambda r:hashlib.sha256(('read-v1|'+sid+'|'+str(r['source_position'])).encode()).hexdigest())[:2],key=lambda r:r['source_position'])
if __name__=='__main__':
    for i,r in enumerate(cohort,1):
        if not int(sys.argv[1])<=i<=int(sys.argv[2]):continue
        j=json.loads((B/'sanitized_captures'/(r['series_id']+'.json')).read_text())
        print(f"{i} {j['title']} | {j['tags']} | {j['synopsis']}")
        for v in selected(r['series_id'],j['reviews']):print(f'  {i}.{v["source_position"]} {v["text"]}')
