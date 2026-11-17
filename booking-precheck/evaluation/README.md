# Booking Precheck Langfuse Evaluation

面向课堂重构的独立黑盒评测工程。首版评测课程提供的 **9 个 Document Pack Stage**，不重复评测规则引擎，也不要求证明 `DP-008:S2` 从 `S1` 的 Checkpoint 恢复。

第一次使用 Langfuse，请从 [`docs/langfuse-evaluation-tutorial.md`](docs/langfuse-evaluation-tutorial.md) 开始。教程完整复盘了 Dataset、Experiment、Trace、Scores、结果解读和故障排查。

## 设计边界

```text
Langfuse Dataset（9 个 DP Stage）
        │
        ▼
Langfuse Experiment Runner
        │ booking-precheck-eval/v1 JSONL
        ▼
被测系统 Adapter ──► Single-Agent / 后续 Multi-Agent
        │
        ▼
result + facts + telemetry
        │
        ▼
确定性 Evaluators ──► Langfuse Scores / Experiment 对比
```

三个工程各自承担单一职责：

- `contracts/`：共享、可版本化的请求、响应和 Manifest 契约；
- `evaluation/`：Dataset 同步、黑盒调用和确定性评分；
- `agent/`：通过薄 Adapter 将内部 Agent 映射到共享契约。

Harness 不导入被测系统的内部 Python 模块。以后 Multi-Agent 只需实现同一协议，不需要修改 Dataset 和 Evaluators。

## 安装

以下命令从 `booking-precheck/` Workspace 目录执行；从 `labs` 仓库根目录先进入该目录。

```bash
uv sync --all-packages --all-extras
uv run python tools/generate_materials.py
uv run python -m pytest contracts/tests
uv run python -m pytest evaluation/tests
```

PDF 根据受版本控制的合成材料重建到现有 `assets/**/output/pdf/` 路径，生成物不提交到 Git。

## 离线黑盒回归

不配置真实模型或 Langfuse，也可以执行实际的确定性规则与 PDF 解析路径，并生成本地评测报告：

```bash
uv run booking-precheck-eval validate-config \
  --config evaluation/configs/deterministic-smoke.json
uv run booking-precheck-eval run \
  --config evaluation/configs/deterministic-smoke.json
```

报告写入 `evaluation/reports/smoke/` 的时间戳子目录，包括原始结果、汇总 JSON、CSV 和 Markdown。该路径未配置 `env_file`，不调用外部模型或 Langfuse；它验证的是确定性基线与评测链路，不能当作真实 Agent 的准确率结果。仅返回 `PrecheckResult` 时，字段准确率会显示 `N/A`；需要同时返回 `result` 和 `facts` 的评测 envelope 才能计算完整提取评分。

协议和工具循环单元测试中的 fake/scripted 响应只验证接口行为，不代表模型性能。

## 配置

Single-Agent 使用其已有 `.env` 中的模型配置：

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=...
LLM_MODEL=...
```

复制 `evaluation/.env.example` 为 `evaluation/.env`，填写 Langfuse 项目凭据：

```dotenv
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

如果使用 EU 或自托管 Langfuse，请把 `LANGFUSE_BASE_URL` 改为对应地址。

## 1. 本地协议检查

先运行一个 Stage，验证 Manifest、JSONL 协议、Adapter 和真实 Agent：

```bash
uv run booking-precheck-eval doctor \
  --config evaluation/configs/workshop.json \
  --manifest agent/booking-precheck-agent.json \
  --pack-id DP-001 \
  --stage S1
```

该步骤会调用外部模型，但不会访问 Langfuse。

## 2. 同步 Langfuse Dataset

```bash
uv run booking-precheck-eval sync-langfuse \
  --config evaluation/configs/workshop.json \
  --env-file evaluation/.env
```

Dataset 名称默认为 `booking-precheck/day2-document-packs-v1`。9 个 Item 使用稳定 ID，重复执行是 upsert，不会不断创建副本。

## 3. 运行 Langfuse Experiment

```bash
uv run booking-precheck-eval experiment \
  --config evaluation/configs/workshop.json \
  --manifest agent/booking-precheck-agent.json \
  --run-name single-agent-baseline-v1 \
  --env-file evaluation/.env
```

首版固定串行执行，避免多个请求共享 JSONL 子进程时相互串线。Langfuse 会记录每个 Dataset Item 的 Experiment Trace，并保存以下确定性 Scores：

- `technical_success`、`status_correct`；
- `rule_f1`、`field_accuracy`、`evidence_integrity`；
- `functional_pass`、`no_critical_false_clear`；
- 模型调用数、Token 和 Agent 延迟；
- 整次 Experiment 的 P95 Agent 延迟。

## 数据边界

- 仓库公开 Expected Output、Ground Truth 和确定性评分器，以支持可重复的课堂实验；这些答案不构成隐藏测试集。
- 发给模型：课程合成 PDF 的文本、系统提示和工具结果；不包含 Expected Output 或 Ground Truth。
- 发给 Langfuse：9 个 Stage 标识、合成数据的 Expected Output/Ground Truth、Agent 输出、评分和 Experiment Trace。
- 首版不把 PDF 二进制上传到 Langfuse；Dataset Item 的 `input` 只包含 `pack_id` 与 `stage_id`。
- 模型供应商和 Langfuse 都是外部服务时，正式运行前应确认课程合成数据允许发送到对应服务。

## 接入重构后的 Agent

重构实现只需继续支持 `booking-precheck-eval/v1` JSONL 协议并提供自己的 Manifest。把 `experiment --manifest` 指向新 Manifest，并使用不同的 `--run-name`，即可在同一 Langfuse Dataset 上比较两种实现。

## 首版确定性文档基线的已知缺口

完整离线运行 51 次调用成功；规则 30/30、业务 12/12 通过，但文档阶段仅 2/9 功能通过。其余 7 项被 evidence_integrity 判为证据不完整，状态和规则判断仍正确。`configs/deterministic-expectations.json` 将这些具体缺口作为迁移回归规格保留；评分器与冻结答案不作放宽。CI通过代表没有新增回归，不代表文档证据质量合格，也不代表真实模型准确率。
