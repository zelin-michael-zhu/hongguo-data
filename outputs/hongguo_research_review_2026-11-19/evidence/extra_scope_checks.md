# 原始状态字段与研究门槛补充核验

核验日：2026-11-19。此为主报告的独立补充检查，不是新增研究结果。可复算脚本为 [extra_scope_checks.py](extra_scope_checks.py)，完整计数、逐日分布、24次状态转移及原始文件哈希为 [extra_scope_checks.json](extra_scope_checks.json)。本次仅保存作品级元数据与校方指南条款，不新增参与者或用户身份资料。

## 1. 36份原始JSON实际包含什么

源目录：`/var/folders/3c/rp2p0_4x7blcyb18cf7ylssh0000gn/T/hongguo-tool-probe-ocpwhkae/radar/data/snapshots/hongguo/`。逐个读取36份日期JSON，未使用CSV回填值。

| 检查 | 独立复算结果 | 对研究建议的影响 |
|---|---:|---|
| 日期、作品日、作品ID | 2026-10-13至11-17；22,901行；1,388个ID | 与主报告总规模一致 |
| `status_code` | 1：22,663行，98.96%；0：238行，1.04%；无缺失 | 不得把空的`status_tags`当缺少原始状态字段 |
| 曾出现状态码0的作品 | 25个ID；其中12个同时出现过0和1 | 有候选连载状态，但规模小且标签会改变 |
| 状态转移 | 24次，涉及12个ID；0→1为16次，1→0为8次；全部发生于相邻日期 | 不支持直接定义为一次性的“真实完结”处理事件 |
| `episodes_total` | 有值21,534行；缺失1,367行 | 缺失全部集中于10/13–16四天迁移快照，不是随机缺失 |
| `episodes_total`与`episodes` | 21,534个非缺失值全部相等，零例不同 | 这里没有提供独立的最终计划集数/剩余集数 |
| `episodes`相邻观测变化 | 238对，93个ID；增加171次、减少67次 | 集数变动还可能包括删除、重编排或修订，不能一律算更新供给 |
| `episodes_total`相邻有值观测变化 | 225对，88个ID | 字段名中的total不意味着不可变的最终总集数 |

解析代码原始锚点：`radar/sources/hongguo/parse.py:248–250`分别取`episode_cnt`、`series_episode_info.episode_total_cnt`、`series_episode_info.series_status`；`source.py:255–257`只在详情解析有值时加入这些字段。代码没有给出状态码含义的官方字典。故本检查先报告数字0/1，不把编码语义当作已核实的不可变平台承诺。

可人工复核的例子：

- `7675288927619533886`：11/03状态0、961集；11/04状态1、961集；11/05又为0、962集；11/06为1、1000集。
- `7699513062054710296`（nova：新星）：11/08状态1、43集；11/09状态0、43集。不能从这一翻转推断开播、完结或新增一集。
- `7690948774083955736`：10/24状态1、160集；10/25仍为1但190集；10/26转0、195集。状态和供给变动并非一一对应。

**建议修正**：若主报告写“历史没有完结状态字段”，应改成“CSV未导出该字段，但原始JSON有status_code；编码语义、往返变更与时效性未充分验证”。若写“有25部可靠连载/16次真实完结”，则证据不足。任何完结事件研究都需额外核验页面状态、首次/持续转换与内容重编排，当前样本也不足以自动满足因果设计。

## 2. T01是否已有可信真实更新时间表

结论是**当前仍未通过材料关，不能按已具备6–8部材料来推荐实施**；这不是证明红果不存在更新安排。

