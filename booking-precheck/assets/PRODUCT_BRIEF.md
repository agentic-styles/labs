# 订舱预审样例工程 Product Brief

## 1. 文档信息

- 产品代号：Booking Precheck Workshop Sample
- 版本：0.4
- 状态：Conditional Freeze（待 DG SME 确认五项教学假设）
- 目标用途：两天 Agentic AI Workshop 的教学样例与课程设计依据
- 产品性质：离线、合成业务数据、非生产、非真实合规决策系统

## 2. 一句话定义

本应用在收到 Booking Request、初步 DGD 和 SDS Extract 后、DG Desk 正式审批前执行文件预审；它只识别资料缺失、跨单证矛盾和教学规则快照冲突，不负责危险品分类，也不代表承运人最终批准或拒绝订舱。

## 3. 背景与问题

危险品订舱预审需要同时阅读不同格式的订舱资料，核对其中的危险品、重量、包装、航线和船期事实，再应用特定版本的承运人及设施规则。真实流程中的资料来源多、表述不完全一致、规则会变化，部分结果必须由不同业务角色复核，因此适合用于演示事实提取、专业角色协作、证据链、人工兜底和效果评估。

Workshop 不尝试复制真实承运人的完整业务。样例将问题压缩为一条固定教学航线、三类合成单证、一个冻结规则快照，以及两套可重复评测数据。

## 4. 产品目标

样例工程应让学员能够：

1. 从三类半结构化单证中提取并归一化 Booking 事实。
2. 识别必填资料缺失和跨单证不一致。
3. 使用固定版本的规则快照产生可重复的预审结果。
4. 为每项结论提供命中规则、输入事实和文档来源证据。
5. 将补件、冲突或需要专业判断的问题交给指定责任队列。
6. 区分 Agent 的事实提取与确定性规则的业务裁决。
7. 使用规则测试集和业务验收集评估不同方案。

## 5. 非目标

本阶段不包括：

- 最小架构设计或技术框架选型。
- Agent、规则引擎、UI、API 或数据库编码。
- 连接真实订舱、港口或客户系统。
- 实时抓取承运人或港口政策。
- 评测 OCR 引擎本身；测试数据中的抽取置信度为预置或模拟值。
- 自动确定真实货物的 UN Number、IMDG Class、Packing Group 或 Proper Shipping Name。
- 对真实货物作出批准、拒载或法律合规判断。
- 使用真实客户、交易方或承运人政策数据。
- 复制或分发需要商业授权的 IMDG Code 数据集。

## 6. 用户与业务阶段

### 6.1 主要用户

- Workshop 学员：1–2 年经验的应用开发人员、产品经理和 BA。
- 课程参与者：运行基线、评审结果、注入 bad case 并完成重构实验。
- 业务评审者：确认业务术语、合成规则和预期结果是否适合教学。

### 6.2 预审起点

业务人员已经收到：

1. Booking Request；
2. 客户提供的初步 DGD；
3. 与货物对应的 SDS Extract。

### 6.3 预审终点

系统输出预审状态、全部命中原因、证据和下一步动作。通过预审的票单进入 DG Desk 后续审批；未通过的票单进入补件、人工复核或暂停自动处理流程。

## 7. 固定教学范围

### 7.1 航线与承运人

| 项目 | 固定值 |
|---|---|
| 承运人 | `TRAINING-LINE`（完全虚构） |
| 规则快照 | `TRAINING-LINE-CNSHA-AEJEA-2026-08-01` |
| 起运港 | `CNSHA` 上海 |
| 起运设施 | `CNSHA-TRAIN-T1` |
| 目的港 | `AEJEA` Jebel Ali |
| 目的设施 | `AEJEA-TRAIN-T1` |
| 服务代码 | `TRAIN-ME1` |
| 默认船舶运营人 | `TRAINING-LINE` |
| 快照冻结日期 | `2026-08-01` |
| 快照有效期 | `2026-08-01` 至 `2026-12-31` |

### 7.2 货物范围

- 主样例货物：`UN1263 PAINT`，IMDG Class 3，Packing Group III，闪点 30°C。
- Class 1、Class 7、低闪点 Class 3 等仅用于负向规则测试。
- 箱型范围：`20GP`、`40GP`、`40HQ`、`20RF`、`40RF`。
- 公司、商品、设施、船舶运营人及承运规则均为合成教学数据。
- UN Number、Proper Shipping Name 和 IMDG Class 使用代表性运输分类术语，不宣称是合成编码；正式授课前须由 DG SME 对基线组合做一次业务确认。

