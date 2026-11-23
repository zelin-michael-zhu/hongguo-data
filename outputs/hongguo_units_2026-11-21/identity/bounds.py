"""Bound the largest series share of repeated seats, retaining all known official links."""
import csv
import hashlib
import json
import re
import unicodedata
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1]
PREVIOUS = OUT / 'hongguo_watchlist_review_2026-11-21'
sys.path.insert(0, str(PREVIOUS))
from decision_audit import read_panel


def write(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def score(days, panels, board, depth, assignment):
    counts = Counter()
    unknown_ids = Counter()
    for day in days:
        groups = Counter()
        for r in panels[day, board]:
            if r['rank'] <= depth:
                groups[assignment.get(r['id'], r['group'])] += 1
                if r['group'].startswith('i:'):
                    unknown_ids[r['id']] += 1
        counts.update({g: n-1 for g,n in groups.items() if n > 1})
    return counts, unknown_ids


def share(value, total):
    return value / total if total else None


def label_augment(panel, proxy):
    # Only consider identical explicit-numbered season stems. Never override a known group.
    by_id = {r['id']: r['group'] for rows in panel.values() for r in rows}
    stem_to_known = defaultdict(set)
    stem_to_missing = defaultdict(list)
    for sid, group in by_id.items():
        stem = proxy[sid]
        if stem.startswith('t:'):
            if group.startswith('g:'):
                stem_to_known[stem].add(group)
            else:
                stem_to_missing[stem].append(sid)
    links = {}
    for stem, ids in stem_to_missing.items():
        officials = sorted(stem_to_known[stem])
        if len(officials) == 1:
            links.update(dict.fromkeys(ids, officials[0]))
        elif not officials and len(ids) > 1:
            links.update(dict.fromkeys(ids, stem))
    return links


def verified_page(sid):
    p = OUT / 'hongguo_expansion_2026-11-21/identity/pages' / (sid+'.json')
    if p.is_file():
        data = json.loads(p.read_text())
        d = data['detail']
        group = (d.get('season_info') or {}).get('series_group_id', '')
        assert str(d['series_id']) == sid
        return (d['series_name'], group, data['url'], data['fetched_at_utc'],
                str(p.relative_to(OUT)), data.get('html_sha256', ''))
    p = PREVIOUS / 'extension/identity_checks' / (sid+'.json')
    if p.is_file():
        data = json.loads(p.read_text())
        assert data['id'] == sid
        return (data['title'], data['group_id'], data['source_url'], data['checked_at_utc'],
                str(p.relative_to(OUT)), '')
    return ('', '', '', '', '', '')


def assignment_stress(days, panels, comic_leader):
    # Feasibility witness only. No content or title evidence supports these hypothetical merges.
    by_board = {board: score(days, panels, board, 100, {})[1] for board in ('ai', 'comic')}
    result = {sid: comic_leader for sid in by_board['comic'] if sid not in by_board['ai']}
    for sid in by_board['ai']:
        if sid not in by_board['comic']:
            bucket = int(hashlib.sha256(sid.encode()).hexdigest(), 16) % 8
            result[sid] = 'hypothetical:'+str(bucket)
    return result


def crossover(ai, comic):
    # f bounds the fraction of unknown seat-days which become additional repeated seats.
    def gap(f):
        ma, ea, ua = (ai[k] for k in ('largest','confirmed_extra','unknown_slots'))
        mc, ec, uc = (comic[k] for k in ('largest','confirmed_extra','unknown_slots'))
        return ma/(ea+f*ua) - (mc+f*uc)/(ec+f*uc)
    if gap(0) <= 0 or gap(1) >= 0:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo+hi)/2
        if gap(mid) > 0:
            lo=mid
        else:
            hi=mid
    return lo


def turnover_sensitivity(days, panels, board, depth, assignment):
    entering = represented = 0
    for a,b in zip(days,days[1:]):
        if (date.fromisoformat(b)-date.fromisoformat(a)).days!=1:
            continue
        yesterday = {r['id']: assignment.get(r['id'],r['group']) for r in panels[a,board] if r['rank']<=depth}
        today = {r['id']: assignment.get(r['id'],r['group']) for r in panels[b,board] if r['rank']<=depth}
        entrants = today.keys()-yesterday.keys()
        entering += len(entrants)
        represented += sum(today[i] in set(yesterday.values()) for i in entrants)
    return entering, represented


