# V11 Batch 0：盘点与冻结（审计）

- 审计时间：2026-10-20（UTC）
- 起始 HEAD：`eb2f64a281677a0fce881769a6592cce1be6f7d9`（与提纲给出版本一致）
- 分支：`main`；工作树仅多出用户未跟踪的 `研究提纲/`，无他人未提交改动
- 执行环境：Windows 11 10.0.26200（x64）、Python 3.13.3、uv 0.13.3、Streamlit 1.66.0（`uv run --with streamlit`）
- 基线测试：`1157 passed in 103.62s`（改动前，`.venv\Scripts\python.exe -m pytest -q`）

## 1. 现有入口与 UI

| 能力 | 现状（审计结论） | 位置 |
|---|---|---|
| CLI 运行单局 | 可用；Legacy / V3 / V10 各自入口 | `src/agent_arena/cli.py` |
| CLI benchmark | 可用；JSON/CSV 汇总 | `cli.py` |
| 模型验证 | `verify-model` / `scripts/verify_model.sh` | `cli.py`、`scripts/` |
| Streamlit | **只读**：单局回放、矩阵总览、错误热点、条件对照 | `src/agent_arena/ui/app.py`、`present.py` |
| 网页启动配置 | **不存在**；不能选图、配置 seed/预算、启动或停止 | 审计确认 |
| 网页导出 | **不存在**；只能浏览 | 审计确认 |
| 运行服务层 | **不存在**；没有 `RunService`/manifest/取消/恢复 | 审计确认 |

现有 UI 通过 `import_module("streamlit")` 延迟导入，读取 `runs/`、`results/`；有路径白名单与符号链接防护。V11 保留四个研究视图，并在同一入口新增可操作页面。

## 2. 30 图 catalog 与运行路径

`src/agent_arena/v10/runtime/catalog.py`：

- `MAP_IDS`：`MAP-01` … `MAP-30`，顺序稳定；
- `WORLD_OF`：10 世界 × 3 图；
- `V10_MAPS`：30 张全部为 V10 原生运行时，V8 回退为 0；
- `create_environment(map_id, environment_seed=...)`、`seed_space()`、`rule_hash()`、`metric_hash()`、`scenario_hash()`；
- `LEVEL_OF`：设计难度 简单/中等/困难（按编号模 3）。

`src/agent_arena/v10/contract.py` 提供带**字段类型**的公开动作契约（DCR-V10-24），`v10/contract_hints.py` 保存 MAP-16/18/19/28 的公开结构提醒；两者都只含公开信息。

决策预算来自 `v10/baselines/suite.py::decision_budget`：简单 30、中等 38、困难 46，MAP-12/19=60、MAP-20=56、MAP-22=80。

**结论**：网页 catalog 直接由 V10 源数据生成，不手填第二套 ID；不存在只在 V3/V8 可用的 selector 混用。

## 3. 现有 V10 runner 审计（`scripts/run_v10_mimo.py`）

| 维度 | 现有实现 | V11 处理 |
|---|---|---|
| seed | 每图预登记 3–10 个 `SEED_SPACE` | 直接复用；页面只能选登记 seed |
| 预算 | V10 独立账本 ¥10、请求前预留、usage 越界封账 | 不触碰 V10 账本；新建 `web/budget.py` 的单局门禁 |
| 停止 | `V10BudgetClosed`、连续 3 次 provider 错误、unknown spend 封账 | 复用 fail-closed 语义；新增用户取消与 `PROVIDER_ERROR` 状态 |
| 事件 | `agent_trace.jsonl` + `judge.json` + `manifest.json` | 新增 `runs/web/<run_id>/events.jsonl` + `manifest.json` + `result.json` |
| hash | `scenario_hash`/`rule_hash`/`metric_hash`/`metric_schema_hash`/`prompt_hash` | 全部写入 V11 result 与 manifest |
| 恢复 | 已完成 `run_id` 跳过；账本未结算则关闭 | 进程重启后非终态 → `INTERRUPTED`，保留部分回放 |
| prompt | `_system_prompt`：公开规则 + 带类型契约 + hints | 提取为 `web/prompting.py`，内容逐字一致 |
| 批量 | 同步串行矩阵 | V11 只跑单局；`RunService` 单 worker 串行 |

`CONTRACT_HINTS` 已提取到 `v10/contract_hints.py`，并有测试与脚本逐字比对，防止 prompt 漂移。

## 4. 现有数据格式

- Legacy / V3：`runs/**/episode_*.json`，`present.py` 只读白名单字段；
- V10 MiMo：`runs/v10/mimo/episodes/<run_id>/agent_trace.jsonl`（agent-visible）、`judge.json`（密封真值与指标）、`manifest.json`；
- V10 指标五态：`VALID` / `CENSORED` / `NOT_APPLICABLE` / `MISSING` / `INVALID`；
- 旧 V8/V9 trace 不保证与 V11 兼容；V11 网页只读取自己的 `runs/web`，研究视图仍按旧逻辑读取。

## 5. Provider 配置

- `.env`（不入库）保存 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`OPENAI_SESSION_ID`、Ollama 地址/模型；
- `RuntimeSettings` 统一合并 CLI / 环境变量 / `.env` / `config/runtime.defaults.json`；
- OpenAI-compatible 走 Responses API；本地 Ollama 走原生 `/api/chat`；
- 本机实测模型：`mimo-v2.6-flash`，`api.xiaomimimo.com`（真实冒烟使用，见 `final-report.md`）。

## 6. 改动前缺口（已核实，不机械照抄提纲）

1. 无网页启动/停止/状态隔离；Streamlit 仅展示。
2. 无 `run_id` 级 manifest、事件日志、取消标记、重启恢复。
3. 无网页侧预算门禁与未知消费处理。
4. 无 JSON/CSV 导出；无历史筛选与同版本对照。
5. 6 张图 `title` 为 `MAP-XX` 占位（08/16/18/22/26/30），需要展示层补全。
6. MAP-19/20/28/29/30 的公开说明对普通用户偏长，需要详情页提醒与折叠。
7. 无启动自检、无网页冒烟测试、无 CI web 检查。

## 7. 任务拆分与风险

| 优先级 | 任务 | 风险 |
|---|---|---|
| P0 | RunService + 持久化 + 取消/恢复 | Windows 文件替换竞争（已观察到并修复重试） |
| P0 | 30 图 catalog + 详情 | 误把密封真值写进详情（已用键名扫描测试） |
| P0 | 离线完整流程 | 规则策略被误解为模型（已显式标注） |
| P0 | 真实 Provider + 预算 | 未知消费/重复计费（fail-closed + 单局串行） |
| P0 | 导出 + README + 自检 | Windows/macOS 差异（本机仅 Windows 实测） |
| P1 | 展示难度、历史对照、引导 | 不污染设计难度/规则 hash |
| P2 | 可视化、成绩榜、启动脚本 | 不引入 3D/公网/用户系统 |

## 8. Gate 0 结论

- 架构草图：Streamlit → `RunService` → 单 worker → V10 execution adapter → `runs/web` 持久化；
- 单局真实运行适配方案：复用 V10 `create_environment`、带类型契约、`OpenAIDecisionProvider` 与 `scenario_v4` 请求语义；
- 预算防护可在进入付费测试前用假 Provider 与单元测试确认；
- **Gate 0 通过**，允许进入 Batch 1–2（零 API）。
