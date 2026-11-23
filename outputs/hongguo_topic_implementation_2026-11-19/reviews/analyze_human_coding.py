"""Validate independent, completed coding sheets and summarize fixed-position coverage."""
import argparse
import csv
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path
import re
from tempfile import TemporaryDirectory

BASE = Path(__file__).resolve().parent
LABELS = ('0', '1', '?')
ALL_DIMS = frozenset(f'D{i}' for i in range(1, 9))
MAIN = 'strict_1_0_unknown'
SPOILER = 'extra_spoiler_1_0_unknown'
IMMUTABLE = ('review_text', 'same_work_card')
REQUIRED = {*IMMUTABLE, MAIN, SPOILER, 'function_codes', 'cue_verbatim', 'matching_card_clause',
            'dimension', 'memo', 'spoiler_evidence', 'survives_redaction', 'surviving_cue'}
POSITIONS = (1, 3, 6, 9)
CONDITIONS = ('full_review', 'hide_whole_review', 'mask_revealing_clauses')

def read_index(path, required):
    with path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        if len(cols)!=len(set(cols)) or not required.union({'blind_id'}).issubset(cols):
            raise ValueError(f'{path.name} 缺少所需表头或有重名表头')
        index = {}
        for row in reader:
            key = row['blind_id'].strip()
            if not key or key in index or None in row or any(v is None for v in row.values()):
                raise ValueError(f'{path.name} 含空ID、重复ID或未正确分列的记录')
            index[key] = row
        if not index:
            raise ValueError(f'{path.name} 没有数据行')
        return index

def require_same_ids(name, records, reference):
    missing = reference.keys()-records.keys()
    extra = records.keys()-reference.keys()
    if missing or extra:
        raise ValueError(f'{name} 的ID不匹配，缺 {len(missing)} 个，多 {len(extra)} 个')

def lines(value):
    return [line.strip() for line in value.splitlines() if line.strip()]

def collapse(value):
    return ''.join(value.split())

def dim_line(line):
    match = re.fullmatch(r'(D[1-8])(?![A-Za-z0-9])\s*[:：,，、+＋|｜-]?\s*(.*)', line)
    if not match or re.search(r'D[1-8](?![A-Za-z0-9])', match[2]):
        raise ValueError('每行应有一个D1至D8编号')
    return match[1], match[2].strip()

def validate_row(row, original):
    if any(row[col] != original[col] for col in IMMUTABLE):
        raise ValueError('盲表中的作品卡或评论正文与冻结模板不同')
    main, spoiler, survive = (row[k].strip() for k in (MAIN, SPOILER, 'survives_redaction'))
    if main not in LABELS or spoiler not in LABELS:
        raise ValueError('新增与剧透的必填判定应为0、1或?')
    funcs = {i.strip() for i in re.split('[,，|、 ]+',row['function_codes'].strip()) if i.strip()}
    if not funcs or not funcs.issubset(set('NGTMSO')):
        raise ValueError('文本功能须从N、G、T、M、S、O中选择')
    body = collapse(row['review_text'])
    dims = [dim_line(s)[0] for s in lines(row['dimension'])]
    cues, cards = lines(row['cue_verbatim']), lines(row['matching_card_clause'])
    revealed, retained = lines(row['spoiler_evidence']), [dim_line(s) for s in lines(row['surviving_cue'])]
    if main == '1' and not dims:
        raise ValueError('确定新增须提供至少一个维度')
    if main == '0' and dims:
        raise ValueError('未新增不应填写新增维度，可在memo说明已出现的维度')
    if dims and not (len(cues)==len(cards)==len(dims)):
        raise ValueError('新增或候选维度与原句、卡片对照须逐行对应')
    if any(collapse(piece) not in body for piece in cues+revealed):
        raise ValueError('证据原句未能在该条评论中找到')
    if spoiler == '1' and not revealed:
        raise ValueError('明确新增剧透须记录原句')
    if spoiler == '0' and revealed:
        raise ValueError('无新增剧透的原句栏应为空，解释可填memo')
    if spoiler == '?' and not (revealed or row['memo'].strip()):
        raise ValueError('不确定的剧透请填原句或memo')
    if main == '?' and not (dims or row['memo'].strip()):
        raise ValueError('不确定的新增请填候选维度或memo')
    if survive not in (LABELS if main=='1' else ('NA',)):
        raise ValueError('局部遮挡判断不符合主标签的跳题条件')
    kept = {d for d, piece in retained}
    if (survive=='1') != bool(retained) or not kept.issubset(dims):
        raise ValueError('遮挡后保留原句须与遮挡判定及原有维度对应')
    if any(not piece or collapse(piece) not in body for _,piece in retained):
        raise ValueError('保留片段必须是含实质内容的评论原句')
    if any(collapse(quote) in collapse(piece) or collapse(piece) in collapse(quote)
           for _, piece in retained for quote in revealed):
        raise ValueError('保留片段与拟遮挡的原句包含彼此，请核查划线范围')
    if main=='1' and spoiler=='0' and (survive!='1' or set(dims)!=kept):
        raise ValueError('无剧透可遮时应保留所有确定新增维度')
    return {'main':main,'spoiler':spoiler,'survives':survive,'dimensions':frozenset(dims),'retained':frozenset(kept)}

