# V11 30 图最终体验检查（map UX checklist）

- 生成时间：2026-10-20T02:43:23+00:00
- HEAD：`eb2f64a281677a0fce881769a6592cce1be6f7d9`
- 方法：逐图读取公开目标 / 规则 / 动作契约 / 初始 Observation，真实运行一局离线公开策略，读取逐步回放并导出 CSV；随后人工复核说明是否足以让普通用户理解。
- 不改世界规则、成功条件、Oracle 或指标公式；发现标题缺失只在展示层补全。
- 判定 30/30：全部可选中、可启动、可回放、可导出。

## 1. 总表

| 图 | 世界 | 标题 | 公开目标 | 规则 | 动作 | 起点 | 回放 | 判定 |
|---|---|---|---|---:|---:|---|---|---|
| MAP-01 | 飞船 | 破损的曙光号 | ✓ | 5 | 5 | `location=B` | 15 步 / SUCCEEDED | PASS |
| MAP-02 | 飞船 | 双重警报 | ✓ | 6 | 5 | `location=C` | 9 步 / SUCCEEDED | PASS |
| MAP-03 | 飞船 | 最后的百步 | ✓ | 7 | 6 | `location=U2` | 31 步 / SUCCEEDED | PASS |
| MAP-04 | 灯塔 | 潮汐密道 | ✓ | 5 | 5 | `location=T` | 9 步 / SUCCEEDED | PASS |
| MAP-05 | 灯塔 | 三束信号 | ✓ | 5 | 5 | `location=C` | 19 步 / SUCCEEDED | PASS |
| MAP-06 | 灯塔 | 暴风眼 | ✓ | 6 | 4 | `location=Q` | 3 步 / SUCCEEDED | PASS |
| MAP-07 | 深海站 | 阀门方向 | ✓ | 5 | 4 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 10 步 / SUCCEEDED | PASS |
| MAP-08 | 深海站 | 漏点诊断 | ✓ | 6 | 4 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 4 步 / SUCCEEDED | PASS |
| MAP-09 | 深海站 | 深海连锁故障 | ✓ | 5 | 5 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 4 步 / SUCCEEDED | PASS |
| MAP-10 | 极地 | 最后一桶燃料 | ✓ | 4 | 4 | `location=A` | 2 步 / SUCCEEDED | PASS |
| MAP-11 | 极地 | 失联的小队 | ✓ | 5 | 3 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 3 步 / SUCCEEDED | PASS |
| MAP-12 | 极地 | 极夜三十天 | ✓ | 5 | 2 | `{"terminal": false, "last_action_result": "READY", "day": 0}` | 30 步 / SUCCEEDED | PASS |
| MAP-13 | 金字塔 | 四神之门 | ✓ | 6 | 5 | `location=C` | 20 步 / SUCCEEDED | PASS |
| MAP-14 | 金字塔 | 说谎的祭司 | ✓ | 7 | 5 | `location=P` | 12 步 / SUCCEEDED | PASS |
| MAP-15 | 金字塔 | 会变化的迷宫 | ✓ | 7 | 5 | `area=A` | 12 步 / SUCCEEDED | PASS |
| MAP-16 | 地铁 | 单线预约与节点容量 | ✓ | 6 | 5 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 20 步 / SUCCEEDED | PASS |
| MAP-17 | 地铁 | 早高峰 | ✓ | 5 | 1 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 12 步 / SUCCEEDED | PASS |
| MAP-18 | 地铁 | 故障传播 | ✓ | 7 | 1 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 12 步 / SUCCEEDED | PASS |
| MAP-19 | 火山 | 温度临界点 | ✓ | 6 | 5 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 37 步 / SUCCEEDED | PASS |
| MAP-20 | 火山 | 冷却网络 | ✓ | 10 | 5 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 30 步 / SUCCEEDED | PASS |
| MAP-21 | 火山 | 喷发倒计时 | ✓ | 6 | 5 | `location=O` | 6 步 / SUCCEEDED | PASS |
| MAP-22 | 丛林 | 无地图的丛林 | ✓ | 6 | 5 | `current_sign=camp` | 35 步 / SUCCEEDED | PASS |
| MAP-23 | 丛林 | 迷雾中的遗迹 | ✓ | 5 | 5 | `location=A` | 9 步 / SUCCEEDED | PASS |
| MAP-24 | 丛林 | 消失的道路 | ✓ | 7 | 6 | `location=A` | 10 步 / SUCCEEDED | PASS |
| MAP-25 | 月球 | 第一次出舱 | ✓ | 5 | 9 | `location=H` | 16 步 / SUCCEEDED | PASS |
| MAP-26 | 月球 | 失败的维修计划 | ✓ | 7 | 5 | `{"terminal": false, "last_action_result": "READY", "tick": 0}` | 4 步 / SUCCEEDED | PASS |
| MAP-27 | 月球 | 月球车 | ✓ | 6 | 7 | `location=B` | 16 步 / SUCCEEDED | PASS |
| MAP-28 | 古堡 | 消失的王冠 | ✓ | 7 | 6 | `location=H` | 18 步 / SUCCEEDED | PASS |
| MAP-29 | 古堡 | 不可靠的证人 | ✓ | 6 | 5 | `location=H` | 31 步 / SUCCEEDED | PASS |
| MAP-30 | 古堡 | 午夜审判 | ✓ | 7 | 6 | `location=H` | 34 步 / SUCCEEDED | PASS |

## 2. 逐图留痕

每张图记录：公开目标、规则条数与全文、动作工具、起点、成功/失败反馈、离线回放与导出结果、说明修复。

### MAP-01 · 破损的曙光号（飞船 / 简单）

