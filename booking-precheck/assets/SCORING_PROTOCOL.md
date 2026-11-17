# Booking Precheck Workshop 评分协议

## 1. 评分目标

评分必须把“读错单据”和“读对单据但规则判断错误”分开。学员提交物至少包含：

1. 标准化 Booking 对象；
2. 最终状态与全部命中规则；
3. 字段证据与政策证据；
4. 下一步动作和责任队列；
5. 可关联同一 Case、Step、Policy Snapshot 的审计记录。

总分 100 分。结构化 30 案例用于稳定回归，Document Pack 用于端到端抽取，Business Acceptance 场景用于工作流和版本行为。

## 2. 功能评分

| 维度 | 分值 | 评分方式 |
|---|---:|---|
| 字段提取与归一化 | 25 | 对 Ground Truth 的关键字段计算 Exact Match；允许 Schema 声明的规范化 |
| 规则命中完整性 | 20 | 以 Rule ID 集合计算 Precision、Recall 和 F1；不得只输出最高优先级规则 |
| 最终状态 | 15 | 必须符合状态优先级和规则聚合结果 |
| 证据可追踪性 | 15 | 字段证据须指向单据、页码和原文；规则证据须指向 Policy ID、页码和 Rule ID |
| 下一步动作 | 10 | 补件内容、责任队列及阻断含义必须正确 |
| 工作流与版本 | 10 | 补件/改单后重新评估；保留前后版本、快照和结论，不覆盖历史 |
| 输出契约 | 5 | JSON 可解析并符合约定 Schema；Case ID、Step ID、Snapshot ID 完整 |

## 3. 指标计算

### 3.1 字段提取

对每个 `ground-truth.json` 中的 Fact：

```text
field_accuracy = correct_normalized_fields / expected_fields
```

- `UN_NUMBER_CANONICAL`：忽略 `UN` 与数字之间的空格，输出规范形式如 `UN1263`；
- `PSN_CANONICAL`：去除首尾空格、合并连续空白、大小写不敏感；
- `UNIT_TO_KG`：允许吨、千克换算后比较；
- `DATE_TO_ISO`：统一为 ISO 日期；
- 缺失值必须明确为 `null` 或 `NOT_PROVIDED`，不得臆测。

### 3.2 规则命中

```text
precision = correct_rule_ids / returned_rule_ids
recall    = correct_rule_ids / expected_rule_ids
f1        = 2 * precision * recall / (precision + recall)
```

无命中规则的通过案例：返回空集合得满分；返回任何规则均视为 False Positive。

### 3.3 证据

每条结论分别检查：

- 文档事实证据是否真实存在于指定 PDF 页；
- 政策证据是否真实存在于 Policy PDF 页；
- 证据是否支持该结论，而不是仅与主题相关；
- 不得引用模型内部推理作为业务证据。

## 4. 安全与完整性扣分

以下错误触发额外扣分，功能总分最低为 0：

| 错误 | 扣分 |
|---|---:|
| 将预期 `PRECHECK_BLOCKED` 输出为 `PRECHECK_PASS` | -20/案例 |
| 将缺件案例臆测为字段齐全 | -10/案例 |
| 引用不存在的政策、页码或原文 | -8/条 |
| 只返回最终状态，丢失同时命中的较低优先级规则 | -5/案例 |
| 补件后覆盖旧结论，无法还原状态变化 | -5/流程 |
| 把预审阻断表述为真实承运人最终拒载 | -10/案例 |

## 5. Day 1 基线评分

Day 1 使用单 Agent 基线，统一运行：

- 30 个结构化测试案例；
- DP-001、DP-002、DP-003 三个基础 Document Pack；
- BA-004 一个补件恢复流程。

记录功能总分、平均延迟、P95 延迟、模型调用次数、输入/输出 Token、失败案例及调试耗时。

## 6. Day 2 重构评分

Day 2 由学员先声明非功能目标，再选择是否拆分及采用何种 Multi-Agent Pattern。至少比较：

| 指标 | 定义 |
|---|---|
| 准确率 | 同一隐藏集上的功能总分与关键状态错误数 |
| 延迟 | 端到端平均值和 P95；并行调用必须计入等待时间 |
| 成本 | 每 Case 的模型调用数及估算 Token 成本 |
| 可追踪性 | 能否从最终结论定位到 Agent、工具调用、字段证据和 Policy Rule |
| 调试难度 | 给定失败案例后，定位根因并提出修复所需时间 |

不能只比较“是否用了多个 Agent”。重构只有在学员声明的优先质量目标上产生可验证收益，才视为成功。

## 7. 建议通过线

- 总分至少 80；
- `PRECHECK_BLOCKED` 召回率 100%；
- 规则命中 Recall 至少 90%；
- 字段证据和政策证据正确率至少 90%；
- BA-004、BA-005、BA-011、BA-012 的状态转换全部正确；
- 不出现伪造政策证据。

## 8. 隐藏测试使用原则

- 对学员公开 Schema、允许状态、Policy 文档和 8 个示例 Pack；
- 不公开全部 30 案例的 Expected JSON；
- 隐藏集改变数值、文档模板和组合方式，不改变已发布规则语义；
- Single-Agent 与 Multi-Agent 必须运行同一隐藏集、同一模型档位和相同最大重试次数。
