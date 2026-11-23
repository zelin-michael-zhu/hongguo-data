from pathlib import Path
from collections import Counter, defaultdict
from datetime import date
from statistics import NormalDist
from math import sqrt, ceil
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json, hashlib

OUT=Path('/Users/zhuzelin/Desktop/fyp/outputs/hongguo_research_review_2026-11-19/evidence')
RAW=Path('/var/folders/3c/rp2p0_4x7blcyb18cf7ylssh0000gn/T/hongguo-tool-probe-ocpwhkae/radar/data/snapshots/hongguo')
files=sorted(RAW.glob('*.json'))
by=defaultdict(list); rows=[]; daily=[]; fingerprints={}; keys=Counter()
for f in files:
    fingerprints[f.name]=hashlib.sha256(f.read_bytes()).hexdigest()
    d=json.loads(f.read_text()); status=Counter(); total_present=0
    for sid,it in d['items'].items():
        keys.update(it.keys())
        r=dict(date=d['date'], id=sid, title=it.get('title'), status_code=it.get('status_code'),
               episodes=it.get('episodes'),episodes_total=it.get('episodes_total'),tracked_by=it.get('tracked_by',[]))
        rows.append(r);by[sid].append(r);status[str(r['status_code'])]+=1
        total_present+=r['episodes_total'] is not None
    daily.append(dict(date=d['date'],rows=len(d['items']),status_code=dict(status),episodes_total_present=total_present))
transitions=[]; ep_changes=[]; total_changes=[]
for sid,rs in by.items():
    for a,b in zip(rs,rs[1:]):
        pair=dict(id=sid,title=b['title'],from_date=a['date'],to_date=b['date'],
                  gap_days=(date.fromisoformat(b['date'])-date.fromisoformat(a['date'])).days,
                  from_status=a['status_code'],to_status=b['status_code'],
                  from_episodes=a['episodes'],to_episodes=b['episodes'],
                  from_total=a['episodes_total'],to_total=b['episodes_total'])
        if a['status_code']!=b['status_code']:transitions.append(pair)
        if a['episodes']!=b['episodes']:ep_changes.append(pair)
        if a['episodes_total'] is not None and b['episodes_total'] is not None and a['episodes_total']!=b['episodes_total']:total_changes.append(pair)
zeroids={r['id'] for r in rows if r['status_code']==0}
oneids={r['id'] for r in rows if r['status_code']==1}
z=NormalDist().inv_cdf(.975);zb=NormalDist().inv_cdf(.8);power=[]
for p0,p1 in [(.5,.65),(.425,.575),(.1,.25),(.25,.4)]:
    p=(p0+p1)/2;n=(z*sqrt(2*p*(1-p))+zb*sqrt(p0*(1-p0)+p1*(1-p1)))**2/(p1-p0)**2
    power.append(dict(p0=p0,p1=p1,alpha=.05,power=.8,per_arm=n,total_rounded=2*ceil(n)))
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
clauses=[];doc_hashes={}
for fn,ids in [
 ('4 FYP Operational Manual 2026-27.docx',{140,152,247,248,300,301,1539}),
 ('5 AY2026-27 BUSA FYP Operational Guidance (Based on BBA FYP Operational Manual).docx',{1,4,6,8,61,81,159,166,260})]:
    p=Path('/Users/zhuzelin/Desktop/fyp')/fn;doc_hashes[fn]=hashlib.sha256(p.read_bytes()).hexdigest()
    root=ET.fromstring(ZipFile(p).read('word/document.xml'))
    for i,el in enumerate(root.findall('.//w:p',ns),1):
        if i in ids:clauses.append(dict(file=fn,paragraph=i,text=''.join(el.itertext())))
audit=dict(checked_at='2026-11-19',raw_directory=str(RAW),files=len(files),rows=len(rows),ids=len(by),
 date_range=[min(r['date']for r in rows),max(r['date']for r in rows)],
 status_code_rows=dict(Counter(str(r['status_code'])for r in rows)),
 status_code_ids={'ever0':len(zeroids),'ever1':len(oneids),'both':len(zeroids&oneids),'only0':len(zeroids-oneids),'only1':len(oneids-zeroids)},
 episodes_total_present=sum(r['episodes_total'] is not None for r in rows),
 episodes_total_missing=sum(r['episodes_total'] is None for r in rows),
 episodes_total_equal_episodes=sum(r['episodes_total'] is not None and r['episodes_total']==r['episodes'] for r in rows),
 episodes_total_unequal_episodes=sum(r['episodes_total'] is not None and r['episodes_total']!=r['episodes'] for r in rows),
 status_transition_count=len(transitions),status_transition_ids=len({p['id']for p in transitions}),
 status_transition_directions=dict(Counter(str(p['from_status'])+'->'+str(p['to_status'])for p in transitions)),
 status_transition_gap_days=dict(Counter(str(p['gap_days'])for p in transitions)),
 episode_change_pairs=len(ep_changes),episode_change_ids=len({p['id']for p in ep_changes}),
 episode_change_directions=dict(Counter('increase'if p['to_episodes']>p['from_episodes']else'decrease'for p in ep_changes)),
 episode_total_change_pairs=len(total_changes),episode_total_change_ids=len({p['id']for p in total_changes}),
 raw_item_key_counts=dict(keys),daily=daily,status_transitions=transitions,
 ever0_candidates=[dict(id=sid,title=by[sid][-1]['title'],first_observed=by[sid][0]['date'],last_observed=by[sid][-1]['date'],
  statuses=sorted({r['status_code']for r in by[sid]}),episodes_first=by[sid][0]['episodes'],episodes_last=by[sid][-1]['episodes'],
  boards=sorted({b for r in by[sid]for b in r['tracked_by']}))for sid in sorted(zeroids)],
 snapshot_sha256=fingerprints, power_planning=power,docx_sha256=doc_hashes,guidance_clauses=clauses)
(OUT/'extra_scope_checks.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
(OUT/'guidance_key_clauses_verified.txt').write_text('\n\n'.join(f"{c['file']} — P{c['paragraph']}\n{c['text']}"for c in clauses))
print(json.dumps({k:v for k,v in audit.items()if k not in ['snapshot_sha256','docx_sha256','daily','status_transitions','ever0_candidates','guidance_clauses','raw_item_key_counts']},ensure_ascii=False,indent=2))