- **公开目标**：修复船壳、恢复供氧与主电源、完成气闸检查并在舰桥确认。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：5 个工具：`inspect`、`interact`、`move`、`pickup`、`wait`
- **起点**：`location=B`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：15 步，结局 `success`，主指标 `map01.v10.mission_success` = 1（VALID）；JSON 19098 B，CSV 10720 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 舰内拓扑：B（舰桥）—H（中枢）—W（船壳/配电）、H—P（反应堆）、H—A（气闸）；W—P 服务通道只在船壳修补后才能通行。
2. 供氧继电器可在 B/H 启动供氧；启动后若把配电切到维修臂，供氧会中断，断供期间氧气储备每 tick 递减，超过容错上限立即失败。
3. 修补船壳的顺序：先取 patch_kit（需供氧稳定）→ 在 W 把配电切到维修臂 → patch 船壳 → 切回供氧。
4. 母线重置必须在船壳修补后；气闸压力测试要求供氧与母线同时在线；最后回 B 在舰桥确认。
5. 公开配电参数（容量/固定负载/供氧/维修臂）见 inspect(power_diagram)；本实例的氧气储备与断供容错以 Observation 的 oxygen_reserve 与规则为准。

</details>

### MAP-02 · 双重警报（飞船 / 中等）

- **公开目标**：导航核心故障与舱段泄漏会按事件顺序出现；泄漏后同时保住导航核心、把乘员送进逃生舱，并在时限内完成。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`inspect`、`interact`、`move`、`pickup`、`wait`
- **起点**：`location=C`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：9 步，结局 `success`，主指标 `map02.v10.mission_success` = 1（VALID）；JSON 15184 B，CSV 7991 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. C 是中枢，连接 L1（乘员区）与 R1（导航核心）；L1–L2 通向乘员，R1–R2 通向逃生舱；C_X + X_L2 是备用通道。
2. 导航核心在 R1，需用维修包固定（interact(nav_core, brace_in_case)）；维修包开局可用一次。
3. 乘员在 L2：先 pickup(crew) 再护送；把乘员带到 R2 即进入逃生舱。
4. **泄漏会在若干动作后出现**（具体时点不公开）；公告后若未隔离 L1，船舱扩散倒计时递减，归零则导航核心报废；同时乘员压力倒计时独立递减，归零则任务失败。
5. 在 C 用 interact(center_gate, isolate_L1) 可隔离 L1；关闭后 C↔L1 不可通行。
6. 导航核心固定 + 乘员进逃生舱**两者都完成**才算成功；deadline 见 Observation。

</details>

### MAP-03 · 最后的百步（飞船 / 困难）

- **公开目标**：依次完成供电、读码并冷藏样本、EVA 修天线、发送遥测，最后在舰桥提交早前读到的航线码。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：6 个工具：`inspect`、`interact`、`move`、`submit`、`wait`、`write_memory`
- **起点**：`location=U2`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：31 步，结局 `success`，主指标 `map03.v10.code_recall_correct` = 1（VALID）；JSON 48037 B，CSV 39065 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 五阶段必须按 P1 供电(D1 aux_panel/restore_power) → P2 读清单并冷藏样本(实验室 sample_manifest/read_tag 后 cryo_case/stabilize_sample) → P3 EVA 修天线(V antenna/repair) → P4 发遥测(U3 telemetry/transmit) → P5 在 U2 submit route_console 航线码；跳步返回 PHASE_OUT_OF_ORDER。
2. 航线码格式为 1 个大写字母 + 1 个数字；只在首次 read_tag 的结果与紧随其后的一个 Observation 中出现一次。稳定样本后清单封存，之后无法再读；只有 1 次提交机会。
3. 读码后样本开始升温：sample_thermal_ticks 从 4 递减，必须在第 4 个后续动作内完成冷藏。
4. write_memory(facts)：facts 为 [{"key": str, "value": str}]，每次 1 tick，最多保留 3 条（同 key 覆盖），内容原样显示在 agent_notes；环境不校验真伪。这是你唯一能跨越很多步保存信息的通道。
5. antenna_panel_code 与 telemetry_ack_code 与航线码同格式，但不是航线码。
6. EVA：只有 eva_supply=3 时才能从 D3 进入 V；进入 V、在 V 内的每个动作、返回 D3 各消耗 1；在 V 内 eva_supply 归零立即失败。
7. tick 达到 return_window_end_tick 仍未校准航线即失败；每个动作（含被拒动作）耗 1 tick。

</details>

### MAP-04 · 潮汐密道（灯塔 / 简单）

- **公开目标**：在救援船抵达前把灯芯装进灯塔并点亮；越早越好。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：5 个工具：`inspect`、`interact`、`move`、`pickup`、`wait`
- **起点**：`location=T`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：9 步，结局 `success`，主指标 `map04.v10.time_margin` = 1（VALID）；JSON 13106 B，CSV 5889 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 地形：T—S—G 与 T—B1—…—B4—D—G 两条路线；G 存放灯芯，T 有灯塔。
2. tide_phase 每 tick +1 并对 tide_period 取模；open_phases 是安全相位。
3. S_G 只能在安全相位通过；否则失败并耗 3 tick、被潮水推回原侧。
4. pickup(wick) 在 G；interact(lamp, fit_wick) 与 interact(lamp, ignite) 在 T。
5. rescue_deadline_tick 前必须点亮；评分是成功时的时间余量，越早越好。

</details>

### MAP-05 · 三束信号（灯塔 / 中等）

- **公开目标**：在 B[22,25]、R[15,18]、W[29,35] 三个窗口内各发出一束信号。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：5 个工具：`inspect`、`interact`、`move`、`switch_power`、`wait`
- **起点**：`location=C`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：19 步，结局 `success`，主指标 `map05.v10.mission_success` = 1（VALID）；JSON 22117 B，CSV 13063 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. C 是唯一能切换供电的节点；供电一次只能指向 R/B/W 中的**一个**塔，切换必须在 C 进行。
2. 每个塔必须先在塔内完成两步校准（calibrate_align → calibrate_phase_lock）才能发信号；未校准发信号会被拒。
3. 发信号（send_signal）在该动作结算后的 tick 判定是否落在窗口内；窗口结束后仍未发出的塔立即判负。
4. 三塔由 C 经 C_R/C_B/C_W 到达，**各通道耗时不同且随实例变化**，可用一次移动观察 tick 增量。
5. 三个窗口的起止 tick 在 Observation 的 windows 中公开；C 的 schedule_chart 可查看排程（inspect(schedule_chart)）。

