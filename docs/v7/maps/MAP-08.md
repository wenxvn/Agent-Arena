# MAP-08｜深海｜中等｜看不见的裂缝

```yaml
map_id: MAP-08
world: deep_sea
nominal_level: 中等
capability_primary: active_experiment_design
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: 1d40008240e719d1af0c7189a9456dcc313ce0c9e2e136d49e56665f197dab8d
source_design_hash: 9c7cc3ef4445bc80ee19942196a5964ea01d4b15c1ba0a5c89c517619dad90b4
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: runtime
metric_status: implemented_offline_validated
```

## 1. 测量构念与不可替代玩法

测“主动实验设计与停止判断”。三个候选漏点 B/D/F 的初始观察、水位、普通传感器底噪与房间描述完全相同；唯一可分辨来源是主动执行 X/Y 压力测试。X/Y 各有确定签名，单次测试可能只排除一部分候选；唯一密封剂只能用一次，错误封堵立即失败。成功不是“猜中漏点”，而是用合法测试把假设集缩到可行动，并在水位越过 7.0 前完成修复。

## 2. 真实规则字段

- 拓扑：六舱环 `A-B-C-D-E-F-A`；测试站 `X` 连 A/C，`Y` 连 D/F；每边 1 tick。
- 初始：`location=A, tick=0, water=1.0, sealant_count=1, sealed=false`。
- 压力：每个动作耗时内，未修复则每 tick `water += 0.5`；`water>7.0` 立即失败；`=7.0` 安全。
- 测试：`pressure_test_X`、`pressure_test_Y` 各耗 2 tick；签名：
  - B: X=`pulse_amber`, Y=`pulse_slate`
  - D: X=`pulse_slate`, Y=`pulse_cobalt`
  - F: X=`pulse_slate`, Y=`pulse_slate`
