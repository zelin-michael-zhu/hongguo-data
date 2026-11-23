"""Cross-check the two local CSV title fields against the source's pinned daily JSON."""
import hashlib
import json
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from title_keys import DATA, HERE, read

REV='9963122332b7bc93b508547fb6802f663afe6d43'
ARCHIVE='https://codeload.github.com/SentDz/drama-radar/zip/'+REV


def main():
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path(tempfile.gettempdir())/('fyp-radar-'+REV+'.zip')
    if not path.exists():
        with urllib.request.urlopen(ARCHIVE,timeout=30) as f:
            path.write_bytes(f.read())
    z=zipfile.ZipFile(path)
    base='drama-radar-'+REV+'/'
    board=read(DATA/'board_daily.csv')
    daily={(r['date'],r['id']):r['title'] for r in read(DATA/'drama_daily.csv')}
    counts=Counter()
    fields=set()
    renames=defaultdict(set)
    days={r['date'] for r in board}
    expected={(r['date'],r['board'],int(r['rank']),r['id']):r for r in board}
    affected=set()
    for date in sorted(days):
        source=json.loads(z.read(base+'data/snapshots/hongguo/'+date+'.json'))
        assert date==source['date']
        for sid,item in source['items'].items():
            fields.update(item)
            if item.get('title'):renames[sid].add(item['title'])
        for b,sections in source['boards'].items():
            for r in sections['items']:
                sid=r['id']
                csvrow=expected.pop((date,b,r['rank'],sid))
                actual=source['items'][sid]['title']
                counts['slots_compared']+=1
                assert actual==daily[date,sid]
                if actual!=csvrow['title']:
                    counts['slots_with_retrospective_title_change']+=1
                    affected.add((date,sid))
    assert not expected
    data=dict(counts,chart_series_days_affected=len(affected),date_count=len(days),
              tracked_ids_with_title_changes=sum(len(v)>1 for v in renames.values()),
              item_fields=sorted(fields),commit=REV,archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
              archive_url=ARCHIVE)
    (HERE/'source_check.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