</details>

### MAP-06 · 暴风眼（灯塔 / 困难）

- **公开目标**：在截止前修复灯塔；风暴类型未知，可付时间读预报、绕行加固或直接维修。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：4 个工具：`inspect`、`interact`、`move`、`wait`
- **起点**：`location=Q`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：3 步，结局 `success`，主指标 `map06.v10.risk_time_utility` = 0.821429（VALID）；JSON 9798 B，CSV 2551 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 起点 Q（预报站）。边耗时：M_Q=1、Q_P=1、M_G=2、G_P=2；Q_P 与 G_P 是暴露区段。
2. inspect(target_id=forecast) 只能在 Q 使用，耗 2 tick，读数为 short 或 long；预报准确率 0.8，长风暴先验 0.5；重复读取返回同一读数并再耗 2 tick。
3. interact(G, harden) 在 G 耗 3 tick 装上护盾；interact(P, repair_lighthouse) 在 P 耗 2 tick，完成即成功。wait(ticks) 原地等待。被拒动作耗 1 tick。
4. 天气隐藏，三种之一：calm 无风险；short 暴露区段与无护盾维修各 +1/tick；long 暴露区段 +1/tick、无护盾维修 +3/tick、有护盾维修 0。
5. 累计风险超过 4 立即失败；tick 达到 deadline_tick 仍未修好即失败。
6. 评分：成功时 U = 1 − 0.5·风险/5 − 0.5·完成 tick/deadline；失败 U = 0。越早修好、风险越低越好。

</details>

### MAP-07 · 阀门方向（深海站 / 简单）

- **公开目标**：判断阀门开向、及时开阀排水，在截止前把水位压到安全线下。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：4 个工具：`inspect`、`read_gauge`、`turn_valve`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：10 步，结局 `success`，主指标 `map07.v10.mission_success` = 1（VALID）；JSON 13213 B，CSV 6283 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. turn_valve(clockwise|counter)：转对方向开阀（此后每 tick 排水），转错方向会把阀再拧紧一档（进水速率 +1）并耗 1 tick。
2. inspect(control_panel) 耗 1 tick，公开阀门方向与进水/排水的因果，但不告诉你当前开向。
3. read_gauge 耗 1 tick，返回精确水位。
4. 进水从 tick 3 起按 inflow_schedule 上升；水位超过 8 即 FLOODED。
5. tick 10 结算：阀已开且水位 ≤ 8 即成功。

</details>

### MAP-08 · 漏点诊断（深海站 / 中等）

- **公开目标**：用测试把漏点候选缩成唯一站点，封存诊断后再修复。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：4 个工具：`repair`、`run_test`、`seal_diagnosis`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：4 步，结局 `success`，主指标 `map08.v10.mission_success` = 1（VALID）；JSON 10154 B，CSV 3932 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 候选站点 S1, S2, S3, S4, S5；其中恰有一处是真实漏点。
2. run_test(test_id) 耗 1 tick，按**公开分区**返回读数；每个测试只能读一次。
3. candidate_sites 是全部读数与初始候选的交集，随测试实时更新。
4. seal_diagnosis(diagnosis_code)：只有候选集**缩成唯一站点**时才成立；封存后不可更改。
5. repair(target_id) 耗 2 tick，只有与封存诊断一致时才执行；修错会浪费一个备件，两次错修即失败。
6. 截止 tick 14。

</details>

### MAP-09 · 深海连锁故障（深海站 / 困难）

- **公开目标**：同时守住水位、电力与供氧，把水位压到门槛以下再修复。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：5 个工具：`pump`、`repair`、`seal`、`vent`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：4 步，结局 `success`，主指标 `map09.v10.mission_success` = 1（VALID）；JSON 8823 B，CSV 2334 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 每个 tick：漏水使水位 + 当前漏速；基载使电力 -1、供氧 -1。
2. 漏速每 5 tick 上升 1（surge）。
3. pump：水位 -4、电力 -2；seal：本 tick 停止漏水、供氧 -2；vent：供氧 +3、水位 +1。
4. repair 要求 水位 ≤ 4 且 供氧 ≥ 4，否则分别返回 TOO_MUCH_WATER / OXYGEN_TOO_LOW。
5. 水位 > 8 即 FLOODED；电力或供氧归零即 LOST_POWER / LOST_OXYGEN。

</details>

### MAP-10 · 最后一桶燃料（极地 / 简单）

- **公开目标**：算出能到站且够用的装载量，别装太满把油烧光。
- **公开规则**：4 条（全文见下方折叠）
- **动作契约**：4 个工具：`load`、`move`、`unload`、`wait`
- **起点**：`location=A`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：2 步，结局 `success`，主指标 `map10.v10.mission_success` = 1（VALID）；JSON 7168 B，CSV 1282 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. A 到补给站 D 一次移动；油耗 = burn_base + ceil(cargo / 2)，burn_base 与容量、库存公开。
2. load(quantity)：装载量 ≤ capacity 且 ≤ 站点库存；可以分多次装。
3. move：燃料不足即 OUT_OF_FUEL，货物一并损失。
4. 抵达时必须 cargo ≥ required_delivery 才算成功；unload 只是把货卸到站点。

</details>

### MAP-11 · 失联的小队（极地 / 中等）

