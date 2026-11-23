"""Audit grouping on a fixed probability-style sample and a separate blinded case subset."""
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from title_keys import HERE, DATA, read, write


def digest(*parts):
    return hashlib.sha256('|'.join(parts).encode()).hexdigest()


def find_form(title):
    norm=unicodedata.normalize('NFKC',title)
    norm=re.sub(r'(?:第\s*)?[0-9零〇一二两三四五六七八九十百]+\s*(?:季|部)\s*[!！?。]?$','',norm)
    norm=re.sub(r'[0-9]+$','',norm)
    return ''.join(c for c in norm.lower() if c.isalnum())


def main():
    board=read(DATA/'board_daily.csv')
    official={r['series_id']:r for r in read(HERE.parents[1]/'hongguo_expansion_2026-11-21/identity/identity_coverage.csv')}
    catalog={r['id']:r for r in read(DATA/'catalog.csv')}
    keys=read(HERE/'asof_groups.csv')
    first={r['id']:r for r in keys if r['date']==r['first_list_date']}
    ids=sorted(first)
    by_board=defaultdict(set)
    for r in board:
        by_board[r['board']].add(r['id'])
    samples={b:sorted(ss,key=lambda s:digest('watchlist-identity-20261121',b,s))[:50] for b,ss in by_board.items()}
    by_group=defaultdict(set)
    by_title=defaultdict(set)
    gid={}
    for s in ids:
        gid[s]=official[s]['series_group_id'] or official[s]['old_sdk_album_id']
        if gid[s]:by_group[gid[s]].add(s)
        by_title[first[s]['group']].add(s)
    lookup={s:find_form(first[s]['title_asof']) for s in ids}
    sample_rows=[]
    audit_rows=[]
    paired=set()
    for b,seeds in sorted(samples.items()):
        counts=Counter()
        seen=set()
        for s in seeds:
            scores=[]
            for other in ids:
                if s==other:continue
                pair=tuple(sorted((s,other)))
                if pair not in seen:
                    seen.add(pair)
                    if gid[s] and gid[other]:
                        truth=gid[s]==gid[other]
                        guess=first[s]['group']==first[other]['group']
                        counts['pairs_verified_both']+=1
                        counts['reference_link']+=truth
                        counts['rule_link_when_both_verified']+=guess
                        counts['links_shared']+=(guess and truth)
                    elif first[s]['group']==first[other]['group']:
                        counts['rule_link_missing_reference']+=1
                a,c=lookup[s],lookup[other]
                if a==c and a:value=1.0
                elif min(len(a),len(c))<3 or not any(a[i:i+2] in c for i in range(len(a)-1)):value=0
                else:value=SequenceMatcher(None,a,c,autojunk=False).ratio()
                if value>0:scores.append((value,other))
            best=sorted(scores,key=lambda x:(-x[0],digest(s,x[1])))[0] if scores else (0,'')
            score,other=best
            paired.add(tuple(sorted((s,other))))
            sample_rows.append(dict(board=b,id=s,title_on_first_list_day=first[s]['title_asof'],first_list_day=first[s]['date'],
                                    verified_group=gid[s],website_status=official[s]['web_status'],
                                    later_catalog_synopsis=catalog[s]['synopsis'],asof_key=first[s]['group'],
                                    other_in_same_verified_group=len(by_group[gid[s]])-1 if gid[s] else '',
                                    other_with_same_rule_key=len(by_title[first[s]['group']])-1,
                                    nearest_candidate_id=other,nearest_candidate_title=first[other]['title_asof'] if other else '',
                                    candidate_title_similarity=round(score,4)))
        nums=[r for r in sample_rows if r['board']==b]
        audit_rows.append(dict(board=b,board_unique_ids=len(by_board[b]),sampled=len(nums),matched_official=sum(bool(r['verified_group']) for r in nums),
                               source_404=sum(r['website_status']=='failed' for r in nums),
                               known_other_season=sum(bool(r['other_in_same_verified_group']) for r in nums),
                               series_pairs_known=counts['reference_link'],rule_pairs_with_both_ids=counts['rule_link_when_both_verified'],
                               agree_links=counts['links_shared'],pairs_with_two_known_groups=counts['pairs_verified_both'],
                               unresolved_rule_pairs=counts['rule_link_missing_reference']))
    write(HERE/'sample_50_per_board.csv',sample_rows)
    write(HERE/'audit_by_board.csv',audit_rows)
    # Select blinded checks without looking at the official IDs; lexical agreement, near pairs, weaker pairs.
    case_rows=[]
    labels=[]
    used=set()
    for b in sorted(samples):
        for low,hi,label in [(1,1.0001,'同名词干'),(.65,1,'近似'),(0,.65,'弱近似')]:
            sub=[r for r in sample_rows if r['board']==b and low<=r['candidate_title_similarity']<hi
                 and r['nearest_candidate_id'] and
                 tuple(sorted((r['id'],r['nearest_candidate_id']))) not in used]
            for r in sorted(sub,key=lambda r:digest('20261121-Blind',r['id']))[:2]:
                s,other=r['id'],r['nearest_candidate_id']
                p=tuple(sorted((s,other)))
                if p in used:continue
                used.add(p)
                ref=f"Q{len(case_rows)+1:02d}"
                case_rows.append(dict(case=ref,title_a=first[s]['title_asof'],title_b=first[other]['title_asof'],
                                      synopsis_a=catalog[s]['synopsis'][:260],synopsis_b=catalog[other]['synopsis'][:260]))
                labels.append(dict(case=ref,board=b,similarity_stratum=label,id_a=s,id_b=other,
                                   rule_merged=int(first[s]['group']==first[other]['group']),
                                   later_group_a=gid[s],later_group_b=gid[other],
                                   same_official=int(gid[s]==gid[other]) if gid[s] and gid[other] else ''))
    write(HERE/'blind_title_cases.csv',case_rows)
    write(HERE/'blind_case_reference.csv',labels)
    # Exhaust all pairs supported on both sides by later official group IDs. No negative label for unknown IDs.
    allct=Counter()
    matched_families=defaultdict(set)
    for a,b in combinations(ids,2):
        pred=first[a]['group']==first[b]['group']
        if pred:allct['all_rule_pairs']+=1
        if not (gid[a] and gid[b]):
            allct['unverified_rule_pairs']+=pred
            continue
        truth=gid[a]==gid[b]
        allct['both_known_pairs']+=1
        allct['both_known_true_pairs']+=truth
        allct['both_known_rule_pairs']+=pred
        allct['both_known_rule_agreements']+=truth and pred
        if pred and truth:matched_families[gid[a]].update([a,b])
    # Drift at title and normalized score level.
    summary=dict(archive_commit='9963122332b7bc93b508547fb6802f663afe6d43',actual_on_chart_ids=len(ids),
                 anchors_unique=len({r['id'] for r in sample_rows}),n_blind_pairs=len(case_rows),
                 current_key_differs_frozen_ids=len({r['id'] for r in keys if r['group_from_today_title']!=r['group']}),
                 retrospective_known_ids=sum(bool(gid[s]) for s in ids),
                 snapshot_mismatch_days_ids=sum(int(r['title_disagrees_catalog']) for r in keys),
                 asof_key_basis='frozen explicit season suffix in title on first archived day listed',
                 same_franchise_matched=len(matched_families),full_reference=allct)
    (HERE/'identity_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
