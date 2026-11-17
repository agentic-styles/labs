# Booking Precheck Architecture Lab

这个 uv workspace 提供 Single-Agent 教学基线、确定性规则内核、统一 JSONL 契约、黑盒评测以及合成样本生成工具。

[课程首页](https://agentic-styles.github.io/lab/) · [课程学习指南](https://agentic-styles.github.io/lab/tutorial.html) · [Agent 说明](agent/README.md) · [评测说明](evaluation/README.md) · [样本重建](tools/README.md)

## 安装与重建

以下命令均在 `labs/booking-precheck/` 执行。需要 Python 3.12 和 uv；依赖由 `uv.lock` 锁定。

```sh
uv sync --all-packages --all-extras --locked
uv run --locked python tools/generate_materials.py
```

生成器从本仓库源码重建并校验 27 份合成 PDF，不读取私有归档、原项目的 `.env` 或已生成 PDF。所有冻结 JSON/Markdown 保持不变，生成物与报告不进入 Git。

## 离线测试与评测

```sh
uv run --locked python -m pytest contracts/tests agent/tests evaluation/tests
uv run --locked booking-precheck --case TC-014
uv run --locked booking-precheck --business-case BA-005
uv run --locked booking-precheck --document-pack DP-003
uv run --locked booking-precheck-eval run --config evaluation/configs/deterministic-smoke.json --output-dir .generated/evaluation
uv run --locked python ../scripts/verify_evaluation.py .generated/evaluation
```

这些命令不调用模型或 Langfuse。规则基线直接处理结构化事实，文档路径使用确定性 PDF 解析；它们与模型驱动的 Single-Agent 是不同的运行路径。

首次迁移验证 83 个测试通过。离线全量评测包含 30 个规则案例、9 个文档阶段和 12 个业务案例，51 次调用成功；规则和业务评分全部通过。文档阶段仅 2/9 功能通过，其他 7 个阶段被原评分器正确判为证据不完整，不能表述为全部质量通过。

`evaluation/configs/deterministic-expectations.json` 明确列出这 7 个已知缺口。回归检查保持这些失败可见，同时拒绝新增失败；后续修复证据输出时应评审期望变化，不得删除评分检查或修改标准答案来获得通过。

报告位于 `.generated/evaluation/`，包括原始运行、摘要、CSV 与 Markdown。CLI 结果不返回完整 facts 时，字段准确率显示 N/A，不得用其他指标替代。

## 可选：真实模型基线

```sh
cp agent/.env.example agent/.env
```

在本地填写模型服务配置后，可从本目录使用 Manifest 启动单案例协议检查：

```sh
uv run --locked booking-precheck-eval doctor --config evaluation/configs/workshop.json --manifest agent/booking-precheck-agent.json --pack-id DP-003 --stage S1
```

该步骤会调用配置的模型，但不访问 Langfuse；Manifest 从 `agent/.env` 加载配置。也可以进入 `agent/` 后运行 `uv run --locked --env-file .env booking-precheck --agent-document-pack DP-003`。普通 CLI 不自动加载 `.env`。

Studio：进入 `agent/`，执行 `uv run --locked langgraph dev`。可选 Langfuse Dataset 同步和 Experiment 见 [评测教程](evaluation/docs/langfuse-evaluation-tutorial.md)。真实服务运行均不在默认 CI 中执行，本次迁移没有使用模型密钥或重测模型准确率。

## 设计与数据边界

- Agent 负责文档理解、工具选择和证据提交；规则内核控制最终业务状态与全部规则命中。
- 当前 Single-Agent 是故意缺少部分应用级 Guardrails 的教学实验版本，测试保留了这一行为；它不是生产推荐配置。
- 契约、样本、Expected Output 与 Ground Truth 可用于复现实验，但标准答案不能送入 Agent Context。
- 所有业务材料均为合成数据。预审通过不等于最终承运批准，案例不适用于真实订舱判断。
- 新架构通过相同的 `booking-precheck-eval/v1` 接口接入；首版没有已完成的 Multi-Agent 变体。
