"""Audit held-out prior trajectories, sample changes and the displayed favorite scale."""
from collections import Counter, defaultdict
import json
from statistics import mean, median
from season_windows import HERE, load, rows, shift, write

panel, boards, first_board, families = load()
def matched(prefix):
    return {r['new_id']:r for r in rows(HERE/(prefix+'_event_results.csv'))
            if r['phase']=='observed_event' and r['match_status']=='matched'}

def summarise(values):
    return {'n':len(values),'mean':mean(values) if values else None,'median':median(values) if values else None}

primary = matched('verified')
out = {}
for name in ('verified_5d', 'verified_visible'):
    alternative = matched(name)
    common = primary.keys() & alternative.keys()
    out[name+'_same_pairs'] = {
        choice:summarise([float(result[key]['relative_change']) for key in common])
        for choice,result in [('primary',primary),('alternative',alternative)]}

donors = defaultdict(list)
for r in rows(HERE/'verified_donors.csv'):
    if r['phase']=='observed_event': donors[r['new_id']].append(r['control_id'])

def fav(sid, d):
    raw=panel.get((sid,d),{}).get('fav')
    return int(raw) if raw else None

# Hold the three primary comparators fixed as well as the candidate pair.
valid_five = {r['new_id'] for r in rows(HERE/'window_exclusions.csv') if r['include']=='1' and r['width']=='5'}
family_of={m['id']:fam for fam, members in families.items() for m in members}
family_events={fam:{first_board[m['id']] for m in ms if m['id'] in first_board} for fam,ms in families.items()}
fixed=[]
for key,r in primary.items():
    if key not in valid_five: continue
    refs=donors[key]
    days=[shift(r['event_date'],k) for k in range(-5,6)]
    if any(set(days) & family_events.get(family_of.get(sid),set()) for sid in refs): continue
    values={sid:[fav(sid,dt) for dt in days] for sid in [r['old_id'],*refs]}
    if any(None in data for data in values.values()): continue
    changes={sid:((data[10]-data[6])-(data[4]-data[0]))/4 for sid,data in values.items()}
    fixed.append({'new_id':key,'event_date':r['event_date'],'family':r['family'],
                  'fixed_donors':'|'.join(refs),'relative_3':float(r['relative_change']),
                  'relative_5':changes[r['old_id']]-mean(changes[sid] for sid in refs)})
if fixed: write('same_pairs_same_donors_3d_5d.csv',fixed)
out['same_pairs_same_donors_3d_5d']={k:summarise([r[k] for r in fixed]) for k in ['relative_3','relative_5']}

check = []
for key,r in primary.items():
    ids = [r['old_id']] + donors[key]
    days = [shift(r['event_date'],k) for k in (-6,-5,-4)]
    stats={'new_id':key,'family':r['family'],'event_date':r['event_date'],'old_minus_control_earlier':'',
           'old_minus_control_matching_window':float(r['old_pre'])-float(r['control_pre'])}
    if any(boards[d,b]!=set(range(1,101)) for d in days for b in ('ai','comic','hot','real')):
        stats['status']='incomplete_prior_boards'
    elif any(fav(id_,d) is None for id_ in ids for d in days):
        stats['status']='prior_favorites_missing'
    else:
        slopes=[(fav(id_,days[-1])-fav(id_,days[0]))/2 for id_ in ids]
        stats.update(status='observed',old_minus_control_earlier=slopes[0]-mean(slopes[1:]))
    check.append(stats)
write('heldout_pretrend.csv',check)
early = [q for q in check if q['status']=='observed']
out['earlier_pretrend']={'status':dict(Counter(r['status'] for r in check)),
       'earlier_days_minus_6_to_minus_4':summarise([q['old_minus_control_earlier'] for q in early]),
       'same_pairs_minus_3_to_minus_1':summarise([q['old_minus_control_matching_window'] for q in early])}
raw_points=[int(r['old_favorites']) for r in rows(HERE/'verified_seven_points.csv') if r['phase']=='observed_event']
out['original_7_points']={'pair_days':len(raw_points),'multiples_of_1000':sum(v%1000==0 for v in raw_points)}
m=Counter(s for key in primary for s in donors[key])
out['references']={'unique_ids_matched':len(m),'matched_slots':sum(m.values()),'max_reuse':max(m.values()),
       'matches_per_pair':dict(Counter(len(donors[key]) for key in primary))}
out['remove_migration_crossover']=summarise([float(r['relative_change']) for r in primary.values()
                                              if shift(r['event_date'],-3)>='2026-10-17'])
out['flow']={}
for width in (3,5,7):
    records=[r for r in rows(HERE/'window_exclusions.csv') if int(r['width'])==width]
    flow={'all':len(records)}
    for reason in ['no_board_event','window_truncated','incomplete_board_window','predecessor_favorites_missing','overlapping_season_first_appearance']:
        records=[r for r in records if reason not in r['reasons'].split('|')]
        flow['remaining_after_'+reason]=len(records)
    out['flow'][str(width)]=flow
(HERE/'sensitivity_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