### 7.3 三类合成单证

1. Booking Request：航线、交易方、货物、箱型、件数和重量。
2. Preliminary DGD/MDGF：UN Number、Proper Shipping Name、IMDG Class、Packing Group、Marine Pollutant、包装、件数、重量及声明状态。
3. SDS Extract：SDS Section 1、9、14 的教学摘录，不表示完整的 16 节 SDS。

SDS Section 14 的存在性检查属于 `TRAINING-LINE` 的合成教学规则，不表述为普遍法规要求。

## 8. 输入、归一化事实与 Golden Dataset

| 层次 | 用途 | 是否由业务用户直接提供 |
|---|---|---|
| Source Documents | Markdown/PDF/文本形式的三类单证，是 Agent 路径的应用输入 | 是 |
| Normalized Booking Facts | 从单证提取的标准化事实、字段置信度和证据位置 | 否，由系统产生 |
| Policy Context | 指定快照、承运人和航线范围 | 否，由系统注入 |
| Golden Expected Result | 标准状态、原因码、证据和责任队列，只用于测试评分 | 否 |

`cases/<CASE_ID>/input.json` 是结构化测试夹具，不是最终应用要求客户提交的格式；其中 `case_id` 属于测试信封，`policy_context` 属于系统上下文。

## 9. 预审结果模型

| 状态 | 含义 | 典型下一步 |
|---|---|---|
| `PRECHECK_PASS` | 当前快照下未发现阻断、缺失或必须人工处理的问题 | 进入后续业务审批；不等同于订舱确认 |
| `REQUIRE_INFORMATION` | 缺少必填单证或字段，无法完成部分或全部预审 | 请求客户补充或更新资料 |
| `MANUAL_REVIEW` | 存在不一致、低置信度、非快照范围或规则冲突 | 转交指定人工队列 |
| `PRECHECK_BLOCKED` | 已有明确事实命中合成快照中的暂停自动处理条件 | 暂停自动流程并展示依据；不等同于最终拒载 |

### 9.1 聚合原则

- 系统必须返回全部命中规则，不因最终状态只保留一条原因。
- 最终状态优先级为：`PRECHECK_BLOCKED` > `MANUAL_REVIEW` > `REQUIRE_INFORMATION` > `PRECHECK_PASS`。
- 缺失资料不会抹去已经由明确事实命中的阻断规则；两类原因都应返回。
- 两条同优先级、同适用范围的有效规则给出冲突动作时，最终结果为 `MANUAL_REVIEW`，原因码为 `GOV-RULE-CONFLICT`。

## 10. 核心业务能力

### 10.1 单证完整性

- Booking Request、初步 DGD 和 SDS Extract 均必须存在。
- Booking Request 必须包含承运人、航线、ETD、ETA、交易方、货物和设备信息。
- 初步 DGD 必须包含核心危险品申报事实。
- SDS Extract 必须包含用于本教学流程的 Section 14 运输信息。

### 10.2 跨单证一致性

- Booking Request、DGD 和 SDS Extract 的 UN Number 必须一致。
- DGD 和 SDS Extract 的 IMDG Class 与 Packing Group 必须一致。
- Booking Request 与 DGD 的件数、包装和重量差异必须按规则处理。
- DGD 与 SDS Extract 的 Marine Pollutant 声明不得矛盾。
- Class 3 的闪点检查以 SDS Extract Section 9 的事实为主，不要求 DGD 重复提供闪点。

### 10.3 承运人、航线与时间

- 当前快照只覆盖 `CNSHA → AEJEA` 和 `TRAIN-ME1`。
- 非固定航线不得使用本快照自动放行。
- 合作伙伴运营船舶必须人工复核。
- Class 1、Class 7、低于指定闪点的 Class 3 和冷箱危险品按合成教学规则暂停自动处理。
- 文档截止规则使用 ETD；目的设施运营限制使用 ETA；规则快照有效期使用 ETD。

### 10.4 单证可信度与运营例外

- 初步 DGD 声明状态不满足教学规则时要求补件。
- 关键字段的模拟抽取置信度低于教学阈值时必须人工确认。
- 使用需要逐票批准的特殊包装时转 DG Desk。
- 目的设施在预计到港日临时停收危险品时暂停自动处理。

