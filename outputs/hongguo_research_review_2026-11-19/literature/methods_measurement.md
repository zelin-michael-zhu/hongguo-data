# 红果 FYP：测量、预测、实验与因果识别的方法证据包

检索日期：2026-11-19。范围：本科可执行研究设计；已知数据条件为 36 天精选榜单面板。本文件是供总评整合的方法备忘录，不是完整项目报告。以下对红果数据的判断是将已核验方法文献应用于该数据条件所得的研究设计推论；文献本身没有审计红果。

## 研究问题与检索边界

1. 公开展示的热度、播放、点赞、评论等数字，在什么条件下能代表所声称的构念？
2. 只有被精选榜单收录的短面板，能支持哪些描述或预测，哪些因果结论尚未识别？
3. 不依赖平台合作的本科实验，怎样把社会信息或悬念操纵变成可解释的因果估计？

按测量审计、推荐反馈与社会信息、预测评估、面板因果四条路径检索。优先 2024–2026 年方法或审计论文，并保留解释预测区分、社会信息实验和 RDiT 的必要早期原文。未在本轮定向检索中核验到可直接等同于“红果短剧选择”的 2024–2026 年高质量随机现场实验；这表示本证据包的检索边界，不能写成该领域不存在实验研究。

## 10 篇核心文献：已核验题名、作者、年份、方法和链接

