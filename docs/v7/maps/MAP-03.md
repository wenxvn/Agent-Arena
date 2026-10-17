# MAP-03｜飞船｜困难｜最后的百步

```yaml
map_id: MAP-03
world: spaceship
nominal_level: 困难
capability_primary: long_horizon_goal_maintenance
source_commit: 766ec82529d4ee2499dde9592452eb68592f4637
source_map_spec_hash: a8b093b23496cd108f60d57b47e1ee9991c52465b89feab68cae86028b9258c8
source_design_hash: 0698f1a023ed30503fef20b4e6ec7875ce15cce84ffb12f520673e26db55be21
design_status: DESIGN_COMPLETE_PENDING_RUNTIME
review_status: pending_human_review
runtime_status: design_only
metric_status: registered_design
```

## 1. 测量构念与不可替代玩法

测“跨阶段目标保持 + 早期一次性信息召回”。五个阶段 `P1 供电 → P2 读取并冷藏样本 → P3 EVA 修天线 → P4 遥测 → P5 提交 K7` 有真实依赖；K7 只在 U1 读取时公开一次，之后重访只返回“标签已读”。样本读取后有 4 tick 冷藏窗口；EVA 恰好消耗 3 单位氧气；返舰窗口 36 tick。即使路线最短，忘记 K7 也无法提交；即使记住 K7，漏阶段或耗尽 EVA 仍失败。

## 2. 真实规则字段

- 初始：`tick=0, location=U2, aux_power=off, cryo_power=off, communications_power=off, sample_cold=false, antenna=damaged, telemetry=not_sent, route_calibrated=false, route_tag_read=false, eva_supply=3, sample_lost=false, return_window_end_tick=36`。
- 阶段完成条件：P1 D1 辅助电源 `on`；P2 U1 读标签并在 4 tick 内 `stabilize_sample`；P3 携带 3 单位 EVA 进入 V、维修并安全返回 D3；P4 U3 天线修复后 `transmit`；P5 U2 精确提交 `K7` 且 P1–P4 完成。
- 公开：位置、相邻边、可见物、公开目标、`milestone_bits`、EVA 补给、航线窗口剩余、读后样本状态。K7 只在读取当步公开一次。
- 硬失败：`SAMPLE_COLD_WINDOW_EXPIRED`、`EVA_OXYGEN_EXHAUSTED`、`ROUTE_KEY_REJECTED`、`RETURN_WINDOW_EXPIRED`。
- 成功：P1–P5 全完成且 `route_submission_is_K7`，`tick<36`。

## 3. 指标

| metric_id | 类别 | 公式 | 单位/方向 | 分母 | 缺失/截尾 |
|---|---|---|---|---|---|
| `map03.phase_completion_coverage` | primary | 合法完成的阶段数 / 5 | 比例 / 高 | 5 | 无终局 → CENSORED |
| `map03.long_delay_recall_accuracy` | primary | 末阶段正确提交的早期事实数 / 需提交数（本图 1 个 K7） | 比例 / 高 | 需提交事实数 | 未到 P5 → N/A/CENSORED |
| `map03.phase_order_violations` | guardrail | 阶段逆序/重复阶段动作数 | 次 / 低 | episode | 0 合法 |
| `map03.lost_sample` | diagnostic | `1[SAMPLE_COLD_WINDOW_EXPIRED]` | 0/1 / 低 | episode | 终局缺失 → CENSORED |
| `map03.completion_ticks` | diagnostic | 成功终局 tick | tick / 低 | 成功局 | 失败 → N/A |

## 4. 能力混淆分析

- 高 `phase_completion_coverage` 可能只是按可见里程碑逐项打卡，不代表记住了 K7；必须与召回率并列。
- 高召回率可能来自“最后猜 K7”，因为本图答案短；必须同时检查 P1–P4 是否完成、提交是否只有一次。
- 低分可能由 EVA 氧气算错造成，而不是记忆失败；用 `lost_sample`、`EVA_OXYGEN_EXHAUSTED` 与阶段位分开归因。
- 模型可能在 `note` 里写了 K7 但从不回看；`note` 不计时也不被裁判读取，不能算环境记忆。

## 5. 两条手算轨迹

**策略 A（依赖串行，30 tick）**：U2→U3→XU→XD→D3→D2→D1 恢复辅助电源（P1）→回 D3→D2→U1 读 K7（当步公开）→立即冷藏（P2，窗口内）→U2→U3→XU→XD→D3→V 修天线（P3，消耗 1）→返回 D3（消耗 1）→再进 V 完成外部作业并返回（消耗最后 1）→XD→XU→U3 发射遥测（P4）→U2 提交 K7（P5）。指标：阶段覆盖 5/5；召回 1/1；逆序 0；完成 30 tick。

