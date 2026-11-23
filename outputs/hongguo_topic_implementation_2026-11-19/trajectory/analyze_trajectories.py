"""Exploratory matched trajectories. All matching covariates stop at day -1."""
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from functools import lru_cache
from statistics import mean, median
from math import asinh, log, log1p, hypot
import json

from season_windows import HERE, BASE, load, rows, shift, window_audit, write

parser = argparse.ArgumentParser()
parser.add_argument('--pairs', help='Optional UTF-8 CSV with verified old_id,new_id columns.')
parser.add_argument('--prefix', default='candidate')
parser.add_argument('--verify-albums', action='store_true', help='Filter using the archived app catalog response for both seasons.')
parser.add_argument('--clock', choices=('board', 'web-visible'), default='board')
parser.add_argument('--width', type=int, choices=(3, 5, 7), default=3)
args = parser.parse_args()
width = args.width
relative_days = range(-width, width + 1)
placebo_lag = 2 * width + 1
placebo_phase = f'placebo_minus_{placebo_lag}'
prefix = args.prefix
panel, complete_boards, first, families = load()
if args.clock == 'web-visible':
    # Limit inference to the primary cohort for which both public HTML pages were checked.
    identity = rows(HERE.parent/'identity/pair_identity.csv')
    primary = {(r['old_id'],r['new_id']):r for r in identity if r['identity_confirmed']=='1'}
    public_dates = defaultdict(set)
    for (sid, day), record in panel.items():
        if record['first_visible']: public_dates[sid].add(record['first_visible'])
    first = {sid:next(iter(vals)) for sid,vals in public_dates.items() if len(vals)==1}
    for row in primary.values():
        for col,key in [('old_id','old_web_first_visible_shanghai'),('new_id','new_web_first_visible_shanghai')]:
            if row[key] and first.get(row[col]) != row[key][:10]:
                raise ValueError('archived date disagrees with checked public page')
    audit = [r for r in window_audit(panel,complete_boards,first,families,width)
             if (r['old_id'],r['new_id']) in primary]
    for r in audit: r['archive_first_seen_date']=primary[r['old_id'],r['new_id']]['event_date']
    write(prefix+'_window_exclusions.csv',audit)
    all_pairs = [r for r in audit if r['include']]
else:
    all_pairs = [r for r in window_audit(panel, complete_boards, first, families, width) if r['include']]
if args.pairs:
    keep = {(r['old_id'], r['new_id']) for r in rows(Path(args.pairs))}
    pairs = [r for r in all_pairs if (r['old_id'], r['new_id']) in keep]
else:
    pairs = all_pairs
if args.verify_albums:
    detail = json.loads((HERE.parent/'identity/public_season_metadata.json').read_text())['details']
    confirmed = []
    for pair in pairs:
        a = detail.get(pair['old_id'], {})
        b = detail.get(pair['new_id'], {})
        if (a.get('related_album_id') and a['related_album_id'] == b.get('related_album_id')
                and a.get('season_index') == pair['old_season'] and b.get('season_index') == pair['new_season']):
            confirmed.append(pair)
    pairs = confirmed
if not pairs: raise SystemExit('No eligible pairs.')
family_of = {m['id']:fam for fam, members in families.items() for m in members}
starts = {fam:{first[m['id']] for m in members if m['id'] in first} for fam,members in families.items()}
byday = defaultdict(set)
category_board = defaultdict(list)
for (sid, day), row in panel.items():
    byday[day].add(sid)
    for name in ('ai','comic','real'):
        if row['rank_'+name]: category_board[sid].append((day,name))

def get_fav(sid, day):
    raw = panel.get((sid,day),{}).get('fav','')
    return int(raw) if raw else None

@lru_cache(None)
def covariates(sid, day):
    past = [get_fav(sid,shift(day,k)) for k in range(-width,0)]
    if None in past: return None
    cutoff=shift(day,-1)
    # This is a board-membership stratum, not an inferred production type.
    category=tuple(sorted({n for dt,n in category_board[sid] if dt<=cutoff}))
    return (category, log1p(past[-1]), asinh((past[-1]-past[0])/((width-1)*1000)))

def observation(sid, day):
    y=[get_fav(sid,shift(day,k)) for k in relative_days]
    if None in y: return None
    pre=(y[width-1]-y[0])/(width-1)
    post=(y[-1]-y[width+1])/(width-1)
    return y,pre,post,post-pre

def matches(old, day, fam):
    base=covariates(old,day)
    if base is None: return []
    datemin=shift(day,-width);datemax=shift(day,width)
    pool=[]
    for cid in byday[shift(day,-1)]:
        cfam=family_of.get(cid)
        if cfam==fam: continue
        # Research eligibility only: exclude comparison families with a recorded nearby event.
        if cfam and any(datemin<=dt<=datemax for dt in starts[cfam]): continue
        candidate=covariates(cid,day)
        if candidate is None or candidate[0]!=base[0]: continue
        levelgap=abs(base[1]-candidate[1])
        trendgap=abs(base[2]-candidate[2])
        if levelgap>log(2) or trendgap>0.75: continue
        score=hypot(levelgap/log(2),trendgap/0.75)
        pool.append((score,cid,levelgap,trendgap))
    pool.sort()
    return pool[:3]