- **公开目标**：在生命窗内找到并救出生还者；风暴里搜索又慢又容易漏检。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：3 个工具：`rescue`、`search`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：3 步，结局 `success`，主指标 `map11.v10.mission_success` = 1（VALID）；JSON 8612 B，CSV 2320 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 三个搜索区 Z1, Z2, Z3；生还者恰在其中一处。
2. search(area) 耗 1 tick；若处于风暴窗口则耗 3 tick，且漏检率显著更高（面板公开 storm_miss_rate / calm_miss_rate）。
3. rescue(area) 耗 1 tick；对错误区域会惊动现场，扣 3 tick。
4. 生命窗结束（life_window_end）仍未救到即失败。
5. 漏检是概率性的：一次 NO_SIGNAL 不代表该区一定没有生还者。

</details>

### MAP-12 · 极夜三十天（极地 / 中等）

- **公开目标**：在极夜里活下去，并把研究积分做够。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：2 个工具：`assign`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "day": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：30 步，结局 `success`，主指标 `map12.v10.mission_success` = 1（VALID）；JSON 29172 B，CSV 18782 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 共 30 天，每天 3 个劳动槽；assign(plan=[...]) 一次排完当天。
2. forage：食物 +2；repair：站体 +2；research：研究 +1。
3. 每日结算：食物 -2、站体 -2。
4. 研究积分达到 34 且存活到第 30 天才算成功。
5. 食物归零 → STARVED；站体归零 → STATION_LOST。

</details>

### MAP-13 · 四神之门（金字塔 / 简单）

- **公开目标**：读碑文、**记录下来**、排出唯一排列并验证开门。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`move`、`read_inscription`、`record_constraint`、`set_trial_layout`、`verify_layout`
- **起点**：`location=C`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：20 步，结局 `success`，主指标 `map13.v10.constraint_satisfaction_ratio` = 1.0（VALID）；JSON 31218 B，CSV 26722 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 星形拓扑：营地 C 直连 N/E/S/W 四间外室，外室之间没有直连。
2. read_inscription(room) 只能读**自己所在**的房间；每条碑文只能读一次同一内容。
3. record_constraint(clue_id) 只能在 C，且只能记录**已读**的碑文。
4. set_trial_layout 在 C，必须恰含 N/E/S/W 四槽且四符号各一次；**至少记录过 1 条约束**才能试排。
5. verify_layout 在 C；**至少记录过 4 条约束**才能验证（观察≠记录）。
6. 错排会清空试排；累计 3 次错排即失败。

</details>

### MAP-14 · 说谎的祭司（金字塔 / 困难）

- **公开目标**：判断真实锁型并开门；推理规则已公开，盲猜不会开门。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：5 个工具：`ask`、`compare_evidence`、`move`、`read_archive`、`submit_configuration`
- **起点**：`location=P`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：12 步，结局 `success`，主指标 `map14.v10.deduction_success` = 0（VALID）；JSON 23867 B，CSV 18693 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. P—A—O—J 三点链条：P 是证词厅、A 是档案室、O 是比对台、J 是审判门。
2. 锁型候选只有 3 种（见 configurations）。
3. **推理规则**：三名祭司中恰有一人对每一条命题都如实作答，另外两人对每一条命题都反报（说反话）。谁诚实未知。
4. 整局最多问 4 条命题（在 P），最多错交 1 次。
5. read_archive 在 A 读取一条排除性档案（有且只有一条）。
6. compare_evidence 在 O 封存一个（锁型, 诚实者）假设，只记录、不判对错。
7. submit_configuration 在 J：只有当**最近一次封存的假设与提交锁型一致、且该假设与全部已观察答复/档案相容**时门才打开；否则记一次错交。

</details>

### MAP-15 · 会变化的迷宫（金字塔 / 困难）

- **公开目标**：从样例推断门色随时间变化的规律，记录假设，并在测试区连续通过 T1 与 T2。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：5 个工具：`choose_door`、`inspect_symbols`、`predict_transition`、`record_rule`、`wait`
- **起点**：`area=A`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：12 步，结局 `success`，主指标 `map15.v10.test_gate_first_try_accuracy` = 1.0（VALID）；JSON 26912 B，CSV 19879 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 区域依次为 A → B → C（训练区）→ T1 → T2（测试区）→ EXIT；每区有若干门，choose_door(slot_index) 选第几扇门（从 1 开始）。
2. 色环顺序 red → gold → blue → green → red。每次选门时，正确门的颜色 = 当前墙色沿色环前进 k 格；k 只取决于当前 tick 除以某个周期的余数，周期为 2 或 3，k ∈ {0,1,2,3}。这条规律在所有区域相同，但具体周期与各余数下的 k 未知，需要从样例推断。
3. inspect_symbols(area=当前区域) 不耗 tick，显示墙色与各门颜色（按槽位顺序）。
4. training_sample_log 含 2 条往期档案样例；在训练区每次选门（对或错）都追加一条样例。训练区选错：耗 1 tick、留在原区、不扣容错。选对：耗 1 tick、前进一区。
5. 离开 C 进入测试区前，必须先 record_rule(rule_id, supporting_sample_ids)，rule_id 格式 'period=P;offsets=k0,k1[,k2]'（offsets 依次对应余数 0,1,2）；环境只校验格式，不告诉对错。supporting_sample_ids 只能引用 training_sample_log 中的 id。
6. 测试区：T1 与 T2 的墙色在训练中从未出现。选对耗 1 tick 前进；选错不耗 tick、扣 1 次容错，共 2 次错误即失败；测试区内 wait 被拒且不推进 tick。
7. predict_transition(answer=颜色) 只在测试区可用、不耗 tick，预测下一次选门时的正确门色，单独计分。

</details>

### MAP-16 · 单线预约与节点容量（地铁 / 中等）

