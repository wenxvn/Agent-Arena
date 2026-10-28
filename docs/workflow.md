# Agent Arena 工作流

本文件是日常操作入口，工程约束以根目录 [AGENTS.md](../AGENTS.md) 为准。Skill 是执行指南，不替代用户授权、已确认 spec 或实验停止条件。

## 开始任务

1. 读取 AGENTS、研究总纲、架构摘要、Scope、目标 spec 和工程日志最近记录。日志有历史补记，不能只看文件末尾判断最新状态。
2. 执行 `git status --short --branch`、`git diff --stat`，确认已有修改归属。用 `git -c core.quotePath=false` 显示中文路径。
3. 按入口和调用链读取受影响代码、局部 AGENTS 与相邻测试。只有全目录审核或跨模块任务才扩大扫描。

## 选择流程

| 任务 | 执行顺序 | 完成条件 |
|---|---|---|
| 新功能 | `/scope`，有关键决策时 `/architect`，然后 `/develop`、`/test`、`/check verify` | spec 的行为验收通过 |
| 缺陷 | `/debug`、必要回归测试、`/check verify` | 原问题复现后消失，相关行为通过 |
| 文档与目录整理 | 核对事实、精简与修复引用、链接与格式检查 | 来源可追溯，历史与当前状态分清 |
| 重要代码改动 | 验证后 `/check review` | 审查发现已处理或明确记录 |
| 收尾 | `/sync`、必要工程事件、commit、push | 仅本次文件入库，远端身份核实 |

9 个 Skill 的对应入口见 [索引](../skills/README.md)。已授权的常规维护直接完成；只有缺少会改变结果的必要信息或明确要求另行批准时才暂停询问。

## 验证

代码、配置或 CI 改动运行项目质量门禁：

```powershell
uv run ruff check .
uv run mypy src
uv run pytest -q
uv lock --check
git diff --check
```

仅文档改动至少核对本地链接、事实来源和 diff。纯文案或文件整理不需要新增镜像实现的测试。缺少 `uv` 时可用现有 `.venv/Scripts/python.exe -m ruff`、`-m mypy`、`-m pytest` 验证，并记录 lock 检查未执行；不得把缺工具记为通过。

V3 离线规则验收使用 `uv run python scripts/replay_v3_oracles.py`，结果只证明参考策略可解。`verify-model`、真实 `run` 和研究矩阵会调用 Provider，不能当成普通整理的验证命令。

CI 配置见 [ci.yml](../.github/workflows/ci.yml)。同一分支的新提交可以取消旧 CI，实验任务不由 CI 启动。本地通过与 GitHub Actions 通过分别报告。

## 文件归属与清理

| 内容 | 权威位置 | 维护方式 |
|---|---|---|
| 工程约束与上下文入口 | `AGENTS.md`、局部 AGENTS | 保持精简，工具入口只链接 |
| 研究摘要与完整蓝图 | `研究总纲.md`、`总纲.md` | 摘要保持当前边界，蓝图按需追溯 |
| 路线与进度 | `docs/scope/` | 只凭代码、测试、验收记录推进状态 |
| 技术决策 | `docs/specs/` | `/architect` 维护内容；`/sync` 核对状态 |
| 稳定模块边界 | `docs/architecture.md` | 不记录易变实现细节 |
| 研究证据与设计验收 | `docs/research/`、`docs/world-design-v3/` | 保留原身份、分母、删失与限制 |
| 重要事件 | `docs/engineering-log.md` | 记录原因、改动、验证、下一步和提交 |
| 工作方法 | `skills/`、本文件 | 统一入口，按需读取模板 |
| 运行数据与本机环境 | `.env`、`.venv/`、`runs/`、`logs/`、缓存 | 默认不入库；整理不能抹掉实验证据 |
| 基准聚合证据 | `results/` | **自 V14 起入库**（仅 `benchmark_v3` / `evaluation_v2` 聚合 JSON/CSV，规则见 `results/README.md`）；`*.lock`、`__pycache__/` 仍忽略 |

删除前确认文件没有独立信息或用途，且引用已修复。历史负结果、原始提纲、冻结清单、账本和未提交用户文件均保留。缺失的本地结果应标注缺失状态，不伪造重建，也不为了修复链接而启动实验。

## 研究门禁与交付

V2 的 BUDGET-01/02/03 已关闭，S2 matched-pilot 未通过。不得复用或重置账本、创建 BUDGET-04 或推进后续行为实验。恢复条件见 [运行登记表](research/v2/00-run-registry.md)。V3 的离线交付不解除这些门禁，真实模型实验须另行设计、登记并授权。

完成后同步受影响的持久文件。记录本次实际验证和未执行项，保留历史验证数字所属日期。提交时逐个暂存本次文件，不使用 `git add .` 混入已有草稿。推送后比较 `git rev-parse HEAD` 与 `git ls-remote origin refs/heads/main`；失败时保留本地提交并如实记录，不能声明已推送。
