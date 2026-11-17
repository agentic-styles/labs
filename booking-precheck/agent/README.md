# Booking Precheck — Single-Agent Baseline

工程同时包含两条明确分开的运行路径：

- `booking_precheck_agent`：从 PDF 逐页文本开始，运行一个真实模型驱动的 Orchestrating Agent 和受控工具循环。
- `booking_precheck_rule_baseline`：从结构化 facts 开始的确定性 oracle，用于规则回归和架构对比。

Agent 负责文档理解、事实与证据提交、工具选择和错误修复；`final_status`、全部规则命中和状态聚合仍由确定性规则内核控制。

> 所有承运人、航线、单据和规则均为合成教学材料，不可用于真实订舱决策。预审通过也不是最终承运批准。

## 快速开始

在本实验的 `booking-precheck/` 目录（包含 Workspace `pyproject.toml`）使用 Python 3.12 和 `uv` 安装。以下命令从 `labs` 仓库根目录开始：

```bash
cd booking-precheck
uv sync --all-packages --all-extras
uv run python tools/generate_materials.py
uv run python -m pytest agent/tests
uv run booking-precheck --case TC-014
uv run booking-precheck --business-case BA-005
uv run booking-precheck --document-pack DP-003
```

业务材料默认位于本实验目录的 `assets/`，也可用 `BOOKING_PRECHECK_ASSETS` 覆盖。PDF 从受版本控制的教学源材料重建到 `assets/**/output/pdf/`，不提交到 Git。Workspace 使用 editable install，修改 `src/` 后不需要重复安装。

## 模型配置

从 `booking-precheck/` 目录复制 `agent/.env.example` 为 `agent/.env`，配置 OpenAI-compatible 模型服务：

```dotenv
LLM_API_KEY=...
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

普通 CLI 不自动加载 `.env`。在 `agent/` 内直接调用真实模型时使用 `uv run --locked --env-file .env booking-precheck --agent-document-pack DP-003`；Manifest 客户端和 LangGraph Studio 按各自配置加载环境。

`.env` 已被 Git 忽略。`booking_precheck_agent` 和 `--agent-document-pack` 会真实调用模型；baseline 命令不会调用模型。

## LangGraph Studio

从 `booking-precheck/agent/` 目录启动本地 Agent Server：

```bash
cp .env.example .env
uv run langgraph dev
```

启动成功后可访问：

- API：`http://127.0.0.1:2024`
- API 文档：`http://127.0.0.1:2024/docs`
- Studio：`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

在 Studio 选择 `booking_precheck_agent`，最小输入只需要指定 Document Pack：

```json
{
  "document_pack_id": "DP-003",
  "stage_id": "S1"
}
```

Agent 会读取该 Pack 中的 PDF，而不会读取 `ground-truth.json`、`expected.json` 或 canonical fixture。选择 `booking_precheck_rule_baseline` 时，输入才是结构化 `facts`。

若 Safari、Brave 或浏览器安全策略阻止 Studio 访问 localhost，可运行 `uv run langgraph dev --tunnel`。

## Single-Agent 流程

```text
PDFs → initialize_case → precheck_agent ⇄ precheck_tools
                                      ↓ no tool call
                               finalize_result
```

Agent 使用标准 `ChatOpenAI.bind_tools`、`AIMessage`、`ToolMessage`、`ToolNode`、`tools_condition` 和 `Command(update=...)`。模型可调用五个工具：

- `submit_extracted_facts`
- `run_precheck_rules`
- `submit_decision_evidence`
- `lookup_policy_evidence`
- `request_human_confirmation`

`submit_extracted_facts` 只提交结构化单证。规则执行后，`run_precheck_rules` 返回本次决定实际依赖的
`required_evidence_paths`；Agent 再用 `submit_decision_evidence` 精确补交这些字段的页码和原文证据。
因此不存在固定的 32 条证据上限，也不需要为未命中规则的字段生成证据。

Agent 返回一个不包含 Tool Call 的最终 AI Message 后，Graph 直接尝试组装结果，不再要求全部必要工具已执行。

本教学基线保留无应用级 Guardrails 的实验行为，供学员分析和改进：结束由 Agent 是否停止调用工具决定；Graph
不再校验工具顺序、证据真实性、证据路径覆盖率或必要步骤是否全部完成。Tool Schema、规则引擎和
结果 Schema 仍作为系统接口保留，但不承担 Agent 流程纠错。

`model_call_count`、`input_tokens` 和 `output_tokens` 来自实际模型响应 usage。

## Rule baseline 流程

```text
input / PDF pack
      ↓
prepare → evaluate_rules → aggregate_findings → compose_auditable_result
                                                       ↓
                                           PRECHECK_RESULT_SCHEMA
```

测试将两条路径分开：规则测试检查内核与契约可重复；Agent 测试使用 scripted model，检查生产 Graph 的工具循环、模型故障不会产生业务放行，以及证据页码可以进入最终结果。Scripted model 预先指定模型响应，不访问模型服务，其通过率不代表真实模型的提取或端到端准确率。端到端模型准确率仍应使用 Document Packs 和独立测试集单独评分。
