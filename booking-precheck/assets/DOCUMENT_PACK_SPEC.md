# Booking Precheck Document Evaluation Pack Specification

## 1. 目标

Document Evaluation Pack 用于验证从源单证到归一化事实、字段证据和最终预审结果的完整链路。它不替代 30 个 Rule Test Cases，也不承担 OCR 引擎评测。

每个 Pack 必须回答三个问题：

1. Agent 是否正确读取源单证？
2. 每个归一化事实能否回到页码和原文证据？
3. 文档提取、规则执行和状态汇总中的错误能否被分别定位？

## 2. 分层关系

| 层次 | 内容 | 用途 |
|---|---|---|
| Rule Test Suite | 30 组结构化 JSON | 隔离验证单条规则和边界 |
| Business Acceptance Suite | 12 组多步骤 Fixture | 验证组合问题、恢复和版本行为 |
| Document Evaluation Pack | 8 组合成源单证 | 验证提取、证据、协作与端到端行为 |

不是所有 Rule Test 都需要 PDF。PDF 只覆盖对 Agentic 行为最有代表性的场景。

## 3. PDF 约束

- 所有内容必须为合成数据。
- PDF 必须带可选择、可检索的文本层。
- 第一阶段不使用扫描、旋转、手写或故意模糊页面。
- 每种单证至少使用两种版式，避免模型只记住固定位置。
- PDF 中允许存在与预审无关的说明文字，但不得引入未定义的新业务规则。
- 每份 PDF 必须有稳定的 Document ID、Version、Issue Date 和页码。
- Preliminary DGD 和 SDS Extract 不复制真实承运人或受商业授权保护的表单。
- PDF 由相同的 Canonical Fixture 派生，禁止手工维护一份与 JSON 不一致的事实副本。

## 4. 建议的版式变体

### Booking Request

- BR-PORTAL-A：Portal Export 表格，字段紧凑。
- BR-EMAIL-B：客户邮件正文加 Booking Details 表格。

### Preliminary DGD

- DGD-FORM-A：单页标准申报表。
- DGD-FORM-B：单页彩色分区申报表，危险品描述与签署区有更明显的视觉分隔。

### SDS Extract

- SDS-EXTRACT-A：两页，Section 1、9、14。
- SDS-EXTRACT-B：两页紧凑厂商版式，包含少量无关字段和说明文字。

允许的表达变化：

- UN1263 与 UN 1263；
- Packing Group III 与 PG III；
- kg 与 KGS；
- ISO 日期与英文日期；
- 字段顺序、换行和跨页位置；
- 表格与短段落混合。

## 5. 八个核心 Document Packs

| Pack | Case Ref | 业务重点 | 单证及版式 | 主要预期 |
|---|---|---|---|---|
| DP-001 | TC-001 | 完整正常票单 | BR-PORTAL-A / DGD-FORM-A / SDS-EXTRACT-A | PRECHECK_PASS；全部关键事实有证据 |
| DP-002 | TC-004 | DGD 缺失 | BR-EMAIL-B / 无 DGD / SDS-EXTRACT-B | REQUIRE_INFORMATION；明确请求 DGD |
| DP-003 | TC-011 | Booking 与 DGD 的 UN Number 冲突 | BR-PORTAL-A / DGD-FORM-B / SDS-EXTRACT-B | MANUAL_REVIEW；同时展示两个 UN Number |
| DP-004 | BA-008 | 重量冲突加合作伙伴运营 | BR-EMAIL-B / DGD-FORM-A / SDS-EXTRACT-A | MANUAL_REVIEW；DOCUMENT_DESK 与 ROUTE_DESK |
| DP-005 | BA-007 | Class 7 加 DGD 未签署 | BR-PORTAL-A / DGD-FORM-B / SDS-EXTRACT-A | PRECHECK_BLOCKED；保留签署补件原因 |
| DP-006 | BA-009 | ETA 落入设施停收窗口且 SDS 过期 | BR-EMAIL-B / DGD-FORM-A / SDS-EXTRACT-B | PRECHECK_BLOCKED；ETA 与 SDS Issue Date 有证据 |
| DP-007 | BA-006 | 同时缺收货人和 SDS Extract | BR-PORTAL-A / DGD-FORM-A / 无 SDS | REQUIRE_INFORMATION；一次返回全部补件项 |
| DP-008 | BA-004 | DGD 补件后恢复 | Stage 1：BR-EMAIL-B + SDS；Stage 2：新增 DGD-FORM-B | S1 REQUIRE_INFORMATION；S2 PRECHECK_PASS；保留历史 |

