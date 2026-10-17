# MAP-20 定稿：冷却网络

| 字段 | 值 |
|---|---|
| 世界 | volcano |
| 难度 | 中等 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `5a5bcd0ba3871f4eeecd48af7524a6321dbc9810a975fdf54ed99f54d8116490` |
| rule_hash | `983f83987d118852a14786cd7053721e7211b9334a1490cc62441c10486c52b5` |
| prompt_hash | `2e9a5c9112ef3e60b160f93916978180e8e1ad3777dcc239f2f71ba3bf3a0753` |
| metric_schema_hash | `c3aad88588e64d69be592ee505fdf730c8c99feea98680eebd1e4f1c740e0269` |
| oracle_hash | `858c0ae04676c134fae5275ae7161c7d363521a0d00cfdfe5220010609581483` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

MAP20不是MAP19的“延迟冷却再换皮”：这里没有阀门时滞，难点是每tick只有6单位来水，A/B/C负荷合计最高9，A-B与B-C旁路会把水转给邻区但必损20%。玩家要同时决定直供分流、旁路方向和区负荷档，利用各区当前温度余量做跨tick资源分配。

MAP-20｜冷却网络：带 20% 损耗的跨区旁路与四重流量约束。

本图与同世界另两图的机制差异：MAP-19 是三片互不传导的独立回路、共享总阀量
且命令延迟两 tick；MAP-21 是隐藏喷发时刻下的风险决策。本图没有时滞与随机事件，
主机制是“水源 60 刻度 + 单支管 25 刻度 + 区间旁路必损 20% + 区阀 4/4/3”，
玩家必须同时决定直供、旁路方向/流量和负荷档，用邻区余量给热点续命。

实现约定（对应 `docs/v8/dcr-resolution.md` 的 V8-DCR-020/021/022）：
- 温度、流量全部用十分之一单位整数；过热线严格 `> 100`。
- 一次非法控制帧（源超预算、支管越界、旁路非法、区阀越界）整帧拒绝、计一次
  `flow_conservation_violations`，但不推进时钟、不结束 episode；这样 Agent 可以
  在下一帧改正。只有热越界与终局产能不足是终止失败。
- 直供与旁路设定是“保持型设定”，在 Agent 改写前逐 tick 复用；水量本身不储存。
- ``max_node_exceedance`` 与 ``safe_node_ticks`` 使用裁判侧精确温度（V7-DCR-010），
  单位均为十分之一度。

## 2. 与同世界另两图的区别

- **MAP-19**（简单）：本图与同世界另两图的机制差异：MAP-20 是带 20% 损耗的互联管网、控制无延迟；MAP-21 是隐藏喷发时刻下的风险决策。本图没有移动、没有随机事件、也没有跨区热传导，主机制是“今天下达的冷却阀向量到 tick+2 才有效”这一条固定时间因果，玩家必须提前两 tick 预判三区温度并用负荷档位交换产能。
- **MAP-21**（困难）：本图与同世界另两图的机制差异：MAP-19/20 都是确定性的热/水控制题；本图没有温度或流量，主机制是“喷发时刻只可能是 12/16/20 且不可见，唯一信息动作是一次耗时 2 tick 的有噪测量”。玩家要在“多取一档样品”和“赶上最早喷发”之间停手。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`bypass_settings`, `current_load_modes`, `direct_flow_tenths`, `flow_rules`, `goal`, `last_temperature_reading`, `previous_tick_flow_ledger`, `production_points`, `production_target`, `source_water_remaining_this_tick`, `temperature_bands`, `tick`, `ticks_remaining`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`bypass`, `counters`, `direct_tenths`, `ledger`, `loads`, `production`, `settled_states_tenths`, `status`, `temperatures_tenths`, `terminal_reason`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `adjust_loads`：`adjust_loads`
- `open_bypass`：`open_bypasses`
- `read_temperature`：`station`
- `set_flow`：`set_flow_tenths`
- `wait`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：无控制延迟；总水源 60、单支管 25、旁路损 20%、区阀 4/4/3；非法帧整帧拒绝、零时间。

- 成功码：`PRODUCTION_TARGET_MET`
- 失败码：`PRODUCTION_BELOW_15`, `THERMAL_OVERHEAT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map20.flow_conservation_violations` | guardrail | lower_is_better | count(FLOW_CONSERVATION_VIOLATION) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.key_node_runaway` | diagnostic | lower_is_better | 1 if any key node exceeds hard limit else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.max_node_exceedance` | primary | lower_is_better | max_node max_t max(0, T_node_t - T_safe) | 关键节点数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map20.safe_node_ticks` | primary | higher_is_better | Σ_nodes Σ_t [T_node_t <= T_safe] | 节点数×有效 tick | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：a_priority（16 步）
- 手算 fixture：a_priority_safe_network（16 步）, full_load_without_bypass_overheats_a（2 步）, zone_valve_rejected_atomically（3 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-20` → `MAP-20: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | failure | False | THERMAL_OVERHEAT | 22 | 0.01901904 | `V8-MAP-20-R0-20261017T093752Z-3824d0d4` | `flow_conservation_violations`=0; `key_node_runaway`=1; `max_node_exceedance`=20; `safe_node_ticks`=29 |
| 1 | success | True | PRODUCTION_TARGET_MET | 19 | 0.01298908 | `V8-MAP-20-R1-20261017T093931Z-00dbed48` | `flow_conservation_violations`=0; `key_node_runaway`=0; `max_node_exceedance`=0; `safe_node_ticks`=30 |
| 2 | success | True | PRODUCTION_TARGET_MET | 17 | 0.01325256 | `V8-MAP-20-R2-20261017T094050Z-669e7442` | `flow_conservation_violations`=1; `key_node_runaway`=0; `max_node_exceedance`=0; `safe_node_ticks`=30 |

三次重复成功 2/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

非法控制帧整帧拒绝、零时间、不终止（V8-DCR-020）；这是一条冻结的运行语义。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `4/4`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`completed`；最终状态：`finalized`。
