# 当前问题记录

更新时间：2026-09-10

## 结论摘要

项目的本地运行链路和 PlanningAgent v1 工程闭环已经可以工作，但“本地模型能否稳定完成飞船逃生”目前还没有验收通过。

简单说：程序能正常启动、调用 Ollama、校验模型输出、执行动作、在终端显示每一步并保存 trace；问题出在模型的多步决策能力，模型经常忘记已经得到的信息，重复走相同路线，最后达到 30 步上限。PlanningAgent 已能记录子目标和重规划，但真实固定 5 seeds 与 Evaluation v2 重跑均为 0/5，主要行为是持续执行合法但无进展的 `look`。

## 最新状态（2026-09-10，2026-10-10 补记 Muse 基线）

- 2026-10-10 起真实实验 provider 从 Mac 本地 Ollama 切换为 Windows 下 OpenCode Zen 网关的 `muse-spark-1.3-contributor`（OpenAI Responses 兼容，`OPENAI_BASE_URL=https://opencode.ai/zen/go/v1`）。密钥只保存在本机 `.env`，绝不提交。
- Muse React 自主 5 seeds（`--autonomous`，30 步）：0/5 成功，0 次非法输出，平均重复动作比例约 83%、唯一公开房间 2 个；5 局全部卡在控制室/走廊循环，从未进入储藏室。严格 schema 消除了协议失败，但任务分解仍不足。
- Muse Memory 自主 5 seeds：0/5 成功，但阶段完成率显著高于 React——工具收集 3/5、面板打开 2/5、主电源恢复 2/5、授权码读取 1/5（seed 0 在第 27 步读到授权码，但把步数耗尽在往返上）。平均唯一房间 4.6 个。
- 结论：Muse 比 `qwen2.5:7b` 探索更深（Memory 已能走完“拿工具→修反应堆→恢复电源→读码”链路），但 30 步预算下仍无可重复成功样本；自主通关验收继续未通过。

- 本机 Ollama 服务和 `qwen2.5:7b` 当前可用；此前验证失败是本地请求受系统代理环境影响，Ollama 适配器已对 loopback 地址绕过代理。
- PlanningAgent 真实 seed 0 smoke：30 步、0 次非法输出、28 次 Planner 调用，未完成逃生；主要行为是持续执行 `look`，结果为 `step_limit`。
- PlanningAgent 真实固定 5 seeds benchmark 已完成：0/5 成功，平均 30 步、重复动作比例 93.3%、唯一公开状态 1 个、平均 28 次 Planner 调用、子目标完成率 0%，总 token 141,445。
- Evaluation v2 独立重跑已完成：0/5 成功，平均 25.6 次 Planner 调用、Planner call ratio 85.3%、State Progress 0、Epistemic Progress 1、无进展动作 29、重复已知事实动作 2、唯一子目标 3、同子目标重复动作 26、唯一房间 1。自动规则在每局识别 3 次 rejected action，并产生 2 次 repeated failure；具体结果见 `results/planning-v1-eval-v2/` 和 [失败分析报告](experiments/planning-v1-failure-analysis.md)。
- 代码和测试已经关闭此前记录的 world selector、公开循环状态、benchmark 基础指标及 planner feedback hash 缺口；旧 P1 清单已改为历史/验证说明。

## 已确认的问题

### 1. 本地模型会陷入重复动作循环

已测试的本地模型：

- `qwen3:4b`
- `qwen3:8b`
- `qwen2.5:7b`
- `qwen2.5:14b`

典型表现：

- 控制终端返回 `no_power` 后，模型仍反复回到控制室。
- 已经检查过密封箱后，模型仍重复 `inspect(storage_crate)`。
- 已经拾取物品后，模型仍重复 `pickup`。
- 模型在 `corridor`、`storage_room` 和 `control_room` 之间来回移动。
- 一局执行满 30 步，但没有完成逃生。

这不是 Ollama 连接失败，也不是 Action JSON 格式错误，而是模型在关闭思考模式后的多步规划能力不足。

### 2. 关闭思考后速度更合适，但推理能力下降

