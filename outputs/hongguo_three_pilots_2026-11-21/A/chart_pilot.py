"""Reproduce the daily chart-composition pilot from two local public-data archives."""
import csv
import json
from collections import Counter, defaultdict
from math import comb
from pathlib import Path
from statistics import mean


OUT = Path(__file__).resolve().parent
DATA = OUT.parents[1]
BOARDS = ('hot', 'real', 'ai', 'comic')
DEPTHS = (10, 20, 100)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(name, rows):
    with (OUT/name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def hhi(counts):
    total = sum(counts)
    return sum(n*n for n in counts) / (total*total) if total else None


def prefix_metrics(slate, depth):
    prefix = [r for r in slate if int(r['rank']) <= depth]
    size = len(prefix)
    groups = Counter(r['key'] for r in prefix)
    known = Counter(r['group_id'] for r in prefix if r['group_id'])
    unknown = size - sum(known.values())
    failed = sum(r['web_status'] != 'ok' and not r['group_id'] for r in prefix)
    known_counts = sorted(known.values(), reverse=True)
    largest = max(groups.values())
    observed_except_404 = Counter(r['key'] for r in prefix if r['group_id'] or r['web_status']=='ok')
    revised_counts = sorted(observed_except_404.values(), reverse=True)
    if revised_counts:
        revised_counts[0] += failed
    else:
        revised_counts = [size]
    slate_groups = Counter(r['key'] for r in slate)
    random_expected = None
    if size == depth and len(slate) == 100:
        denominator = comb(100,depth)
        random_expected = depth - sum(1 - comb(100-n,depth)/denominator for n in slate_groups.values())
    group_sq = sum(n*(n-1) for n in groups.values())
    return {
        'observed_slots':size, 'id_count':len({r['id'] for r in prefix}),
        'observed_groups_including_unlinked_singletons':len(groups),
        'confirmed_extra_slots':size-len(groups), 'confirmed_extra_share':(size-len(groups))/size,
        'all_slots_in_multi_appearance_groups':sum(n for n in groups.values() if n>1),
        'largest_group_size':largest, 'largest_group_share':largest/size,
        'slots_with_verified_group':size-unknown,'ungrouped_slots_page_ok':unknown-failed,'slots_without_page_or_group':failed,
        'verified_group_share':(size-unknown)/size,
        'id_slot_hhi':1/size,'group_slot_hhi':hhi(groups.values()),
        'known_only_hhi':hhi(known_counts),
        'distinct_group_floor_extreme':max(1,len(known_counts)),
        'hhi_upper_extreme':hhi(([known_counts[0]+unknown]+known_counts[1:]) if known_counts else [size]),
        'hhi_if_only_unresolved_404_join_largest':hhi(revised_counts),
        'same_pair_probability':group_sq/(size*(size-1)) if size>1 else 0,
        'one_largest_group_fraction_of_same_pairs':largest*(largest-1)/group_sq if group_sq else None,
        'expected_extra_slots_if_positions_random_in_slate':random_expected,
    }


def main():
    roster = read_csv(DATA/'hongguo_expansion_2026-11-21/identity/identity_coverage.csv')
    members = {r['series_id']:r for r in roster}
    slates = defaultdict(list)
    for r in read_csv(DATA/'hongguo_free_pilot_2026-11-18/history/board_daily.csv'):
        member = members[r['id']]
        group = member['series_group_id'] or member['old_sdk_album_id']
        if member['series_group_id'] and member['old_sdk_album_id']:
            assert member['series_group_id'] == member['old_sdk_album_id']
        r.update(group_id=group, key=('group:'+group if group else 'id:'+r['id']),web_status=member['web_status'])
        slates[r['date'],r['board']].append(r)
    dates = sorted({d for d,_ in slates})
    complete_dates = {d for d in dates if all(len(slates[d,b])==100 for b in BOARDS)}
    gaps = {}
    for (d,b),rs in slates.items():
        ranks = {int(r['rank']) for r in rs}
        assert len({r['id'] for r in rs}) == len(ranks) == len(rs)
        assert ranks <= set(range(1,101))
        if len(rs)!=100:
            gaps[d+':'+b] = sorted(set(range(1,101))-ranks)
        rs.sort(key=lambda r:int(r['rank']))
    daily = []
    topgroups = []
    for (d,b),rs in sorted(slates.items()):
        for k in DEPTHS:
            vals = prefix_metrics(rs,k)
            daily.append(dict(date=d,board=b,depth=k,common_complete_day=int(d in complete_dates),**vals))
        group_counts = Counter(r['key'] for r in rs)
        for key,n in group_counts.most_common():
            if n<2:
                break
            entries = [r for r in rs if r['key']==key]
            topgroups.append(dict(date=d,board=b,group_id=entries[0]['group_id'],n_slots=n,
                                  tied_or_sole_largest=int(n==max(group_counts.values())),
                                  positions='|'.join(r['rank'] for r in entries),
                                  titles='|'.join(r['title'] for r in entries)))
    write_csv('daily_by_board.csv',daily)
    write_csv('repeated_group_placements.csv',topgroups)
    averages = []
    fields = ('observed_groups_including_unlinked_singletons','confirmed_extra_slots','confirmed_extra_share',
              'all_slots_in_multi_appearance_groups','largest_group_size','verified_group_share','id_slot_hhi',
              'group_slot_hhi','distinct_group_floor_extreme','hhi_upper_extreme','hhi_if_only_unresolved_404_join_largest',
              'expected_extra_slots_if_positions_random_in_slate')
    for cohort in ('35_matched_days','all_available_complete_prefixes'):
        for k in DEPTHS:
            for b in BOARDS:
                rows = [r for r in daily if r['board']==b and r['depth']==k and r['observed_slots']==k and
                        (cohort!='35_matched_days' or r['common_complete_day'])]
                means = {}
                for field in fields:
                    present = [r[field] for r in rows if r[field] is not None]
                    means[field] = mean(present) if present else None
                averages.append(dict(cohort=cohort,board=b,depth=k,n_days=len(rows),
                                     days_with_repeat=sum(r['confirmed_extra_slots']>0 for r in rows),
                                     largest_observed=max(r['largest_group_size'] for r in rows),**means))
    write_csv('board_summary.csv',averages)
    sample=slates['2026-11-16','ai'][:10]
    write_csv('example_ai_top10_2026-11-16.csv',[{k:r[k] for k in ('date','board','rank','id','title','group_id')} for r in sample])
    # Determine the most frequently dominant group, counting tied leaders once per board/date.
    persistence = []
    for b in BOARDS:
        leader_days = Counter(r['group_id'] for r in topgroups if r['date'] in complete_dates and r['board']==b and r['tied_or_sole_largest'])
        for group,count in leader_days.most_common():
            reference = next(r['catalog_title'] for r in roster if (r['series_group_id'] or r['old_sdk_album_id'])==group)
            no_group_hhi = []; shares = []; remainder_share = []; remainder_max = []; removed_slots = []
            for d in sorted(complete_dates):
                slate = slates[d,b]
                c = Counter(r['key'] for r in slate)
                n = c.pop('group:'+group,0)
                pairs=n*(n-1)+sum(v*(v-1) for v in c.values())
                if pairs:
                    shares.append(n*(n-1)/pairs)
                no_group_hhi.append(hhi(c.values()))
                remaining = sum(c.values())
                remainder_share.append((remaining-len(c))/remaining)
                remainder_max.append(max(c.values()))
                removed_slots.append(n)
            persistence.append(dict(board=b,group_id=group,example_member=reference,
                                    days_largest_resolving_ties_inclusively=count,
                                    mean_fraction_of_same_pairs_on_days_with_any=mean(shares),
                                    mean_removed_slots=mean(removed_slots),
                                    mean_remainder_extra_share=mean(remainder_share),
                                    mean_remainder_max_group_size=mean(remainder_max),
                                    mean_hhi_omitting_group_and_renormalizing=mean(no_group_hhi)))
    write_csv('dominant_group_persistence.csv',persistence)
    audit={'observed_rows':sum(map(len,slates.values())),'calendar_days':len(dates),'observed_ids':len({r['id'] for rs in slates.values() for r in rs}),
           'common_complete_count':len(complete_dates),'missing_ranks':gaps,'start_date':dates[0],'end_date':dates[-1]}
    (OUT/'coverage.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':
    main()
