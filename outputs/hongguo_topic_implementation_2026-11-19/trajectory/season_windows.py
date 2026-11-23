"""Create event-window cohorts and an exclusion log from the frozen exports."""
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
import csv
import json

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = ROOT / "outputs/hongguo_free_pilot_2026-11-18/history"
FAMILY = ROOT / "outputs/hongguo_topic_feasibility_2026-11-19/series_matching_candidates.json"

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def write(name, data):
    with (HERE / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)

def shift(day, k):
    return (date.fromisoformat(day) + timedelta(days=k)).isoformat()

def load():
    daily = {(r['id'], r['date']): r for r in rows(BASE/'drama_daily.csv')}
    boards = defaultdict(set)
    first = {}
    for r in rows(BASE/'board_daily.csv'):
        boards[r['date'],r['board']].add(int(r['rank']))
        first[r['id']] = min(first.get(r['id'], r['date']),r['date'])
    families = json.loads(FAMILY.read_text())['candidates']
    return daily, boards, first, families

def window_audit(daily, boards, first, families, width):
    out = []
    complete = set(range(1,101))
    archive_days = {day for _, day in daily}
    earliest, latest = min(archive_days), max(archive_days)
    for family, members in families.items():
        for old in members:
            for new in members:
                if old['season']+1 != new['season']: continue
                day = first.get(new['id'],'')
                window = [shift(day, k) for k in range(-width,width+1)] if day else []
                reasons = []
                if not day: reasons.append('no_board_event')
                if not window or any(d<earliest or d>latest for d in [window[0],window[-1]]): reasons.append('window_truncated')
                if not window or any(boards[d,b] != complete for d in window for b in ('ai','comic','real','hot')): reasons.append('incomplete_board_window')
                if not window or any(not daily.get((old['id'],d),{}).get('fav') for d in window): reasons.append('predecessor_favorites_missing')
                others = [m['id'] for m in members if m['id']!=new['id'] and first.get(m['id']) in window]
                if others: reasons.append('overlapping_season_first_appearance')
                out.append(dict(family=family,old_id=old['id'],old_title=old['title'],old_season=old['season'],new_id=new['id'],new_title=new['title'],new_season=new['season'],event_date=day,width=width,include=int(not reasons),reasons='|'.join(reasons),other_seasons_in_window='|'.join(others)))
    return out

if __name__=='__main__':
    inputs = load()
    checks = []
    for width in [3,5,7]:
        audit=window_audit(*inputs,width)
        keep=[r for r in audit if r['include']]
        print(width,len(audit),len(keep),len({r['family'] for r in keep}),len({r['event_date'] for r in keep}))
        if width==3: write('candidate_season_pairs.csv',keep)
        checks+=audit
    write('window_exclusions.csv',checks)