当前 Ollama 适配器使用原生 `/api/chat`，发送 `think: false`，并以 Action JSON Schema 约束输出格式（Ollama `format` 参数；OpenAI-compatible 默认 `json_object`，可选 `json_schema`，见 `config/runtime.defaults.json` 的 `response_format`）。

优点：

- 不再长时间生成隐藏思考内容。
- 每一步响应时间更容易接受。
- 输出格式稳定，能够被 Pydantic 正确校验。

缺点：

- 模型更容易忘记前置条件。
- 模型不能稳定规划“拿工具、修复反应堆、恢复电源、读取授权码、发射逃生舱”的完整链路。

### 3. 更严格的提示词只能部分改善问题

提示词已经加入以下约束：

- 只能移动到 `available_exits` 中的房间。
- 只能操作当前 `visible_objects` 中的目标。
- `no_power` 后不要立即回控制室。
- 进入存储室后先检查密封箱。
- 发现物品后先拾取。
- 已经拥有的物品不能重复拾取。

这些规则可以改善前几步行为，但不能完全阻止模型在后续步骤中循环。因此提示词不是根本解决方案。

### 4. 14B 暂缓测试

此前曾验证 `qwen2.5:14b` 可以连接，但固定 seed=0、MemoryAgent、30 步的真实运行仍在恢复主电源后重复读取诊断终端，最终达到步数上限。当前用户使用 Mac M5 Air，运行 14B 的资源开销过高，因此暂不继续测试，也不将 14B 纳入当前实验矩阵。后续只有在更合适的硬件条件下才恢复该对照。

当前已确认可用的模型是：

- `qwen2.5:7b`
- `qwen3:8b`
- `qwen3:4b`
- `qwen3:4b-no-think`

## 已通过的部分

- Ollama 本地服务连接正常。
- `uv run agent-arena verify-model --provider ollama` 通过。
- 默认本地模型为 `qwen2.5:7b`。
- 模型输出可以被 JSON Schema 和 Pydantic Action 校验。
- 终端能够显示每一步的简短理由、动作和环境结果。
- 每局 trace 会写入 `runs/`，benchmark 汇总写入 `results/`。
- 不保存完整思维链、API Key 或原始模型响应。
- `uv run ruff check .` 通过。
- `uv run mypy src` 通过。
- `uv run pytest`：116 个测试全部通过（2026-09-10，包含 Evaluation v2 和 Ollama 代理绕过修复后的回归）。
- `qwen2.5:14b` 的 `verify-model` 通过，但完整逃生局结果为 `step_limit`。

## 当前验收状态

| 验收项目 | 状态 | 说明 |
|---|---|---|
| 本地 Ollama 服务 | 通过 | 服务和模型均可访问 |
| 模型连接验证 | 通过 | `qwen2.5:7b` 与 `qwen2.5:14b` 均返回成功 |
| JSON 动作格式 | 通过 | 输出可被严格校验 |
| 思考关闭 | 通过 | 使用 `think: false` |
| 终端逐步输出 | 通过 | 每一步显示理由、动作和结果 |
| Trace 保存 | 通过 | 步骤写入 `runs/` |
| 自动完成逃生 | 未通过 | 7B 出现重复动作并达到步数上限；14B 暂缓，不作为当前结论 |

## Hiyo Responses provider 复验（2026-08-19）

新增 `openai` provider，使用 `OPENAI_BASE_URL=https://codex.hiyo.top/v1` 的原生 `/v1/responses` 接口和 `gpt-5.6-terra`。模型连接验证通过，`planner_assisted` 在 seed 0/1/2 共 3 局全部于 19 步成功逃生，0 次非法输出。

相同 provider、模型、seed 和 30 步预算下，ReactAgent 与 MemoryAgent 使用通用 `--autonomous` prompt 均在第 2 步后的格式修正阶段达到 `invalid_action_limit`，没有自主逃生成功。因此当前结论是“远程模型可执行公开规划建议”，不是“远程模型已具备纯自主逃生能力”。

## 受控变量复验（2026-08-19）

