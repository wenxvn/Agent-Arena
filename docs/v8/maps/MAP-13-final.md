# MAP-13 定稿：四神之门

| 字段 | 值 |
|---|---|
| 世界 | pyramid |
| 难度 | 简单 |
| 条件 | `default` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `93e7b639bd2fe8a3129a1f7cae4724eb47ea9af7a72abb6958a4d910f44a2cdd` |
| rule_hash | `0481b734b73d7d3786a7fb2c68bcdb1cb5e4d309e517f5135a52a359db519229` |
| prompt_hash | `198e1a24658d16472d1b83c7493741a96e24272c90e83ef214e285fb0f53970e` |
| metric_schema_hash | `6c7e42f604f3f1b674efe3307b331d079744f9422d5932d205c5a4f3764a83a4` |
| oracle_hash | `7fbad6220cd51456375ef07faae3fe3e7c055df3f8aca33e6777bfbabd1da0b6` |
| commit | `4ffbdeb2e6d22abfd340b9ea1aff73fade979674` |

## 1. 设计意图与独特机制

这是一个带空间标号语义的约束满足关卡：外侧四室在移动图上只与中央 C 相连，但符号谜题使用另一条明确标出的阅读序。破解者必须分别保留“房间连通图”和“碑文位置序列”，不可把逻辑相邻误当作房间之间有通道。

MAP-13｜四神之门：显式符号约束满足与“房间图 / 碑文阅读序”分离。

本图与同世界另两图的机制差异：MAP-14 的陈述有真假与说谎者，需在锁型×诚实者
假设中找一致解；MAP-15 的规则随 tick 奇偶变化，需要归纳与迁移；本图五条信息
全部为真、规则静态，核心是把星形移动拓扑与碑文阅读序 `N→E→S→W` 分开，逐条
传播约束到唯一排列，并在最多两次错误开门内完成。失败码与状态变量与另两图不重叠。

动作契约（每个动作 1 tick；``set_trial_layout`` 不消耗开门次数）：

- ``move``：只走 `C_N / C_E / C_S / C_W`，四间外室之间没有直连。
- ``read_inscription``：只能在自己所在房间读；观察与记录是两件事。
- ``record_constraint``：只在 C，只能记录已读碑文。
- ``set_trial_layout``：只在 C，必须恰含 N/E/S/W 四槽且四符号各一次。
- ``verify_layout``：只在 C，正确开门；错误则 ``STATE_RESET``（清空试排并计错）。

指标口径（与 docs/v7/maps/MAP-13.md 一致）：

- ``map13.constraint_satisfaction_ratio``：最后一次试排满足的房间谓词数 + 方向钉
  是否已读，分母 5（4 条房间约束 + 方向钉）；无试排 → 0/5。
- ``map13.correct_sequence``：最后一次试排是否等于唯一解（0/1）。
- ``map13.illegal_door_attempts``：被拒绝的 ``verify_layout`` 次数（含未成型试排
  与错排）；0 合法。
- ``map13.state_resets``：错排触发的 ``STATE_RESET`` 次数；0 合法。
- ``map13.completion_ticks``：成功终局 tick；失败 → None。

唯一解与约束表只存在裁判侧，不进 Observation。

## 2. 与同世界另两图的区别

