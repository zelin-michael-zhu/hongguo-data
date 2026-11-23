"""Join local 21 November previews to independently recorded book and series identifiers."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent
CURRENT = OUT / 'hongguo_expansion_2026-11-21'
CASE = OUT / 'hongguo_nine_topic_screen_2026-11-20/ip'


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, items):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def group(record):
    website, sdk = record['series_group_id'], record['old_sdk_album_id']
    if website and sdk:
        assert website == sdk
    return website or sdk


def run():
    catalog = rows(CURRENT / 'identity/identity_coverage.csv')
    all_ids = {r['series_id'] for r in catalog}
    coverage = {r['series_id']: r for r in rows(CURRENT / 'series_coverage.csv')}
    texts = defaultdict(list)
    for review in rows(CURRENT / 'reviews_preview.csv'):
        assert review['scope'] in ('series_review', 'first_episode_comment')
        if review['text'].strip():
            texts[review['series_id'], review['scope']].append(review['text'].strip())
    books = defaultdict(list)
    line_books = defaultdict(set)
    group_catalog = defaultdict(set)
    credits = defaultdict(list)
    for r in catalog:
        book_id, gid, sid = r['old_sdk_book_id'], group(r), r['series_id']
        if gid:
            group_catalog[gid].add(sid)
        if book_id:
            books[book_id].append(r)
            if gid:
                line_books[gid].add(book_id)
        title_credit = r['web_intro_explicit_adaptation_title'] or r['catalog_book_from_intro']
        if title_credit:
            credits[title_credit.strip()].append(r)
    assert all(len(v) == 1 for v in line_books.values())

    previously_tested = json.loads((CASE/'four_title_metadata.json').read_text())['titles']
    outside = defaultdict(list)
    for r in previously_tested:
        if r['id'] not in all_ids:
            outside[r['related_novel_book_id']].append(r)

    book_table, product_table, title_table, extra_table = [], [], [], []
    for bid, entries in sorted(books.items()):
        lines = defaultdict(list)
        checked_ids = {r['series_id'] for r in entries}
        for r in entries:
            key = ('group', group(r)) if group(r) else ('entry', r['series_id'])
            lines[key].append(r)
        line_types = {}
        book_texts, first_texts = 0, 0
        extra = set()
        for (kind, key), members in sorted(lines.items()):
            boards = {b for r in members for b in r['catalog_boards'].split('|')}
            forms = boards & {'ai','real','comic'}
            line_types[(kind,key)] = forms
            if kind == 'group':
                extra |= group_catalog[key] - checked_ids
            lp, ls = 0, 0
            for r in members:
                sid = r['series_id']
                fc = texts[sid,'first_episode_comment']
                sr = texts[sid,'series_review']
                assert len(fc) == int(coverage[sid]['first_episode_comments_with_text'] or 0)
                assert len(sr) == int(coverage[sid]['series_reviews_with_text'] or 0)
                lp += len(fc)
                ls += len(sr)
                title_table.append(dict(book_id=bid,series_id=sid,title=r['catalog_title'],group_id=group(r),
                                        recorded_season=r['old_sdk_season_index'],board_history=r['catalog_boards'],
                                        old_content_type=r['old_sdk_content_type'],record_number=r['record_number'],
                                        first_preview_rows=len(fc),first_distinct_texts=len(set(fc)),
                                        first_reported=coverage[sid]['first_episode_comments_total'],
                                        review_preview_rows=len(sr),review_distinct_texts=len(set(sr)),
                                        reviews_reported=coverage[sid]['series_reviews_total']))
            product_table.append(dict(book_id=bid,identifier_kind=kind,line_id=key,entries=len(members),
                                      observed_forms='|'.join(sorted(forms)),
                                      title_ids='|'.join(r['series_id'] for r in members),
                                      titles='|'.join(r['catalog_title'] for r in members),
                                      first_preview_rows=lp,series_review_preview_rows=ls))
            book_texts += ls
            first_texts += lp
        real = {key for key, forms in line_types.items() if 'real' in forms}
        ai = {key for key, forms in line_types.items() if 'ai' in forms}
        distinct_pairs = {(a,b) for a in ai for b in real if a!=b}
        floor = len({r['related_album_id'] or r['id'] for r in outside[bid]})
        book_table.append(dict(book_id=bid,representative_drama=entries[0]['catalog_title'],
                               exact_book_entries=len(entries),observed_catalog_lines=len(lines),
                               grouped_lines=sum(k[0]=='group' for k in lines),
                               entries_without_group=sum(k[0]=='entry' for k in lines),
                               ai_board_lines=len(ai),real_board_lines=len(real),cross_form_distinct_pairs=len(distinct_pairs),
                               extra_same_group_entries_without_direct_book_id=len(extra),
                               external_prechecked_entries=len(outside[bid]),external_album_groups=floor,
                               first_comments=first_texts,series_reviews=book_texts))
        for r in outside[bid]:
            extra_table.append(dict(book_id=bid,series_id=r['id'],title=r['title'],album_id=r['related_album_id'],
                                    season=r['season_index'],content_type=r['content_type'],in_catalog=False,
                                    first_episode_comment_rows=None,series_review_rows=None,
                                    stored_evidence='2026-11-20 case metadata; no 2026-11-21 preview sampled'))
    write('逐书覆盖.csv',book_table)
    write('产品线.csv',product_table)
    write('逐剧与评论覆盖.csv',title_table)
    write('目录外同书线索.csv',extra_table)
    dup_credits = [dict(credit_display=name,series_id=r['series_id'],title=r['catalog_title'],group_id=group(r),
                        boards=r['catalog_boards']) for name,rs in credits.items() if len(rs)>1 for r in rs]
    if dup_credits:
        write('重名原著文字线索.csv',dup_credits)
    stats = dict(catalog=len(catalog),direct_book_entries=len(title_table),books=len(book_table),
                 grouped_entries=sum(bool(r['group_id']) for r in title_table),
                 distinct_lines=len(product_table),grouped_lines=len(line_books),
                 without_groups=sum(not r['group_id'] for r in title_table),
                 books_by_observed_lines=dict(Counter(r['observed_catalog_lines'] for r in book_table)),
                 direct_entries_by_book_count=dict(Counter(r['exact_book_entries'] for r in book_table)),
                 books_with_examined_ai_live_pair=sum(bool(r['cross_form_distinct_pairs']) for r in book_table),
                 paired_case=[r for r in book_table if r['cross_form_distinct_pairs']],
                 direct_rows_with_both_review_types=sum(bool(r['first_preview_rows'] and r['review_preview_rows']) for r in title_table),
                 first_comments=sum(r['first_preview_rows'] for r in title_table),
                 series_reviews=sum(r['review_preview_rows'] for r in title_table),
                 other_members_same_group_no_direct_book=sum(r['extra_same_group_entries_without_direct_book_id'] for r in book_table),
                 outside_case_rows=len(extra_table),unique_credit_strings=len(credits),
                 repeated_credit_strings=sum(len(rs)>1 for rs in credits.values()),
                 repeated_credit_spanning_groups=sum(len(rs)>1 and len({group(r) or r['series_id'] for r in rs})>1
                                                    for rs in credits.values()))
    (HERE/'summary.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    print(json.dumps(stats,ensure_ascii=False))


if __name__=='__main__':
    run()