**策略 B（分区记忆，31 tick）**：电源恢复后先读本区通信面板检查项，再去 U1 读标签并冷藏；完成下层 EVA 后回 U3 发射，最后 U2 提交。指标：阶段覆盖 5/5；召回 1/1；逆序 0；完成 31 tick；比 A 多 1 tick，但仍低于 36。

> 文档小冲突：`DESIGN.md` 写策略 B “多花两个 tick”，而 `oracle_trace.jsonl` 实际为 31 行（A=30、B=31）。V7 以 oracle_trace 的 30/31 为准，并记录该文档笔误；不涉及规则变更。

## 6. 三个机制特有失败

1. **保留码却漏阶段**：记住了 K7，但跳过 P2 冷藏，`SAMPLE_COLD_WINDOW_EXPIRED`；阶段覆盖 4/5，召回不可评估。
2. **阶段全过但码错**：P1–P4 完成，最后提交非 K7，`ROUTE_KEY_REJECTED`；阶段覆盖 5/5，召回 0/1。
3. **EVA 氧气算错**：进入 V、工作、返回需要 3 单位；若在 V 内多做一次动作，氧气归零且仍在 V，`EVA_OXYGEN_EXHAUSTED`；与记忆失败无关。

## 7. 两个边界

- **样本窗口第 4 vs 第 5 个动作**：读标签后连续 4 个环境动作内完成冷藏即成功；第 5 个动作才冷藏则 `SAMPLE_COLD_WINDOW_EXPIRED`。必须用同一前缀只改一个等待动作验证。
- **返舰 tick 35 vs 36**：提交在 tick 36 之前完成才成功；规则写 `tick<36`，tick 36 结算失败。提交动作先于同 tick 超时检查这一点需在运行时固定，否则边界会漂移。

## 8. 信息泄漏负例

若 prompt 或阶段摘要重复显示 K7 原文、或在 Observation 中预装“K7”字符串，远期召回能力被直接替代。V7 只允许读取当步公开一次；阶段摘要只能返回“标签已读”，不得返回原文、字符数或前缀。

## 9. Oracle/求解状态

`oracle_trace.jsonl` 有 `milestone_first`（30 步）与 `zone_first`（31 步）两条手写成功；`failure_traces/cases.yaml` 有三条资源/记忆失败；`acceptance.md` 只完成纸面自审。**没有独立求解器证明 30 tick 最优**，也没有运行时回放。

## 10. 与同世界另两图差异

**vs MAP-01**：MAP-01 的 18 tick 内只有局部互斥供电与供氧硬约束，没有一次性远期事实；它的失败是断供/违规复位。MAP-03 的核心是“早期 K7 → 30 多 tick 后提交”，并叠加五阶段依赖、样本窗口和 EVA 氧气。把 MAP-01 的路线加长不会产生 `long_delay_recall_accuracy`，因为 MAP-01 没有需要跨阶段保留的隐藏字符串。

**vs MAP-02**：MAP-02 是第 4 个动作触发泄漏后的短时重排，跨度 20 tick，记忆维度 M=1；MAP-03 没有突发事件，跨度 36 tick，M=3，失败来自漏阶段与远期召回。MAP-02 的“先锁闸还是先救人”是事件后优先级，MAP-03 的“先读码还是先修天线”是阶段依赖与时间窗，两者不共享胜负谓词。

## 11. 可计算性来源

需要逐 tick 的 `milestone_bits`、`eva_supply`、`sample_status_after_read`、`route_window_remaining`、`location`、`terminal_reason`，以及唯一一次 `submit` 的公开内容。阶段完成事件由 `milestone_bits` 的 0→1 边沿派生；召回由 `submit` 内容与离线 K7 真值比较（K7 可来自 oracle 参考，不进入 prompt）。

## 12. 难度定位与对照

D=(1,3,1,2,3,2)。相对 MAP-02 提升 D（跨阶段依赖）与 M（长间隔记忆），不提升 E（无随机事件）。预登记对照：**完整历史 / 最近 5 步 / 合法外部笔记**；同一前缀与后续决策预算。若外部笔记额外获得地图未公开的信息，标为“信息可用性实验”。

## 13. 未决

记忆失败与资源失败缺少独立原因码（`V7-DCR-003`）；K7 真值只允许离线裁判使用。运行时接入前需固定“tick 36 提交”与“样本窗口第 4 动作”的结算顺序。