| ID | 文献与年份 | 方法、可支持的论点 | 对本项目的具体边界 |
|---|---|---|---|
| M01 | George D. H. Pearson, Nathan A. Silver, Jessica Y. Robinson, Mona Azadi, Barbara A. Schillo, Jennifer M. Kreslake. **Beyond the margin of error: a systematic and replicable audit of the TikTok research API.** *Information, Communication & Society* 28(3), 452–470；2024-11-07 online，2025 卷期。[出版社](https://www.tandfonline.com/doi/full/10.1080/1369118X.2024.2420032?af=R) | 两个研究团队、两个主题语境，将 Research API 与网页前端的元数据和视频可得性对照。摘要报告，2024 年 7 月前数据的多个互动指标存在差异，播放计数问题尤为明显。 | 可据此要求红果做自己的来源对账与指标审计；不能从 TikTok 结果推断红果必然有同一种错误，也不能把前端当成已验证的真实观看人数。 |
| M02 | Smitha Milli, Micah Carroll, Yike Wang, Sashrika Pandey, Sebastian Zhao, Anca D. Dragan. **Engagement, user satisfaction, and the amplification of divisive content on social media.** *PNAS Nexus* 4(3), pgaf062，2025。[DOI](https://doi.org/10.1093/pnasnexus/pgaf062)；[作者最终预印本 v6](https://arxiv.org/html/2305.16941v6) | 预注册算法审计：806 位用户的真实算法 feed 与逆时间 feed 候选内容，随机顺序展示后逐条评价。互动导向的排序与自报偏好并非同一构念；不同类别结果也有差异。 | 最终版称 algorithmic audit。随机的是评价时的呈现顺序，不能改写为长期随机分配真实 feed 的现场 RCT；更不能把 Twitter 政治内容结论直接搬到短剧。 |
| M03 | Allison J. B. Chaney, Brandon M. Stewart, Barbara E. Engelhardt. **How Algorithmic Confounding in Recommendation Systems Increases Homogeneity and Decreases Utility.** *RecSys 2018*, 224–232。[DOI](https://doi.org/10.1145/3240323.3240370)；[Princeton 原文](https://oar.princeton.edu/bitstream/88435/pr1zc2c/1/RecSystemsUtility.pdf) | 推荐系统与用户选择共同生成后续训练数据的模拟实验，演示反馈循环及 algorithmic confounding。 | 公开互动是曝光政策与用户反应的联合产物。该文是模拟机制证据，不是红果算法的实证审计，也不证明所有推荐系统都会产生同样结果。 |
| M04 | Lev Muchnik, Sinan Aral, Sean J. Taylor. **Social Influence Bias: A Randomized Experiment.** *Science* 341(6146), 647–651，2013。[DOI](https://doi.org/10.1126/science.1240466)；[原作者解释](https://seanjtaylor.com/2013/08/08/science-paper-on-social-influence-bias.html) | 在真实社交新闻站点随机施加先行正负评分，观察后续评分和聚集效应。正负社会信息的反应不对称。 | 为随机化显示社会信息提供方法依据；既有高评分与后续高评分的相关不能区分质量与社会影响。效应大小不应直接作为短剧实验的预期效应。 |
| M05 | Dominique S. Wirz, Alexander Ort, Björn Rasch, Andreas Fahr. **The Role of Cliffhangers in Serial Entertainment: An Experiment on Cliffhangers’ Effects on Enjoyment, Arousal, and Intention to Continue Watching.** *Psychology of Popular Media* 12(2), 186–196，2023 卷期；机构库标记 2022。[DOI](https://doi.org/10.1037/ppm0000392)；[作者机构库与摘要](https://folia.unifr.ch/unifr/documents/319990) | N=133 的实验，观看 3–4 集剧集，结尾有无 cliffhanger；测量自报与生理唤醒。报告唤醒上升，但未发现 enjoyment 或继续观看意愿随之上升。 | 这是反证：悬念、唤醒、喜欢、继续观看不应互换。未发现显著提升不等于证明任何短剧场景下效应恒为零；该文也不是移动微短剧现场实验。 |
| M06 | Galit Shmueli, Otto R. Koppius. **Predictive Analytics in Information Systems Research.** *MIS Quarterly* 35(3), 553–572，2011。[DOI](https://doi.org/10.2307/23042796)；[AIS 官方记录](https://aisel.aisnet.org/misq/vol35/iss3/5/) | IS 方法研究论文，以 TAM 转换案例说明解释与预测在建模、评估和研究价值上不同。解释力不能自动推出预测力。 | 一个透明、有时间外检验的短剧预测项目可以有 IS 价值；高预测精度或 SHAP 重要性不能被表述为某特征造成热度。 |
| M07 | Sayash Kapoor 等 19 位作者（完整作者见 JSON）. **REFORMS: Consensus-based Recommendations for Machine-learning-based Science.** *Science Advances* 10(18), eadk3452，2024。[DOI](https://doi.org/10.1126/sciadv.adk3452)；[作者机构原文](https://pure.hw.ac.uk/ws/portalfiles/portal/126539339/sciadv.adk3452.pdf) | 共识与文献综合形成报告清单，覆盖研究目标、数据质量、预处理、建模、泄漏、评估、不确定性及推广边界。 | 要先写预测时点、目标、人群和可用信息集合，再做切分；报告模型不能替代数据与标签可靠性的论证。 |
| M08 | Kirill Borusyak, Xavier Jaravel, Jann Spiess. **Revisiting Event-Study Designs: Robust and Efficient Estimation.** *The Review of Economic Studies* 91(6), 3253–3285，2024。[出版社原文](https://academic.oup.com/restud/article/91/6/3253/7601390) | 对错峰处理及异质效应给出明确假设、目标参数和 imputation estimator；传统 TWFE event-study 在异质效应下可能不估计目标量。 | 换成现代 DID 估计器解决特定估计问题，不会让内生入榜、缺失反事实或不可信平行趋势消失；该框架不能替项目创造外生处理。 |
| M09 | Albert Chiu, Xingchen Lan, Ziyi Liu, Yiqing Xu. **Causal Panel Analysis under Parallel Trends: Lessons from a Large Reanalysis Study.** *American Political Science Review* 120(1), 245–266，2026 卷期，2025-06-09 online。[出版社原文](https://www.cambridge.org/core/journals/american-political-science-review/article/causal-panel-analysis-under-parallel-trends-lessons-from-a-large-reanalysis-study/219275E0CE901F099F2CFFBA07079243) | 对 49 项已发表研究重新分析，用六种异质效应稳健估计器、诊断和敏感性分析比较。强调研究设计、平行趋势证据与功效；不显著预趋势不能视为已证实平行趋势。 | “有剧固定效应和日期固定效应”只说明回归结构；不等于已识别因果。2026-06-24 [更正](https://www.cambridge.org/core/journals/american-political-science-review/article/causal-panel-analysis-under-parallel-trends-lessons-from-a-large-reanalysis-study-corrigendum/CE7CFC9513F2A3451CDDAC17C3E43040)仅纠正 Figure 5 两个案例面板互换，本包不使用其个案图。 |
| M10 | Catherine Hausman, David S. Rapson. **Regression Discontinuity in Time: Considerations for Empirical Applications.** *Annual Review of Resource Economics* 10, 533–552，2018。[DOI](https://doi.org/10.1146/annurev-resource-121517-033306)；[作者机构原文](https://haas.berkeley.edu/wp-content/uploads/WP282R.pdf) | 方法综述讨论时间作 running variable 时的自相关、短长期效应、远离阈值的观测及同期事件问题；有些 RDiT 更接近 event study。 | 给“新剧上线第 3 天”画断点不会自动产生 RD。必须先存在可信、事先规定并真正改变处理概率的制度阈值，还需排除自然生命周期与同期变化。 |

## 测量：先验证数字代表什么

M01 指出来源之间可能不一致，M02 则指出即使数字无采集错误，行为指标与评价构念仍可不同；这两类问题应分别审计。对本项目，至少记录每字段的前端原标签、数据来源、采集时刻、累计/当日属性、计数单位、展示精度、是否为平台计算的综合指数。热度若是未知复合分数，就称“平台展示热度”，不能重新命名为观看人数、满意度、留存或收益。

抽取同剧同刻的前端与采集值对账；跨日识别负差分、突然重置、单位变化和延迟刷新；保存截图或原始响应。展示为“1.2 万”的数值带有舍入区间，直接相减可能得到没有真实精度支持的日增长率。播放也可能计次而非去重人数，点赞和评论的分母若没有曝光人数，则只能报告计数或份额，不能称点击率、完播率或用户转化率。这些是本项目应做的审计要求，不是文献已经发现红果存在的事实。

## 只有 36 天精选榜单时，可识别的结论

可以做：（a）该窗口该榜单内的作品构成、名次变动、进入退出、可观测指标共变；（b）明确限定在“当前已入选榜单作品”上的下一日榜单存续/名次预测；（c）端点均被观察到时的展示指标变化预测，但必须交代因此产生的幸存者选择。若每日榜单完整，次日是否仍在榜是可定义的标签；离榜不意味着播放为零，也不意味着某计数停止增长。

不能仅据此推断全平台“什么内容导致成功”、算法推荐的净效应、入榜的因果效应或悬念对留存的因果效应。作品质量、宣发、演员知名度、推荐曝光和先前热度都可同时影响入榜与后续表现。条件化于入榜还可能产生选择偏差。M03 的反馈机制与 M04 的随机社会信息实验共同说明：观察到的成功既可能反映质量，也可能反映曝光和路径依赖；从面板回归中无法自动拆开这些部分。

36 天本身不是“绝对不能估计”的数学阈值，但限制了时间外测试、生命周期覆盖和可用事件窗口；同一作品的多个日记录也不是等量独立样本。若只在榜时采集，第一次出现是首次被本数据观察到，不是作品首次上线，也通常没有入榜前完整结果序列。

## 四类常见识别错误及可修复条件

| 拟议做法 | 为什么当前不足 | 何种新增证据才可能改变判断 |
|---|---|---|
| 将榜单入榜当随机处理，用 FE/DID 比较入榜后增长 | 入榜往往由先前表现与平台选择决定；只有入榜样本可能既没有未入榜比较组，也缺入榜前结果。DID 可容许非随机处理，但需要可信反事实平行趋势、无预期等假设；回归加入 FE 不提供这些假设。 | 获得候选全集及入榜前后结果、清晰曝光变化和选择规则；提出可以被反驳的识别设计。若有真实随机展示/轮换则优先用随机化。 |
| 把第 3 天的新剧标签或研究者自定分组当 RD | 研究者定义的 age≤3 不等于处理概率在 3 天跳变；年龄本身伴随自然热度衰减、发行节奏和留存变化。离散天数且窗口短时局部比较尤其有限。 | 平台明确的预定规则，并验证第 3 天确实改变曝光/资格；足够接近两侧观测、没有同期干预、潜在结果连续性等。若只是描述年龄差异，称生命周期相关。 |
| 在一部剧中以弹幕峰值识别“悬念提升参与/留存” | 弹幕是选择性响应，峰值可能来自笑点、争议、演员、重复刷屏或更多人看到了该处。剧 FE 不能消除场景位置、观众流失与剧情推进的时间变混杂；用同一弹幕峰值定义“悬念”又以弹幕作结果是循环测量。 | 先由不知道结果的独立编码者标剧情；最好随机分配同一素材的结尾版本，收集真实继续点击/观看。观测分析若没有分段观看人数，只能研究评论时点分布，不能叫留存机制。 |
| 看 pretrend 不显著、换现代 DID 或做几次 placebo 就宣布因果 | 不拒绝零可能是功效不足；现代估计器与稳健标准误改变估计/推断，不能验证未观测的反事实。M08 与 M09 均将估计问题和识别假设分开。 | 事前论证选择机制、合理比较组、可解释的负对照/敏感性分析；若仍无可信处理，则保持关联语言。 |

真正的排名 cutoff RD 并非原则上不可能，但需要预先固定的连续排序分数、阈值两侧完整候选、可信的曝光跳变和连续性论证。只有精选榜上作品的名次、没有阈值下方作品与打分规则，尚不足以实现这种设计。Top-K 的竞争也使无干扰假设需要专门讨论。

## 本科优先设计：一个处理、一个主要行为结果

**路线 A：随机显示社会信息。** 在自行搭建的短剧选择页面，保持同一作品的封面、标题、简介、位置相同，按参与者随机分配“显示真实来源且固定的热度/收藏信息”或“隐藏该信息”。使用多部预先选定作品并平衡位置，分析保留参与者层面的随机化单位。主要结果预先指定为点击哪部/是否点击继续看；若只能问观看意愿，就准确称意愿。该设计估计的是实验页面里“显示这类信息”的平均因果效应，而不是红果真实推荐算法或全平台热度的因果效应。它比先改计数、封面、榜单位置再解释一个综合差异更容易说明处理是什么。M04 提供随机社会线索的方法依据，M02 提醒需要把行为与自报价值分开。

**路线 B：随机分配结尾版本。** 保留相同剧情前缀，制备悬念结尾和解决结尾，尽量匹配时长、画质、音乐强度及人物信息；预试测量主观悬念，主要结果用是否选择下一集及实验中实际继续观看时长。这个处理通常改变“结尾是否解决冲突”这一组合，不能把所得差异自动解释为纯粹的心理悬念中介效应。M05 表明唤醒与继续观看可能分离，因此不能只量唤醒或弹幕数就宣布提升追剧。

二者优先选一个；不要在有限本科样本中同时做多种剧情、社会证明、性别差异、交互与多重中介后挑显著结果。无平台合作不妨碍对自行构建情境做随机实验；结论的外部效度要限定于样本、素材和场景。参与者招募、刺激版权/真实信息来源、退出条件与适用的学校伦理要求应在实施协议中具体化。

**功效不是保证。** 两组等量、独立个体、连续结果、双侧 α=.05、80% 功效的正态近似为每组 n≈15.7/d²：d=.5 时约 63/组，d=.4 约 99/组，d=.3 约 175/组，尚未计流失、多重检验或群组相关。若主要结果是二元点击且基线约 50%，检测 10 个百分点差异通常约需 390/组。小样本更适合将结果定义为有置信区间的先导实验；重复给同一人看多部剧，不会自动把独立样本量乘上剧数。上述为本包的设计计算，不是引用文献的效应大小。

## 若保留预测路线：时间外验证与最小基线

用 M06 的 IS 区分先固定预测目标：在 t 日采集完成时，用当时可得信息预测 t+1 日“仍在该榜单”或一个明确的可观测变化。按照 M07 报告人口、标签形成、缺失机制与可用信息集合。只对当前已入榜作品训练的模型，其性能不能外推为全平台新剧发现能力。

按日历时间滚动训练/验证/最终测试，不能将相邻作品日行随机 80/20 分开；若目标有 h 天未来窗口，训练标签必须在测试预测时点之前已经可获得。把未来累计评论、未来名次、全窗口最高热度、全窗口聚类标签、用全数据拟合的插补/标准化/词表带回 t 时点均可能泄漏。窗口重叠与标签成熟时间要显式处理。若要声称预测未见过的新作品，需要另做按作品留出的冷启动评估；它和“旧作品的未来日期”是两个不同推广问题。

官方 [scikit-learn TimeSeriesSplit 文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)也将训练未来、评估过去列为时间数据普通交叉验证的问题，但直接按行调用 TimeSeriesSplit 不足以处理多作品同一天的面板：必须将同一个日历日整体分配到同一折，并按预测时点处理标签间隔。

至少与“明日等于今日/当前名次”“最近可得增速”“简单正则线性或逻辑模型”比较，再考虑树模型。分类报告基准率、PR/ROC 或 Brier 等与任务匹配的指标及时间分段表现；连续目标优先展示 MAE/排名误差等直观量。样本外性能提升说明预测信息增量，不能把 SHAP、相关系数或高 R² 写成因果机制。

## 检索与核验说明

- Crossref：先尝试 query.title（部分请求被环境代理返回 Tunnel 503，且 top-1 曾返回 working paper 而非期刊版本），随后对 10 个候选 DOI 精确查询，均 HTTP 200；另对 M06 精确查询 HTTP 200。未经人工比对的首个检索命中不被当作最终引文。
- Semantic Scholar Graph API：一次公开检索请求因本环境代理 `Tunnel connection failed: 503 Service Unavailable` 失败；不能据此声称 S2 无文献。
- Google Scholar：直接公开题名检索请求同样因环境代理 Tunnel 503 失败；web 索引检索未取得可核验的 Scholar 记录。本包不使用未经核验的 Scholar 被引量或搜索结果数。
- 出版社/作者来源：Cambridge、Oxford REStud、AIS、作者机构库、arXiv 可用于核验；部分 Science/Taylor & Francis 直接打开 403，PMC 部分打开出现 reCAPTCHA，Oxford PNAS Nexus 有工具重定向限制，APA DOI 有 restricted URL。对应条目使用可核验的出版社摘要、作者最终预印本或机构库，并注明访问层级。M01 的详细样本量与分项表格未核验，不作表格级断言。
- 日期处理：M01 用 2025 卷期并保留 2024 online；M05 用 2023 卷期并保留机构库 2022；M09 用 2026 卷期并保留 2025 online。M02 Crossref print/online 日份不一致，但年份均 2025；本包不依赖具体上线日。

机器可读证据为 `methods_measurement.json`；检索式、原始元数据与访问状态分别保存于 `methods_web_search_queries.json`、`methods_crossref_verification.json`、`methods_crossref_exact_doi.json`、`methods_crossref_shmueli.json`、`methods_index_access_log.json` 和 `methods_search_log.md`。
