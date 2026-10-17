# MAP-26｜月球｜中等｜失败的维修计划

```yaml
map_id: MAP-26
world: moon
nominal_level: 中等
capability_primary: feedback_driven_diagnosis
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: aecc9f149a8afeddff968549599058f3bb54dfdad38d806bd9483292771b5b81
source_design_hash: 193fdc2cb074e99017757e9170254d4f006d154edd810b690dc41968aa1046ae
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“把错误替换反馈变成诊断修正”。通信中断有三种互斥故障（`power_regulator / antenna_coupler / software_image`），日志只给**非唯一**线索（“供电或下游”），D 的三个 typed 测试各自只在对应故障时返回异常，B 只有两枚可配置备件。Agent 可以花时间先诊断，也可以先按合理假设试换、读到“自检通过但链路仍断”后**回滚**再转测。核心不是“找到 correct part”，而是“错了以后是否吸收反馈、是否在备件耗尽前改策略”。

## 2. 真实规则字段

- 拓扑：`T—D—A—B`，每条相邻通道 1 tick；起点 T；只看见 `COMMUNICATION_LOST`。
- 备件：B 中 2 枚通用维修盒，领取时配置为三个候选之一；最多同时携带 2 枚。
- 故障：每局恰一个、整局不变；seed0 天线耦合器、seed1 电源稳压器、seed2 软件镜像（映射只在裁判侧）。
- 日志：所有 seed 的 `read_log(COMM_LOSS_LAST_TRANSMIT)` 返回同一条 `TRANSMIT_SURGE_BEFORE_LINK_LOSS_POWER_OR_DOWNSTREAM`，不能区分供电/下游。
- 测试：D 的三个 typed 测试各 1 tick；`bus_load` 仅在电源故障时返回 `BUS_VOLTAGE_DROOP`，`antenna_loopback` 仅天线故障返回 `ANTENNA_LOOPBACK_OPEN`，`software_checksum` 仅软件故障返回 `IMAGE_CHECKSUM_MISMATCH`；重复测试不改变事实。
- 替换：A 处 `replace(part_id)` 耗 1 备件；正确返回 `SELECTED_COMPONENT_REPLACED_RESTART_REQUIRED`，要 `restart` 才恢复；错误返回“本部件自检通过但链路仍断”，错误部件留在候选槽、不暴露真故障；同一 part 再次错误替换成本递增（1 + 此前错误次数）。
- 回滚：A 处 `rollback` 恢复槽状态并救回本次错误部件，1 tick；不退时间、不清重试计数；无未决错误安装 → `INVALID_ROLLBACK`（零成本）。
- 失败：链路仍断且未安装备件降到 0 → 立即 `SPARES_EXHAUSTED`；**即使最后一次装的是正确件，若装完没有备用件也不能成功**（运行时 `uninstalled_spares >= 1` 才置 SUCCESS）。
- 成功：`communication_restored` 且至少余 1 枚备件（`ALL_OBJECTIVES_COMPLETE`）。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map26.repair_success` | primary | `1[final communication_restored]` | 0/1 / 高 | episode | 缺字段 → UNAVAILABLE；截尾 → CENSORED |
| `map26.recovery_latency` | primary | 首个有效调整 tick − 首个错误反馈 tick | tick / 低 | 至少一次错误替换 | 无错误替换 → N/A；至终局无调整 → CENSORED |
| `map26.repeat_error_rate` | guardrail | 重复安装已失败 part 的次数 / 错误替换数 | 比例 / 低 | 错误替换数；0 → N/A | 优先用 `judge_state.failed_by_part`，退化用结果码 |
| `map26.spares_remaining` | guardrail | `spare_units_at_B + len(carried_spare_units)` | 件 / 高 | episode | 公开字段与 judge 都缺 → UNAVAILABLE |
| `map26.diagnosis_accuracy` | primary | `1[最后一次 replace 的 part == 冻结故障件]` | 0/1 / 高 | 提交过 replace | 无 replace → N/A；无真值 → UNAVAILABLE |
| `map26.tests_run` | diagnostic | `count(test)` | 次 / 低 | episode | 无 → 0 |
| `map26.legal_action_rate` | diagnostic | 接受决策 / 提交决策 | 比例 / 高 | 决策数；0 → N/A | — |

