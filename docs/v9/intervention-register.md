# V9 干预登记表

- 原则：**无证据不修改**；优先补公开信息，其次修指标，最后才考虑规则/实例
- 所有 DCR 均在 `docs/v9/dcr/`；V8 文件、账本、90 局 Trace 未被修改
- 状态：`accepted` 表示 V9 层已实现（prompt addendum / 指标叠加 / 只读重算）；`requires_user_decision` 表示构念或规则变更，执行 Agent 不单方采用

## 1. 已实施（V9 层）

| DCR | 地图 | 类型 | 改动 | 状态 | 验证 |
|---|---|---|---|---|---|
| DCR-01 | 全部 30 图 | 指标投影 | `decision_budget_reached` 的 `None` 从 N/A 改为 CENSORED | accepted | 90 局重算 28 个状态变化；`test_v9_audit` |
| DCR-02 | MAP-05 | 公开信息 | 切电只能在 C；窗口外发射不计有效信号 | accepted | addendum 泄漏/边界测试 |
| DCR-03 | MAP-09 | 公开信息 | 隔板开放 → water_E+1；>4 短路；E 舱封舱停止推进 | accepted | V9 smoke + MiMo 同期对照 |
| DCR-04 | MAP-10 | 公开信息 | 油库只供暖；发电机/雪地车吃随身燃料；load 只在 B | accepted | 同上 |
| DCR-05 | MAP-11 | 公开信息 | 移动消耗随身补给；不足即失败；resupply 只在 B | accepted | 同上 |
| DCR-06 | MAP-12 | 公开信息 + 指标 | 6 条 transfer 边；研究周期；新增研究分完成率 | accepted | Oracle 2/2；overlay 测试 |
| DCR-07 | MAP-16 | 公开信息 | release/occupy 语义；同节点冲突在 move_train 结算 | accepted | 启发式 16 决策成功 |
| DCR-08 | MAP-25 | 公开信息 + 指标 | H–T–A–S 邻接/耗氧；覆盖率不把被拒诊断算完成 | accepted | 16 决策成功；overlay 测试 |
| DCR-09 | 02/04/05/21/25 | 指标叠加 | 新增自适应响应、潮汐路线、科研单位、修正覆盖率等 | accepted | `test_v9_overlay` |
| DCR-14 | 07/08/26 | 公开信息 | `control_panel`、复合边名/`ordinary_sensor`、log/test/part 枚举 | accepted | addendum 测试；07/08/26 启发式成功 |

## 2. 已登记、需用户裁定

| DCR | 地图 | 议题 | 为什么不能单方改 |
|---|---|---|---|
| DCR-10 | MAP-06 | 正式评测改为 10-seed cohort | 改变实例采样与可比值；V8 90 局不可比 |
| DCR-11 | MAP-15 | goal 直接泄露“偶数同色、奇数互补” | 删除规则会改变公开信息条件与研究构念 |
| DCR-12 | MAP-03 | 记忆通道/远期召回 + EVA 计费 | 需要新动作或改 runner 契约/规则 |
| DCR-13 | MAP-21 | 成功判据是否要求科研单位 | 改成功判据属于构念变更 |
| DCR-25 | MAP-25 | 诊断记账与必需步骤对齐 | 与 DCR-08 部分重叠；正式指标需用户确认 |
| DCR-26 | MAP-26 | 词表/错误码/指标分母/适配层文案 | 词表已由 DCR-14 临时覆盖；正式版本需统一 |
| DCR-27 | MAP-27 | 动作地点表、受困判定、失败局电池余量 | 该图已 VALIDATED；属于增强而非阻塞 |

## 3. 未实施但证据充分的规则/预算缺陷

| 地图 | 缺陷 | 证据 | 建议 |
|---|---|---|---|
| MAP-18 | `step_limit=min(step_limit, 12)` 把 horizon 与动作上限绑死；拒绝动作也耗 horizon | 20/20 随机局第 12 决策截尾；R2 仍有 15/18 可达路线 | 解耦 step_limit 与 horizon（改 V4 规则，需新版本） |
| MAP-03 | EVA 退出不扣氧，与设计文档“进入/维修/返回各 1”不符 | Oracle 第 24 步 `eva_supply=1` 而非 0 | 文档对齐或修规则并重建 Oracle |
| MAP-04 | `stranded_ticks` 直接返回 `high_tide_entries` | 三局与全部基线逐条相等 | 实现真正计数器或标 unavailable |
| MAP-06 | `value_of_information` 硬编码 None；设计效用未实现 | 3/3 N/A | 实现配对 VOI + cohort |
| MAP-14 | 3 锁 + 1 次容错 → 盲交 2/3 通关 | seed 0–8 扫描 6/9 | 改成功判据/锁型数，需用户裁定 |
| MAP-15 | 错误后相位翻转使重试必中 | 4 步固定路径、随机 25% | 改相位推进规则，需用户裁定 |
| MAP-19 | `forecast_next` 无反馈、无指标 | 三局 0 次使用 | 补反馈/指标或移除承诺 |
| MAP-24 | `replanning_latency` 对“没改路”报 1 | R2=1 但未改路 | 重定义事件 |
| MAP-29/30 | 比对/案卷语义未公开 | 0 次 compare；记录 14/19 被拒 | 补公开语义（下一轮 DCR） |

## 4. 不修改清单（明确保持只读）

- V8 90 局 `agent_trace.jsonl`、`judge_metrics.json`、`v8_metrics.json`
- `runs/v8/ledger.jsonl` 与 `supplement_*/ledger.jsonl`（含 4 次 unknown spend 记录）
- `runs/v8/freeze_manifest.json`、`runs/v8/offline_gate.json`、`results_90.csv`
- V4/V6/V7 冻结规则与指标实现
- 30 图 `rule_hash`、`scenario_hash`、`source_hash`（V9 未改任何地图模块）

## 5. 版本与回滚

- V9 只新增：`src/agent_arena/v9/`、`docs/v9/`、`runs/v9/`、`tests/test_v9_*.py`、`scripts/v9_*`、`scripts/run_v9_mimo.py`。
- 回滚：删除 `V9_PUBLIC_ADDENDA` 条目 → 回到 V8 prompt；删除 overlay → 回到 V8 指标；两者都不影响 V8 文件。
- 所有 V9 结果带 `prompt_hash`（v8_compat/v9_fixed）与 `overlay_schema_hash`，可与 V8 分开报告。
