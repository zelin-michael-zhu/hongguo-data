# 方法与测量文献检索日志

检索日期：2026-11-19。负责人：methods/measurement 子任务。使用 deep-research 的题名存在性与主张匹配双重核验；本文件为定向检索记录，不声称穷尽系统综述。

## 检索渠道与实际访问结果

| 渠道 | 实际操作 | 结果与限制 |
|---|---|---|
| Web 学术定向检索 | 2024–2026 的 measurement audit、recommender/social information、prediction leakage、DID/RDiT，再以完整题名检索 | 核心题名与作者均找到，最终证据优先出版社、作者机构及作者预印本。 |
| Crossref REST | /works?query.title=...&rows=1，随后 /works/{DOI} | 初次题名搜索部分代理 Tunnel 503；Borusyak 与 Hausman 的 top-1 为工作论文 DOI，未误当最终期刊。精确 DOI 11/11 HTTP 200；其中 10 篇核心与 1 篇筛查补充。 |
| Semantic Scholar Graph API | /graph/v1/paper/search?query=Beyond the margin of error...&limit=3&fields=... | 环境代理 Tunnel 503；不是论文不存在或 S2 搜索零结果的证据。后续 web domain 查询未产生可核验 S2 记录。 |
| Google Scholar | /scholar?hl=en&q=exact distinctive title | 环境代理 Tunnel 503；后续 web domain 查询未产生可核验 Scholar 记录。没有使用 Scholar 被引次数或命中数。 |

## Web 检索式（按批次）

### Batch 1

- 2024 2025 social media platform metrics measurement API reliability public engagement counts research Nature Human Behaviour
- 2024 2025 recommender systems feedback loops randomized experiment social influence popularity information Management Science
- 2024 2025 machine learning temporal leakage out of time validation prediction paper

### Batch 2

- "Beyond the margin of error" TikTok research API authors
- "Engagement, user satisfaction, and the amplification of divisive content on social media" 2025
- 2024 2025 suspense cliffhanger randomized experiment video streaming short drama content selection

### Batch 3

- "The Role of Cliffhangers" Wirz Ort Rasch Fahr
- REFORMS checklist machine learning science 2024 Science Advances Kapoor Narayanan
- "Regression Discontinuity in Time" "Hausman" "Rapson"
- "difference-in-differences" "2024" "2025" "parallel trends" "review"

### Batch 4

- 2024 2025 "social influence" "randomized" "Information Systems Research" popularity
- 2024 2025 "short video" "experiment" "Management Science" recommendation
- "Causal Panel Analysis under Parallel Trends" authors
- "Revisiting Event-Study Designs" 2024 Borusyak Jaravel Spiess

### Batch 5

- "The Role of Cliffhangers in Serial Entertainment" DOI
- "Causal Panel Analysis" "CORRIGENDUM" Cambridge 2026
- "How Algorithmic Confounding" Chaney Stewart Engelhardt 2018
- "Social Influence Bias" Muchnik Aral Taylor Science 2013

### Batch 6

- site:semanticscholar.org/paper "Beyond the margin of error" TikTok
- site:scholar.google.com "Revisiting Event-Study Designs" Borusyak
- "The role of cliffhangers" site:unifr.ch
- "Beyond the margin of error" "TikTok" pdf Pearson

### Batch 7

- "Predictive Analytics in Information Systems Research" Shmueli Koppius 2011 DOI
- "Predictive Analytics in Information Systems Research" pdf misq

### 补充混合检索与精确核验

- site:cambridge.org "S0003055426101798"
- "Experimental Study of Inequality and Unpredictability" Salganik 2006 Princeton
- "REFORMS" "Sayash" "Cantrell" "Pham" authors 2024
- "Engagement, user satisfaction" "methods" 2025 1730
- 每个候选完整题名经 Crossref query.title，再以出版社识别的 DOI 精确核验；具体请求 URL、原始题名、作者和日期见 JSON 原始记录。

## 关键原文/摘要访问记录