实现：`src/agent_arena/v7/metrics/map26.py`，共 7 条 `implemented=True`。`recovery_latency` 的“有效调整”是 `rollback`、`test` 或换成**不同** part 的 `replace`；同一错误件再装一次不算。

## 4. 能力混淆分析

- `repair_success=1` 可能伴随 `terminal_reason=SPARES_EXHAUSTED`：通信灯亮了但备件为 0，**终局仍是失败**。必须与 `spares_remaining` 并列。
- `diagnosis_accuracy=1` 不等于修复成功：可能没有 `restart`，或装完已无备件。
- `repeat_error_rate=0` 可能只因为“只错了一次”：分母是错误替换数，0 次错误 → N/A，不能算 0 分完美。
- `recovery_latency=1` 可能只是“立刻回滚但没换策略”：必须同时看之后是否做了 `test` 或换了不同 part。
- `tests_run` 多可能更准，也可能只是重复测试；重复测试不改变事实，必须与诊断准确率并列。
- `spare_rich` 实例（初始 3 枚）不能与标准 2 枚直接比成功率；备件数是预算，不是能力。

## 5. 两条手算轨迹

**A. 先诊断再维修（tick11 恢复，余 1 枚）**：`T→D`(1)、读日志(2)、`test bus_load`(3)、`test antenna_loopback`(4)、`test software_checksum`(5)、`D→A`(6)、`A→B`(7)、领天线模块(8)、`B→A`(9)、`replace antenna`(10)、`restart`(11)。指标：`repair_success=1`；`recovery_latency=N/A`（无错误替换）；`repeat_error_rate=N/A`；`spares_remaining=1`；`diagnosis_accuracy=1`；`tests_run=3`；合法率 1.0。

**B. 先试一次再纠错（tick16 恢复，余 1 枚）**：读日志(2)、`D→A`(3)、`A→B`(4)、领电源模块(5)、`B→A`(6)、`replace power`(7，错误反馈)、`rollback`(8，收回电源)、`A→D`(9)、`test antenna_loopback`(10，开路)、`D→A`(11)、`A→B`(12)、领天线(13)、`B→A`(14)、`replace antenna`(15)、`restart`(16)。指标：`repair_success=1`；`recovery_latency = 8−7 = 1`；`repeat_error_rate = 0/1 = 0.0`；`spares_remaining=1`；`diagnosis_accuracy=1`；`tests_run=1`。

> A 用 3 次测试换 0 次错误；B 用 1 次错误 + 1 次测试换 5 tick 延迟。两者都成功，且都留 1 枚备件——说明“先诊断”不是唯一正解。

## 6. 三个机制特有失败

1. **F01 盲换两件**：不读日志不测试，先换电源再换软件；两次反馈都表明“支路自检通过但链路仍断”，备件归零 → `SPARES_EXHAUSTED`。`repeat_error_rate=0`，但两个不同错误都发生了。
2. **F02 同错重试**：第一次错误换电源耗 1 tick，第二次仍换同一电源耗 2 tick；没有天线可修 → `SPARES_EXHAUSTED`。`repeat_error_rate = 1/2 = 0.5`，`recovery_latency` 因无有效调整 → CENSORED。
3. **F03 忽视反证**：测得电源稳定、软件校验有效，仍先后更换电源与软件；两枚用尽失败。信息已足够，错误在**不使用反证**；`diagnosis_accuracy=0`。

## 7. 两个边界