- **公开目标**：用 set_route + move_train 把 a、b 分别送到 B 与 A；必要时用侧线 D 让行。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`inspect_network`、`move_train`、`occupy_siding`、`release_section`、`set_route`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：20 步，结局 `success`，主指标 `map16.v10.mission_success` = 1（VALID）；JSON 30618 B，CSV 23718 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 线路：A—X—M—Y—B 为单线主线，M—D 为唯一侧线；每段同一 tick 只能过 1 列车，每个节点（含侧线）同一时刻只能停 1 列车。
2. 两列车 a、b 各自有固定方向表（见 train_route_directions）；set_route(train_id, next_node) 只登记下一跳，move_train() 才会把**所有**已登记的路由作为一整帧提交并推进 1 tick。
3. 若两列车的下一跳占用同一区段，或同帧后停在同一节点，立即以对应冲突终局。
4. 让行必须把一列车临时停到侧线 D：occupy_siding(train_id, next_node) 与 set_route 等价，但目标必须是侧线。
5. 两列车都到达各自终点即成功；提交后若不存在安全完成路径，则判定死锁失败。
6. 本实例的起点、终点与侧线节点见 Observation 的 train_positions、train_goals、siding_nodes 与 topology。

</details>

### MAP-17 · 早高峰（地铁 / 困难）

- **公开目标**：在 12 tick 内运送至少 8/10 名乘客，并自行权衡服务率、等待与能耗。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：1 个工具：`set_timetable`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：12 步，结局 `success`，主指标 `map17.v10.mission_success` = 1（VALID）；JSON 25861 B，CSV 19084 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 环线 A—B—C—D 与支线 B—E—F 共用 B 站咽喉；每段每 tick 只能过 1 列车。
2. 每 tick 提交一整行时刻表：set_timetable(tick, operations)。operations 以列车 id 为键，每项含 op（stop/release/detour/switch_line/delay）与目标/上车人数。
3. 上车（board）必须对应列车的 task 路线与需求表 demand_matrix；站台/区段容量或同段冲突会让整帧被拒（tick 不前进）。
4. 需求表共 10 人；到时限时送达人数达到本实例的服务阈值即成功。
5. 公开验收参数（服务阈值与时限）见 goal 与 ticks_remaining。

</details>

### MAP-18 · 故障传播（地铁 / 困难）

- **公开目标**：在 horizon 前送达至少 13/18 名乘客，并在区段封闭时安全恢复服务。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：1 个工具：`set_timetable`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：12 步，结局 `success`，主指标 `map18.v10.service_rate` = 1.0（VALID）；JSON 33837 B，CSV 27384 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 每个决策提交当前 tick 的一整行时刻表：set_timetable(tick=当前 tick, operations)。operations 只列需要动作的列车；未列出的列车原地等待。被提交的行使物理 tick +1。
2. op ∈ release(to)|detour(to)：沿一条相邻区段移动一站（detour 与 release 等价，用于跨线联络段）；temporary_stop：原地等待；cancel_service(task_id)：列车在起点时取消本车任务，3 人计入服务损失且不可撤销，空车之后可用 release 调位。
3. 每项任务只能由 train_task 指定的列车沿 task_routes 的路线完成；列车在 release_tick 之前离开起点 → 整行被拒 DISPATCH_WINDOW_VIOLATION（tick 不前进，消耗动作预算）。
4. 每个区段每 tick 最多 1 列车（双向合计）；每站最多 2 列车（含已交付停靠的车）。相向对穿 HEAD_ON_COLLISION、同段双车 SEGMENT_CAPACITY、站台超员 STATION_CAPACITY_EXCEEDED 都会立即终局。
5. 已交付的列车不能再移动（整行被拒 COMPLETED_TRAIN_MOVED）。非法相邻、未知列车、tick 不符等也整行被拒，tick 不前进但消耗动作预算。
6. 运行期间可能有一个区段临时封闭；区段与时长事先未知，封闭期间出现在 closed_segments。进入封闭区段的列车返回 TRACK_CLOSED 并原地等待，同行其他操作照常结算。
7. 到 horizon 结算：送达 ≥ 13/18 人为成功；所有任务都已交付或取消时提前结算。动作预算用尽仍未结算即截尾。

</details>

### MAP-19 · 温度临界点（火山 / 困难）

- **公开目标**：在 horizon 内累计目标产能且三区不超 10；每个 tick 必须申报下一 tick 的温度，误差超过公开容差时该 tick 产能作废。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`adjust_loads`、`forecast_next`、`read_temperature`、`set_cooling`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：37 步，结局 `success`，主指标 `map19.v10.production_credit` = 1.0（VALID）；JSON 51376 B，CSV 43526 B，字段与步数一致。
- **说明修复**：详情页新增提醒：记住：读取温度、设置冷却、调负荷都不会推进时间，每个 tick 必须 wait 一次。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 三区 A/B/C；每 tick 结算一次温度：T_next = max(0, T + 负荷 − 已生效冷却)。
2. 负荷每区 0–2；冷却向量每区 0–2 且总和不超过 4；同一生效 tick 上最后一条入队向量生效。
3. set_cooling 在提交后 tick+2 才生效。
4. **forecast_next 是申报**：必须提交下一 tick 的三区温度预测；预测最大误差 ≤ 1 时该 tick 的负荷才计入产能，否则该 tick 产能记 0。
5. 在 12 tick 内累计 49 点产能且温度不超 10 即成功。
6. 时间只在 wait 时推进：read_temperature / set_cooling / adjust_loads / forecast_next 只修改本 tick 的设置或申报，不推进 tick；每个 tick 必须调用一次 wait 才结算（否则 tick 不变、产能为 0）。

</details>

### MAP-20 · 冷却网络（火山 / 困难）

