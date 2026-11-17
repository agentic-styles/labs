# TRAINING-LINE 订舱预审教学规则手册

## 使用声明

- 版本：0.2
- 快照：`TRAINING-LINE-CNSHA-AEJEA-2026-08-01`
- 航线：`CNSHA → AEJEA`，服务 `TRAIN-ME1`
- 性质：所有规则均为 `SYNTHETIC_TRAINING_POLICY`，不代表任何真实承运人、港口或监管要求。
- 预审结果不是订舱确认、拒载决定或危险品分类结论。
- 每条规则的阈值只服务于教学；正式授课前应由 DG SME 对业务可理解性做一次确认。

## 业务阶段

规则在 Booking Request、初步 DGD 和 SDS Extract 已经收到后执行，处于 DG Desk 正式审批之前。文档截止使用 ETD，目的设施运营限制使用 ETA，快照有效期使用 ETD。

## 状态与聚合

| 状态 | 业务含义 |
|---|---|
| `PRECHECK_PASS` | 当前快照下未发现需要补件、人工处理或暂停自动流程的问题 |
| `REQUIRE_INFORMATION` | 请求客户补充或更新资料 |
| `MANUAL_REVIEW` | 转交指定业务队列确认 |
| `PRECHECK_BLOCKED` | 当前事实命中合成快照中的暂停自动处理条件，不等同于最终拒载 |

最终状态按 `PRECHECK_BLOCKED > MANUAL_REVIEW > REQUIRE_INFORMATION > PRECHECK_PASS` 汇总，但输出必须保留全部命中规则、原因和证据。

## 规则目录

| Rule ID | 教学目的 | 可观察条件 | 结果 | 责任队列 |
|---|---|---|---|---|
| `DOC-DGD-REQUIRED` | 演示必需单证检查 | 危险品 Booking 未提供初步 DGD | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-SDS-REQUIRED` | 演示必需单证检查 | 危险品 Booking 未提供 SDS Extract | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-DGD-UN-REQUIRED` | 演示关键字段补件 | 初步 DGD 缺少 UN Number | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-DGD-PSN-REQUIRED` | 演示关键字段补件 | 初步 DGD 缺少 Proper Shipping Name | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-SDS-S14-REQUIRED` | 演示承运人自定义文件要求 | SDS Extract 缺少 Section 14 运输信息 | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-SDS-FRESHNESS` | 演示日期阈值规则 | SDS Extract 签发时间相对提交日超过 24 个月 | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-CONSIGNEE-REQUIRED` | 演示角色完整性检查 | Booking Request 没有 CONSIGNEE | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `CON-BOOKING-DGD-UN` | 演示跨单证事实冲突 | Booking 与初步 DGD 的 UN Number 不一致 | `MANUAL_REVIEW` | DG_DESK |
| `CON-DGD-SDS-UN` | 演示跨单证事实冲突 | 初步 DGD 与 SDS Extract 的 UN Number 不一致 | `MANUAL_REVIEW` | DG_DESK |
| `CON-DGD-SDS-CLASS` | 演示危险品分类事实冲突 | 初步 DGD 与 SDS Extract 的 IMDG Class 不一致 | `MANUAL_REVIEW` | DG_DESK |
| `CON-GROSS-WEIGHT` | 演示数值容差 | Booking 与初步 DGD 的毛重差异超过 DGD 毛重的 2% | `MANUAL_REVIEW` | DOCUMENT_DESK |
| `CON-PACKAGE-COUNT` | 演示数量一致性 | Booking 与初步 DGD 的件数不一致 | `MANUAL_REVIEW` | DOCUMENT_DESK |
| `CON-MARINE-POLLUTANT` | 演示布尔事实冲突 | 初步 DGD 与 SDS Extract 的 Marine Pollutant 声明不一致 | `MANUAL_REVIEW` | DG_DESK |
| `CON-FLASH-POINT` | 演示 Class 3 必填事实 | SDS Extract 声明 Class 3，但 Section 9 缺少闪点 | `REQUIRE_INFORMATION` | DG_DESK |
| `CAR-CLASS-1-BLOCK` | 演示明确暂停条件 | 初步 DGD 申报 Class 1 | `PRECHECK_BLOCKED` | — |
| `CAR-CLASS-7-BLOCK` | 演示明确暂停条件 | 初步 DGD 申报 Class 7 | `PRECHECK_BLOCKED` | — |
| `CAR-LOW-FLASH-POINT-BLOCK` | 演示阈值阻断 | SDS Extract 声明 Class 3，且闪点低于 -18°C | `PRECHECK_BLOCKED` | — |
| `CAR-REEFER-DG-BLOCK` | 演示设备限制 | 危险品使用 20RF 或 40RF | `PRECHECK_BLOCKED` | — |
| `ROU-SNAPSHOT-SCOPE` | 演示快照范围保护 | POL、POD 或 Service 不属于固定教学航线 | `MANUAL_REVIEW` | ROUTE_DESK |
| `ROU-PARTNER-OPERATOR` | 演示外部运营例外 | Vessel Operator 不是 TRAINING-LINE | `MANUAL_REVIEW` | ROUTE_DESK |
| `TIM-DOCUMENT-CUTOFF` | 演示工作日计算 | 提交时间距离 ETD 少于 5 个工作日 | `MANUAL_REVIEW` | DOCUMENT_DESK |
| `CON-PACKING-GROUP` | 演示枚举事实冲突 | 初步 DGD 与 SDS Extract 的 Packing Group 不一致 | `MANUAL_REVIEW` | DG_DESK |
| `DOC-DGD-SIGNATURE` | 演示声明状态补件 | 初步 DGD 的托运人声明未签署或缺失 | `REQUIRE_INFORMATION` | DOCUMENT_DESK |
| `DOC-KEY-FIELD-LOW-CONFIDENCE` | 演示 Agent 不确定性升级 | DGD UN Number 的模拟抽取置信度低于 0.80 | `MANUAL_REVIEW` | DOCUMENT_DESK |
| `CAR-IBC-MANUAL-APPROVAL` | 演示专业人工批准 | 初步 DGD 的包装类型为 IBC | `MANUAL_REVIEW` | DG_DESK |
| `PORT-TEMPORARY-DG-SUSPENSION` | 演示带时间窗的运营规则 | 目的设施为 AEJEA-TRAIN-T1，且 ETA 在 2026-09-10 至 2026-09-12 | `PRECHECK_BLOCKED` | — |
| `GOV-SNAPSHOT-EXPIRED` | 演示规则版本治理 | Booking ETD 晚于 2026-12-31 | `MANUAL_REVIEW` | POLICY_OWNER |
| `GOV-RULE-CONFLICT` | 演示规则冲突治理 | 相同优先级和范围的有效规则产生冲突动作 | `MANUAL_REVIEW` | POLICY_OWNER |

## 教学阈值说明

以下数字是为了制造边界测试而设置，不宣称是真实政策：

- SDS Extract 时效：24 个月；
- 毛重容差：2%；
- 低闪点阈值：-18°C；
- 文档截止：ETD 前 5 个工作日；
- 关键字段低置信度阈值：0.80；
- 目的设施停收窗口：2026-09-10 至 2026-09-12。

机器可执行版本以 `policy_snapshot.json` 为准；本手册用于业务评审和课堂解释。

## 执行动作字段

- `routing_queue` 表示问题的业务责任归属；对 `REQUIRE_INFORMATION`，它表示负责组织补件的队列，不等同于人工审批。
- `pause_automation=true` 表示暂停业务流程自动推进，但系统仍按 `collect_all_matches=true` 评估并保留其他命中规则。