- 25个曾出现码0的ID可作为核查候选，当前观察仅落在AI/漫剧榜追踪路径，没有一个曾由`real`榜追踪。它们不直接提供真人连载材料库。
- 11/19实际读取[官方nova详情](https://hongguoduanju.com/detail?series_id=7699513062054710296)及[其分集页](https://hongguoduanju.com/player/7699513062054710296)：可观察现有选集至60集，但在本次页面正文未读到未来哪天更新几集的排期。只留存作品元数据摘要，见`raw/t01_nova_metadata_only.json`。
- 本次两轮8条检索包含`site.hongguoduanju.com 更新至 每`、`红果短剧 每周 更新 官方`、`红果短剧 更新日历 官方`、`红果短剧 更新时间 每天 官方`等；未取得可验证的指定作品官方更新日历。大量命中的是其他域名自称官网。另有新浪“观剧日历/明日10:00更新”文章明确标注“本文由AI生成”，不能用来证明官方功能或指定作品排期。
- [官方预约榜](https://hongguoduanju.com/rank/subscribe-drama)确有预计上线日期，但这是待播首发时间；不能替代已连载作品的逐集更新时间表。

**T01实施前的具体门槛**：逐部留存带日期的官方剧页/已核实创作者公告，明确区分红果版本与抖音版本，记录已可观看集数、真实未来排期、排期变更与核查时点。若最终计划集数未知，不应由`episodes_total`编出“剩余多少集/何日完结”。只有在准备到足够的可比真实材料并完成操纵预试后，才保留“真实时间表披露”设计；否则改为明确的模拟情境或测量审计，并相应改变结论范围。

## 3. 主报告样本门槛的数值复核

T01“约350名独立参与者检测约15个百分点差异”作为粗略规划量级合理。独立两组、等额分配、双侧α=.05、power=.80的正态近似，0.50→0.65约需340人，0.425→0.575约需348人。它未包含失访、无效作答、多结果检验、复杂区组或重复任务的设计影响，不能当普适保证；20%流失时348名有效样本约需招募435人（为等额分组可向上取偶数436）。

20–40人Pilot只适合检查题目理解、操纵和招募流程，不能声称已具备检验中小效应的功效。其他50部作品、100部阈值作品、20–30系列家族等应继续标为设计/Pilot目标；没有独立的效应、变异和依赖结构假设，不能升级为充分样本量或统计门槛。

## 4. 原始FYP指南的作者与伦理条款

以下锚点重新从两份原始DOCX的OOXML逐段提取，与11/02的paragraphs.txt逐段编号相同；源文件哈希及精确英文条款保存在`extra_scope_checks.json`和[guidance_key_clauses_verified.txt](guidance_key_clauses_verified.txt)。未读取学生名单、联系方式或成绩资料。

| 原始来源与段落 | 原文规定及适用边界 |
|---|---|
| BUSA Guidance P1、P4、P6 | 标题为AY2026–27 BCom；说明当年所有BUSA学生及导师注意，BCom沿用BBA的CA、rubrics和workflow（课程在第二学期注册） |
| BUSA Guidance P8 | BUSA必须使用该文件所附BCom模板/表格，而不是BBA模板 |
| BUSA Guidance P260 | 提交声明要求是学生原创作品，未作为其他学位提交，原始资料来源均应正确引用和致谢 |
| BUSA Guidance P166 | Acknowledgement应认可导师及其他参与者贡献 |
| BBA Manual P140 | AI-assisted Writing Tools一般禁止用于BBA project，并提及AI检测与返工。这是明确写作政策；不能把AI生成的本次评估直接当学生可提交的论文。BCom引用BBA workflow，但具体允许的工具用途应按课程/导师现行解释，不能自行假定全面获准 |
| BBA Manual P152 | 建议保存全部研究数据；考试委员会可要求提交以核验和澄清报告结果。原始响应、失败记录、清理规则与分析代码保留有直接核验价值 |
| BBA Manual P300 | 涉及human participants的FYP必须获得BNBU Research Ethics Committee批准。T01–T05实验、访谈及T07真实用户任务都须纳入该要求；建议把批准作为招募与收集参与者数据的前置条件 |

本次没有从这两份指南读到可直接引用的匿名化/保存年限/平台抓取许可详细条款，不能补写成校方已经明定。去标识、数据最小化与版权素材处理可作为研究设计建议，仍需遵从实际伦理审批及平台条款。

原始文件：

- [BBA FYP Operational Manual 2026–27](</Users/zhuzelin/Desktop/fyp/4 FYP Operational Manual 2026-27.docx>)
- [AY2026–27 BUSA FYP Operational Guidance](</Users/zhuzelin/Desktop/fyp/5 AY2026-27 BUSA FYP Operational Guidance (Based on BBA FYP Operational Manual).docx>)

## 5. 11月27日的对象、学年和交付件

**2026年11月27日是本学年BUSA/BCom的Project Proposal截止，不是Final Project Report截止。** BUSA Guidance P1/P4界定AY2026–27及BUSA对象，P81明确“project proposal is due November 27, 2026”；BBA Manual P247–248的年度schedule对应“Submission of project proposal, and (if needed) the application for ethics approval”。

BBA年度schedule P262–263、P301写最终报告截止为2027-04-23 15:00。该手册P136另残留April30,2026、P270另残留May14,2026，与年度schedule及后文注释冲突，不能从这些旧年份段落推定本年最终交付日期；应优先核当年课程通知。BUSA P81这条11/27提案日期在专属指南与年度schedule中一致，核验较稳。