### 10.5 证据与审计

每次结果至少包含：

- 使用的规则快照 ID。
- 最终状态及全部原因码。
- 全部命中规则 ID。
- 支撑判断的事实路径和值。
- 原始单证 ID、版本及证据位置。
- 规则的合成属性、教学目的和生效区间。
- 需要补充的字段或责任队列。
- 处理时间和唯一预审运行 ID。

## 11. Agentic 业务边界

本节只定义业务职责，不规定技术架构：

1. 单证事实提取：读取三类源单证，输出标准化事实、置信度和证据位置。
2. 单证一致性复核：比较不同单证中的同一业务事实，不自行修改客户资料。
3. 航线与规则复核：只使用指定版本的冻结快照解释命中规则。
4. 结果协调：汇总全部结果、应用确定性优先级并生成下一步动作。
5. 人工复核：处理低置信度、范围外、规则冲突和需要专业批准的票单。

Agent 可以提取、比较、解释和组织证据；不能自行创造运输分类、修改规则或绕过责任队列。

## 12. 教学规则基线

规则共 28 条，机器定义见 `policy_snapshot.json`，人工可读说明见 `rule-book.md`。每条规则必须声明：

- `rule_basis.type = SYNTHETIC_TRAINING_POLICY`；
- `rule_basis.real_policy_claim = false`；
- 独立的教学目的；
- 生效区间和适用范围；
- 可观察动作和责任队列。

规则覆盖：单证缺失、关键字段、跨单证一致性、阈值边界、航线范围、合作伙伴运营、文档截止、特殊包装、目的设施停收、快照过期和规则冲突。

## 13. 测试策略

### 13.1 Rule Test Suite

`TEST_CASES.md` 保留 30 个小而独立的规则、边界和治理案例，用于快速定位一条规则是否正确。该套件故意以异常案例为主，不代表真实业务分布。

### 13.2 Business Acceptance Suite

`BUSINESS_ACCEPTANCE_CASES.md` 定义跨规则、补件重提、文档版本和规则版本行为；`business-cases/BA-xxx/` 提供对应的多步骤结构化 Fixture 和期望结果。该套件包含合理比例的正常通过案例，且要求返回所有命中原因。

### 13.3 Document Evaluation Packs

`DOCUMENT_PACK_SPEC.md` 定义 8 组代表性源单证包及字段级 Ground Truth。它们用于评估文档事实提取和证据定位，不替代 Rule Test 与 Business Acceptance Suite。

当前材料包含 24 份合成业务单证 PDF、3 份合成政策 PDF、238 条字段级证据，以及覆盖全部 28 条规则的政策页码索引。评分口径见 `SCORING_PROTOCOL.md`。

本仓库有意公开 Expected、Manifest 和 Ground Truth，以支持可重复的教学评测。Agent 运行时仍不得读取这些答案或将其写入提示词。

## 14. 进入架构与编码前的验收标准

1. `BOOKING_SCHEMA.json` 明确区分测试信封、系统上下文和归一化单证事实。
2. DGD 使用独立声明 Schema，不复用 Booking 内部商品模型。
3. Route 同时包含 ETD 与 ETA，并与相应时间规则一致。
4. `RULE_SCHEMA.json` 能表达合成规则依据、教学目的、证据和全量命中聚合策略。
5. `PRECHECK_RESULT_SCHEMA.json` 明确区分技术失败与业务状态，并定义规则、证据、路由和评测指标。
6. 30 个规则测试和业务验收场景均有明确、可观察的预期行为。
7. 任一 `PRECHECK_BLOCKED` 结果都必须对应明确事实和可追踪的合成规则。
8. 不允许以模型自由推理替代确定性规则。
9. 不出现真实承运人政策或超出固定航线订舱预审范围的检查。
10. `routing_queue` 表示业务责任归属；`pause_automation` 只暂停流程推进，不停止全部规则评估。

## 15. 建议效果指标

- 规则测试状态准确率：30/30。
- Business Acceptance Scenario 通过率：100%。
- Critical False Clear：`PRECHECK_BLOCKED` 标准案例不得输出 `PRECHECK_PASS`。
- 缺失信息识别召回率：100%。
- 全部命中规则追踪完整率：100%。
- 证据字段覆盖率：100%。
- 相同输入与快照重复运行的一致率：100%。

这些指标用于后续课程和样例工程评估，本阶段只定义，不实现。
