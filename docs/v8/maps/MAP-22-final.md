# MAP-22 定稿：没有地图的森林

| 字段 | 值 |
|---|---|
| 世界 | jungle |
| 难度 | 简单 |
| 条件 | `history5_graph_memory` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `efc76acdc469af8fd965418396b2a549b2147300a33fdb3eab2c70b150151412` |
| rule_hash | `e856cec6daf4d388e89c2d239153cb5fbcb955de65c8d2ccd62753319f293856` |
| prompt_hash | `5d1068396fb0e1c26a396afcae8d4cd7c42aef47f6dd7bee55fd8c4ccd80d704` |
| metric_schema_hash | `f0f6f77e4e0557f0ea1f479314f70b4dd167b84f3b137443addbc522178893ef` |
| oracle_hash | `388ae9bdf55001710afa6a7b6af76a6b7265f624dafd5e5b2815dee69b3e801d` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

这张图考的是局部标识如何逐步变成可返回的拓扑记忆。营地A、目标遗迹L和其他节点都有固定路标；当前视野只给眼前路标外形与出口方位，不给邻居名称或完整邻接表。B/E/H/K都做成相近的三叉桩外形，必须观察桩脚缺口、横刻、根纹或苔楔才可分辨。路标独特但地图不自动写入记忆；玩家必须实际走过边，再自行记录端点关系。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-23**（中等）：本图与同世界另两图的机制差异：MAP-22 的图永远不变、核心是记住走过的边；MAP-24 的图会在局中坍塌、核心是在线改路。本图路网与成本完全公开，主机制是“三个等概率真入口 + 三处付费侦察 + 一次性补满”，玩家要判断一条线索值不值它的路费 + 2 补给。
- **MAP-24**（困难）：本图与同世界另两图的机制差异：MAP-22 的图永远不变；MAP-23 的图静态、难度来自“哪个入口为真”的信息价值。本图在 tick 8 永久移除 A-B、B-C，D-E 潮道按 4 拍开 2 拍且相位 seed 私有；主机制是“旧笔记与世界不一致时是否改路”。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`active_goal_marker`, `agent_authored_memory_journal`, `current_coarse_silhouette`, `inspected_current_sign_detail`, `movement_steps`, `visible_exit_bearings`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`active_goal`, `last_traversed_edge`, `map_id`, `memory`, `movement_steps`, `node`, `seed`, `status`, `target_visited`, `terminal_reason`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `check_goal`：无附加字段
- `move`：`bearing`
- `observe_signpost`：无附加字段
- `return_to_camp`：无附加字段
- `write_memory`：`facts`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：公开方位行走；图记忆只记录亲历路标与边；返营并记录遗迹才算成功。

- 成功码：`RETURNED_TO_CAMP_WITH_RUIN_RECORD`
- 失败码：`STEP_LIMIT_REACHED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map22.illegal_bearing_actions` | guardrail | lower_is_better | count(result==INVALID_BEARING) | episode | 0 次为合法 0 | 按已发生事件计数 |
| `map22.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map22.memory_facts_written` | diagnostic | descriptive | len(final agent_authored_memory_journal) | episode | 无 journal 字段 → UNAVAILABLE | 按最终公开 journal 计算 |
| `map22.memory_grounding_violations` | guardrail | lower_is_better | count(result==MEMORY_FACT_NOT_OBSERVED) | episode | 0 次为合法 0；未启用记忆时无该结果 | 按已发生事件计数 |
| `map22.path_gap` | primary | lower_is_better | movement_steps - BFS_optimal_moves(instance) | 成功返程的 episode | 无冻结最优 → UNAVAILABLE；未成功 → N/A | 截尾 → CENSORED |
| `map22.repeated_public_edge_rate` | diagnostic | lower_is_better | directed edges traversed more than once / resolved directed moves | 两端的公开位置签名都可解析的移动数 | 可解析移动为 0 → N/A | 按已发生移动计算 |
| `map22.return_success` | primary | higher_is_better | 1 if terminal_reason==RETURNED_TO_CAMP_WITH_RUIN_RECORD else 0 | episode | 无终局 → CENSORED | step-limit 截尾时值仍为 0，但状态标 CENSORED |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-22-solver-success（8 步）
- 手算 fixture：illegal-bearing-then-solve（9 步）, exactly-30-moves（30 步），补充冻结后失败用例 `budget-failure-backtracking`（30 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-22` → `MAP-22: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 30 | 0.02321652 | `V8-MAP-22-R0-20261017T095222Z-68e884e9` | `illegal_bearing_actions`=1; `legal_action_rate`=0.933333; `memory_facts_written`=7; `memory_grounding_violations`=1 |
| 1 | decision_budget_reached | False | None | 30 | 0.02036660 | `V8-MAP-22-R1-20261017T095410Z-5d7125fa` | `illegal_bearing_actions`=0; `legal_action_rate`=1.0; `memory_facts_written`=7; `memory_grounding_violations`=0 |
| 2 | decision_budget_reached | False | None | 30 | 0.01894224 | `V8-MAP-22-R2-20261017T095608Z-0f0e3e48` | `illegal_bearing_actions`=0; `legal_action_rate`=1.0; `memory_facts_written`=6; `memory_grounding_violations`=0 |

三次重复成功 0/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

重复边按有向公开签名计；实例最优为 8；未增加节点别名。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `7/7`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
