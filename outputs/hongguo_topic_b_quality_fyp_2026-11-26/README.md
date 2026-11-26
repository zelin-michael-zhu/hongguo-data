# 基于观众反馈与多模态内容验证的 AI 短剧质量改进优先级模型

FYP Topic B · 2026 年 11 月 26 日 · 提案阶段

研究拟检验在候选集合、基础评分规则和审核项数固定的条件下，加入视频核验信息能否提高跨作品清单前 K 项中经独立复核、获内容证据支持且可行动的问题比例。

## 提案与方法

- [中文版 PDF](proposal/TopicB_Proposal_中文版_2026-11-26.pdf) · [可编辑 Markdown](proposal/TopicB_Proposal_中文初稿_2026-11-26.md)
- [评论语义编码提示词](methods/评论语义编码提示词.txt)记录接口原型采用的编码口径。正式类别和评价规则以开发阶段冻结的版本为准。

## 先导试标

- [试验报告](outputs/hongguo_quality_feedback_2026-11-24/试验结果.md) · [试标口径](outputs/hongguo_quality_feedback_2026-11-24/标注口径.md)
- [样本覆盖](outputs/hongguo_quality_feedback_2026-11-24/coverage.json) · [问题覆盖](outputs/hongguo_quality_feedback_2026-11-24/缺陷覆盖.csv) · [结果汇总](outputs/hongguo_quality_feedback_2026-11-24/pilot_results.json)
- [备样脚本](outputs/hongguo_quality_feedback_2026-11-24/prepare.py) · [汇总脚本](outputs/hongguo_quality_feedback_2026-11-24/analyze.py) · [试标行号标签](outputs/hongguo_quality_feedback_2026-11-24/labels.json)

2026 年 11 月 24 日的先导试标覆盖 25 部作品的 215 条评论，由单一 AI 完成。它用于识别样本覆盖和标注限制。正式研究的独立复核与视频证据增量实验仍待开展。

历史数据参见[红果数据归档](../../README.md)。如需复算试标，将本仓库的 `outputs/hongguo_expansion_2026-11-21/` 和 `outputs/hongguo_free_pilot_2026-11-18/` 复制或链接到本目录的 `outputs/`，再依次运行 `prepare.py` 和 `analyze.py`。复算会在本地生成包含原评论的中间文件。