def load_codes(path, template):
    rows = read_index(path,REQUIRED)
    require_same_ids(path.name, rows, template)
    if all(not r[MAIN].strip() and not r[SPOILER].strip() for r in rows.values()):
        raise ValueError(f'{path.name} 尚未编码。没有生成一致性或覆盖率结果')
    codes = {}
    for key,r in rows.items():
        try:
            codes[key] = validate_row(r,template[key])
        except ValueError as exc:
            raise ValueError(f'{path.name} · {key} · {exc}') from exc
    return codes

def read_positions(path, template):
    key = read_index(path,{'series_id','source_position'})
    require_same_ids(path.name, key, template)
    titles = defaultdict(dict)
    for blind_id, row in key.items():
        sid, pos = row['series_id'].strip(), int(row['source_position'])
        if not sid or pos in titles[sid]:
            raise ValueError('位置表的作品ID为空或同剧位置重复')
        titles[sid][pos] = blind_id
    for sid, lookup in titles.items():
        if set(lookup)!=set(range(1,10)):
            raise ValueError(f'作品 {sid} 未完整覆盖固定位置1至9，无法估计全曲线')
    return titles

def agreement_from_counts(counts):
    n = sum(counts.values())
    observed = sum(counts[t,t] for t in LABELS)/n
    left = {v:sum(counts[v,j] for j in LABELS) for v in LABELS}
    right = {v:sum(counts[j,v] for j in LABELS) for v in LABELS}
    expected_numerator = sum(left[t]*right[t] for t in LABELS)
    denominator = n*n-expected_numerator
    return {'n':n,'labels':list(LABELS),'agreement':observed,
            'cohen_kappa':(sum(counts[t,t] for t in LABELS)*n-expected_numerator)/denominator if denominator else None,
            'unresolved_A':left['?'],'unresolved_B':right['?'],
            'confusion_rows_A_columns_B':[[counts[i,j] for j in LABELS] for i in LABELS]}

def agreement(a,b,field):
    return agreement_from_counts(Counter((val[field],b[key][field]) for key,val in a.items()))

def coverage_sets(r, condition):
    main, spoiler, survives = r['main'], r['spoiler'], r['survives']
    low = r['dimensions'] if main=='1' else frozenset()
    high = (r['dimensions'] or ALL_DIMS) if main=='?' else low
    if condition=='full_review':
        return low,high
    if condition=='hide_whole_review':
        return (low if spoiler=='0' else frozenset(), high if spoiler!='1' else frozenset())
    if main!='1':
        return frozenset(), high
    if survives=='?':
        return frozenset(), high
    return r['retained'],r['retained']

