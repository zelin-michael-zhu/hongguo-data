# 红果内容设计与参与：文献证据分表

检索日期：2026-11-19。内容设计、悬念、叙事节奏、弹幕/评论参与、免费模式、IP改编与续季；最终研究样本仅限红果内部。邻近平台只作理论/方法参考。

12条核心记录。Scholar主站被异常流量页拦截，不声称逐篇验证其Google Scholar收录。Crossref、Semantic Scholar API与CNKI期刊门户均已实际使用；不同出版形态与元数据冲突分别列明。

## 对选题重评的直接影响

- 不能再写‘微短剧内容设计与用户参与尚未被研究’：C01、C02、C04直接重叠，C03还已建立红果纵向多模态档案。
- 红果内部某一明确叙事机制的人工可复核测量、节目/集/片段层次对齐，以及预测外验证，仍可能构成本科贡献。仅换到红果是情境/数据增量，不自动产生问题或方法创新。
- 评论情感、弹幕密度、点赞、分享、追剧意愿、观看时长与完播率不是同一个结果变量；公开热度不可替代平台留存。
- 免费模式解释不能直接沿用付费解锁的悬念—付费转化链；IAA广告实际触发及跳过机制需要红果当前界面/记录确认。
- IP和多季应先验证红果内有足量、关系清楚的改编/续季作品。系列编号、同名、同演员不能自行当作同一IP或续季关系。

## 12条核心记录

以下“本科可贡献点”是研究设计推断，不是原论文结论。相似度针对研究问题与方法，不把邻近平台论文算成红果实证。

### C01 · Audience in the Loop: Viewer Feedback-Driven Content Creation in Micro-drama Production on Social Media

**作者/年份/出处：** Gengchen Cao; Tianke He; Yixuan Liu; RAY LC (2026). CHI 2026。peer-reviewed conference paper。

**DOI：** 10.1145/3772318.3790592。

**核验：** Crossref标题/作者/DOI/年份吻合，Semantic Scholar API与作者arXiv全文确认。S2作者名存在自动规范化差异，引用采用作者全文。

**研究问题：** 微短剧创作者的角色与工作流程如何变化；编剧如何通过观众反馈迭代人物和剧情。

**方法/材料：** 28名从业者半结构访谈与质性分析；以抖音、快手等社媒生产实践为主要背景，并讨论红果等分发基础设施。

**结论支持范围：** 评论、转发、梗等成为写作反馈，创作者在多重角色间切换；反馈驱动叙事受平台治理及商业压力约束。

**限制：** 从业者访谈能够支持工作流程解释，不能证明某类评论使红果剧本实际修改或提升留存；不能把社媒连拍连更等同于全部红果存量完整剧。

**与拟题相似性：** 与‘观众评论怎样反馈内容生产/设计’高度相似；与公开评论的情绪分析中度相似。

**本科可贡献点：** 仅限红果：把明确提出改编、人物、节奏建议的评论与一般情绪反应区分，建立可复核反馈分类；若无生产记录，研究反馈表达与创作需求，避免宣称反馈已改变剧本。

**创新区分：** 问题：笼统反馈驱动创作问题已有研究；需更窄机制；情境/数据：红果专属评论语料可能有增量；方法：内容分析/主题编码本身不新。