## 6. 不进入首批 PDF 的场景

TC-027 的低置信度为预置教学值。若使用清晰文本层 PDF，无法稳定地产生固定的 0.62 置信度；若故意使用模糊扫描件，则会把 OCR 评测引入当前范围。因此：

- TC-027 继续作为结构化模拟案例；
- BA-011 继续用于人工确认和恢复行为；
- 不将 0.62 写进单据正文；
- 后续如单独增加 OCR Stretch Track，再为其准备扫描件。

## 7. 每个 Pack 的目录约定

    document-packs/
    └── DP-001/
        ├── manifest.json
        ├── source/
        │   ├── booking-request.md
        │   ├── preliminary-dgd.md
        │   └── sds-extract.md
        ├── output/
        │   └── pdf/
        │       ├── booking-request.pdf
        │       ├── preliminary-dgd.pdf
        │       └── sds-extract.pdf
        └── ground-truth.json

多步骤 Pack 使用：

    DP-008/
    ├── stage-01/
    └── stage-02/

缺失单证不创建占位 PDF；缺失事实写入 manifest.json 和预期结果。

## 8. 字段级 Ground Truth

每个存在的单证至少标注以下事实：

### Booking Request

- Carrier、Vessel Operator、Service；
- POL、POD、ETD、ETA；
- Shipper、Consignee；
- UN Number、PSN、Class、Packing Group；
- Package Count、Package Type、Gross Weight；
- Container Type。

### Preliminary DGD

- UN Number、PSN、Class、Packing Group；
- Marine Pollutant；
- Package Count、Package Type；
- Net Weight、Gross Weight；
- Shipper Declaration Signed。

### SDS Extract

- Product Name、Issue Date；
- Flash Point；
- Section 14 UN Number、PSN、Class、Packing Group；
- Marine Pollutant。

每条 Ground Truth 包含：

- 归一化 fact_path；
- expected_value；
- 所需 normalization；
- 页码；
- Section；
- 最短充分 evidence_text；
- 可选 bbox。

结构以 DOCUMENT_GROUND_TRUTH_SCHEMA.json 为准。

## 9. 合成政策来源包

除单据外，已准备三份带文本层的合成政策 PDF：

| Policy Doc | 覆盖内容 |
|---|---|
| POL-001 Dangerous Goods Acceptance Guide | Class 1、Class 7、低闪点、冷箱和 IBC 教学规则 |
| POL-002 Booking Precheck Documentation and Consistency Standard | 缺件、跨单证一致性、路线、时限和治理规则 |
| POL-003 Temporary Dangerous Goods Operations Notice | 设施、ETA、生效窗口和版本 |

机器裁决仍以 `policy_snapshot.json` 为准；政策 PDF 用于检索、解释和证据展示。Rule ID 到 Policy ID、页码和证据原文的映射见 `policy-documents/POLICY_DOCUMENT_INDEX.json`。

## 10. Pack 验收标准

- Case Ref 与 Rule/Business Fixture 一致。
- 所有存在的 PDF 都有文本层。
- PDF 页面渲染正常，无截断、重叠或字体缺失。
- Ground Truth 的 evidence text 能在对应 PDF 页中找到。
- 归一化事实与 Canonical Fixture 一致。
- 缺失单证不使用假的占位文件。
- 同一场景重复运行能够得到相同标准答案。
- 每个错误可以定位为 extraction、normalization、rule evaluation 或 aggregation 中的一类。

## 11. 已完成的制作与验证顺序

1. 已完成 12 个 Business Acceptance Fixture。
2. 已为 DP-001 至 DP-008 创建 Manifest。
3. 已从 Canonical Fixture 生成 Markdown 源单证。
4. 已编写字段级 Ground Truth。
5. 已生成 24 份单证 PDF 和 3 份政策 PDF。
6. 已渲染并目视检查全部 41 页。
7. 已确认 238 条字段证据可在指定页面检索。
8. 已确认 28 条规则均能追踪到三份政策 PDF。