def bootstrap_title_draws(titles, strata_path, replicates=2000):
    if strata_path:
        with strata_path.open(encoding='utf-8-sig',newline='') as f:
            strata = list(csv.DictReader(f))
        if not strata or not {'series_id','stratum'}.issubset(strata[0]):
            raise ValueError('分层表缺少series_id或stratum')
        lookup = {r['series_id']:r['stratum'] for r in strata}
        if len(lookup)!=len(strata) or set(lookup)!=set(titles) or not all(lookup.values()):
            raise ValueError('分层表须为每个入样剧ID提供唯一的非空分层')
    else:
        lookup = dict.fromkeys(titles,'all_titles')
    groups = defaultdict(list)
    for index,sid in enumerate(sorted(titles)):
        groups[lookup[sid]].append(index)
    rng = random.Random(20261119)
    draws = [[i for group in sorted(groups) for i in rng.choices(groups[group],k=len(groups[group]))]
             for _ in range(replicates)]
    return draws, {label:len(ids) for label,ids in sorted(groups.items())}

def percentile(values, p):
    location=(len(values)-1)*p
    left=int(location)
    right=min(left+1,len(values)-1)
    return values[left]+(values[right]-values[left])*(location-left)

def dimension_state(sets, dim):
    certain, possible=sets
    if dim in certain:
        return '1'
    return '?' if dim in possible else '0'

def dimension_agreement(a,b,titles,draws):
    results=[]
    for condition in CONDITIONS:
        pairs={i:(coverage_sets(a[i],condition),coverage_sets(b[i],condition)) for i in a}
        for dim in sorted(ALL_DIMS):
            counts=Counter()
            both_one=[]; one_sided_determinate=[]
            supporting_titles=0
            for sid in sorted(titles):
                cluster=Counter((dimension_state(pairs[i][0],dim),dimension_state(pairs[i][1],dim))
                                for i in titles[sid].values())
                counts.update(cluster)
                both_one.append(cluster['1','1'])
                one_sided_determinate.append(cluster['0','1']+cluster['1','0'])
                supporting_titles+=any(n>0 and '1' in pair for pair,n in cluster.items())
            numerator=2*counts['1','1']
            denominator=numerator+counts['1','0']+counts['0','1']
            denominator_including_unknown=denominator+counts['1','?']+counts['?','1']
            sampled_rates=[]
            if denominator:
                for draw in draws:
                    weighted_yes=2*sum(both_one[i] for i in draw)
                    weighted_total=weighted_yes+sum(one_sided_determinate[i] for i in draw)
                    if weighted_total:
                        sampled_rates.append(weighted_yes/weighted_total)
            sampled_rates.sort()
            stats=agreement_from_counts(counts)
            row={'condition':condition,'dimension':dim,'n_reviews':stats['n'],'n_titles':len(titles),
                 'titles_with_either_coder_positive':supporting_titles,
                 'n_determinate_pairs':sum(counts[x,y] for x in ('1','0') for y in ('1','0')),
                 'agreement_three_categories':stats['agreement'],'kappa_three_categories':stats['cohen_kappa'],
                 'positive_agreement_determinate':numerator/denominator if denominator else None,
                 'positive_agreement_unknown_as_nonpositive':numerator/denominator_including_unknown if denominator_including_unknown else None,
                 'bootstrap_total':len(draws),'bootstrap_defined':len(sampled_rates),
                 'positive_agreement_cluster_p025':percentile(sampled_rates,.025) if sampled_rates else None,
                 'positive_agreement_cluster_p975':percentile(sampled_rates,.975) if sampled_rates else None}
            for x in LABELS:
                for y in LABELS:
                    row[f'n_A{x}_B{y}']=counts[x,y]
            results.append(row)
    return results

