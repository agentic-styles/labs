# Agentic Styles · Labs

可运行的 Agentic 架构实验工程，与 [Patterns 图鉴及课程](https://agentic-styles.github.io/patterns/) 配套。课程、Slides 与网站源码保留在 [agentic-styles/patterns](https://github.com/agentic-styles/patterns)，本仓库维护基线、契约、评测与样本生成工具。

## Booking Precheck

[工程与快速开始](booking-precheck/README.md) · [课程](https://agentic-styles.github.io/patterns/lab/) · [学习指南](https://agentic-styles.github.io/patterns/lab/tutorial.html)

```text
booking-precheck/
├── agent/          Single-Agent 教学基线与确定性规则内核
├── contracts/      booking-precheck-eval/v1 JSONL 契约
├── evaluation/     黑盒 Harness、确定性评分与可选 Langfuse 接入
├── assets/         冻结合成数据、规则、清单、真值及单证源文件
├── tools/          隔离重建与验证样本 PDF
├── pyproject.toml  uv workspace 与生成依赖
└── uv.lock         锁定依赖
```

所有承运人、航线、规则和单证都是合成教学材料，不可用于真实订舱决策。预审通过不代表最终承运批准。

## 最短离线路径

安装 Python 3.12 与 uv 后：

```sh
git clone --branch v0.1.0 https://github.com/agentic-styles/labs.git
cd labs/booking-precheck
uv sync --all-packages --all-extras --locked
uv run --locked python tools/generate_materials.py
uv run --locked python -m pytest contracts/tests agent/tests evaluation/tests
uv run --locked booking-precheck-eval run --config evaluation/configs/deterministic-smoke.json --output-dir .generated/evaluation
uv run --locked python ../scripts/verify_evaluation.py .generated/evaluation
```

离线流程不需要模型密钥或 Langfuse。真实模型调用、Studio 与 Langfuse 的可选用法见工程文档，默认 CI 不执行这些外部服务实验。

## 首版验证范围与已知缺口

- 83 个契约、规则、文档、评分及 scripted Agent 测试通过；scripted 模型测试不是模型准确率。
- 重建 27 份 PDF、41 页，覆盖 8 个 Pack / 9 个 Stage；238 条字段证据与 28 条政策证据逐条匹配，冻结 JSON/Markdown 源文件不变。
- 51 次确定性黑盒调用均成功；规则案例 30/30、业务案例 12/12 通过。
- 文档阶段的业务状态与规则判断正确，但 7 个阶段的结果缺少完整文档证据，功能评分仅 2/9 通过。这是迁移基线已有缺口，评分器保留失败判定。
- CI 按 `deterministic-expectations.json` 检查这 7 个明确的已知缺口以及其他回归，不能把 CI 通过解释为全部质量指标通过。真正改善证据后应评审并更新该回归规格。
- Single-Agent 保留原来的部分无应用级 Guardrails 教学实验行为；本次未复跑真实模型准确率，也未实现 Multi-Agent 变体。

## 源码与制品

仓库及可达历史只保存源码、冻结测试数据、示例配置和锁文件。HTML/PDF、评测报告、Trace、截图、虚拟环境、运行状态及真实 `.env` 都不提交；生成的 PDF 位于忽略的 `assets/**/output/pdf/`，报告位于 `.generated/`。

Actions 在干净 Linux 环境安装锁定依赖、重建样本、运行测试及评测，并上传生成证据为 artifact，保留 14 天。课程通过固定发布版本引用实验工程；网站构建不依赖本仓库。

## 来源

从 OOCL AI 2026 的私有结项归档提取自有教学源码及合成样本（归档提交 `b7fc04f`），采用全新的源码历史。未迁入原 Git 历史、真实凭据、运行日志或第三方培训仓库。完整原始交付继续留在私有归档中。
