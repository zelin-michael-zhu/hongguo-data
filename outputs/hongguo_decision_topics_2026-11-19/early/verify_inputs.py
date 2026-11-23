"""Check the local CSV against a supplied drama-radar daily Hongguo JSON archive."""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('snapshot_directory', type=Path)
args = parser.parse_args()
out = Path(__file__).resolve().parent
history = out.parents[2] / 'outputs/hongguo_free_pilot_2026-11-18/history/board_daily.csv'
with history.open(encoding='utf-8-sig') as f:
    hist = {(row['date'], row['board'], row['id']): (int(row['rank']), int(row['heat']) if row['heat'] else None)
            for row in csv.DictReader(f)}
dates = {key[0] for key in hist}
raw = {}
for day in dates:
    payload = json.loads((args.snapshot_directory / (day+'.json')).read_text())
    for board,obj in payload['boards'].items():
        for item in obj['items']:
            raw[day,board,str(item['id'])] = item['rank'],item.get('heat')
assert set(raw)==set(hist)
same = sum(raw[key]==val for key,val in hist.items())
shared = [(heat,hist[day,'hot',sid][1]) for (day,board,sid),(_,heat) in hist.items()
          if board!='hot' and (day,'hot',sid) in hist and heat is not None and hist[day,'hot',sid][1] is not None]
report=dict(rows=len(hist),raw_rows=len(raw),rank_heat_exact_matches=same,
            hot_category_shared_title_rows_with_both_heat=len(shared),
            heat_exact_agreement=sum(a==b for a,b in shared))
(out/'source_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