def main():
    first, dates, panels, proxy = read_panel()
    augmented = label_augment(panels, proxy)
    # Two unnumbered-title exceptions were read alongside catalog synopses. They remain hypothetical.
    # These identities are used only for a sensitivity scenario, never for confirmed group counts.
    plausible = dict(augmented)
    for first_id, later_id in (
            ('7694560624101035070','7696029520809167897'),
            ('7696822712345299993','7700193386157837336')):
        ref = next(r['group'] for rows in panels.values() for r in rows if r['id']==later_id)
        key = ref if ref.startswith('g:') else 'candidate:'+first_id
        plausible[first_id] = key
        if ref.startswith('i:'):
            plausible[later_id] = key
    catalog = {}
    with (OUT/'hongguo_free_pilot_2026-11-18/history/catalog.csv').open(encoding='utf-8-sig') as file:
        catalog = {r['id']:r for r in csv.DictReader(file)}
    reference_pairs = [
        ('7694560624101035070','7696029520809167897','plausible','完整题名加第四季；两简介出现楚眠、厉天阙、风岛、蔷园；目前两部官网均缺可核组号。'),
        ('7696822712345299993','7700193386157837336','plausible','完整题名加第二季；两简介均有李星月、自由城、暴君和修罗；只有第二部有可核官网组号。'),
        ('7691579570427792408','7703822281448901656','insufficient','同名不同ID；主演人物不同，文本均谈继亲关系，缺少明确季数和同一产品系列的证据。')]
    # Reconstruct the title-based review queue. Only pairs involving a missing key were read.
    by_title = defaultdict(list)
    catalog_rows = {r['id']: r for rows in panels.values() for r in rows}
    for sid, r in catalog_rows.items():
        title = unicodedata.normalize('NFKC', r['title'])
        cleaned = re.split(r'第[一二三四五六七八九十百0-9]+季|[（(]完结?[版篇]?|[（(]完[）)]|[（(]全集',title)[0]
        stem = ''.join(c for c in cleaned if c.isalnum()).lower()
        if len(stem)>=3:
            by_title[stem].append(sid)
    candidates = {tuple(sorted((i,j))) for ids in by_title.values() for i,j in combinations(ids,2)
                  if any(catalog_rows[s]['group'].startswith('i:') for s in (i,j))}
    assert candidates == {tuple(sorted((a,b))) for a,b,decision,reason in reference_pairs}
    write('plausible_review_pairs.csv',[dict(left_id=a,right_id=b,left_title=catalog[a]['title'],
          right_title=catalog[b]['title'],decision=decision,reason=reason) for a,b,decision,reason in reference_pairs])
    summary, witnesses, members, high_unknown, scenarios, threshold = [], [], [], [], [], []
    for period, days in [('original35',first), ('extended39',dates)]:
        phase = {}
        for board in ('ai','comic','hot','real'):
            for depth in (20,50,100):
                counts, unknown = score(days,panels,board,depth,{})
                if counts:
                    leader, m = sorted(counts.items(), key=lambda p:(-p[1],p[0]))[0]
                else:
                    leader, m = '', 0
                e, u = sum(counts.values()), sum(unknown.values())
                row = dict(period=period, board=board, depth=depth, n_days=len(days),
                           known_slot_share=1-u/(depth*len(days)), unknown_slots=u,
                           known_leader=leader, confirmed_extra=e, largest=m,
                           observed_share=share(m,e), outer_lower=share(m,e+u),
                           outer_upper=share(m+u,e+u))
                summary.append(row)
                phase[board,depth]=row
                for scheme, merges in [('official_plus_strict_title',augmented),
                                       ('plus_two_plausible_pairs',plausible)]:
                    a, _ = score(days,panels,board,depth,merges)
                    scenarios.append(dict(period=period,board=board,depth=depth,scheme=scheme,
                                          eligible_changed_ids=sum(s in merges for s in unknown),
                                          changed_slot_days=sum(n for s,n in unknown.items() if s in merges),
                                          total_extra=sum(a.values()),largest=max(a.values(),default=0),
                                          largest_share=share(max(a.values(),default=0),sum(a.values()))))
                if period=='extended39' and depth==100 and board in ('ai','comic'):
                    all_rows = [r for day in days for r in panels[day,board]]
                    member_days=Counter(r['id'] for r in all_rows if r['group']==leader)
                    for sid,n in sorted(member_days.items(), key=lambda p:(-p[1],p[0])):
                        title, g, url, at, path, digest = verified_page(sid)
                        assert 'g:'+g == leader
                        members.append(dict(board=board,group=leader,id=sid,official_title=title,
                                            observed_days=n,url=url,fetched_utc=at,
                                            source_path_from_outputs=path,html_sha256=digest))
                    for sid,n in sorted(unknown.items(),key=lambda p:(-p[1],p[0]))[:10]:
                        title,g,url,at,path,digest=verified_page(sid)
                        assert not g
                        observed = next(r['title'] for r in all_rows if r['id']==sid)
                        high_unknown.append(dict(board=board,id=sid,chart_title=observed,
                                            observed_days=n,official_title=title,official_group=g,
                                            checked_source=path or 'no_cached_detail',url=url,
                                            candidate_strict_assignment=augmented.get(sid,'')))
        ai, comic = phase['ai',100], phase['comic',100]
        threshold.append(dict(period=period,depth=100,
                              cross_fraction_both=crossover(ai,comic),
                              ai_lower_comic_fixed=ai['outer_lower']-comic['observed_share'],
                              comic_upper_ai_fixed=ai['observed_share']-comic['outer_upper']))
        stress=assignment_stress(days, panels,comic['known_leader'])
        for b in ('ai','comic'):
            counts,unknown=score(days,panels,b,100,stress)
            leader,m=counts.most_common(1)[0]
            witnesses.append(dict(period=period,board=b,depth=100,model='fixed_id_extreme_witness',
                                  changed_missing_ids=sum(s in stress for s in unknown),
                                  original_confirmed_group_leader=phase[b,100]['known_leader'],
                                  resulting_leader=leader,largest=m,total_extra=sum(counts.values()),
                                  largest_share=m/sum(counts.values())))
    entries = []
    for period, days in [('original35',first), ('extended39',dates)]:
        for board in ('ai','comic','hot','real'):
            for depth in (20,50,100):
                for label,mapping in [('confirmed',{}),('two_plausible_pairs',plausible)]:
                    n, known = turnover_sensitivity(days,panels,board,depth,mapping)
                    entries.append(dict(period=period,board=board,k=depth,grouping=label,
                                        title_entries=n,entered_existing_family=known,frac=share(known,n)))
    write('plausible_turnover.csv',entries)
    write('missing_outer_bounds.csv',summary)
    write('thresholds.csv',threshold)
    write('strict_title_sensitivity.csv',scenarios)
    write('feasible_extreme_stress.csv',witnesses)
    write('largest_group_page_checks.csv',members)
    write('influential_unknowns.csv',high_unknown)


if __name__ == '__main__':
    main()