- **MAP-14**（中等）：本图与同世界另两图的机制差异：MAP-13 的碑文全部为真、约束静态；MAP-15 的规则随全局 tick 奇偶切换；本图规则静态，但六条证词只有恰一名祭司全局如实、另外两人逐命题反报。玩家要在 4 问预算内维护“锁型 × 诚实者”九态一致假设，再到审判门承担最终验证。共享严格模型把 ``configuration`` / ``configuration_candidate`` 定义为整数列表，故本图用 ``choice`` 携带锁型候选、用 ``person_id`` 携带诚实者候选、用 ``support_evidence_ids``携带已观察证据 ID；``claim_id`` 携带命题 ID。
- **MAP-15**（困难）：本图与同世界另两图的机制差异：MAP-13 的碑文约束静态且全真；MAP-14 的规则静态、难点是不可靠证词与问询预算；本图没有证词，规则本身随全局 tick 奇偶切换——偶数 tick 目标色等于墙符号色，奇数 tick 等于其互补色（红↔蓝、金↔绿），同一面墙在不同相位要求不同门。玩家须从 A/B/C 三间训练室的成功样例迁移到 T 的四色未见布局。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`current_tick`, `gate_open`, `goal`, `incorrect_attempts`, `location`, `observed_clues`, `recorded_clue_ids`, `remaining_incorrect_attempts`, `trial_layout`, `visible_edges`, `visible_neighbors`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`gate_open`, `illegal_door_attempts`, `incorrect_attempts`, `last_attempted_layout`, `location`, `observed`, `recorded`, `state_resets`, `target_layout`, `tick`, `trial_layout`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `move`：`edge_id`, `from_node`, `to_node`
- `move`：`edge_id`
- `read_inscription`：`room`
- `record_constraint`：`clue_id`
- `set_trial_layout`：`layout_by_room`
- `verify_layout`：无附加字段

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

对 `target`/`choice`/`operation` 这类字符串动作，系统 prompt 公开静态词表（见 `mimo-preregistration.md` §2）：只列可尝试的动作名，不表示当前位置可执行、前置条件已满足或顺序正确；隐藏真值不进入词表。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：静态全真约束；错误开门最多 2 次；未获得布局的 `verify` 视为非法门。

- 成功码：`GATE_OPENED`
- 失败码：`INCORRECT_ATTEMPT_LIMIT`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map13.completion_ticks` | diagnostic | lower_is_better | terminal_tick if success else N/A | 成功局 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.constraint_satisfaction_ratio` | primary | higher_is_better | satisfied_constraints / total_constraints | 总约束数 | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.correct_sequence` | primary | higher_is_better | 1 if door_order == derived_unique_order else 0 | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.illegal_door_attempts` | guardrail | lower_is_better | count(ILLEGAL_DOOR) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |
| `map13.state_resets` | diagnostic | lower_is_better | count(STATE_RESET) | episode | 运行时缺少来源事件 → UNAVAILABLE；不得默认为 0 | 预算/provider 截尾 → CENSORED，并保留原因码 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：constraint_propagation（20 步）, systematic_enumeration（20 步）
- 手算 fixture：constraint_propagation_full_evidence（20 步）, three_blind_guesses_exhaust_tolerance（6 步）, two_wrong_then_correct_still_opens（6 步）, verify_without_layout_is_illegal_door（1 步）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-13` → `MAP-13: OK`。

## 9. MiMo 三次正式运行

| rep | status | success | 终止原因 | 决策 | cost | run_id | 主指标 |
|---|---|---|---|---|---|---|---|
| 0 | decision_budget_reached | False | None | 30 | 0.02209248 | `V8-MAP-13-R0-20261017T083403Z-a0b524e9` | `constraint_satisfaction_ratio`=0.2; `correct_sequence`=0; `illegal_door_attempts`=3; `state_resets`=2 |
| 1 | success | True | GATE_OPENED | 27 | 0.01553652 | `V8-MAP-13-R1-20261017T083612Z-3c577add` | `completion_ticks`=27; `constraint_satisfaction_ratio`=0.8; `correct_sequence`=1; `illegal_door_attempts`=0 |
| 2 | success | True | GATE_OPENED | 19 | 0.00938184 | `V8-MAP-13-R2-20261017T084003Z-2a5b828c` | `completion_ticks`=19; `constraint_satisfaction_ratio`=0.8; `correct_sequence`=1; `illegal_door_attempts`=0 |

三次重复成功 2/3。n=3 只描述重复运行，不做显著性断言；MiMo 失败是合法结果，不能由 Oracle 成功率替代。

## 10. 未决问题与边界说明

静态约束、无随机；两次错误开门是硬上限。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `5/5`；oracle: `verified`；fixtures: `4/4`。
- 正式 3 局：`completed`；最终状态：`finalized`。
