"""Validate and bundle the finished 21 November 2026 coverage test."""
import csv
import json
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'hongguo_free_pilot_2026-11-18'


def read_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        yield from csv.DictReader(f)


def read_json(path):
    return json.loads(path.read_text())


def main():
    summary = read_json(HERE/'coverage_summary.json')
    stats = summary['counts']
    identity = read_json(HERE/'identity/summary.json')
    named_seasons = read_json(HERE/'identity/explicit_summary.json')
    series = {r['series_id']:r for r in read_rows(HERE/'series_coverage.csv')}
    assert set(series)=={r['id'] for r in read_rows(OLD/'history/catalog.csv')}
    for field in ('detail_status','first_episode_status'):
        assert sum(summary[field].values())==len(series) and not summary[field].get('not_checked')
    assert identity['status']['ok']==summary['detail_status']['ok']
    assert not identity['status'].get('not_attempted')
    positions = Counter()
    indexed = set()
    for r in read_rows(HERE/'episode_index.csv'):
        sid, eid = r['series_id'], r['episode_id']
        positions[sid] += 1
        assert eid.isdigit() and int(r['episode_position'])==positions[sid]
        assert (sid,eid) not in indexed
        indexed.add((sid,eid))
    assert len(indexed)==stats['episode_index_rows']
    matched_first = sum((sid,r['first_episode_id']) in indexed for sid,r in series.items())
    assert matched_first==stats['first_ids_cross_checked']
    reviews = Counter()
    for r in read_rows(HERE/'reviews_preview.csv'):
        assert r['series_id'] in series and r['text'].strip()
        if r['scope']=='first_episode_comment':
            assert series[r['series_id']]['first_episode_id']==r['episode_id']
        reviews[r['scope']] += 1
    assert reviews['series_review']==stats['series_reviews_text_rows']
    assert reviews['first_episode_comment']==stats['first_comments_text_rows']
    for sid,n in positions.items():
        assert n==int(series[sid]['listed_episode_ids'])
    report = f"""# 红果数据覆盖实测

2026 年 11 月 21 日（北京时间），以本地旧目录的 **{len(series):,} 个不同作品或编号季 ID** 为固定分母。每个 ID 分别尝试红果公开详情页与默认首集页，采集内容为 HTML 内的文字、标识和计数。每一行保存实际采集时间。此前的客户端样本单列日期与来源。

| 项目 | 新采集及已核验结果 |
|---|---|
| 作品覆盖 | 详情页 {summary['detail_status']}。首集页 {summary['first_episode_status']}。HTTP 404 只记录为本次网址不可用。|
| 整剧指标 | 详情页有收藏值的作品 {stats['detail_nonempty_series_favorite_count']:,} 个。历史原始客户端播放量和关注数各覆盖 {stats['historical_sdk_series']} 个 ID，仅供历史横截面参考。另有 4 个有官方公开战报的作品或季 ID，以发布当日下界表示，没有统一的精确值。 |
| 全部分集编号 | 列表内共有 {stats['episode_index_rows']:,} 行、{stats['distinct_episode_ids']:,} 个不同集 ID。{stats['enumerations_match_count']:,} 个作品的列表长度、列表内去重 ID 数、官网当日标注集数三者相等。集序取同一详情页公开列表的位置。 |
| 单集互动 | 官网首集页有点赞数 {stats['first_with_likes']:,} 个，有评论总数 {stats['first_comments_pages_with_total']:,} 个，有时长 {stats['first_with_duration']:,} 个。旧样本 {stats['historical_sdk_episode_rows']:,} 集有客户端分集点赞和评论数。不同来源和不同时间分别保留。 |
| 整剧评论 | {stats['series_reviews_pages_with_text']:,} 部取得正文，合计 {reviews['series_review']:,} 条网页预览。{stats['series_reviews_pages_count_equal']:,} 个页面取得的正文数与其报告总数恰好一致。未取得稳定评论 ID 的行只保留当次展示位置。|
| 首集评论 | {stats['first_comments_pages_with_text']:,} 个首集取得正文，合计 {reviews['first_episode_comment']:,} 条预览。{stats['first_comments_pages_count_equal']:,} 个首集取得正文数与报告数一致。跨日期的同一条正文可能重复出现。|
| 弹幕 | 本次 4 个首集检查新增 0 条。2026-11-18 的历史样本覆盖 5 个首集、共 46 条；5 个首集的旧接口报告总数合计 16,734。 |
| 系列与原著 | {stats['website_group_members']:,} 个 ID 有官网系列分组，分属 {stats['website_group_ids']:,} 个不同分组，其中 {stats['website_groups_with_multiple_catalog_members']:,} 个组在本目录有至少两个成员。历史结构化原著书号可关联 {identity['counts']['old_sdk_book_id']:,} 个目录 ID。一个作品可能有原著而页面未披露。 |

## 文件与使用

- `series_coverage.csv` 每个目标作品一行。首集计数、网页收藏和历史客户端播放／追剧按字段区分。网页收藏即页面字段，部分数值只有展示精度。历史 `follow_count` 指客户端的关注／追剧相关计数，其与独立订阅量的关系尚待核实。
- `episode_index.csv` 每个公开列出的集一行，可按剧 ID、分集 ID 关联。分集编号完整不代表相应分集的评论、点赞或视频文件均可得。
- `reviews_preview.csv` 含当日整剧和首集的公开正文。筛选 `scope` 区分这两个评论区。发表时间 `create_time_raw` 保留原网页字段，采集时间为 UTC。文件中省略评论作者账号、昵称和头像。
- `identity/identity_coverage.csv` 按剧整合当日公开分组、历史核实的季号和原著书号，以及简介文本中明示的改编线索。编号季、系列、同一原著分别是三个层次。
- `identity/explicit_seasons.csv` 中的 {named_seasons['members']} 个条目同时有官网季组和剧名中写明的“第几季”。在有历史客户端季号可对照的 {named_seasons['crosscheck_with_sdk'].get('agree',0)+named_seasons['crosscheck_with_sdk'].get('disagree',0)} 个中，{named_seasons['crosscheck_with_sdk'].get('agree',0)} 个一致。`identity/explicit_adjacent_seasons.csv` 仅在同一组的前后两个季号各自只对应一个条目时配对，共 {named_seasons['unique_adjacent_pairs']} 对。这是一种由公开组号与文字共同支持的关系，不能单凭标题判定两季是否独立制作。
- `historical_2026-11-18/` 保留原五部的整剧／分集计数及首集弹幕。`reported_plays/` 是不同时点披露的观看量下界，各行有来源链接。
- `comments/` 和 `danmaku/` 记录另外抽取的少量页面和点击“查看更多”的结果，与主表可能重复，不能把示例再加到总数。官网对带两个路径参数的分集播放地址列有爬虫限制，本轮批量读取的页面为剧目详情和默认首集。[官网公开规则](https://hongguoduanju.com/robots.txt)

剧、系列、原著和集 ID 很长，导入 Excel 时请将 ID 列指定为**文本**。CSV 中的空值表示该字段本次未取得，不能换算为零。导入 Python 可用 `pandas.read_csv(..., dtype={{'series_id':'string','episode_id':'string'}})`。此次采集是单次快照，不能回填此前 36 天的历史播放、首集点赞或评论数。
"""
    (HERE/'实测范围与数据说明.md').write_text(report,encoding='utf-8')
    files = ['series_coverage.csv','episode_index.csv','reviews_preview.csv','coverage_summary.json','实测范围与数据说明.md',
             'identity/identity_coverage.csv','identity/summary.json','identity/explicit_seasons.csv',
             'identity/explicit_adjacent_seasons.csv','identity/explicit_summary.json','identity/explicit_seasons.py',
             'identity/分季与原著核验.md','identity/collect.py','danmaku/弹幕覆盖实测.md',
             'comments/评论覆盖核验.md','comments/整剧指标公开来源复核.md','reported_plays/官方战报观看量下界.csv']
    # Include the small evidence notes/tables underlying the linked examples.
    supporting = [p for sub in ('comments','danmaku','reported_plays') for p in (HERE/sub).rglob('*')
                  if p.is_file() and p.suffix in ('.md','.json','.csv','.py') and p.relative_to(HERE).as_posix() not in files]
    target = HERE/'红果数据覆盖实测.zip'
    with ZipFile(target,'w',compression=ZIP_DEFLATED,compresslevel=6) as z:
        for f in files:
            z.write(HERE/f, f)
        for p in supporting:
            z.write(p,p.relative_to(HERE))
        for f in ('series_metrics.csv','episodes.csv','danmaku_sample.csv','data_dictionary.json'):
            z.write(OLD/f, 'historical_2026-11-18/'+f)
    with ZipFile(target) as z:
        assert z.testzip() is None
    print('verified',len(series),len(indexed),dict(reviews),target.stat().st_size)


if __name__=='__main__':
    main()
