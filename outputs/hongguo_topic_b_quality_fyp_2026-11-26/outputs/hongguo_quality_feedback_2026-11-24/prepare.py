"""Audit format provenance before attempting the three-format quality study."""

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUTS = HERE.parent
ARCHIVE = OUTPUTS / 'hongguo_expansion_2026-11-21'
TEAM = 'https://www.thepaper.cn/newsDetail_forward_34352445'
INTERVIEW = 'https://www.sohu.com/a/1102106936_250147'


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write(name, rows):
    with (HERE / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    catalog = {r['id']: r for r in read(OUTPUTS / 'hongguo_free_pilot_2026-11-18/history/catalog.csv')}
    identities = {r['series_id']: r for r in read(ARCHIVE / 'identity/identity_coverage.csv')}
    evidence = []
    for path in sorted((ARCHIVE / 'identity/pages').glob('*.json')):
        source = json.loads(path.read_text())
        sid, detail = str(source['series_id']), source['detail']
        title = detail['series_name']
        boards = set(catalog[sid]['boards_seen'].split('|'))
        roles = [r for r in detail.get('celebrities', []) if r.get('celebrity_id') and r.get('sub_title', '').startswith('饰 ')]
        form, basis, url, scope = 'unknown', 'No independent format evidence in this audit', '', ''
        if 'real' in boards and not boards & {'ai', 'comic'} and len(roles) >= 2:
            form, basis, url, scope = 'live_action', 'Real chart history and at least two named acted-role credits', source['url'], 'title_metadata'
        if title.startswith('持械入宋'):
            form, basis, url, scope = 'ai_realistic', 'Named creator interview explicitly describes the series/team as AI realistic', TEAM, 'series_claim'
        if title.startswith('退役归来，这个保镖不好惹'):
            form, basis, url, scope = 'ai_realistic', 'Same named team and identified production; realistic assignment inferred from team specialization', INTERVIEW, 'team_inference'
        if '仿真人' in title and 'ai' in boards:
            form, basis, url, scope = 'ai_realistic', 'Official title explicitly says realistic and the title appears on AI chart', source['url'], 'explicit_title_and_chart'
        if title.startswith(('万妖图录传', '聚宝仙盆之杂灵根才是真BOSS')):
            form, basis, url, scope = 'ai_animation', 'Named industry interview identifies these series as 3D animation in the AI series context', TEAM, 'series_claim'
        evidence.append(dict(series_id=sid, title=title, family=identities[sid]['series_group_id'] or sid,
                             form=form, evidence_scope=scope, basis=basis, source_url=url,
                             evidence_status='unclassified' if form == 'unknown' else 'provisional_assignment',
                             local_source=str(path.relative_to(OUTPUTS.parent)), boards='|'.join(sorted(boards))))
    assert len(evidence) == len({r['series_id'] for r in evidence}) == 1365
    write('分类证据.csv', evidence)
    reviews = read(ARCHIVE / 'reviews_preview.csv')
    reviews = [r for r in reviews if r['scope'] == 'series_review']
    assert len(reviews) == 12247
    assert all(r['rating'].isdigit() and 1 <= int(r['rating']) <= 10 for r in reviews)
    review_by_title = defaultdict(list)
    for row in reviews:
        review_by_title[row['series_id']].append(row)
    coverage = {}
    for form in ('live_action', 'ai_realistic', 'ai_animation', 'unknown'):
        group = [r for r in evidence if r['form'] == form]
        coverage[form] = dict(titles=len(group), families=len({r['family'] for r in group}),
                              reviews=sum(len(review_by_title[r['series_id']]) for r in group),
                              by_evidence_scope=dict(Counter(r['evidence_scope'] for r in group)))
    # One member per recorded series, chosen without consulting reviews or scores.
    candidates = sorted((r for r in evidence if r['form'] != 'unknown'),
                        key=lambda r: hashlib.sha256(f'quality-pilot-1124|{r["series_id"]}'.encode()).hexdigest())
    selected, selected_families, form_n = [], set(), Counter()
    for row in candidates:
        if row['family'] in selected_families or form_n[row['form']] >= 20:
            continue
        selected.append(row)
        form_n[row['form']] += 1
        selected_families.add(row['family'])
    texts = []
    for title in selected:
        for review in review_by_title[title['series_id']]:
            texts.append({**title, 'position': review['display_position'], 'rating': int(review['rating']),
                          'published_at_raw': review['create_time_raw'], 'text': review['text']})
    texts.sort(key=lambda r: hashlib.sha256(f'{r["series_id"]}|{r["position"]}|blind-quality'.encode()).hexdigest())
    indexed = [{'row_id': i, **r} for i, r in enumerate(texts, 1)]
    write('试读索引.csv', indexed)
    write('盲标文本.csv', [{'row_id': r['row_id'], 'text': r['text']} for r in indexed])
    support = [form for form in ('live_action', 'ai_realistic', 'ai_animation') if form_n[form] < 20]
    summary = dict(coverage=coverage, selected_titles=len(selected), selected_by_form=dict(form_n),
                   blind_reviews=len(indexed), rating_distribution=dict(Counter(r['rating'] for r in reviews)),
                   status='insufficient_format_evidence' if support else 'ready_for_annotation', insufficient_forms=support,
                   data_date='2026-11-21', audit_date='2026-11-24',
                   format_warning='Provisional format assignments. Cast credits and chart membership do not establish production purity; series or team reports do not verify every season.')
    (HERE / 'coverage.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