- 修复环境拒绝副作用：错误使用终端工具或断电读取终端后，终端继续出现在公开 Observation 中，不再永久隐藏。修复后纯自主 React 能执行满 30 步，但仍在 `inspect(control_terminal)` 与 `read_terminal(control_terminal)` 间循环，结果为 `step_limit`。
- `reasoning_effort=high`：同一 seed 下执行 10 步、8 次非法输出后终止，仍是终端循环；没有证据表明增加推理预算能解决任务分解问题。
- `guarded` 公开动作候选：第一次请求遇到 relay 400，重试后能离开控制室、进入储藏室并检查密封箱，但在拾取阶段因缺少 Action 必填参数达到 `invalid_action_limit`，尚未通关。
- 非法输出分类显示本轮主要为 `missing_argument`。Responses relay 拒绝 `json_schema`（HTTP 400），因此默认继续使用 `json_object`，并将安全的缺参类别反馈给格式修正请求。

当前证据更支持“错误恢复与任务分解不足，叠加结构化输出约束不够”这一解释，而不是单一的模型过弱或思考太长。关卡可由人工和 `planner_assisted` 稳定通关，但断电终端反馈曾存在不可恢复的可见性副作用，已修复。

## 2026-08-19 纯模型自主基线结果

使用 `qwen2.5:7b`、`spaceship-escape-v2-zh`、seed 0 至 4、每局 30 步、关闭思考、通用 `react_v12_autonomous` prompt，并关闭 Runner 循环提醒，分别运行 ReactAgent 和 MemoryAgent。

| Agent | 局数 | 成功 | 成功率 | 平均步数 | 平均环境拒绝 | 非法输出 |
|---|---:|---:|---:|---:|---:|---:|
| ReactAgent | 5 | 0 | 0% | 30 | 2 | 0 |
| MemoryAgent | 5 | 0 | 0% | 30 | 15 | 0 |

ReactAgent 的典型行为是第 1 步误用 `inspect(control_terminal)`，第 2 步尝试不可见目标，之后连续 28 次 `look`，直到达到步数上限。MemoryAgent 能走出控制室并返回走廊，但随后在控制室和走廊之间循环，反复对不可见的 `control_terminal` 调用 `read_terminal`。

这组结果证明：移除谜题攻略式提示后，当前 `qwen2.5:7b` 还不能依靠公开 Observation 和结构化 Memory 自主完成任务。它不是连接、格式校验或非法 JSON 问题，所有 10 局的模型输出都通过格式校验。

## 2026-10-11 第二世界迁移：灯塔 5/5 自主通关

灯塔首轮（无 phase）0/5 但 5/5 读码，死法与飞船无 phase 时完全一致；阶段系统泛化为世界声明里程碑后，同一自主组合在新地图 **5/5 成功**（27/28/28/55/57 步）。迁移实锤：新拓扑、新名称、新授权码，无飞船专用知识可用。

## 2026-10-11 首个真正自主通关（Muse + Memory + 公开上下文组合）

在 `--autonomous`（无规划辅助、无候选动作、无动作提示）下，Memory + 最近 5 步公开轨迹 + 卡死恢复 + 公开阶段上下文 + 60 步，seeds 0–4 获 **3/5 成功逃生**（seed 0/1/4，36/35/45 步，0 非法输出），全新 seeds 5–9 获 **2/5 成功**（seed 5/9，均 57 步）——合计 10 局 5 胜，可重复性确认，非 seed 运气。每局全部 Action 均由模型返回并经统一 schema 校验；trace 中 `provenance` 可查：`public_action_hints/candidate_selection/concrete_candidates/guard` 全关。

成功路径与 `planner_assisted` 的 19 步一致（拿工具→修面板→换保险丝→恢复电源→读码→逃生舱用码），但全部由模型自主走出。消融矩阵（60 步，5 seeds/组）：history-only 0/5、phase-only 0/5、history+phase 1/5、history+phase+recovery 3/5——三者互补，决定性的是 history+phase 组合（读码后把授权码与逃生舱绑定，此前 15 局全倒在这一步），recovery 把 1/5 提升到 3/5。同组合 30 步版本 0/5（成功局需 35–57 步，seed 0 在 30 步时已走到反应堆门口，还差约 3 步）。

结论更新：自主通关验收首次通过（Muse + 记忆 + 公开上下文组合）；纯 React/Planning 与 qwen 基线仍未通过。成功与失败 trace 均已归档（`results/muse-memory-s60-h5rp/` 与 `results/muse-memory-s60-h5rp-s59/`）。

