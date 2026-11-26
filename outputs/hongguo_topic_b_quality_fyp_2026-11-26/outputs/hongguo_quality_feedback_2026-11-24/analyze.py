"""Validate field-blind annotations and enforce feasibility before format comparisons."""

import hashlib
import json
import re
from collections import Counter

from prepare import ARCHIVE, HERE, read, write


ISSUES = ('audio_negative', 'identity_negative', 'visual_negative', 'logic_negative')
TAGS = (*ISSUES, 'other_negative', 'explicit_praise', 'promo')
MENTIONS = {
    'audio_or_lipsync_mention': r'配音|口型|对嘴|声音|音量|音效|BGM|背景音乐',
    'identity_or_model_mention': r'串脸|换脸|崩脸|建模|脸不[一稳]|认不出|认不清|分不清谁|人物.{0,6}(?:变了|变来变去|不一致)',
    'visual_or_edit_mention': r'画面|画质|特效|动作|穿帮|剪辑|运镜|表情僵|五官乱飞',
    'logic_mention': r'逻辑|不合理|漏洞|前后矛盾|降智|智商|编剧|剧情混乱',
}


def main():
    rows = read(HERE / '试读索引.csv')
    blind = read(HERE / '盲标文本.csv')
    assert list(blind[0]) == ['row_id', 'text']
    expected = {int(row['row_id']) for row in rows}
    assert len(expected) == len(rows) == len(blind)
    assert {int(r['row_id']): r['text'] for r in rows} == {int(r['row_id']): r['text'] for r in blind}
    labels = json.loads((HERE / 'labels.json').read_text())
    assert set(labels) == {'reviewed_rows', *TAGS}
    assert len(labels['reviewed_rows']) == len(expected) and set(labels['reviewed_rows']) == expected
    for name, ids in labels.items():
        assert all(type(v) is int for v in ids) and len(ids) == len(set(ids)) and set(ids) <= expected, name
    classified = []
    for row in rows:
        n = int(row['row_id'])
        classified.append({**row, **{tag: int(n in labels[tag]) for tag in TAGS},
                           'score_mentioned_in_text': int(bool(re.search(r'五星|五[颗个]星|满分|[一二三四五六七八九十0-9]+分|差评|好评', row['text'])))})
    write('逐条质量标注.csv', classified)
    audience = [row for row in classified if not row['promo']]
    summaries = []
    for form in ('live_action', 'ai_realistic', 'ai_animation'):
        group = [r for r in audience if r['form'] == form]
        for issue in (*ISSUES, 'other_negative'):
            detected = [r for r in group if r[issue]]
            summaries.append({'provisional_form': form, 'issue': issue, 'audience_reviews': len(group),
                              'candidate_titles': len({r['series_id'] for r in group}),
                              'issue_reviews': len(detected), 'issue_titles': len({r['series_id'] for r in detected}),
                              'meets_support_threshold': int(len(detected) >= 40 and len({r['series_id'] for r in detected}) >= 15)})
    write('缺陷覆盖.csv', summaries)
    totals = {tag: {'reviews': sum(r[tag] for r in audience),
                    'titles': len({r['series_id'] for r in audience if r[tag]})} for tag in TAGS if tag != 'promo'}
    variation = sum(len({int(r['rating']) for r in audience if r['series_id'] == sid}) > 1
                    for sid in {r['series_id'] for r in audience})
    public_examples = []
    for row in audience:
        if row['visual_negative'] or row['logic_negative']:
            public_examples.append({k: row[k] for k in ('row_id', 'title', 'series_id', 'text', 'rating', *ISSUES)})
    write('具体问题与评分.csv', public_examples)
    suspect = [r for r in audience if r['form'] == 'live_action' and re.search('AI|不是真人|都是真人', r['text'], re.I)]
    write('制作形式待核对线索.csv', [{k: r[k] for k in ('row_id', 'title', 'series_id', 'text', 'local_source')} for r in suspect])
    archive = [r for r in read(ARCHIVE / 'reviews_preview.csv') if r['scope'] == 'series_review']
    mentions, mention_counts = [], {}
    for label, pattern in MENTIONS.items():
        group = [r for r in archive if re.search(pattern, r['text'], re.I)]
        mention_counts[label] = {'reviews': len(group), 'titles': len({r['series_id'] for r in group})}
        mentions.extend({'screen': label, **{k: r[k] for k in ('series_id', 'display_position', 'text', 'source_url')}} for r in group)
    write('全量词式候选_未语义核验.csv', mentions)
    result = {
        'pilot_reviews': len(rows), 'pilot_titles': len({r['series_id'] for r in rows}),
        'self_declared_promo': sum(r['promo'] for r in classified), 'audience_reviews': len(audience),
        'pooled_issue_counts': totals, 'titles_with_rating_variation': variation,
        'score_mentioned_in_audience_texts': sum(r['score_mentioned_in_text'] for r in audience),
        'classification_conflict_clue_titles': len({r['series_id'] for r in suspect}),
        'full_corpus_mentions_not_defect_labels': mention_counts,
        'independent_recode_n': 0, 'human_reference_n': 0,
        'regressions_fitted': 0, 'status': 'not_ready_for_three_format_comparison',
        'reasons': ['Fewer than 20 provisionally classified independent series in both AI groups',
                    'None of the four defects has 40 comments across 15 works in each format',
                    'Independent recoding has not been performed',
                    'All format assignments require stronger production verification before formal comparisons'],
        'sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                   for name in ('prepare.py', '标注口径.md', 'labels.json', '盲标文本.csv')},
    }
    (HERE / 'pilot_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