- **公开目标**：在 10 tick 内保持三区温度不超过 10.0 并累计目标产能；热点区需要从邻区经有损旁路调水。
- **公开规则**：10 条（全文见下方折叠）
- **动作契约**：5 个工具：`adjust_loads`、`open_bypass`、`read_temperature`、`set_flow`、`wait`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：30 步，结局 `success`，主指标 `map20.v10.production_credit` = 1.0（VALID）；JSON 58326 B，CSV 52494 B，字段与步数一致。
- **说明修复**：详情页新增提醒：记住：set_flow、旁路与负荷只改本 tick 设置，必须 wait 才结算；旁路只送到 4/5。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 三区 A/B/C，每 tick 结算一次：T_next = max(0, T + 本 tick 热量 − 交付水)。
2. 水源每 tick 60；单支管直供上限 25；区阀上限 A/B/C = 40/40/35；交付超过区阀 → 整帧拒绝。
3. set_flow(tenths)：`set_flow_tenths` 是长度为 3 的整数数组，顺序固定为区 A、B、C；每项 0–25，三项之和不超过水源 60，超限整帧拒绝。
4. adjust_loads(loads)：`adjust_loads` 是长度为 3 的字符串数组（顺序 A、B、C），取值只能是 "FULL"、"REDUCED"、"IDLE"；三档的热量分别为 本 tick 热量、本 tick 热量 ×0.5、0。
5. open_bypass(bypasses)：`open_bypasses` 是以链路名为键的对象，链路只能是 "AB" 或 "BC"；值为 {"from": 端点, "to": 另一端点, "input_tenths": 取水档位}，端点取自该链路两端；`input_tenths` 必须是 5 的整数倍且不超过 20（可选 5/10/15/20）。
6. 旁路按 5 一档、单链路上限 20，下游只收到 4/5。
7. **本 tick 三区热量公开**（heat_schedule）；热点区热量会超过单支管上限，必须从邻区经有损旁路调水。
8. 区产量系数 A/B/C = 4/3/2：交付覆盖该区热量才拿满，否则按 交付/热量 折减。
9. 在 10 tick 内累计目标产能且三区不超过 10.0 即成功。
10. 时间只在 wait 时推进：set_flow / open_bypass / adjust_loads 只修改本 tick 的设置，不推进 tick；每个 tick 必须调用一次 wait 才提交并结算（否则 tick 不变、产能为 0）。

</details>

### MAP-21 · 喷发倒计时（火山 / 困难）

- **公开目标**：在喷发前撤到 E 保证人员安全；在安全前提下尽量多带回科研价值。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`collect_and_carry_sample`、`measure`、`move`、`reinforce_sample_case`、`wait`
- **起点**：`location=O`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：6 步，结局 `success`，主指标 `map21.v10.overall_utility` = 0.590909（VALID）；JSON 14073 B，CSV 7153 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 地图：O—R(1)—W(2)—S(2)—E(2)，另有 O—E 直达(6)；括号为耗时 tick。move 在途中自动推进，抵达前其他动作被拒。到达 E 即安全撤离并结算。
2. 喷发时刻隐藏，只可能是 12/16/20，先验 0.2/0.5/0.3。喷发 tick 时仍未抵 E 即死亡，失去全部科研。同 tick 抵 E 视为安全。
3. measure 只能在 O 用一次，耗 2 tick，返回 EARLY_WARNING 或 LATE_WARNING；P(EARLY | 12/16/20) = 0.8/0.3/0.1；后验在 posterior_over_eruption_ticks 公开。
4. 样品（只能带一件）：R_SURFACE_ASH 在 R 采集耗 1 tick 得 5 分；W_LAYERED_CORE 在 W 耗 5 tick 得 12 分（加固后 20）；S_DEEP_ISOTOPE 在 S 耗 6 tick 得 40 分（加固后 50）。reinforce_sample_case 只能在 W 或 S 用一次，耗 1 tick，对当地样品生效。
5. 测量记录也算 5 分科研。科研分只有安全撤离才计入。被拒动作耗 1 tick。
6. 评分：安全撤离为前提，overall = 0.5 + 0.5 × 科研完成度；死亡为 0。立即撤离是合法且安全的选择，但科研完成度为 0。

</details>

### MAP-22 · 无地图的丛林（丛林 / 中等）

- **公开目标**：先到遗迹完成记录，再回到营地；路线只能靠自己记。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`check_goal`、`move`、`observe_signpost`、`return_to_camp`、`write_memory`
- **起点**：`current_sign=camp`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：35 步，结局 `success`，主指标 `map22.v10.mission_success` = 1（VALID）；JSON 55628 B，CSV 47528 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 你在一片没有地图的丛林里，只能看到**当前**路标与可用方位（north/east/south/west）。
2. move(bearing) 沿该方位走到相邻节点；方位不可用 → BEARING_NOT_AVAILABLE。
3. observe_signpost 耗 1 tick，给出当前路标的特征（用于自证记忆），不改变位置。
4. write_memory(facts) 把 1–3 条 {key,value} 写进 agent_notes；内容原样保留，是跨阶段唯一可靠通道。
5. 先在遗迹 check_goal，再回到营地 return_to_camp 才算完成。
6. 移动次数上限 44；相邻节点在你走过去之前不可见。

</details>

### MAP-23 · 迷雾中的遗迹（丛林 / 中等）

- **公开目标**：先买线索再出手：mark 一个与线索相容的候选入口，然后到该入口调查；调查扣费后补给必须严格大于 0。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：5 个工具：`investigate`、`mark`、`move`、`resupply`、`scout`
- **起点**：`location=A`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：9 步，结局 `success`，主指标 `map23.v10.clue_utilization` = 0.666667（VALID）；JSON 15343 B，CSV 8751 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. A 是枢纽，直连 N/R/H（侦察站）与 X/Y/Z/W（入口）；move(to) 扣路费。
2. scout 只在侦察站可用、每站一次，费用 {'N': 2, 'R': 2, 'H': 3}；返回该站的 supports （该线索认为可能的入口集合）。
3. investigate 必须先 mark 声明候选，且必须**至少买过一条线索**，并且候选不能被已购线索排除；否则被拒并记 unjustified。
4. 调查费用 {'X': 2, 'Y': 2, 'Z': 3, 'W': 3}；真入口 + 扣费后补给 > 0 即成功。
5. A 的补给箱一次性补满到 16。