## 2026-10-10 Muse 自主基线结果（Windows + Zen 网关）

使用 `muse-spark-1.3-contributor`（OpenCode Zen 网关，OpenAI Responses 兼容）、`spaceship-escape-v2-zh`、seed 0 至 4、每局 30 步、通用 prompt、关闭 Runner 循环提醒（`--autonomous`），分别运行 ReactAgent 和 MemoryAgent。传输层使用 `json_schema` 严格模式（`AGENT_ARENA_RESPONSE_FORMAT=json_schema`，见下节）。

| Agent | 局数 | 成功 | 成功率 | 平均步数 | 平均环境拒绝 | 非法输出 |
|---|---:|---:|---:|---:|---:|---:|
| ReactAgent | 5 | 0 | 0% | 30 | 15 | 0 |
| MemoryAgent | 5 | 0 | 0% | 30 | 2 | 0 |

阶段完成率（Memory）：工具收集 3/5、面板打开 2/5、主电源恢复 2/5、授权码读取 1/5、逃生 0/5。平均唯一房间 4.6 个，平均 State Progress 13.2。

PlanningAgent 5 seeds（第一轮）：0/5 成功（4 局 `step_limit` + 1 局网关瞬断 `provider_error`，已排除 schema 原因）。平均 Planner 调用 2.6 次、重规划 1.6 次、子目标完成率 12%；阶段：工具 1/5、面板 1/5、电源 1/5（seed 1 走完修复链路）、读码 0/5。Planning 的 Planner 调用远少于 qwen 时代（25+ 次），Monitor 很少触发重规划——Muse 的 Executor 行为更稳定，PlanMonitor 的无进展阈值可能偏宽容，这是下一步可消融的点。

Planning 第二轮 5 seeds（复核，`results/muse-planning-autonomous2`）：仍 0/5（4 step_limit + 1 网关瞬断），子目标完成率 45%、Planner 调用 5.6 次。seed 0 留下标准 grounding 样本：Executor 在面板打开后果断但错误地反复 `use(screwdriver → damaged_fuse)`（正确应为 `replacement_fuse`），连续 5 次 `missing_item` 仍不换物品、不触发有效重规划——子目标（修反应堆）正确，动作绑定错误，且失败反馈未转化为约束。这正是 Gate B 的教科书证据。

ReactAgent 的典型行为是在控制室与走廊之间往返（重复导航 7 次/局），从未进入储藏室。MemoryAgent 能走完“读诊断终端→进反应堆→回维修室→去储藏室拿工具→修面板→换保险丝→恢复电源→回控制室读码”链路（seed 0 在第 27 步读到授权码 `ALPHA-731`），但把剩余步数耗尽在往返和重复读取上，未进入逃生舱。

结论：Muse 的探索深度和阶段推进明显好于 `qwen2.5:7b`（后者在 Memory 下平均唯一房间约 1–2 个、State Progress 接近 0），但 30 步预算下仍无可重复成功样本。自主通关验收继续未通过；Muse 结果与 qwen 基线独立统计，不合并成功率。

## 2026-10-10 Zen 网关严格 schema 适配记录

OpenCode Zen 网关在 `text.format=json_schema + strict:true` 下拒绝三类写法（均为 400）：`$defs`/`$ref`、`oneOf`、以及 `required` 未覆盖全部 properties 的对象。`TypeAdapter(Action).json_schema()` 的鉴别联合和 Planner 结构化 criterion 的可选 `target`/`value` 因此不可直接下发。

解法（不改 canonical 契约，只改传输编码）：`src/agent_arena/llm/protocol.py` 新增 `decision_response_schema_strict()`（`anyOf` 内联全部 6 种 Action，无 `$ref`）和 `planner_response_schema_strict()`（全部属性列入 `required`，无目标时填 `""`）；`src/agent_arena/llm/openai.py` 的 `json_schema` 分支改用二者；`PlanningAgent` 用 `_normalize_planner_candidate` 把 `""` 转回 `None` 再做 Pydantic 校验。默认仍是 `json_object`（Hiyo 兼容），Zen 下用 `AGENT_ARENA_RESPONSE_FORMAT=json_schema` 显式启用。

