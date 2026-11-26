# 红果数据

截至 2026 年 11 月 23 日的红果短剧 FYP 数据快照、标注和分析归档，共覆盖 22 个研究目录。保留原始 `outputs/hongguo_*` 路径，方便查找资料和复算。[文件清单](文件清单.csv)

## 从哪里开始

**FYP Topic B（2026 年 11 月 26 日）**　[AI 短剧质量改进优先级提案、方法和先导试标](outputs/hongguo_topic_b_quality_fyp_2026-11-26/README.md) · [中文版 PDF](outputs/hongguo_topic_b_quality_fyp_2026-11-26/proposal/TopicB_Proposal_中文版_2026-11-26.pdf)

- **历史榜单与目录**　2026 年 10 月 13 日至 11 月 17 日共 36 天，覆盖 1,388 个作品 ID。[每日榜单](outputs/hongguo_free_pilot_2026-11-18/history/board_daily.csv) · [每日作品指标](outputs/hongguo_free_pilot_2026-11-18/history/drama_daily.csv) · [作品目录](outputs/hongguo_free_pilot_2026-11-18/history/catalog.csv)
- **分集、评论与系列**　11 月 21 日扩采覆盖 1,365 部作品、238,397 个分集 ID 和 32,707 条网页评论预览。[分集索引](outputs/hongguo_expansion_2026-11-21/episode_index.csv) · [评论预览](outputs/hongguo_expansion_2026-11-21/reviews_preview.csv) · [系列身份](outputs/hongguo_expansion_2026-11-21/identity/identity_coverage.csv) · [覆盖说明](outputs/hongguo_expansion_2026-11-21/实测范围与数据说明.md)
- **弹幕与试采互动**　11 月 18 日的 46 条首集弹幕样本来自 5 部剧。[弹幕样本](outputs/hongguo_free_pilot_2026-11-18/danmaku_sample.csv) · [整剧指标样本](outputs/hongguo_free_pilot_2026-11-18/series_metrics.csv) · [字段字典](outputs/hongguo_free_pilot_2026-11-18/data_dictionary.json)
- **AI 榜与前瞻验证**　[按日榜单及候选作品](outputs/hongguo_ai_chase_2026-11-22/daily/) · [评论快照](outputs/hongguo_sentiment_pilot_2026-11-21/snapshots/) · [首批 22 部冻结预测](outputs/hongguo_ai_chase_2026-11-22/11月21日三种选法_冻结.csv) · [语义覆盖汇总](outputs/hongguo_semantics_pilot_2026-11-23/首批22部_三维覆盖.csv) · [逐条语义标签](outputs/hongguo_semantics_pilot_2026-11-23/首批22部_逐条语义标签.csv) · [前瞻结果状态](outputs/hongguo_semantics_pilot_2026-11-23/prospective/validation.json)
- **预约与上线**　[预约榜快照](outputs/hongguo_reservation_pilot_2026-11-22/预约榜_当日快照.json) · [首批 100 部上线与首周收藏](outputs/hongguo_reservation_pilot_2026-11-22/tracking/首批100部_上线与首周收藏.csv) · [采集口径](outputs/hongguo_reservation_pilot_2026-11-22/预约榜与首周收藏日采.md)
- **分析与复算**　[七日冲榜](outputs/hongguo_breakout_2026-11-21/七日冲榜预测试验.md) · [系列信息的增量价值](outputs/hongguo_franchise_forecast_2026-11-21/滚动时间验证.md) · [作品榜与系列榜](outputs/hongguo_units_2026-11-21/作品榜还是系列榜_导师讨论稿.md) · [首集时长与互动](outputs/hongguo_ai_topic_pivot_2026-11-22/首集时长与互动_对数模型.csv) · [完整研究目录](outputs/)

## 下载与数据口径

登录有访问权限的 GitHub 账号后，可以[下载整个仓库 ZIP](https://github.com/zelin-michael-zhu/hongguo-data/archive/refs/heads/main.zip)，也可以在仓库首页点击 **Code → Download ZIP**。需要 Git 操作时运行下列命令。

```bash
git clone https://github.com/zelin-michael-zhu/hongguo-data.git
```

将长 ID 列按文本导入 Excel 或 pandas，保留原始精度。空字段表示缺失。网页评论只覆盖各次抓取时公开展示的内容，跨日期可能重复，预览条数与页面报告总数分别保留。历史弹幕及播放指标属于小样本。进行前瞻分析时，请以各文件的采集时间、冻结规则和结果状态为准。部分复算脚本需要把原来的本机路径改成下载后的目录。

旧成果包中的数据均保留为可直接访问的散文件，可随整仓 ZIP 一并下载。四个本机只有云端占位的旧文件已从归档里的绘图脚本、数据或 HTML 重新导出，在文件清单中注明。
