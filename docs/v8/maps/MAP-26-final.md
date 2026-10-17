# MAP-26 定稿：失败的维修计划

| 字段 | 值 |
|---|---|
| 世界 | lunar |
| 难度 | 中等 |
| 条件 | `free_diagnosis` |
| 生命周期 | design_audited → rules_frozen → runtime_verified → metrics_verified → mimo_3runs_completed → finalized |
| scenario_hash | `3a292dd03e01fb8fdd588e2b08dbdc3cf0b08cf975e3633e37750d9f4d612c0c` |
| rule_hash | `a0de5a1957c0a82cff7636ba86f8ce513c85d7ec30edee810885dcd882cc595e` |
| prompt_hash | `86d0b168b5e5b5e3bd85e66cb5657421044856a886a6e2e5be0076440ab878f7` |
| metric_schema_hash | `6a53a449699c1a647d23711002166ee5987f86cff10e1fcada31334bc29cdcea` |
| oracle_hash | `81b9cb207b7b78ba4c710b26c0edb0122fc8faa555c6fe661fb1dfa230eb8f23` |
| commit | `a13ba1e11e267447fbb3c8a4c6b1f5319a313806` |

## 1. 设计意图与独特机制

本图不是“找到一个零件并安装”的收集任务。它把一个同样的通信中断报警，三种互斥故障、粗糙历史日志、可重复但有区别力的台架测试、错误替换反馈、可回滚备件和递增的同类重试成本串成一条自我纠错链。没有全局倒计时；失败来自把仅有的两枚备件消耗在错误部件上。

运行时的状态机、动作前置与失败码见本文件第 4–5 节。

## 2. 与同世界另两图的区别

- **MAP-25**（简单）：本图与同世界另两图的机制差异：MAP-26 有诊断反馈与备件预算、核心是错误后修正；MAP-27 是多主体协同。本图是单 Agent 单线程流程，故障固定且单一，核心是“别在准备阶段漏步”：穿服、挂绳、排压、检查、诊断、维修、返舱之间的前置关系不可交换。
- **MAP-27**（困难）：本图与同世界另两图的机制差异：MAP-25 是单人顺序合规（穿服/挂绳/诊断），没有货舱、电池和远程救援；MAP-26 是隐藏故障的诊断-反馈-回滚循环。本图没有隐藏故障（中继 OFFLINE 是公开状态），难度来自两格货舱里互斥工具的先后、14 电与 18 氧按道路原子并行消耗、P–E 四 tick 远路与 S–E 一 tick 短路的选择，以及“现场稳定 ≠完成救援”的两阶段救援（稳定 → 中继在线后才可远程撤离）。

本图动作、状态变量与失败码均独立于上述两图；共享的只有 `MapEnvironment` 生命周期、一个逻辑时钟、图边工具和哈希函数。

## 3. 公开与私有状态

公开 Observation 字段（白名单）：

`alert`, `carried_spare_units`, `communication_restored`, `current_node`, `current_tick`, `installed_candidates`, `last_action_error_code`, `log_readings`, `spare_units_at_B`, `test_readings`

私有 `judge_state` 字段（不进入 Observation 或 prompt）：

`carried`, `communication_restored`, `failed_by_part`, `fault_part`, `installed`, `log_readings`, `map_id`, `node`, `seed`, `spares_at_B`, `status`, `terminal_reason`, `test_readings`, `tick`

泄漏扫描：公开字段全部在 `PUBLIC_FIELDS` 内，prompt 不含指标 id、`judge_state` 或 Oracle 路径。离线门禁结果：通过。

## 4. 动作契约

- `move`：`to`
- `read_log`：`log_id`
- `replace`：`part_id`
- `restart`：无附加字段
- `rollback`：无附加字段
- `take_spare`：`part_id`
- `test`：`test_id`

字段组合必须精确匹配；多字段、少字段或同义字段都会被拒绝为 `INVALID_ACTION_SCHEMA`。

## 5. 结算顺序、胜负与失败码

统一顺序：形状校验 → `_apply` 提交动作效果 → 按 `_action_cost` 推进 tick → `_after_tick` 结算周期事件 → 检查步数上限。

本图结算要点：复用 V6 规则：诊断→测试→取备件→更换→rollback；错误备件消耗备件额度。

- 成功码：见运行时
- 失败码：`由终局 `verdict`/动态码表达，见失败路径`

## 6. 资源边界与护栏

资源边界由地图私有状态逐 tick 结算；步数上限 160，决策预算见冻结清单。护栏指标（guardrail）只报告，不参与成功判定；任何越界、欠供、碰撞、泄漏或不安全操作都保留在 judge metrics 与失败归因中。

## 7. 指标（V7 登记，V8 只做五态投影）

| 指标 | 类别 | 方向 | 公式 | 分母 | 缺失规则 | 截尾规则 |
|---|---|---|---|---|---|---|
| `map26.diagnosis_accuracy` | primary | higher_is_better | 1 if last replaced part == frozen fault_part else 0 | 提交过 replace 的 episode | 无 replace → N/A；无冻结真值 → UNAVAILABLE | 截尾且未完成诊断 → CENSORED |
| `map26.legal_action_rate` | diagnostic | higher_is_better | accepted decisions / submitted decisions | 模型决策数 | 0 次决策 → N/A | 按已提交决策计算 |
| `map26.recovery_latency` | primary | lower_is_better | tick(first rollback/test/different-part replace) - tick(first wrong feedback) | 至少发生一次错误替换的 episode | 没有错误替换 → N/A | 至终局仍无有效调整 → CENSORED |
| `map26.repair_success` | primary | higher_is_better | 1 if final communication_restored else 0 | episode | 无公开 communication_restored → UNAVAILABLE | step-limit 截尾 → CENSORED |
| `map26.repeat_error_rate` | guardrail | lower_is_better | replaces of an already-failed part / total wrong replacements | 错误替换尝试数；0 则 N/A | 无错误替换 → N/A | 按已发生替换计算 |
| `map26.spares_remaining` | guardrail | higher_is_better | spare_units_at_B + len(carried_spare_units) | episode | 公开字段与 judge 均缺失 → UNAVAILABLE | 按已观察库存计算 |
| `map26.tests_run` | diagnostic | lower_is_better | count(test) | episode | 无 → 0 | 按已发生测试计算 |

比例类返回 `{numerator, denominator}`；分母为 0 记 `not_applicable`；无法计算的配对指标返回 `None`，不填 0。

## 8. Oracle 与离线回放

- Oracle 用例：MAP-26-solver-success（9 步）
- 手算 fixture：same-wrong-part-twice（8 步）, diagnose-then-repair（11 步），补充冻结后失败用例 `two-different-wrong-parts`（8 步，见 `docs/v8/extra-fixtures.json`）
- 同初态确定性重放：通过；终止后不变性：通过；无泄漏：通过。
- 单图自检：`.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-26` → `MAP-26: OK`。

## 9. MiMo 三次正式运行

正式 90 局尚未生成；本节由 `scripts/report_v8_maps.py` 在运行结束后回填。

## 10. 未决问题与边界说明

复用 V6 `map26_l1_antenna_fault`；恢复地板与诊断准确率分开报告。

## 11. 验收结论

- design: `audited`；runtime: `verified`；metrics: `7/7`；oracle: `verified`；fixtures: `3/3`。
- 正式 3 局：`pending`；最终状态：`runtime_verified`。