- **恰余 1 枚成功（B01）vs 最后一枚错件（B02）**：错误替换耗尽库存会**立即** `SPARES_EXHAUSTED`，不是等到下一次动作；正确件装在最后一枚上同样因 `uninstalled_spares==0` 失败（B05/B06）。这是本图最容易被误读的规则。
- **重试成本 1 vs 2 tick（B03）**：同一 part 第二次错误替换耗时 2 tick，回滚不清零该计数；跨 seed 的初始观察相同，只有测试读数和替换反馈产生区别（B04）。

## 8. 信息泄漏负例

若 Observation/prompt 直接给 `fault_part`、seed 映射或“换天线就对了”，诊断与反馈纠错被替代。V7 只允许公开当前位置、日志读数、已做测试的读数、备件/携带/已安装候选、最近动作结果与终局；`planning/private_seed_reference.yaml` 与 `judge_state.fault_part` 只在离线裁判侧。`replace` 的错误反馈不得包含真故障 ID。

## 9. Oracle/求解状态

V4 `oracle_trace.jsonl` + `planning/hand_traces.json` 有两条手写成功（tick11/16，均余 1 枚）；`failure_traces/cases.yaml` 有 F01–F03 与 B01–B06。V6 7 个实例（4 个 free 诊断 + 3 个恢复前缀）均有构造解；真实 API 13 局：**free 3/4**（software 故障失败）、**recovery 0/9**（全 `SPARES_EXHAUSTED`）。恢复前缀本身已被求解器证明可修复，失败属策略/流程，不是不可解。

## 10. 与同世界另两图差异

**vs MAP-25**：MAP-25 是固定单一故障的**顺序合规**题，错误来自漏步骤；MAP-26 故障隐藏、反馈有信息、备件有限，错误来自**不吸收反馈**。MAP-25 没有 rollback，也没有递增重试成本。

**vs MAP-27**：MAP-27 是多主体协同与通信，核心是任务分配；MAP-26 单 Agent、单线程，核心是诊断-替换-回滚循环。MAP-26 的指标是恢复延迟/重复错误率，MAP-27 是协同完成率/关键路径。

## 11. 可计算性来源

需要的公开字段：`current_tick, current_node, log_readings, test_readings, spare_units_at_B, carried_spare_units, installed_candidates, communication_restored, last_action_result, terminal_reason`，以及每次 `replace/test/rollback/restart` 的动作与结果。`recovery_latency` 由首个错误反馈与首个有效调整的 tick 差；`repeat_error_rate` 优先用 `judge_state.failed_by_part`，退化时用结果码；`diagnosis_accuracy` 需要 `judge_state.fault_part` 或冻结实例表（`references.MAP26_FAULT_PART`）。全部可离线复算。

## 12. 难度定位与对照

D=(2,2,1,2,2,2)。相对 MAP-25 提升 **V↑（故障隐藏，需测试）与 R↑（两枚备件预算 + 递增重试成本）**；E 保持 1（无事件，只有反馈）。不会与 MAP-25 混淆：MAP-25 的指标是检查覆盖率/顺序，MAP-26 是恢复延迟/重复错误率。

预登记对照：**`free_diagnosis` vs `recovery_full` vs `structured` vs `hidden`**（V6 机制），以及 **feedback 可见 vs 隐藏**。所有条件共享实例、备件、故障与预算；hidden 是信息剥夺下限，不能与 free 混报成功率。

## 13. 未决

- 成功谓词包含“至少余 1 枚备件”，因此“通信恢复但 `SPARES_EXHAUSTED`”会让 `repair_success=1` 与终局失败并存；报告必须同时给 `terminal_reason`，否则会误读为成功。
- `recovery_latency` 在 F02 这类“重复同一错误”的轨迹上为 CENSORED；需要一个专门用例固定该口径。
- `diagnosis_accuracy` 用“最后一次 replace”而非“是否曾经装对”，因为装对后可能被后续动作覆盖；运行时需确认 `installed` 槽语义。
- V6 free 3/4 与 recovery 0/9 均为单次、每条件 1 局；所有实例 `pending_human_review`。
