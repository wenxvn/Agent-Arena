# MAP-23 定稿：迷雾中的遗迹

| 字段 | 值 |
|---|---|
| 世界 | jungle |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `9dc4b4a5a17621b9b25f12201ebe36fed7098eb2c0a48bac8ef57319305d1a8b` |
| rule_hash | `7579ca9aa3fa5e4d752b215dc99c69ed90bf7737eafc7c5d91838fd242909682` |
| prompt_hash | `e405e97a377c542ae5cb05d73415e1a7331fe476ad1d1c9687876d2a40bad1fa` |
| metric_schema_hash | `678d9e0132d61ca9967709cfeb9f2eb8c8b625999ac1e0c1f562debd3c692627` |
| oracle_hash | `41e53eba2084a791b9c3740d4694011a23132083687c28e33c64d427c046f8ab` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

MAP23的难点是信息值必须换算成可执行的补给账：北林与河谷各只能把三座入口缩到两座，高处远眺花相同2补给却能唯一定位；绕到侦察点本身还要付路费。玩家也可以不侦察，直接花1–3补给逐个试入口，并用A营地的一次补给缓存恢复路线。所有入口变体与三处线索必须作为同一张表重写。

MAP-23｜迷雾中的遗迹：把线索信息量换算成可执行补给账。

本图与同世界另两图的机制差异：MAP-22 的图永远不变、核心是记住走过的边；
MAP-24 的图会在局中坍塌、核心是在线改路。本图路网与成本完全公开，主机制是
“三个等概率真入口 + 三处付费侦察 + 一次性补满”，玩家要判断一条线索值不值
它的路费 + 2 补给。

指标口径（与 V7 卡片一致）：
- ``clue_utilization`` = 最强单条已购线索缩减的候选数 / 2；未侦察记 0。
- ``cost_per_discovery`` = (14 − 终局剩余补给) / 成功发现数；0 发现为 N/A。
- ``repeated_invalid_exploration`` = 对已排除入口再次调查的次数。
- ``ignored_counterevidence`` = 最终调查入口是否已被已购线索排除。

实现约定：重复调查一个已排除入口允许执行并再次扣费，用于让
``repeated_invalid_exploration`` 可达；它不会改变入口真假。

## 2. 与同世界另两图的区别

- **MAP-22**（简单）：这张图考的是局部标识如何逐步变成可返回的拓扑记忆。营地A、目标遗迹L和其他节点都有固定路标；当前视野只给眼前路标外形与出口方位，不给邻居名称或完整邻接表。B/E/H/K都做成相近的三叉桩外形，必须观察桩脚缺口、横刻、根纹或苔楔才可分辨。路标独特但地图不自动写入记忆；玩家必须实际走过边，再自行记录端点关系。
- **MAP-24**（困难）：本图与同世界另两图的机制差异：MAP-22 的图永远不变；MAP-23 的图静态、难度来自“哪个入口为真”的信息价值。本图在 tick 8 永久移除 A-B、B-C，D-E 潮道按 4 拍开 2 拍且相位 seed 私有；主机制是“旧笔记与世界不一致时是否改路”。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`actions_taken`, `agent_marked_candidate`, `available_scout_stations`, `clues_received`, `goal`, `location`, `neighbors`, `resupply_cache_available`, `searched_false_entrances`, `supply_remaining`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`clues`, `counters`, `final_target`, `location`, `marked`, `resupply_used`, `scouted`, `searched_false`, `status`, `supply`, `terminal_reason`, `tick`, `true_entrance`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `investigate`：`entrance`
- `mark`：`choice`
- `move`：`to`
- `resupply`：无附加字段
- `scout`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：三个等概率真入口；侦察付费；补给一次性补满；seed=0 的真入口为 Z。

- 成功码：`TRUE_ENTRANCE_FOUND`
- 失败码：`SUPPLY_DEPLETED`, `SUPPLY_MUST_REMAIN_POSITIVE`, `SUPPLY_STRANDED`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map23.clue_utilization` | primary | higher_is_better | reduced_candidate_regions / reducible_candidate_regions | 可缩减候选区域数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.cost_per_discovery` | primary | lower_is_better | supplies_spent / discoveries | 发现数；0 则 N/A | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.ignored_counterevidence` | diagnostic | lower_is_better | count(action contradicting confirmed clue) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map23.repeated_invalid_exploration` | guardrail | lower_is_better | count(region re-searched after exclusion) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：river_double_ripples_then_z（7 步）, ridge_unique_signal（7 步）
- 手算 fixture：river_clue_then_z（7 步）, ridge_scout_full_reduction（7 步）, repeat_false_entrance_is_counted（4 步）, ignoring_single_support_clue（4 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-23` → `MAP-23: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

seed=0 的真入口为 Z；三入口先验等概率，但正式运行固定 seed 后不再随机。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