def coverage(coders, titles):
    detailed, summary = [],[]
    for coder, records in coders.items():
        for condition in CONDITIONS:
            grouped = defaultdict(list)
            for sid in sorted(titles):
                low, high = set(), set()
                for pos in range(1,10):
                    r = records[titles[sid][pos]]
                    sure, maybe = coverage_sets(r,condition)
                    low.update(sure); high.update(maybe)
                    if pos in POSITIONS:
                        grouped[pos].append((len(low),len(high)))
                        detailed.append({'coding_source':coder,'condition':condition,'k':pos,'series_id':sid,
                           'certain_dimensions':'|'.join(sorted(low)),'possible_dimensions':'|'.join(sorted(high)),
                           'n_certain_dimensions':len(low),'n_possible_dimensions':len(high)})
            for pos, pairs in grouped.items():
                n=len(pairs)
                summary.append({'coding_source':coder,'condition':condition,'k':pos,'n_titles':n,
                    'mean_certain_dimensions':sum(v[0] for v in pairs)/n,'mean_possible_dimensions':sum(v[1] for v in pairs)/n,
                    'share_titles_with_certain_dimension':sum(v[0]>0 for v in pairs)/n,'share_titles_with_possible_dimension':sum(v[1]>0 for v in pairs)/n})
    return detailed, summary

def save_csv(path, records, fields=None):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields or records[0].keys())
        writer.writeheader();writer.writerows(records)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coder-a',type=Path,required=True);p.add_argument('--coder-b',type=Path,required=True)
    p.add_argument('--adjudicated',type=Path,help='可选的全样本裁定版，格式与盲表相同')
    p.add_argument('--template',type=Path,default=BASE/'blind_270.csv');p.add_argument('--key',type=Path,default=BASE/'blind_key.csv')
    p.add_argument('--strata',type=Path,help='可选，样本框的series_id与stratum；默认位置表自动使用本次冻结分层')
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    try:
        template=read_index(args.template,set(IMMUTABLE))
        titles=read_positions(args.key,template)
        a=load_codes(args.coder_a,template)
        if args.coder_a.samefile(args.coder_b):
            raise ValueError('需两位编码员各自提交的独立文件')
        b=load_codes(args.coder_b,template)
        coders={'coder_A':a,'coder_B':b}
        if args.adjudicated:
            coders['adjudicated']=load_codes(args.adjudicated,template)
        report={'coding_sources':list(coders),'curves_presented_separately':True,'number_of_titles':len(titles),
                'strict_new_information':agreement(a,b,'main'),'extra_spoiler':agreement(a,b,'spoiler'),
                'unknown_handling':'?作为一致性第三类别。曲线下界只计确认维度，未知如有限候选取其并集，无候选按D1至D8作宽上界。区间是编码不确定性界限。',
                'kappa_null':'若两人都只采用同一个类别，偶然一致率为1，kappa不可定义。'}
        strata_path=args.strata
        if not strata_path and args.key.resolve()==(BASE/'blind_key.csv').resolve():
            strata_path=BASE/'frozen_30.csv'
        draws,stratum_sizes=bootstrap_title_draws(titles,strata_path)
        dimension_results=dimension_agreement(a,b,titles,draws)
        report['dimension_agreement_bootstrap']={
            'unit':'complete title','replicates':len(draws),'seed':20261119,'stratum_sizes':stratum_sizes,
            'stratified':bool(strata_path),'interval':'2.5th/97.5th percentiles conditional on a defined positive-agreement denominator'}
        detailed,summary=coverage(coders,titles)
        disagreements=[{'blind_id':i,'different_fields':'|'.join(key for key in a[i] if a[i][key]!=b[i][key])} for i in sorted(a) if a[i]!=b[i]]
        out=args.out.resolve()
        out.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=out) as temp:
            dest=Path(temp)
            (dest/'agreement.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
            save_csv(dest/'dimension_agreement.csv',dimension_results)
            save_csv(dest/'coverage_per_title.csv',detailed)
            save_csv(dest/'coverage_equal_title_means.csv',summary)
            save_csv(dest/'rows_to_adjudicate.csv',disagreements,['blind_id','different_fields'])
            for f in dest.iterdir():
                os.replace(f,out/f.name)
    except (ValueError,OSError,csv.Error) as exc:
        p.exit(2,f'{exc}\n')
    print(f'已核验{len(a)}条、{len(titles)}部。结果写入{out}')
if __name__=='__main__':
    main()
