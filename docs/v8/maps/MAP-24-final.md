# MAP-24 定稿：消失的道路

| 字段 | 值 |
|---|---|
| 世界 | jungle |
| 难度 | 困难 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `15b070864d4d70f109e31aec0f5d77761ead75775181f22fec4ab414885ff7ae` |
| rule_hash | `394665914bb5c2e22f0dddf070142e23ed1ebe28f8432756a05665a34eb0fa9f` |
| prompt_hash | `e3de9bb00f301a1be00f419ab8bb339cd2b578fa44545278a1d4e0e1f72cf0d3` |
| metric_schema_hash | `d86f91f264766519786113bb65ac9f0dd7f247174f61b8ce87e00e3e2668dae2` |
| oracle_hash | `2fd0ac718f61cc92bed2b84e4fe3084425969d96fb2584b4d6c1baafd2f6c6cd` |
| commit | `039e25ce6503871ceb31184e85c9265451ee7486` |

## 1. 设计意图与独特机制

这关要测的是路线图会过期：玩家出发时看到A-B-C桥环可通，途中桥永久消失；潮道D-E又有每四拍开放两拍的局部窗口；较慢的A-F-C山路始终可走。手工图固定为六个节点、七条双向边。必须把C遗迹与D河岸的两件物资都带回A，且回营时刻不晚于24。E是旧补给转运点和潮道会合地，本关不在那里添加第三件目标物资。

MAP-24｜消失的道路：桥塌事件、潮窗与过期路线笔记。

本图与同世界另两图的机制差异：MAP-22 的图永远不变；MAP-23 的图静态、难度来自
“哪个入口为真”的信息价值。本图在 tick 8 永久移除 A-B、B-C，D-E 潮道按 4 拍
开 2 拍且相位 seed 私有；主机制是“旧笔记与世界不一致时是否改路”。

指标口径（与 V7 卡片一致）：
- ``replanning_latency`` = 坍塌后首次“改路移动”的发起 tick − 8；若 Agent 在
  坍塌时不在 A/B/C 或没有改路需求，返回 ``None``。
- ``route_cost_ratio`` = 首次本地看到断边后到交付的实际移动成本（含失败移动）
  / 同点最短可行移动成本；未观察断边或已交付前未观察，返回 ``None``。
- ``collapsed_edge_attempts`` = 坍塌后仍尝试已移除桥边的次数。
- ``rescue_failure`` = 终局未把两件物资都带回 A 记 1。

实现约定：坍塌在动作完成 tick 结算；tick 8 完成的一拍移动可以先到位，若此时
身在 B 则立即 ``STRANDED_ON_BRIDGE``。潮道开窗用出发 tick 判定。

## 2. 与同世界另两图的区别

- **MAP-22**（简单）：这张图考的是局部标识如何逐步变成可返回的拓扑记忆。营地A、目标遗迹L和其他节点都有固定路标；当前视野只给眼前路标外形与出口方位，不给邻居名称或完整邻接表。B/E/H/K都做成相近的三叉桩外形，必须观察桩脚缺口、横刻、根纹或苔楔才可分辨。路标独特但地图不自动写入记忆；玩家必须实际走过边，再自行记录端点关系。
- **MAP-23**（中等）：本图与同世界另两图的机制差异：MAP-22 的图永远不变、核心是记住走过的边；MAP-24 的图会在局中坍塌、核心是在线改路。本图路网与成本完全公开，主机制是“三个等概率真入口 + 三处付费侦察 + 一次性补满”，玩家要判断一条线索值不值它的路费 + 2 补给。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`bridge_probe_result`, `carried_items`, `goal`, `latest_local_tide_reading`, `local_connections`, `location`, `route_notes`, `tick`, `tide_rule`, `visible_item_here`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`carried`, `collapsed`, `collapsed_attempts`, `counters`, `delivery_tick`, `failed_moves`, `first_replan_tick`, `location`, `notes`, `observation_node`, `observation_tick`, `phase_offset`, `remaining_move_cost`, `status`, `taken`, `terminal_reason`, `tick`, `tide_measurements`, `tide_reading`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `measure_tide`：无附加字段
- `move`：`to`
- `probe_bridge`：无附加字段
- `record_route`：无附加字段
- `take`：`item_id`
- `wait`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：tick 8 永久移除 A-B、B-C；D-E 潮道 4 拍开 2 拍且相位 seed 私有；旧笔记会过期。

- 成功码：`ALL_ITEMS_DELIVERED`
- 失败码：`DEADLINE_EXCEEDED`, `STRANDED_ON_BRIDGE`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map24.collapsed_edge_attempts` | guardrail | lower_is_better | count(move onto collapsed edge) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.replanning_latency` | primary | lower_is_better | tick(first replanned move) - tick(collapse public) | 坍塌实际发生的 episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.rescue_failure` | diagnostic | lower_is_better | 1 if rescue target not reached by deadline else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map24.route_cost_ratio` | primary | lower_is_better | actual_remaining_cost / shortest_feasible_cost_after_collapse | 坍塌后最短可行成本 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：probe_then_update（11 步）, mountain_and_tide（8 步）
- 手算 fixture：normal_update_after_collapse（11 步）, mountain_route_has_no_replan（8 步）, stranded_on_bridge（8 步）, stale_note_repeats_collapsed_edge（24 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-24` → `MAP-24: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | STRANDED_ON_BRIDGE | 9 | 0.0059154 | `V8-MAP-24-R0-20261017T100123Z-3523377d` | `collapsed_edge_attempts`=0; `rescue_failure`=1 |
| 1 | success | True | ALL_ITEMS_DELIVERED | 9 | 0.00240008 | `V8-MAP-24-R1-20261017T100207Z-2b1d8bb1` | `collapsed_edge_attempts`=0; `rescue_failure`=0 |
| 2 | success | True | ALL_ITEMS_DELIVERED | 12 | 0.00647696 | `V8-MAP-24-R2-20261017T100237Z-087a6524` | `collapsed_edge_attempts`=0; `replanning_latency`=1; `rescue_failure`=0; `route_cost_ratio`=1.0 |

三次重复成功 2/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

`route_cost_ratio` 的分母排除没有本地潮位读数的 D-E 潮道。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