</details>

### MAP-24 · 消失的道路（丛林 / 困难）

- **公开目标**：在 tick 18 前把 relic_C 与 supply_case_D 都带回 A；桥会在未知时刻永久断开，断了就必须改走山路。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：6 个工具：`measure_tide`、`move`、`probe_bridge`、`record_route`、`take`、`wait`
- **起点**：`location=A`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：10 步，结局 `success`，主指标 `map24.v10.replan_success` = 1（VALID）；JSON 16252 B，CSV 9102 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 路网：A-B-C-D-E-A 环 + A-F-C 山路；A-B 与 B-C 是桥，C-D、D-E、E-A 是地面/潮道。
2. 任务：把 relic_C（在 C）与 supply_case_D（在 D）都带回 A；两者都要。
3. 桥会在**未知时刻**永久断开；站在桥上会被推回岸边并多耗 2 tick。
4. D-E 潮道每 4 tick 开 2 tick，相位隐藏；measure_tide 在 D 或 E 读出下一 tick 的状态。
5. probe_bridge 只能在 B 用，耗 2 tick，读出桥是否已断。
6. 山路 A-F-C 比桥路慢：桥路 2 tick 到 C，山路 6 tick。
7. tick 18 前把两件物资带回 A 即成功。

</details>

### MAP-25 · 第一次出舱（月球 / 中等）

- **公开目标**：穿上 EVA 服、在 A 挂安全绳并排压，出舱检查并诊断阵列，用精确工具组合维修后返回 H；氧气只在舱外消耗。
- **公开规则**：5 条（全文见下方折叠）
- **动作契约**：9 个工具：`depressurize`、`diagnose`、`equip`、`eva_exit`、`inspect`、`move`、`pressurize`、`repair`、`return_to_A`
- **起点**：`location=H`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：16 步，结局 `success`，主指标 `map25.v10.mission_success` = 1（VALID）；JSON 21200 B，CSV 13271 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. H（居住舱）—T（装备间）—A（气闸）为舱内通路；A 之外是阵列 S。
2. 在 T 穿 EVA 服、取诊断单元与扳手并检查装备；在 A 挂安全绳；排压后才能出舱（未穿服/未挂绳/未排压都会失败）。
3. 在 S 先检查阵列、再用诊断单元诊断，维修必须带齐诊断单元与扳手并给出诊断码。
4. 维修后依次返回 A、增压、经 T 回 H；回到 H 且维修完成才算成功。
5. 氧气只在舱外消耗（出舱、检查、诊断、维修、返舱各计费），本实例的起始位置与氧气预算见 Observation。

</details>

### MAP-26 · 失败的维修计划（月球 / 中等）

- **公开目标**：用测试判断故障并换上正确备件后重启；盲换也可以，但会更费备件。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：5 个工具：`read_log`、`replace`、`restart`、`rollback`、`run_test`
- **起点**：`{"terminal": false, "last_action_result": "READY", "tick": 0}`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：4 步，结局 `success`，主指标 `map26.v10.mission_success` = 1（VALID）；JSON 9969 B，CSV 3792 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 三种故障 F1/F2/F3 分别需要备件 P1/P2/P3；当前只有一台机器要修。
2. run_test(test_id) 耗 1 tick，按公开分区返回读数并缩小 candidate_faults。
3. read_log(log_id) 耗 1 tick，日志会披露一条历史维修记录（不影响候选集）。
4. replace(part_id) 耗 2 tick：装上备件；若与真实故障匹配，restart 即可恢复。换错会消耗该备件、磨损 +1。
5. rollback 撤销最后一次更换，但**已消耗的备件不返还**。
6. 磨损达到 2 时机器不可恢复；截止 tick 16。
7. 诊断不是开门的必要步骤：盲换也是合法策略，但会更费备件、更容易磨损失败。

</details>

### MAP-27 · 月球车（月球 / 困难）

- **公开目标**：在 B 提交：样本已封存回基地、伤员经中继远程撤离、中继在线、全员存活且余氧大于 0。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：7 个工具：`charge`、`drive`、`load`、`repair_relay`、`rescue`、`sample`、`submit`
- **起点**：`location=B`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：16 步，结局 `success`，主指标 `map27.v10.mission_success` = 1（VALID）；JSON 26455 B，CSV 18814 B，字段与步数一致。
- **说明修复**：无需修复：公开目标、规则、动作契约与终局反馈均可读。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. B 是基地（提单与样本容器）、S 是中继站补给点与唯一充电桩、R 是中继塔、P 是采样点、E 是伤员位置；每条通道的耗时 = 电量消耗 = 氧气消耗。
2. 月球车有电量上限、货舱上限与余氧上限（数值见 Observation 的 battery_capacity / cargo_capacity / oxygen）；电量不足以进入下一段会抛锚。
3. 装载会占货舱槽位；货舱满时装载或充电会被拒绝并记一次冲突。
4. 在 S 可消耗充电桩充一次电（增益见实例）；充电桩数量见 Observation。
5. 中继塔需要 relay_repair_kit 才能修复；伤员需要 medical_kit 现场稳定后，在**中继在线**时才能远程撤离；样本容器需带到 P 采样封存。
6. 回到 B 提交才算完成：样本已封存、伤员已撤离、中继在线、全员存活且余氧 > 0。

</details>

### MAP-28 · 消失的王冠（古堡 / 中等）

