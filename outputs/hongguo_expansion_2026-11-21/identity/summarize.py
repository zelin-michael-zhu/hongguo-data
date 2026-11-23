"""Tabulate observed public fields, keeping archived source types separate."""
from collections import Counter, defaultdict
import csv
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent
HIST = OUT / 'hongguo_free_pilot_2026-11-18'


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def save(path, fields, data):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(data)


def string(value):
    if value is None or value == '' or value == 0:
        return ''
    return str(value)


def visible_id_list(detail):
    return [string(x) for x in detail.get('vid_list', [])]


def num(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def main():
    oldseason = read(OUT/'hongguo_topic_implementation_2026-11-19/identity/public_season_metadata.json')['details']
    oldip = read(OUT/'hongguo_nine_topic_screen_2026-11-20/ip/four_title_metadata.json')['titles']
    oldfive = read(HIST/'openhongguo_raw.json')['series']
    legacy = {}
    for record in [*oldseason.values(),*oldip,*[s['metadata'] for s in oldfive]]:
        fields = ('season_index','related_album_id','related_novel_book_id','content_type','is_multi_season')
        legacy.setdefault(str(record['id']),{}).update({k:record[k] for k in fields if record.get(k) is not None})
    catalog = rows(HIST/'history/catalog.csv')
    episodes = defaultdict(dict)
    for r in rows(HIST/'episodes.csv'):
        episodes[r['series_id']][int(r['episode_number'])] = r['episode_id']
    trial = set(read(HERE/'sample_ids.json'))
    stats = Counter()
    details = Counter()
    socials = Counter()
    errors = Counter()
    book_keys = Counter()
    season_fields = Counter()
    groups = Counter()
    vid_lengths = Counter()
    rev_lengths = Counter()
    checked = {}
    within_book = set()
    stated_titles = set()
    inventory = []
    unique_vids = set()
    for cat in catalog:
        sid = cat['id']
        path = HERE/'pages'/f'{sid}.json'
        err = HERE/'errors'/f'{sid}.json'
        prev = legacy.get(sid,{})
        book = string(prev.get('related_novel_book_id'))
        if book:
            within_book.add(book)
        row = dict(series_id=sid, catalog_title=cat['title'], catalog_boards=cat['boards_seen'],
                   old_sdk_album_id=prev.get('related_album_id'), old_sdk_book_id=book,
                   old_sdk_season_index=prev.get('season_index'), old_sdk_content_type=prev.get('content_type'),
                   old_sdk_is_multi_season=prev.get('is_multi_season'),
                   catalog_book_from_intro=cat['adapt_work'], catalog_book_author_from_intro=cat['adapt_author'])
        for key in ('old_sdk_book_id','old_sdk_album_id','old_sdk_season_index','catalog_book_from_intro'):
            if row[key] not in ('',None): stats[key]+=1
        if not path.exists():
            if err.exists():
                error = read(err)['attempts'][-1]
                row.update(web_status='failed',web_failure=error['error'])
                errors[str(error['status']) if error['status'] else error['error']] += 1
            else:
                row.update(web_status='not_attempted')
            inventory.append(row)
            continue
        doc = read(path)
        d,s = doc['detail'],doc['social']
        details.update(doc['returned_detail_keys'])
        socials.update(doc['returned_social_keys'])
        stats['retrieved'] += 1
        if sid in trial:stats['trial_success']+=1
        vids = visible_id_list(d)
        local_vids = [v for v in vids if v]
        unique_vids.update(local_vids)
        length = num(d.get('episode_cnt'))
        duplicate_count = len(local_vids)-len(set(local_vids))
        list_complete = length is not None and length > 0 and len(vids) == length and len(set(local_vids)) == length
        group = string((d.get('season_info') or {}).get('series_group_id'))
        season_fields.update((d.get('season_info') or {}).keys())
        review_block = s.get('reviews') or {}
        previews = review_block.get('reviews',[])
        total_reviews = num(review_block.get('total_count'))
        rcount = len(previews)
        reviews_with_text = sum(bool(r.get('content')) for r in previews)
        vid_lengths[len(local_vids)]+=1
        rev_lengths[rcount]+=1
        if sid in episodes:
            old = episodes[sid]
            aligned = sum(old.get(i)==v for i,v in enumerate(vids,1) if v)
            checked[sid] = {'old_count':len(old),'today_count':len(vids),'matching_number_and_id':aligned,'id_intersection':len(set(old.values())&set(local_vids))}
        if group:groups[group]+=1
        if group and string(prev.get('related_album_id')):
            stats['compare_group']+=1
            stats['same_group'] += (group==str(prev['related_album_id']))
        if d.get('record_number'):stats['record_number_present']+=1
        if d.get('first_visible_time'):stats['first_visible_time_present']+=1
        credit = re.search(r'改编自[^《。！？；]{0,30}《([^》\n]{1,120})》',d.get('series_intro') or '')
        if credit:
            stats['web_intro_explicit_adaptation_title']+=1
            stated_titles.add(credit.group(1))
            row['web_intro_explicit_adaptation_title']=credit.group(1)
            row['web_intro_credit_phrase']=credit.group(0)
        for k in ('related_novel_book_id','book_id','novel_info','novel','book_info','book_name','novel_name','novel_author'):
            if d.get(k):book_keys[k]+=1
        if list_complete:stats['complete_unique_episode_id_list']+=1
        if duplicate_count:stats['series_with_duplicate_ids']+=1
        if not local_vids:stats['series_without_episode_ids']+=1
        if len(local_vids)<len(vids):stats['series_with_empty_ids']+=1
        if s.get('reviews') is not None:stats['with_public_review_block']+=1
        if rcount:stats['with_review_previews']+=1
        if total_reviews is not None:
            stats['with_reported_review_total']+=1
            stats['total_reported_reviews_sum']+=total_reviews
            if reviews_with_text==total_reviews:
                stats['preview_text_count_equals_reported_total']+=1
                if total_reviews>0:stats['positive_preview_text_count_equals_reported_total']+=1
            if total_reviews>rcount:stats['reported_reviews_exceed_preview']+=1
        stats['preview_records']+=rcount
        stats['nonempty_preview_texts']+=reviews_with_text
        stats['episode_positions']+=len(vids)
        stats['episode_id_fields_nonempty']+=len(local_vids)
        if length is not None:stats['reported_episode_count_sum']+=length
        row.update(web_status='ok',web_at_utc=doc['fetched_at_utc'],web_url=doc['url'],
                   series_group_id=group,record_number=d.get('record_number'),first_visible_time=d.get('first_visible_time'),
                   episode_cnt=length,accessible_episode_cnt=d.get('accessible_episode_cnt'),vid_list_len=len(vids),
                   distinct_nonempty_vids=len(set(local_vids)),vid_list_complete=int(list_complete),
                   review_count_reported=total_reviews,review_previews=rcount,review_previews_with_text=reviews_with_text,
                   favorite_display=s.get('series_favorite_count'),like_display=s.get('series_like_count'),
                   rating=s.get('rating'),rating_count=s.get('rating_count'),heat=(s.get('hot_score_data') or {}).get('score'),
                   series_status=(d.get('series_episode_info') or {}).get('series_status'),
                   published_tags='|'.join(str(t) for t in (d.get('tags') or [])),
                   website_book_id=d.get('related_novel_book_id') or d.get('book_id'))
        inventory.append(row)
    fields=list(dict.fromkeys(k for r in inventory for k in r))
    save(HERE/'identity_coverage.csv',fields,inventory)
    out = {'catalog_size':len(catalog),'initial_trial_size':len(trial),'status':dict(Counter(r['web_status'] for r in inventory)),
           'errors':dict(errors),'counts':dict(stats),'distinct_episode_ids':len(unique_vids),'website_grouped_entries':sum(groups.values()),
           'distinct_website_group_ids':len(groups),'multiple_catalog_entries_in_group':sum(v>1 for v in groups.values()),
           'distinct_legacy_sdk_book_ids_in_catalog':len(within_book),'nonempty_website_structured_book_fields':dict(book_keys),
           'distinct_book_title_strings_explicitly_credited_in_web_intro':len(stated_titles),
           'returned_seriesDetail_keys':dict(details),'returned_seriesSocialInfo_keys':dict(socials),
           'returned_nested_season_info_keys':dict(season_fields),
           'preview_rows_per_title':dict(sorted(rev_lengths.items())),
           'legacy_5_episode_id_alignment':checked}
    (HERE/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    unattempted = out['status'].get('not_attempted',0)
    notes = f"""# 2026 年 11 月 21 日红果官网详情与系列身份核验

本次将过去 36 天档案里的 {out['catalog_size']:,} 个不同剧或季 ID 作为母表，普通 GET 读取官网公开详情 HTML。成功核对返回 ID 的有 {stats['retrieved']:,} 个，失败 {sum(errors.values())} 个，尚未尝试 {unattempted} 个。失败状态和原始响应原因存放在 errors 子目录。网页不可访问只能说明这次采集的结果。

| 观察项 | 此次结果 |
|---|---:|
| 详情页给出非空季组 ID 的作品 | {sum(groups.values()):,} |
| 可见的不同季组 ID | {len(groups):,} |
| 在本目录至少包含两条的季组 | {out['multiple_catalog_entries_in_group']:,} |
| 成功页中有备案号 | {stats['record_number_present']:,} |
| 成功页中有首次可见时间 | {stats['first_visible_time_present']:,} |
| 同时有官网组 ID 与旧 SDK 的专辑 ID 供对照 | {stats['compare_group']:,} |
| 两个来源的非空组 ID 完全相同 | {stats['same_group']:,} |
| 目录 ID 中连接到历史 SDK 季号的条目 | {stats['old_sdk_season_index']:,} |
| 目录 ID 中连接到历史 SDK 原著书号的条目 | {stats['old_sdk_book_id']:,} |
| 上述不同原著书号 | {len(within_book):,} |
| 官网简介写明“改编自……《书名》”的作品 | {stats['web_intro_explicit_adaptation_title']:,} |

每个成功页的官网原始可用字段名称、投影后的值、URL、接收时间和页面校验摘要都保存在 pages 子目录。读到的 season_info 子字段为 {', '.join(season_fields) or '无'}。在本次有值的结构化书号或原著信息字段为 {', '.join(book_keys) or '无'}。网页没有公开季号时留空，不能给没有组 ID 的作品推定“没有续季”。目录之外也可能存在同一系列的其他季。

此前保存的 SDK 样本由 113 个编号季、4 条同书作品和 5 个试采项目取并集，以 ID 合并到本目录。旧书号是历史业务元数据，不代表 11 月 21 日重新取得；只有 book ID 才支持精确关联。简介中写出的书名保留其原始证据片段，年内数据库中从简介抽出的目录书名另列。未标书名或书号仍可能是改编作品。

详情页列出的非空分集 ID 位置共有 {stats['episode_id_fields_nonempty']:,} 个。{stats['complete_unique_episode_id_list']:,} 条详情的分集列表满足每项非空、剧内无重复、长度与该页标注的集数相等。这项检查针对当次页面。可读、可播放与全部集的互动统计各需分别验证。剧评预览取自页面的 reviews 区块，保留正文、发表时间、点赞数、评分和原始顺序，省略用户账号信息。公开总数和实际预览条数分别统计。

[逐作品身份和覆盖表](identity_coverage.csv) · [机器可读统计](summary.json) · [采集脚本](collect.py) · [官网详情样例](https://hongguoduanju.com/detail?series_id=7691615145977449496) · [官网 robots 声明](https://hongguoduanju.com/robots.txt)
"""
    (HERE/'分季与原著核验.md').write_text(notes)
    print(json.dumps({k:out[k] for k in ('status','counts','distinct_episode_ids','website_grouped_entries','distinct_website_group_ids','errors')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