- 修复：正确耗 1 tick 并成功；错误耗 4 tick、消耗密封剂并以 `SEALANT_MISUSED` 失败。
- V6 实例参数化：L1 两候选 B/D；L2 改覆盖（X 单测即可区分）或改候选/拓扑（B/C/D）；L3 原场景。所有实例共享同一公开签名语义字段。
- 公开：位置、边、tick、水位、候选集、等先验、签名语义、密封剂数、测试结果。
- 离线裁判：`true_leak`、seed 映射。绝不进入 Observation。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map08.diagnosis_accuracy` | primary | `1[repair target == true_leak]` | 0/1 / 高 | 提交过 repair 的 episode | 无 repair → N/A；无真值 → UNAVAILABLE |
| `map08.candidate_reduction` | primary | `(N_initial − N_final) / N_initial` | 比例 / 高 | 初始候选数 | 签名不可解析 → UNAVAILABLE；无测试 → 0 |
| `map08.information_gain_bits` | diagnostic | `Σ_t [H_t − H_{t+1}]`，等先验候选集 | bit / 高 | 合法测试数 | 0 测试 → 0 |
| `map08.peak_core_water` | guardrail | `max_t water_t` | 水位 / 低 | episode | 无读数 → UNAVAILABLE |
| `map08.wrong_repair` | guardrail | `1[SEALANT_MISUSED]` | 0/1 / 低 | 提交过 repair 的 episode | 未 repair → N/A |
| `map08.tests_run` | diagnostic | 合法 X/Y 测试数 | 次 / 低 | episode | 0 → 0 |
| `map08.legal_action_rate` | diagnostic | 接受决策 / 提交决策 | 比例 / 高 | 模型决策数 | 0 → N/A |

实现位置：`src/agent_arena/v7/metrics/map08.py`。候选缩小只复演公开签名，不读真漏。

## 4. 能力混淆分析

- 高诊断率可能只因为候选只有 2 个（L1）；必须与 L3 分报，不能把 L1 的 100% 当完整诊断能力。
- 高信息增益可能来自测试次数多，而不是测试选得好；必须报 `tests_run` 与候选缩小。
- 低分可能由水位时序误解造成（测试耗时 2 tick），不是诊断错；用 `peak_core_water` 与终止码区分。
- 重复同一测试有 0 信息增益，但会让水位继续上涨；重复率是过程诊断，不是能力本身。
- V6 真实结果 6/6 是**该模型在该实例集上的天花板**，不证明 MAP-08 无区分度；L2/L3 与偏置先验仍需更多实例。

## 5. 两条手算轨迹（来自确定性环境回放，非模型）

**X-first 成功（seed 0，真漏 B，6 tick）**：`move X_A`（1）→`pressure_test_X`（2 tick，tick3，读数 amber）→`move X_A`（4）→`move A_B`（5）→`repair_leak B`（6）。水：1.0→1.5→2.5→3.0→3.5→4.0。指标：诊断 1；候选缩小 `(3−1)/3=0.667`；信息增益 `H(3)−H(1)=1.585 bit`；峰值水 4.0；测试 1；错误封堵 0；合法动作率 1.0。

**Y-first 边界成功（seed 0，真漏 B，12 tick）**：`move F_A`（1）→`move Y_F`（2）→`pressure_test_Y`（2 tick，tick4，读数 slate）→`move Y_D`（5）→`move C_D`（6）→`move X_C`（7）→`pressure_test_X`（2 tick，tick9，读数 amber）→`move X_C`（10）→`move B_C`（11）→`repair_leak B`（12）。水：1.0 + 0.5×12 = **7.0**，恰好安全。指标：诊断 1；候选缩小 0.667；信息增益 1.585 bit；峰值水 7.0；测试 2；合法动作率 1.0。

## 6. 三个机制特有失败

1. **未测试就修错**：seed 8（真漏 F）直接 `move A_B` + `repair B`；耗 4 tick、水 3.5、`SEALANT_MISUSED`；诊断 0、错误封堵 1、测试 0。
2. **重复无信息测试**：X 已给出 amber 后继续测 X，信息增益 0，水位继续上涨；最终到达 F 前越过 7.0。
3. **把负结果读成阳性**：X 的 `pulse_slate` 被当成“B 确认”，实际候选是 D/F；错误封堵后无法重试。

## 7. 两个边界

- **水位 7.0 vs 7.5**：恰在 tick 12 完成正确修复，水=7.0，仍成功；若再多走一步，水=7.5，`CORE_WATER_LIMIT_EXCEEDED`。上述 Y-first 轨迹就是 7.0 边界。
- **单测 vs 双测信息**：L3 中 X 的 `slate` 只排除 B，剩 D/F，信息增益 `H(3)−H(2)=0.585 bit`，必须再测 Y 才能唯一；L2 改覆盖实例中 X 可能一次唯一，不能把 L3 的“必须两次”套到所有实例。

## 8. 信息泄漏负例

若 Observation 或 prompt 公开 `true_leak`、seed→漏点映射、或“X 的 amber 就是 B”的答案表，主动诊断被替代。V7 只允许公开签名语义（每个测试对各候选的读数）与测试结果；真漏只在离线裁判与 `diagnosis_accuracy` 中使用。

## 9. Oracle/求解状态

V4 `oracle_trace.jsonl` 有 X-first/Y-first 两条手写成功与三条失败；V6 用独立构造求解器为每个实例生成 5–8 动作成功路径，并在真实环境逐步回放（`scripts/validate_v6_instances.py`，45 次实例/seed 回放）。`docs/v6/validation-report.md` 记录 45/45 回放成功；`docs/v6/pilot-report.md` 记录 6/6 真实 API 成功（单次、每条件 1 局）。**最优性**：V6 求解器给的是构造解，不是全局最短动作证明。

## 10. 与同世界另两图差异

**vs MAP-07**：MAP-07 的水位完全可见，动作直接改变物理水量，失败是舱室溢流；MAP-08 的关键状态是**隐藏漏点与候选集**，动作通过测试改变假设集合，失败是错误封堵或水压耗尽。MAP-07 的主指标是超额水量与因果方向率，MAP-08 是诊断准确率与信息增益；把 MAP-08 的漏点公开会退化成 MAP-07 式的直接控制题。

**vs MAP-09**：MAP-09 是电力、泵、氧气、通信的跨系统耦合，修复一个系统可能诱发另一系统故障；MAP-08 只有一个隐藏故障点和一条诊断链，没有氧气/电池/通信预算。MAP-09 的失败是短路、氧耗尽、发报电量不足，MAP-08 是错封堵/水压；两者的资源循环和不可逆失败模式不同。

## 11. 可计算性来源

`map08.py` 从 `observation.published_candidate_set`、`known_test_semantics`、`test_results`、`current_core_water`、`interact` 动作与 `judge_state.true_leak` 计算。签名解析用公开文本正则；解析失败返回 UNAVAILABLE，不猜。截尾时诊断/错误封堵标 CENSORED，过程量按已发生事件计算。

## 12. 难度定位与对照

D=(3,1,0,2,2,3)。比 MAP-07 多隐藏真值与主动测量，不以走廊变长提升。预登记对照：**有假设表 vs 无假设表**；同候选、同公开读数、同预算。V6 中该对照 6/6 全过，属天花板，需加难度或偏置先验后再判断敏感性。

## 13. 未决

V6 的 4 个实例与 V4 单一 `map_spec.yaml` 并存；V7 按实例公开签名计算，不写死 B/D/F。真实 API 6/6 为单次结果，不能外推跨模型；实例仍 `pending_human_review`。