- **公开目标**：在 H 提交人物、跨入宝库的门、进入分钟与离开分钟；每个字段至少引用两种不同来源类别，且值必须正确。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：6 个工具：`interview`、`investigate`、`move`、`read_record`、`record`、`submit`
- **起点**：`location=H`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：18 步，结局 `success`，主指标 `map28.v10.timeline_constraint_satisfaction` = 1.0（VALID）；JSON 33826 B，CSV 28278 B，字段与步数一致。
- **说明修复**：详情页新增提醒：提交前检查：四个字段都要有至少两种不同来源类别的已记录证据。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 六室环路 H—V—G—K—S—V 加 A—G 档案支线；move(to) 沿公共边移动，1 tick。
2. 取证动作：investigate(vault_lock_events)（V）、investigate(footprint_trail)（S）、read_record(key_registry)（A）、interview(kitchen_cook)（K）。
3. record(clue_id) 只能记录**已观察**的具体证据 ID；观察过但没记录的证据不能作为来源。
4. submit 一次终局：claims 四个字段 person_id / entry_path_id / entry_time / exit_time，citations_by_claim 为每个字段的已记录证据 ID 列表。
5. person_id 合法值仅：ADA, BASIL, CELINE；entry_path_id 合法值仅：BANQUET_H_V, GUARD_G_V, SECRET_S_V；时间格式 HH:MM。
6. 每个字段必须由**至少两种不同来源类别**（instrument_log / physical_trace / documentary_register / testimony）支持，且值必须正确。
7. 失败码：引用未记录/未观察的证据 → EVIDENCE_MISSING；值被已记录证据排除 → CLAIM_CONTRADICTS_RECORDED_EVIDENCE；值可能正确但来源类别 <2 → ACCUSATION_WITHOUT_TWO_SOURCES；终局拒绝统一为 CASE_REJECTED。

</details>

### MAP-29 · 不可靠的证人（古堡 / 困难）

- **公开目标**：提交准确的事件时刻与地点，并指出至少一位经固定比对规则证明不可靠的证人。
- **公开规则**：6 条（全文见下方折叠）
- **动作契约**：5 个工具：`ask`、`compare_testimony`、`investigate`、`move`、`submit`
- **起点**：`location=H`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：31 步，结局 `success`，主指标 `map29.v10.contradiction_detection_rate` = 0.5（VALID）；JSON 72727 B，CSV 73339 B，字段与步数一致。
- **说明修复**：详情页新增提醒：提问预算只有 12 次；先取物证再比对证词，能少走弯路。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. H 是中枢，直连 L/K/Y/G；move(to) 沿公共边移动，1 tick。
2. ask(npc_id, question_template_id) 必须在该 NPC 所在房间；有效提问扣 1 预算与 1 tick。预算 12；预算耗尽返回 QUESTION_BUDGET_EXHAUSTED，不扣 tick。
3. investigate(target_id) 取物证（study_clock / bell_trace），1 tick，不占提问预算。
4. compare_testimony(npc_id, statement_ids, against_evidence_ids)：两个列表都只能引用已听到的 answer/source ID 与已发现的物证。返回 INSUFFICIENT（证据不够）、CONTRADICTED_AND_EXPLAINED（可证伪且给出解释）、TESTIMONY_PARTIALLY_SUPPORTED（部分真实）、TESTIMONY_CONSISTENT（无关但可信）。
5. submit 只能在 H，一次终局：提交时刻、地点、被指认的不可靠 NPC，以及支持证据与“不可靠证明”引用；被指认者必须已被比对规则证明。
6. 模板：OPEN_ACCOUNT / TIME_BASIS / LOCATION_BASIS / ARCHIVE_CROSS_INDEX / SOUND_PATTERN。不同 NPC 只掌握其中一部分；证人可能记错、隐瞒或诚实但不知道。

</details>

### MAP-30 · 午夜审判（古堡 / 困难）

- **公开目标**：把三次近期事件从现场观察沉淀成可引用的案卷，用案卷解锁证人记忆，核对链条后在法庭节点提交一次有据指控。
- **公开规则**：7 条（全文见下方折叠）
- **动作契约**：6 个工具：`compare_records`、`formal_accuse`、`inspect`、`interview`、`move`、`record`
- **起点**：`location=H`
- **成功反馈**：完成公开目标后，环境返回 scenario_success。
- **失败/截尾反馈**：触犯公开规则、超过时限或资源归零时返回 scenario_failure；动作/决策预算耗尽另记为 CENSORED / BUDGET_REACHED，不伪装成失败。
- **离线回放**：34 步，结局 `success`，主指标 `map30.v10.evidence_chain_coverage` = 1.0（VALID）；JSON 66568 B，CSV 61118 B，字段与步数一致。
- **说明修复**：详情页新增提醒：案卷条目需要“现场记录 + 证人确认”；近期动作窗口只保留最近 5 条。
- **判定**：PASS。

<details><summary>公开规则全文</summary>

1. 房间图：H 连 B/J/L；L—K—T—A 为一条走廊。move(to) 1 tick；正式指控 formal_accuse 只能在法庭节点 J。
2. record(entry_id) 的合法条目 ID 仅：EVENT_1_HANDOFF, EVENT_2_WAX, EVENT_3_SIGNAL, Q4_CODEBOOK。
3. 每个事件条目需要**现场记录 + 证人确认**两件证据；Q4_CODEBOOK 只需交叉索引文书。
4. interview 的 topic_id 也用同一套条目 ID；证人分条件作答：需要出示对应物证，通常还需要**更早事件的完整条目**（档案看守要求先归档第一件事件），否则只给泛泛回忆。
5. 档案看守给出的交叉索引把值班代号（duty_code）映射到人名；现场物证同时公开该事件的 time / location / duty_code。
6. 近期动作窗口只保留最近 5 条事件；窗口外只能通过 casebook 引用。
7. compare_records(entry_ids) 返回 CHAIN_COHERENT 需四个条目都完整且交叉索引一致。

</details>

