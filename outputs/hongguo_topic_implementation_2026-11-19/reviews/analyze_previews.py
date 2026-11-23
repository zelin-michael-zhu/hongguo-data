"""Analyze saved public-page previews offline. Never use machine flags as ground truth."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import json
import re
import statistics

from collect_public_previews import BASE, PILOT, read_rows, write_rows
from read_stratified_audit import selected

# Literal clues, deliberately biased toward precision. They cannot resolve context or sarcasm.
CUES = {
    '节奏与重复':r'拖沓|拖拉|注水|拖戏|節奏太慢|节奏太慢|节奏很慢|推进少|节奏紧凑|情节紧凑|套路都差不多|快进|跳着看|很啰嗦|毫不拖泥带水',
    '情感或类型雷点':r'无虐|無虐|没有虐恋|没有误会|没有系统|不虐|沒有誤會|没有明面上的后宫|雷点|避雷|出轨|虐心|全程高甜|没有感情线|全程无刀',
    '结局':r'结局圆满|结局美满|开放式结局|烂尾|爛尾|大团圆|幸福的生活|圆满结局|悲剧结局',
    '画面或声音制作':r'建模|配音|口型|运镜|穿帮|滤镜|字幕|借位|武侠电影的质感',
    '角色或叙事重心':r'群像|工具人|戏份.{0,3}少|剧情推进少|重复套路|套路重复|主次不分|重心转移',
    '改编对照':r'还原原著|原著.{0,5}(?:不一样|不符合|差异|魔改)|偏离原著|魔改|两个剧本|从二人转改成',
    '跨季承接':r'接不上|承接上季|衔接上季|不用看前|独立故事|需要看前|跳过前',
}
PROMO = r'饰演者|扮演者|我饰演|我饰.{0,2}的|作为制作组|制作组来|我们制作组|我们剧组|我和编剧组|我们团队|我在剧中|我是.{0,8}导演'
SOLICIT = r'多多支持|求关注|求五星|五星好评返|来.{0,3}集合'
PRAISE = r'好看|太棒|真棒|好评|精彩|难看|無聊|难看的|喜欢|不好看|太差|真好|很爽'
SELF = r'我(?:也是|看过|看到|喜欢|觉得|追|觉得|家|今年|终于|看了|的)|看完|熬夜|一口气|刷了'
PLOT = r'讲述|剧情[：:]|故事[：:]|结局[是的]|剧情[:：]|最后.{0,8}(?:结婚|在一起|选择|离开)|剧情梳理|梳理一下剧情'
def mask_key(sid, position):
    return hashlib.sha256(f'blind-review-v1|{sid}|{position}'.encode()).hexdigest()[:14]
def fraction(n, d):
    return round(n/d,4) if d else None
def midpoint(items):
    return statistics.median(items) if items else None
def matched(pattern, text):
    return [m.group() for m in re.finditer(pattern,text)]
def normalized(s):
    return re.sub(r'[^\w\u3400-\u9fff]','',s).lower()
def shingles(s):
    s=normalized(s);return {s[i:i+4] for i in range(len(s)-3)}
def make_card(j):
    return {
        '剧名':j['title'],'简介':j['synopsis'],'标签':j['tags'],'集数':j['episode_count'],
        '演职员':j['cast'],'聚合评分':j['display_rating'],'评分人数':j['rating_count'],
    }
def flag_all(j,row):
    txt=row['text']; card=make_card(j); source=str(card); shared=shingles(txt)&shingles(j['synopsis'] or '')
    hits=[(dim,cue) for dim,pattern in CUES.items() for cue in matched(pattern,txt)]
    absent=[(dim,cue) for dim,cue in hits if normalized(cue) not in normalized(source)]
    return {
        'signal_dimensions':'|'.join(dict.fromkeys(x[0] for x in hits)),
        'signal_excerpts':'|'.join(dict.fromkeys(x[1] for x in hits)),
        'signal_literal_not_on_card':int(bool(absent)),
        'plot_word_or_synopsis_overlap':int(bool(matched(PLOT,txt)) or len(shared)>=4),
        'shared_distinct_4grams_with_synopsis':len(shared),
        'broad_appraisal_word':int(bool(matched(PRAISE,txt))),
        'creator_self_claim_word':int(bool(matched(PROMO,txt))),
        'solicitation_word':int(bool(matched(SOLICIT,txt))),
        'viewing_or_personal_statement_word':int(bool(matched(SELF,txt))),
    }
def write_blank_template(path, rows):
    if path.exists():
        saved = read_rows(path)
        answer_columns = ('function_codes', 'cue_verbatim', 'matching_card_clause', 'dimension', 'strict_1_0_unknown', 'memo', 'extra_spoiler_1_0_unknown', 'spoiler_evidence', 'survives_redaction', 'surviving_cue')
        if any(r.get(column) for r in saved for column in answer_columns):
            return
    write_rows(path, rows)

def load_manual():
    with (BASE/'paired_reading.tsv').open() as f:
        return list(csv.DictReader(f,delimiter='\t'))
def run():
    cohort=read_rows(BASE/'frozen_30.csv'); readings=load_manual()
    notes={(int(v['draw']),int(v['pos'])):v for v in readings}
    assert len(notes)==len(readings)==60
    all_codes,blind,title_report,key,paired=[],[],[],[],[]
    dimension_pairs=[]
    texts=[]; global_ratings=[]; totals=[]; cast=[]; yr=[]; positions=[]
    for i,entry in enumerate(cohort,1):
        sid=entry['series_id']; j=json.loads((BASE/'sanitized_captures'/(sid+'.json')).read_text());rows=j['reviews']
        card=make_card(j); note_list=[]; title_codes=[]; arr=selected(sid,rows); expected={r['source_position'] for r in arr}
        assert expected=={p for (d,p) in notes if d==i}
        totals.append(int(j['source_review_total']))
        if j['display_rating'] is not None:
            yr.append(j['display_rating'])
        for row in rows:
            pos=row['source_position']; bid=mask_key(sid,pos); note=notes.get((i,pos)); flags=flag_all(j,row)
            group=entry['stratum'];card_txt=json.dumps(card,ensure_ascii=False)
            blind.append({'blind_id':bid,'same_work_card':card_txt,'review_text':row['text'],'function_codes':'','cue_verbatim':'','matching_card_clause':'','dimension':'','strict_1_0_unknown':'','memo':'','extra_spoiler_1_0_unknown':'','spoiler_evidence':'','survives_redaction':'','surviving_cue':''})
            key.append({'blind_id':bid,'series_id':sid,'source_position':pos,'in_locked_60':int(note is not None)})
            code={'series_id':sid,'title':j['title'],'stratum':group,'source_url':j['url'],'sample_time':j['sample_time'],'source_position':pos,
                  'review_text':row['text'],'review_rating':row['review_rating'],'digg_count':row['digg_count'],'create_time_raw':row['create_time'],**flags,
                  'strict_close_read':note['strict'] if note else '未精读','qualitative_function':note['classification'] if note else '',
                  'close_read_dimension':note['dimension'] if note else '','close_read_excerpt':note['cue'] if note else '',
                  'source_comparison':note['card_comparison'] if note else ''}
            if note:
                assert note['cue'] in row['text'], (i,pos,note['cue'])
                note_list.append(note)
                paired.append({k:code[k] for k in ['series_id','title','stratum','source_url','source_position','review_text','qualitative_function','strict_close_read','close_read_dimension','close_read_excerpt','source_comparison']})
                positions.append(pos)
            all_codes.append(code); title_codes.append(code); texts.append(row['text']); global_ratings.append(row['review_rating'])
        pos_notes=[r for r in note_list if r['strict']=='1']
        if len(pos_notes)==2:
            d1,d2=(r['dimension'] for r in pos_notes)
            dimension_pairs.append({'series_id':sid,'title':j['title'],'source_url':j['url'],
                'pos_1':pos_notes[0]['pos'],'dim_1':d1,'pos_2':pos_notes[1]['pos'],'dim_2':d2,
                'pair_comparison':'same_dimension' if d1==d2 else 'distinct_dimensions'})
        title_report.append({'draw':i,'series_id':sid,'title':j['title'],'stratum':entry['stratum'],'source_url':j['url'],'sample_time':j['sample_time'],
            'episode_count':j['episode_count'],'card_rating':j['display_rating'],'rating_count':j['rating_count'],'source_review_total':j['source_review_total'],
            'preview_rows':len(rows),'preview_max_ratings':sum(r['review_rating']==10 for r in rows),'rule_candidate_rows':sum(r['signal_literal_not_on_card'] for r in title_codes),
            'close_read_n':len(note_list),'close_read_yes':sum(r['strict']=='1' for r in note_list),'close_read_no':sum(r['strict']=='0' for r in note_list),
            'close_read_uncertain':sum(r['strict']=='?' for r in note_list),'sampled_positions':'|'.join(map(str,sorted(expected)))})
    write_rows(BASE/'all_270_rule_screen.csv',all_codes);write_rows(BASE/'paired_60_close_read.csv',paired)
    write_rows(BASE/'double_positive_pairs.csv',dimension_pairs)
    write_rows(BASE/'title_summary.csv',title_report);write_blank_template(BASE/'blind_270.csv',sorted(blind,key=lambda r:r['blind_id']))
    write_rows(BASE/'blind_key.csv',key)
    b60={r['blind_id'] for r in key if r['in_locked_60']};write_blank_template(BASE/'blind_60.csv',sorted([r for r in blind if r['blind_id'] in b60],key=lambda r:r['blind_id']))
    preliminary=read_rows(PILOT/'comments_preview.csv');old=[r for r in preliminary if r['scope']=='series_review'];calib=[]
    for v in json.loads((PILOT/'selected_series.json').read_text()):
        sid=v['id']; j=json.loads((BASE/'calibration_today'/(sid+'.json')).read_text())
        old_meta=next(s['metadata'] for s in json.loads((PILOT/'openhongguo_raw.json').read_text())['series'] if str(s['metadata']['id'])==sid)
        oldrows=[r for r in old if r['series_id']==sid];f=PILOT/'web_previews'/(sid+'_detail.json')
        oldrate=next((el['seriesSocialInfo'].get('rating') for el in json.loads(f.read_text())['social_data'] if 'seriesSocialInfo' in el),None) if f.exists() else None
        prevtxt=[r['content'] for r in oldrows];newtxt=[r['text'] for r in j['reviews']]
        calib.append({'series_id':sid,'title':j['title'],'source_url':j['url'],'public_rating_prior_if_saved':oldrate,'public_rating_2026_11_19':j['display_rating'],
            'old_synopsis_nonempty':int(bool(old_meta['description'])),'new_synopsis_nonempty':int(bool(j['synopsis'])),'old_preview_n':len(oldrows),
            'old_max_individual_rating_n':sum(float(r['rating'])==10 for r in oldrows if r['rating']),'today_preview_n':len(newtxt),
            'matched_verbatim_reviews_between_days':len(set(prevtxt)&set(newtxt)),'old_capture_time':oldrows[0]['collected_at'],'new_capture_time':j['sample_time']})
    write_rows(BASE/'calibration_5.csv',calib)
    adjudicated=[r for r in all_codes if r['strict_close_read']!='未精读']
    pergroup={g:dict(Counter(r['strict_close_read'] for r in adjudicated if r['stratum']==g)) for g in {r['stratum'] for r in adjudicated}}
    noM=[r for r in adjudicated if 'M' not in r['qualitative_function'].split(',')]
    report={
        'snapshot_n':len(title_report),'capture_range':[min(r['sample_time'] for r in title_report),max(r['sample_time'] for r in title_report)],
        'scope':'One public detail-page capture per title; not a census of authors, impressions, unique people, or reviews.',
        'frame_n':{r['stratum']:int(r['stratum_size']) for r in cohort},'total_rows':len(texts),'unique_texts':len(set(texts)),
        'title_metadata_nonempty':{k:sum(bool(json.loads((BASE/'sanitized_captures'/(r['series_id']+'.json')).read_text())[k]) for r in cohort) for k in ['title','synopsis','tags','episode_count','cast','display_rating','rating_count']},
        'source_total_review_count_range':[min(totals),midpoint(totals),max(totals)],'display_rating_range':[min(yr),midpoint(yr),max(yr)],
        'preview_rating_counts':dict(Counter(global_ratings)),'all_rule_positive':sum(r['signal_literal_not_on_card'] for r in all_codes),
        'preview_fraction_within_title_min_med_max':[min(9/n for n in totals),midpoint([9/n for n in totals]),max(9/n for n in totals)],
        'close_read_counts':dict(Counter(r['strict_close_read'] for r in adjudicated)),'close_read_strata':pergroup,'close_read_positions':dict(Counter(positions)),
        'close_read_titles_with_positive':sum(r['close_read_yes']>0 for r in title_report),
        'close_read_no_promo':dict(Counter(r['strict_close_read'] for r in noM)),
        'close_read_pure_reader_source':dict(Counter(r['strict_close_read'] for r in adjudicated if 'M' not in r['qualitative_function'].split(',') and 'S' not in r['qualitative_function'].split(','))),
        'rule_vs_close_read':dict(Counter(f"{r['signal_literal_not_on_card']}/{r['strict_close_read']}" for r in adjudicated)),
        'class_counts_nonexclusive':dict(Counter(f for r in adjudicated for f in r['qualitative_function'].split(','))),
        'onetime_rule_flags':{col:sum(r[col] for r in all_codes) for col in ['creator_self_claim_word','solicitation_word','plot_word_or_synopsis_overlap','broad_appraisal_word','viewing_or_personal_statement_word']},
        'rechecked_calibration_prior_max':sum(r['old_max_individual_rating_n'] for r in calib),'rechecked_calibration_same_comments_between_days':sum(r['matched_verbatim_reviews_between_days'] for r in calib)}
    with (BASE/'spoiler_reading.tsv').open() as handle:
        spoiler_by_key = {(int(r['draw']),int(r['pos'])):r for r in csv.DictReader(handle,delimiter='\t')}
    assert spoiler_by_key.keys()==notes.keys()
    spoiler_rows = []
    for (draw,pos), original in notes.items():
        sid = cohort[draw-1]['series_id']
        code = next(r for r in adjudicated if r['series_id']==sid and r['source_position']==pos)
        spec = spoiler_by_key[draw,pos]
        assert spec['evidence'] in code['review_text'] and spec['surviving_cue'] in code['review_text'], (draw,pos)
        assert (spec['survives_redaction']=='NA')==(original['strict']!='1')
        spoiler_rows.append({'series_id':sid,'title':code['title'],'source_url':code['source_url'],'position':pos,
            'strict_new_information':original['strict'],'extra_spoiler':spec['spoiler'],'spoiler_evidence':spec['evidence'],
            'justification':spec['rationale'],'new_info_survives_redaction':spec['survives_redaction'],'retained_excerpt':spec['surviving_cue']})
    write_rows(BASE/'spoiler_60.csv',spoiler_rows)
    report['spoiler_all60'] = dict(Counter(r['extra_spoiler'] for r in spoiler_rows))
    report['spoiler_in_26'] = dict(Counter(r['extra_spoiler'] for r in spoiler_rows if r['strict_new_information']=='1'))
    report['confirmed_new_after_redacting_reveals'] = dict(Counter(r['new_info_survives_redaction'] for r in spoiler_rows if r['strict_new_information']=='1'))
    report['title_counts_spoiler_sensitivity']={name:len(set(r['series_id'] for r in spoiler_rows if r['strict_new_information']=='1' and r[field]==value)) for name,field,value in [('fully_clean','extra_spoiler','0'),('survives_deletion','new_info_survives_redaction','1')]}
    (BASE/'findings.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