附带发现：`json_object` 下 Muse 会偶发自造冗余参数（如 `read_terminal` 附带 `"object"` 字段），被统一 Action schema 拒绝为 `EXTRA_FIELD`；严格 schema 上线后 10 局 Muse 自主对照非法输出均为 0。

## 建议的下一步

1. 扩展已完成的 Evaluation v2 人工抽样，覆盖每局完整的 replan 后首个 Action，区分 vague/wrong subgoal、wrong action、forgotten fact 和 ineffective replan。
2. 在保持 PlanningAgent v1、通用 prompt 和世界不变的前提下，逐一开展 grounding 或 exploration/recovery 单变量消融；每个变量单独标记。
3. 在获得人工抽样证据和可解释对照前，不实现 PlanningAgent v2，也不把 `planner_assisted` 结果并入自主能力。
4. `planner_assisted` 只作为辅助通关和演示模式，不能替代自主通关验收。
5. 在自动逃生成功率稳定前，不应把 benchmark 结果描述为模型自主规划已完成。

## 复验命令

```bash
uv run agent-arena verify-model --provider ollama
uv run agent-arena run --provider ollama --agent react --seed 0 --output-dir runs
uv run agent-arena benchmark --provider ollama --agent react --episodes 1 --output-dir results
uv run ruff check .
uv run mypy src
uv run pytest
```

真实逃生验收的最低标准是：终端最后显示“成功逃生”，并且对应 trace 的 `outcome` 为成功，而不是“达到步数上限，未完成逃生”。

## 历史问题盘点（2026-09-05，已按当前代码校正）

以下条目区分已确认的缺口、尚未验证的行为和外部运行阻塞；未测试项不应被描述为现有缺陷。

### P0：研究验收未完成

1. 纯 ReactAgent、MemoryAgent 和 PlanningAgent 在 Ollama `qwen2.5:7b` 的固定五个 seed 对照中均为 0/5 成功，尚无可重复的纯模型成功样本。
2. `planner_assisted` 的稳定成功只代表带公开规划建议的可靠性上界，不能与纯模型 trace、指标或结论混合。
3. 尚未公开一组同时包含成功与失败的纯模型 trace；在取得可重复成功前，不能宣称自主规划验收通过。

### 已关闭的实现与实验契约项（原 P1 清单）

以下问题已在 `a308dd5` 和 `07f7457` 中完成代码修复与回归测试，不再作为当前阻塞：

1. `RuntimeSettings.world` 和 `RuntimeSettings.world_version` 已通过 `create_environment` 驱动环境选择，并拒绝未知组合。
2. `PublicLoopDetector` 的公开状态已包含可见出口、对象和背包等进展信息，并有合法回程回归测试。
3. benchmark 已汇总阶段完成率、重复 Action 比例、连续 `look`、唯一公开状态数、Planning 成本和 guidance 偏离率。
4. planner feedback 已以长度受限文本和 hash 写入 trace，不保存完整 reasoning。

### P1：尚未完成的真实验证

1. 尚未完成 React、Memory、Planning 与 `planner_assisted` 的统一真实模型对照，以及成功与失败 trace 的公开归档。
2. 仍需在真实模型下验证 `guarded`、规划建议被拒绝/偏离/产生非法 Action 时的 Runner 行为。
3. 仍需用真实 Planning 运行覆盖完整阶段转换；Fake provider 已覆盖生命周期、重规划、reset 和 finish 的工程路径。
4. 仍需在不同 seed、模型温度和可用 world version 下验证路线稳定性；当前 14B 受本机资源限制暂缓。

### P2：范围与外部条件

1. Streamlit、ReflectionAgent、第二 world version 和第二种模型的对照仍未交付；PlanningAgent v1 工程实现与真实 5 seeds 对照（含 Evaluation v2 重跑，均为 0/5）已完成，缺的是统一归档与单变量消融。
2. `qwen2.5:14b` 受本机资源限制暂缓，不纳入当前实验矩阵。
3. 本次 Hiyo Responses 链路曾返回 `401 INVALID_API_KEY`；这是本地凭据或服务端配置的外部阻塞，不记录或输出密钥。更新有效本地配置后才可继续该 provider 的复验。