| 来源 | 观察到的访问结果 | 本包采用方式 |
|---|---|---|
| Taylor & Francis /10.1080/1369118X.2024.2420032 | web search 可取得出版社原摘要与作者；直接 open 标准 URL 返回 403 | 仅使用摘要明确报告的审计框架、问题类型与时间范围；不使用未核验分项表格。 |
| PNAS Nexus /10.1093/pnasnexus/pgaf062 | Crossref HTTP 200；Oxford DOI 重定向到工具无法访问的 CDN；PMC 搜索可取原文摘要但直接 open 出现 reCAPTCHA | 主方法以作者 arXiv v6（2024-12-07）原文验证，期刊题名/年份由 Crossref 与期刊记录核验。 |
| Milli arXiv v4 与 v6 | 均可读；v4 abstract 称 randomized experiment，v6 改为 algorithmic audit | 使用 v6，明确随机呈现顺序不等于长期随机分配 feed。 |
| Princeton Chaney manuscript | 作者机构 PDF 在 web 索引显示题名、作者、模拟方法摘要；Crossref HTTP 200 | 将研究类型标为 simulation，而非真实平台 RCT。 |
| Muchnik Science DOI / PubMed / 原作者网页 | Science 链接可能受限；PubMed 原摘要、作者解释和 exact DOI 可用 | 使用现场随机先行评分的设计与方向，不外推短剧效应量。 |
| Wirz APA DOI / Folia institution | APA DOI 工具 restricted/redirect；机构库摘要与完整作者、卷期可用；PDF 是 application/octet-stream，web parser 不支持 | 方法、N=133 和结果均由机构库作者摘要验证；未把无法阅读的 PDF 细节补写出来。 |
| AIS MISQ Shmueli–Koppius | 官方摘要、推荐引用和 Crossref HTTP 200 | 规范题名剥除末尾脚注 1，保留 MISQ 2011 卷期。 |
| Science Advances REFORMS | Science 直接 open 403；PMC 搜索返回原文段落；作者所在机构原文可被索引；exact DOI 可用 | 使用已核验清单模块与摘要；完整作者取 Crossref。 |
| Oxford REStud Borusyak | 出版社原文可读；exact DOI HTTP 200 | 使用期刊 2024 版本，拒绝初次题名 top-1 的工作论文版本混淆。 |
| Cambridge Chiu original | 出版社原文可读；exact DOI HTTP 200 | 保留 online 2025 / issue 2026 的区别。 |
| Cambridge Chiu corrigendum | 出版社全文可读，2026-06-24 | 核验仅 Figure 5 Latura 与 Liao 两案例图面板调换；不使用这两个面板。 |
| Annual Reviews Hausman–Rapson / Haas manuscript | 出版社元数据/摘要与作者机构方法摘要可读；exact DOI HTTP 200 | 使用 2018 期刊版而非初次 title search 的 2017 NBER 版。 |
| sklearn TimeSeriesSplit stable docs | 官方文档可读，页面显示 1.9.1 | 只作时间切分实施文档，明确多作品面板不能简单按行套用。 |

## 筛选与反证

- Salganik, Dodds & Watts (2006) 的人工音乐市场随机社会信息实验已验证，Crossref DOI 10.1126/science.1121066；核心 10 篇已含社会信息现场实验，故保留为已筛查补充而未增加核心数量。
- 无法核验或仅有泛泛行业评论的短剧材料不用于方法因果断言。
- 发现结果与直觉不一致时保留：Wirz 的 cliffhanger 实验并未报告 enjoyment/继续观看意愿同步提高。
- 观察窗口、榜单选择和处理定义的判决是本项目应用推论，不能写成上述文献直接研究了红果。

## 文件索引

- methods_measurement.md：中文方法证据备忘录。
- methods_measurement.json：10 篇核心文献的标准化元数据、证据层级与推广边界。
- methods_crossref_verification.json：初始 query.title 搜索的实际结果与失败。
- methods_crossref_exact_doi.json：10 个精确 DOI 原始结果（含 Salganik，不含 Shmueli）。
- methods_crossref_shmueli.json：MISQ 精确 DOI 原始结果。
- methods_index_access_log.json：S2 与 Scholar 的真实失败状态。
- methods_web_search_queries.json：主要 web 搜索批次。