def comparison(pair, day, phase):
    old=pair['old_id'];family=pair['family'];source=observation(old,day)
    row=dict(family=family,old_id=old,old_title=pair['old_title'],new_id=pair['new_id'],event_date=pair['event_date'],analysis_day=day,phase=phase,board_stratum='',match_status='',selected_donors=0,observed_donors=0,old_pre='',old_post='',old_change='',control_pre='',control_post='',control_change='',relative_change='')
    if not all(complete_boards[shift(day,k),b]==set(range(1,101)) for k in relative_days for b in ('ai','comic','real','hot')):
        row['match_status']='incomplete_board_calendar';return row,[],[]
    if source is None:
        row['match_status']='predecessor_window_missing';return row,[],[]
    if phase==placebo_phase and any(shift(day,-width)<=v<=shift(day,width) for v in starts[family]):
        row['match_status']='family_event_in_placebo_window';return row,[],[]
    y,pre,post,change=source
    row.update(old_pre=pre,old_post=post,old_change=change,board_stratum='+'.join(covariates(old,day)[0]) or 'none')
    selected=matches(old,day,family)
    donorrows=[];obs=[]
    for dist,cid,g1,g2 in selected:
        v=observation(cid,day)
        donorrows.append(dict(phase=phase,old_id=old,new_id=pair['new_id'],event_date=pair['event_date'],analysis_day=day,control_id=cid,distance=dist,pre_log_level_distance=g1,pre_asinh_slope_distance=g2,post_complete=int(v is not None)))
        if v: obs.append(v)
    row.update(selected_donors=len(selected),observed_donors=len(obs))
    if not selected: row['match_status']='outside_calipers_or_no_exact_stratum'
    elif len(obs)!=len(selected): row['match_status']='donor_followup_missing'
    else:
        row.update(match_status='matched',control_pre=mean(v[1] for v in obs),control_post=mean(v[2] for v in obs),control_change=mean(v[3] for v in obs),relative_change=change-mean(v[3] for v in obs))
    points=[]
    for i,k in enumerate(relative_days):
        points.append(dict(family=family,old_id=old,new_id=pair['new_id'],event_date=pair['event_date'],phase=phase,relative_day=k,observed_day=shift(day,k),old_favorites=y[i],old_delta_vs_event=y[i]-y[width],control_delta_vs_event=mean(v[0][i]-v[0][width] for v in obs) if row['match_status']=='matched' else ''))
    return row,donorrows,points

analysis=[];donors=[];points=[]
for pair in pairs:
    for offset,phase in [(0,'observed_event'),(-placebo_lag,placebo_phase)]:
        row,matchrows,pointrows=comparison(pair,shift(pair['event_date'],offset),phase)
        analysis.append(row);donors.extend(matchrows);points.extend(pointrows)

write(prefix+'_event_results.csv',analysis)
if donors: write(prefix+'_donors.csv',donors)
write(prefix+('_seven_points.csv' if width==3 else '_raw_points.csv'),points)

def summary(sub):
    if not sub:return {'pairs':0}
    m=[a['relative_change'] for a in sub]
    return dict(pairs=len(sub),families=len({a['family'] for a in sub}),days=len({a['event_date'] for a in sub}),mean=mean(m),median=median(m),positive=sum(x>0 for x in m),zero=sum(x==0 for x in m),negative=sum(x<0 for x in m),old_pre=mean(r['old_pre'] for r in sub),old_post=mean(r['old_post'] for r in sub),control_pre=mean(r['control_pre'] for r in sub),control_post=mean(r['control_post'] for r in sub))

actual=[r for r in analysis if r['phase']=='observed_event']
matched=[r for r in actual if r['match_status']=='matched']
sham=[r for r in analysis if r['phase']==placebo_phase and r['match_status']=='matched']
intersect={r['new_id'] for r in matched}&{r['new_id'] for r in sham}
sensitivity=[]
for field in ['family','event_date']:
    for value in sorted({r[field] for r in matched}):
        rem=[r for r in matched if r[field]!=value]
        if rem: sensitivity.append({'omit_by':field,'omit':value,**summary(rem)})
if sensitivity: write(prefix+'_leave_one_out.csv',sensitivity)
compact={'eligible':len(pairs),'families':len({r['family'] for r in pairs}),'event_days':len({r['event_date'] for r in pairs}),'status':dict(Counter(r['match_status'] for r in actual)),'strata':dict(Counter(r['board_stratum'] for r in actual)),'actual':summary(matched),'placebo_status':dict(Counter(r['match_status'] for r in analysis if r['phase']==placebo_phase)),'placebo':summary(sham),'same_pairs_actual':summary([r for r in matched if r['new_id'] in intersect]),'same_pairs_placebo':summary([r for r in sham if r['new_id'] in intersect])}
for fld in ['family','event_date']:
    vals=[v['mean'] for v in sensitivity if v['omit_by']==fld]
    compact[f'leave_one_{fld}_mean_range']=[min(vals),max(vals)] if vals else []
(HERE/(prefix+'_summary.json')).write_text(json.dumps(compact,ensure_ascii=False,indent=2))
print(json.dumps(compact,ensure_ascii=False,indent=2))