**原始来源：** [来源1](https://arxiv.org/abs/2602.14045) · [来源2](https://arxiv.org/html/2602.14045v1) · [来源3](https://doi.org/10.1145/3772318.3790592)

### C02 · Bridging Visual Dynamics and Reasoning Evaluation: Multimodal Large Language Models for Short Drama Quality Assessment

**作者/年份/出处：** Qingyang Liu; Jiangtong Li; Zelin Peng; Shaobo Wang; Zhaohe Liao; Shuochen Chang; Bingjie Gao; Haonan Zhao; Mu Liu; Jidong Jiang; Li Niu (2026). Proceedings of the ACM Web Conference 2026 (WWW 2026)。conference paper; author PDF and index record verified; metadata discrepancy retained。

**题名冲突：** Bridging Visual Dynamics and Narrative Reasoning: Multimodal Large Language Models for Short Drama Quality Assessment（Semantic Scholar变体）。

**DOI：** 10.1145/3774904.3792827。

**核验：** 作者页与13页PDF、公开GitHub、S2的DOI记录对应。作者版题名为Reasoning Evaluation，S2为Narrative Reasoning；本次Crossref精确DOI返回Resource not found，标题查询也未命中，不能写成Crossref已确认。

**研究问题：** 如何结合视觉、叙事逻辑和用户偏好评估短剧质量，并服务采购和推荐冷启动。

**方法/材料：** 作者报告23,472部红果短剧、26类型；用户信号形成hot value；SFT及GRPO训练多模态模型；500新剧进行两周红果排序A/B（PDF§3.1、§4.4）。

**结论支持范围：** 加入质量分后表4报告相对提升：停留时长0.101%、观看时长0.094%、完播0.286%、PV点击率0.732%。

**限制：** A/B操纵是排序器特征，不能证明悬念/反转自身的因果效果；复合用户偏好指标不等同于独立艺术质量；公开评估集不代表完整训练数据可得。题名/DOI冲突需在正式引用前继续核对ACM。

**与拟题相似性：** 对‘红果内容特征/质量预测参与或冷启动’极高重叠，不能宣称红果内容质量从未量化研究。

**本科可贡献点：** 手工可解释、范围较窄的叙事测量及误差审计；避免追求复现工业级训练与线上A/B。

**创新区分：** 问题：内容质量与偏好问题已覆盖；情境/数据：红果情境本身已覆盖；方法：简单LLM评分不是新方法；可贡献可靠性与可解释性验证。

**原始来源：** [来源1](https://www.jiangtongli.me/publication/www2026-dramaqa/) · [来源2](https://www.jiangtongli.me/uploads/papers/2026-WWW-DramaQA.pdf) · [来源3](https://github.com/Narumi-Maria/Short-Drama-Quality-Assessment) · [来源4](https://www.semanticscholar.org/paper/c9da06159bf2b55fca2edd3082b3b3d298c82e9d)

### C03 · HongguoTrending: A Longitudinal, Multimodal Archive of Trending Videos and Topics on a Leading Micro-Drama Platform

**作者/年份/出处：** Rongxin Ouyang (2026). arXiv:2611.19351v1。preprint, not verified peer-reviewed。

**DOI：** 10.48550/arXiv.2611.19351。arXiv页面标pending registration；DataCite DOI，不是Crossref期刊DOI

**核验：** arXiv摘要页、v1全文和提交历史一致。尚未验证API真实可调用性与覆盖完整性，不把论文描述当作已下载数据。

**研究问题：** 建立红果榜单可见性、参与及内容之间的纵向多模态关联档案。

**方法/材料：** 7榜单逐小时采集；63,200榜单记录、632 web list-hours和157 client hours、889部剧；链接封面、简介、视频样本和聚合参与指标。

**结论支持范围：** 探索榜单更新、题材/封面及分享与次日排名的关联；并明确回归相关性限制。

**限制：** 单匿名配置、短观察窗；榜单可能反向诱发分享；并未恢复私有热度公式。公开发布不含原始视频/转录/个人评论等，数据可用性须单独实测。

**与拟题相似性：** ‘首次构建红果纵向数据集’‘封面/简介与参与’‘分享预测排名’均高重叠。

**本科可贡献点：** 复用经验证可得的榜单/元数据，新增一个既有档案未直接测量的片段级叙事变量，并严格区分系列、集及榜单时点。

**创新区分：** 问题：泛可见性/参与关系已有研究；情境/数据：单纯红果采集不足以声称首次；方法：常规面板模型是复用；可贡献测量和复现。

**原始来源：** [来源1](https://arxiv.org/abs/2611.19351) · [来源2](https://arxiv.org/html/2611.19351v1) · [来源3](https://micro-drama.rongxin.me/)

### C04 · 都市言情微短剧的叙事惯例及其对观众情感体验和参与行为的影响

**作者/年份/出处：** 胡岑岑; 朱格 (2026). 全球传媒学刊 13(3):41–61。journal article。

**DOI：** 未找到/原页未提供。CNKI期刊原页DOI栏为空，未编造DOI

**核验：** CNKI支持的期刊原始门户，Neo实际打开，中英摘要、作者、年月、卷期页码确认；本次只获得摘要，未取得全文。

**研究问题：** 都市言情微短剧的类型化叙事如何通过情感体验关联观众参与。

**方法/材料：** 54部热门剧内容分析，2,700条评论情感分析与统计分析。

**结论支持范围：** 摘要报告主线模式、冲突/反转密度与情感体验的差异关联，进一步关联参与行为。

**限制：** 仅摘要可得，不能确认红果是否在样本内、参与操作化、具体回归和控制变量；观察性情感路径不能直接当作因果机制。

**与拟题相似性：** ‘叙事/冲突反转密度→评论情感→参与’极高重叠，是内容设计选题必须处理的近期中文先行研究。

**本科可贡献点：** 限红果的扩展/复制，考虑负面吐槽、认知困惑与积极投入的区分，或者重复悬念的饱和效应；先取得全文核对编码维度。

**创新区分：** 问题：一般内容—情感—参与链已被研究；情境/数据：红果内可复核样本和新时间窗有增量；方法：常规内容分析+情感分析不新。

**原始来源：** [来源1](https://qqcm.cbpt.cnki.net/portal/journal/portal/client/paper/6d2c638c034d262cef83d73e92ff11c6)

### C05 · New directions in vertical storytelling: creative shifts in micro-drama for mobile audiences

**作者/年份/出处：** Roy Hanney (2026). Media Practice and Education, online first:1–19。journal critical review。

**DOI：** 10.1080/25741136.2026.2705748。

**核验：** Crossref精确DOI和网页索引的出版社摘要吻合；Neo出版社页停在Cloudflare，web open亦403。本次未完成直接全文阅读。

**研究问题：** 2024–2026移动竖屏微短剧创作实践如何受到形式、平台分析、AI与观众反馈影响。

**方法/材料：** 批评性/实践导向综述，综合行业报道、平台案例及新兴学术材料；并非新因果实验。

**结论支持范围：** 将压缩连载、悬念节奏、类型循环、改编和反馈式写作理解为移动原生叙事实践。

**限制：** 行业案例和批评综合不能为具体红果用户机制提供效应量；国际平台案例不能直接当作红果样本。

**与拟题相似性：** 泛‘竖屏叙事创新’或‘AI/互动是新趋势’创新度低。

**本科可贡献点：** 将综述中的一个叙事概念缩为可检验变量，而非再罗列产业趋势。

**创新区分：** 问题：宽泛叙事趋势已有综述；情境/数据：红果具体样本可细化；方法：无需方法创新宣称。

**原始来源：** [来源1](https://www.tandfonline.com/doi/full/10.1080/25741136.2026.2705748) · [来源2](https://api.crossref.org/works/10.1080/25741136.2026.2705748)

### C06 · Investigating Responses to Narrative Cliffhangers Using Affective Disposition Theory

**作者/年份/出处：** Katherine Schibler; Lindsay Hahn; Melanie C. Green (2024). Media Psychology 27(1):1–25。journal experiments。

**DOI：** 10.1080/15213269.2023.2219456。

**核验：** Crossref精确DOI确认作者、online 2023与issue 2024；出版社摘要确认两研究及结论，开放数据链接由出版社提供。

**研究问题：** 相较主角获胜/反派获胜式结局，悬而未决结局如何影响悬念、享受与追续集意愿。

**方法/材料：** 两项实验，阅读叙事结局；不是红果平台实验。

**结论支持范围：** 悬念结局增强希望看到后续的欲望，但未发现相较解决式结局显著提高享受或主观悬念。

**限制：** 意向不等于真实续播；文本刺激不等于短剧视频；不能认为‘悬念必然更爽或更满意’。

**与拟题相似性：** 笼统‘cliffhanger提升继续消费意愿’不再新。

**本科可贡献点：** 在红果内容样本测量悬念类型、兑现距离和重复强度；分别讨论续看欲望、愉悦和困惑，避免用同一情感分数替代全部。

**创新区分：** 问题：区分悬念—欲望与悬念—享受可提供具体问题；情境/数据：红果视频扩展属于情境增量；方法：编码或小实验是标准方法。

**原始来源：** [来源1](https://www.tandfonline.com/doi/abs/10.1080/15213269.2023.2219456) · [来源2](https://osf.io/f4kv5/)

### C07 · Influence of Danmaku Comments on User Engagement in Short-Form Videos

**作者/年份/出处：** Xiaotong Sun; Fujie Jin; Jingjing Zhang (2024). ICIS 2024 Proceedings, 32; paper 2770。complete conference paper。

**DOI：** 未找到/原页未提供。AIS原页未列DOI，使用永久论文URL

**核验：** AIS Electronic Library原始记录实际打开，题名、三作者、2024、Complete paper确认。

**研究问题：** 短视频平台引入弹幕后，点赞、分享及普通评论如何变化。

**方法/材料：** 中国一家主要短视频平台弹幕上线自然实验，difference-in-differences。

**结论支持范围：** 摘要报告点赞与分享增加、普通评论减少；较小创作者、较长视频获益更大。

**限制：** 平台未在摘要中明确，本次不可假定就是红果。效应是弹幕功能引入，不是弹幕情感或剧情设计；各参与形式可能替代。

**与拟题相似性：** ‘弹幕提高参与’问题已有准实验；只看评论数可能把参与迁移误判为参与下降。

**本科可贡献点：** 红果内分别记录弹幕、评论、分享，不盲目相加；若无已确认功能变更及对照组，不模仿DiD声称因果。

**创新区分：** 问题：弹幕是否增加参与已有研究；情境/数据：红果参与形式替代可以窄化；方法：DiD只有真实干预与识别条件时可用，不是标签创新。

**原始来源：** [来源1](https://aisel.aisnet.org/icis2024/user_behav/user_behav/32/)

### C08 · Constant or inconstant? The time-varying effect of danmaku on user engagement in online video platforms

**作者/年份/出处：** Haixia Yuan; Kevin Lu; Ali Ausaf; Mohan Zhu (2025). Internet Research 35(2):771–797。journal article。

**DOI：** 10.1108/INTR-06-2023-0479。

**核验：** Crossref四作者/卷期页码/2024上线确认；Brunel作者存档与全文确认TVEM和1,019电影。仓储元数据作者列表不全，采用Crossref与PDF四作者。

**研究问题：** 弹幕数量及情感方向与参与的关系是否随视频时间而变。

**方法/材料：** Bilibili 1,019部电影，time-varying effect model，社会临场感和信息过载框架。

**结论支持范围：** 弹幕数量与valence的关系随时间变化，数量的作用较强。

**限制：** 电影与红果超短集时长结构不同；观察性模型不证明弹幕导致观看或反映全体静默观众。

**与拟题相似性：** ‘弹幕情感随时间变化’‘动态参与’已研究，不能把时间维度本身当创新。

**本科可贡献点：** 红果的集末/集首、悬念兑现前后等预定义窗口；样本较小时采用简单、解释清楚的分层模型。

**创新区分：** 问题：动态效应已有；片段叙事对齐可进一步缩窄；情境/数据：从电影到红果短集是情境数据扩展；方法：TVEM不是原创方法。

**原始来源：** [来源1](https://bura.brunel.ac.uk/handle/2438/29558) · [来源2](https://bura.brunel.ac.uk/bitstream/2438/29558/3/FullText.pdf) · [来源3](https://doi.org/10.1108/INTR-06-2023-0479)

### C09 · Continuation and desperation in contemporary multiseason television drama

**作者/年份/出处：** Jeremy Strong (2024). Adaptation 17(2):191–211。journal textual/conceptual analysis。

**DOI：** 10.1093/adaptation/apae006。

**核验：** Crossref及Oxford出版社原始摘要确认；全文需付费，本次未取得。

**研究问题：** 多季电视剧怎样管理持续连载、叙事完结和自我改编之间的关系。

**方法/材料：** 剧集、文学改编与show/pitch bible的文本和概念分析。

**结论支持范围：** 前季形成后季可沿用的叙事模型，延续本身成为明显的创作压力。

**限制：** 非微短剧/红果用户实证，不能推导续季一定提高平台热度或IP价值。

**与拟题相似性：** 多季叙事连续性/重复与新意并非理论空白。

**本科可贡献点：** 先确认红果内真实续季配对，再做角色、未结线索、回顾负担的配对文本比较；若只有少数续季，作为案例研究而非大样本回归。

**创新区分：** 问题：续季叙事问题已有理论；情境/数据：红果续季若能验证可有情境增量；方法：配对比较是标准设计。

**原始来源：** [来源1](https://academic.oup.com/adaptation/article/17/2/191/7664334) · [来源2](https://doi.org/10.1093/adaptation/apae006)

### C10 · Innovative Pathways for the Screen Adaptation (Micro-Drama) of Online Literature from a Transmedia Narrative Perspective and Its Cross-Cultural Dissemination

**作者/年份/出处：** Suya Bao (2026). Auckland University of Technology, Master of Communication Studies dissertation。master dissertation, not journal peer review。

**DOI：** 未找到/原页未提供。

**核验：** AUT官方仓储，作者/2026/学位/摘要确认；本次未逐章核对论文。

**研究问题：** 网文改编微短剧怎样重组故事世界，触发参与及跨文化接受。

**方法/材料：** 两案例Fortune Writer(2024)、How Dare You?(2025)，文本分析、观众数据挖掘、跨文化比较；摘要提出互文性、延展性、参与、跨文化四维。

**结论支持范围：** 摘要称剧情/世界观扩展与互文关系并存，弹幕、评论和二创参与改编后的意义生产。

**限制：** 学位论文证据地位单列；案例平台非红果专属，不能借它证明红果IP表现；具体数据质量需看全文。

**与拟题相似性：** 泛‘网文IP改编+观众参与’已有相近学位研究。

**本科可贡献点：** 红果可核验的原作—改编配对，测量压缩、移位、视角变化和悬念重排；研究样本严格保持红果端，原作用于确认改编关系和文本参照。

**创新区分：** 问题：笼统跨媒介改编问题不新；情境/数据：红果授权可核验配对有数据增量；方法：文本比较及参与分析不是新方法。

**原始来源：** [来源1](https://openrepository.aut.ac.nz/items/f053cf0f-8895-47d0-9125-42006ba66c9b/full) · [来源2](https://hdl.handle.net/10292/21053)

### C11 · 数字时代注意力经济下红果短剧的运营模式

**作者/年份/出处：** 刘晓晓; 杨鸿烨 (2025). 新闻传播科学 13(5):782–786。journal descriptive case analysis; lower evidentiary weight。

**DOI：** 10.12677/jc.2025.135116。

**核验：** 出版社PDF确认两作者、页码、日期；Crossref记录只列第一作者，需以PDF为准。

**研究问题：** 红果免费内容、广告变现、字节生态协同和版权运营如何组织。

**方法/材料：** 双边市场、平台生态、版权价值视角的描述性个案分析；未见可识别的用户实验或透明大样本因果设计。

**结论支持范围：** 以免费内容—广告—用户增长、跨平台协同和IP/分账说明红果运营。

**限制：** 可作当时研究对象背景，不作广告容忍度、内容升级或留存效果的因果证据；作者关于IAP到IAA转型的表述也应再用红果官方史料核对。

**与拟题相似性：** 宽泛‘红果免费商业模式创新’已有人发表；研究论文存在不等于其全部结论已充分验证。

**本科可贡献点：** 将免费模式作为边界条件，若研究广告中断则需实际红果广告位置/频率/观看任务记录；不从论文背景断言当前机制。

**创新区分：** 问题：泛运营模式描述不新；情境/数据：当期红果界面/行为记录可能新增；方法：简单个案复述不新。

**原始来源：** [来源1](https://pdf.hanspub.org/jc_3040936.pdf) · [来源2](https://doi.org/10.12677/jc.2025.135116)

### C12 · The Impact of Danmaku Ritual Types on User Digital Engagement in Video-Based Social Media: The Moderating Role of Influencer Types and Domains

**作者/年份/出处：** Xuebing Dong; Biao Wang; Wenting Chu; Raffaele Filieri; Junyun Liao (2025). Psychology & Marketing 42(10):2650–2672。journal mixed-methods study。

**DOI：** 10.1002/mar.70003。

**核验：** Crossref精确DOI和Wiley出版社摘要确认五作者、日期、卷期页码及设计。

**研究问题：** 创作者导向与信息导向弹幕仪式如何影响数字参与，以及创作者类型/领域如何调节。

**方法/材料：** Bilibili次级数据加三项在线实验，互动仪式链理论。

**结论支持范围：** 创作者导向仪式经正向社交情绪、群体认同促进参与，效应受真人/虚拟及领域范围调节。

**限制：** 创作者/网红关注与红果角色/演员粉丝并不等同；实验机制不能自动迁移到短剧叙事及真实观看留存。

**与拟题相似性：** 弹幕情绪—社群认同—参与一般机制已有较强研究。

**本科可贡献点：** 红果内区分面向角色/演员的应援、对情节的预测/吐槽与信息补充；检验分类可靠性，不简单套用网红量表。

**创新区分：** 问题：一般社交认同机制已研究；情境/数据：红果角色/演员/情节的对象区别可细化；方法：分类迁移和量表验证是测量贡献。

**原始来源：** [来源1](https://onlinelibrary.wiley.com/doi/10.1002/mar.70003)

## 补充记录与待补原文的高重叠候选

### Micro-Drama narrative engagement and marriage anxiety among Chinese college and university students: Cross-sectional associations with romantic reality comparison and mate-selection materialism

Yanli Hua、Yihuan Yuan、Shengxuan Li、Dongming Li (2026)；10.3389/fpsyg.2026.1929861。

Crossref、Frontiers原文、PubMed PMID43016792三方确认，2026-10-28。补充文献，不纳入12篇核心以免稀释内容设计重点。

2015名中国高校学生横断问卷/SEM；未记录具体平台或实际观看时长，便利/滚雪球样本，不能推断红果或因果。若走婚恋观社会影响方向必须引用，并承认量表概念重叠与自报局限。

[来源](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2026.1929861/full)

### 微短剧叙事呈现节奏对受众认知与情感的影响机制研究——基于B站微短剧及其弹幕的分析

孙鹤立、郭沛豪、汪文斌、李鹏 (2025)；DOI未核实。

存在及基本引文由C04期刊原始参考文献确认，另有全文转载。未找到该文出版社/作者原文，不把转载方法和效应细节视为完成原文验证。

拟做‘视觉节奏+弹幕语义/情感’时应视为高重叠候选并补全文核实；不能声称该组合首次提出。

[来源](https://qqcm.cbpt.cnki.net/portal/journal/portal/client/paper/6d2c638c034d262cef83d73e92ff11c6)；[转载线索，非原始来源](https://www.juduanduan.com/2025/0912/449.shtml)

## 检索日志与访问限制

所有检索均发生于2026-11-19。验证码/异常流量页面没有自动绕过，检索失败不作为“无此论文”的证据。

1. **Neo/Google Scholar**：`"micro-drama" narrative 2024 2025`。Google异常流量页；未过验证，未检索到结果。仅记尝试，不声称完成Scholar收录核查。 [检索/页面](https://scholar.google.com/scholar?q=%22micro-drama%22+narrative+2024+2025)

2. **Neo/Crossref REST**：`Audience in the Loop Viewer Feedback Driven Content Creation; rows=2`。命中C01，ACM DOI/四作者/2026确认。 [检索/页面](https://api.crossref.org/works?query.title=Audience%20in%20the%20Loop%20Viewer%20Feedback%20Driven%20Content%20Creation&rows=2)

3. **Neo/Semantic Scholar web**：`micro-drama narrative`。页面read为空，未据此宣称没有结果；改用正式Graph API。 [检索/页面](https://www.semanticscholar.org/search?q=micro-drama%20narrative&sort=relevance)

4. **Neo/Semantic Scholar Graph API**：`DOI:10.1145/3772318.3790592; title,authors,year,abstract,url,venue,externalIds`。命中C01，paperId 3ba2b7c69bbfba8dbcd2ccb19f25d4a3784f7fda，DBLP conf/chi/CaoHLL26。 [检索/页面](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3772318.3790592?fields=title,authors,year,abstract,url,venue,externalIds)

5. **Neo/CNKI主站**：`红果 短剧 叙事`。重定向安全滑块验证；没有自动操作或绕过。后续使用可公开访问的期刊原始门户。 [检索/页面](https://kns.cnki.net/kns8s/defaultresult/index?kw=%E7%BA%A2%E6%9E%9C%20%E7%9F%AD%E5%89%A7%20%E5%8F%99%E4%BA%8B)

6. **web search**：`micro drama narrative cliffhanger audience engagement 2025 2024 research DOI; danmaku engagement drama 2024 2025 DOI; Hongguo free short drama narrative 2025 journal DOI`。发现C01/C05/C06/C11及若干低透明度刊物；核心条目优先出版商和作者/机构原文。

7. **web search**：`"danmaku" "2024" "engagement" journal; "danmaku" "2025" narrative engagement comments; "short drama" "IP adaptation" "2024" journal; "short drama" "free" "2025" audience research Hongguo`。发现C07/C08/C12、直播电商邻近研究；直播购物结果不直接用作红果短剧效果证据。

8. **web search**：`microdrama adaptation 2024 academic; microdrama seasons 2025 academic; 短剧 IP改编 2024 知网; 短剧 多季 论文 红果`。发现C09/C10及跨文化/低透明度候选；未据此断言红果具有足量续季/IP配对。

9. **Neo/Crossref REST exact DOI**：`10.1080/25741136.2026.2705748;10.1080/15213269.2023.2219456;10.1002/mar.70003;10.1177/20594364261440574`。四条精确记录成功；C05/C06/C12元数据确认。另验证Roussel2026访谈研究但未纳核心12篇。

10. **Neo/Crossref REST**：`Constant or inconstant time varying effect danmaku; select=title,author,DOI,published,container-title,volume,issue,page`。C08精确命中，四作者、2024上线、35(2):771–797确认。

11. **Neo/Crossref REST exact DOI**：`10.1145/3774904.3792827;10.3389/fpsyg.2026.1929861;10.1093/adaptation/apae006;10.12677/jc.2025.135116`。DramaQA返回Resource not found；其他三条成功。Hans记录缺第二作者，以出版商PDF两作者为准。

12. **Neo/Crossref title query**：`Bridging Visual Dynamics and Reasoning Evaluation Multimodal Large Language Models for Short Drama Quality Assessment;rows=3`。前3返回其他论文，不能标记DramaQA已在Crossref命中。

13. **Neo/Semantic Scholar Graph API**：`DOI:10.1145/3774904.3792827;title,authors,year,url,externalIds`。命中paperId c9da06159bf2b55fca2edd3082b3b3d298c82e9d；题名Narrative Reasoning，与作者版Reasoning Evaluation不同；保留冲突。 [检索/页面](https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3774904.3792827?fields=title,authors,year,url,externalIds)

14. **Neo/publisher & author pages**：`arxiv 2602.14045v1;arxiv 2611.19351v1;AISeL ICIS2024/32;AUT handle10292/21053;Jiangtong Li DramaQA page`。实际打开并读取原始页面；C01/C03全文、C07/C10原始摘要元数据和C02作者来源确认。

15. **Neo/Taylor & Francis**：`10.1080/25741136.2026.2705748`。Cloudflare安全验证；web open也403，仅使用Crossref与可索引出版社摘要，不宣称全文已读。

16. **web search/CNKI期刊门户**：`site:cnki.net 红果 微短剧 叙事 2025;site:cnki.net 微短剧 弹幕 用户 参与 2024;site:cnki.net 微短剧 IP 改编 2024`。发现C04及若干中文论文。CNKI主站不可用不代表CNKI期刊门户不可读。

17. **Neo/CNKI期刊门户**：`C04 paper 6d2c638c034d262cef83d73e92ff11c6`。原页中英文摘要、54剧/2700评论、卷期页码、发布日期、作者确认；DOI为空；全文未取得。 [检索/页面](https://qqcm.cbpt.cnki.net/portal/journal/portal/client/paper/6d2c638c034d262cef83d73e92ff11c6)

18. **web search**：`"微短剧叙事呈现节奏对受众认知与情感的影响机制研究";同题+孙鹤立 DOI;同题 site:cnki.net`。C04原始参考文献确认引文，另找到剧短短/搜狐转载；未找到该论文原始全文或DOI，列待补核候选。

19. **web/publisher PDF**：`DramaQA PDF§3.1,§4.4,Table4`。确认23,472红果剧/26类型、500新剧两周A/B及四项相对提升；数据发布边界不推定为全训练集。 [检索/页面](https://www.jiangtongli.me/uploads/papers/2026-WWW-DramaQA.pdf)
