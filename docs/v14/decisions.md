# V14 决策记录

记录 V14 实施过程中对协议、口径、版本的**实质**决定。每条包含：背景、决定、影响、可回滚性。

## D-V14-001 · 只修口径，不改冻结资产

- 背景：V13 交付了 `docs/v13/` 与 V8/V9/V10 冻结账本、trace。
- 决定：V14 的所有修正只落在**分析层与报告层**（`lab/v13/*` 的纯展示函数、新增 `lab/v14/*`、
  `docs/v14/*`），不修改 `worlds/scenario_v8`、`v10/runtime`、历史 trace、历史账本。
- 影响：`docs/v13/map-validity.md` 会被修正并加注"由 V14 修正"，因为它是由代码生成的
  **展示产物**而不是源数据；源数据（`docs/v12/real-runs/*.csv`）只读。
- 可回滚：是（纯文档/展示层）。

## D-V14-002 · `UNKNOWN` 与 `0` 必须在数据模型里分开

- 背景：历史 CSV 没有 `mechanism_triggered` 列，V13 的 markdown 直接打印 `0/N`。
- 决定：`map_validity()` 输出三个互斥计数 `observed_true / observed_false / unknown` 与
  `mechanism_triggered_observed` 分母；只有 `observed_*` 才可写 `x/n_observed`，
  全未知写 `UNKNOWN (0 observed)`。保留旧字段 `mechanism_triggered_runs` 以兼容 V13 调用方，
  但新增 `mechanism_triggered_status` 枚举（`OBSERVED_TRUE` / `OBSERVED_FALSE` / `UNKNOWN` / `MIXED`）。
- 影响：UI/CSV/JSON/Markdown 共用同一语义。
- 可回滚：是（新增字段，不改旧字段类型）。

## D-V14-003 · 观测条件身份与 `condition_key` 并存

- 背景：V12 的 `condition_key = map|seed|agent` 不含 config hash；V13 的
  `comparable_group_id` 含预算但不含采样画像。
- 决定：V14 新增 `observation_condition_id`（8 元组：
  map / environment_seed / agent_id / config_hash / contract_version /
  effective_prompt_version / budget_profile / sampling_profile），
  **不改** 冻结的 `condition_key` 字段，只在分析层用它做分组与拒绝判定。
- 影响：旧 trace 仍可读；新分析可以拒绝跨预算/跨采样配对。
- 可回滚：是。

## D-V14-004 · `SUPPORTED` 只描述证据形式

- 背景：V13 四级结论 `SUPPORTED / TENTATIVE / INSUFFICIENT / NOT_TESTED` 容易被读成"策略有效"。
- 决定：V14 在报告与 UI 上把结论拆成三个独立字段：
  `evidence_level`（证据形式）、`mechanism_exposure`（干预是否真的发生）、
  `effect_direction`（描述性方向）。`SUPPORTED` 永不等价于"显著改善"或"因果证实"。
- 可回滚：是（新增字段，旧 `level` 保留）。

## D-V14-005 · 未获批不产生任何付费请求

- 决定：V14 全部 LIVE 相关代码路径默认 `PLANNED_ONLY`，`--submit` 需要显式 `LiveApproval`；
  文档中所有真实模型效果一律写 `LIVE_PENDING`。本轮新增外部付费请求 **0**。

## DCR-V14-01 · 历史 CSV 无法在数据层区分契约版本

- **发现**：`docs/v12/real-runs/*.csv` 的列里没有 `prompt_hash`、`contract_version`、
  `agent_config`。MAP-22 的 contract-1 与 contract-2（DCR-V12-01/02 的修复前后）
  在 `rule_hash` / `metric_hash` / `agent_version` 上**完全相同**，只有来源文件不同。
- **影响**：任何“跨契约版本合并”或“按契约版本排除”的分析，都无法仅凭 CSV 证明；
  V13 的 21 局 MAP-22 分母里混了 contract-1、contract-2 与 route_log 消融三类。
- **处理**：V14 的 `protocol_group()` 用 `(experiment_kind, source_file, 指纹)` 分组，
  多组并存时标 `POOLED_ACROSS_PROTOCOLS` 并禁止合并求均值；不删数据、不改历史。
- **后续要求**：V14 之后的新 trace 必须落 `prompt_hash` 与 `contract_version`，
  否则同类问题会重现。
- **验证（2026-10-28）**：V14 的 308 份 LIVE `result.json` **确实**含
  `agent_contract_version` / `prompt_hash` / `base_prompt_hash`（例：`agent_policy_v1`、
  `37c740bd…`、`f547618f…`），因此该缺陷只影响**历史 CSV**，不影响新数据。
  已把这条要求固化成回归检查：`scripts/verify_v14.py::check_live_trace_fields`
  （`verify_v14` 由 14 项增至 **15 项**），本机无 LIVE 数据时跳过、不误报。
- **仍未落**：`sampling`（模型采样支持）不在 result 里 → `SamplingProvenance.support`
  仍为 `UNKNOWN`，这是所有 LIVE 配对只能 `DESCRIPTIVE_ONLY` 的直接原因。
- **可回滚**：不适用（只读分析层）。

## DCR-V14-02 · 预算申请文档的算术错误

- **发现**：`docs/v13/live-budget-proposal.md`（2026-10-26）逐行子局合计 221，正文写 229；
  方案 B 写“150 局 / ¥4.19”（实为 186 局）；方案 A 写“¥1.68”（实为 ¥2.11）；
  E2-d/E4/E5 的“预估”未统一使用文档自己声明的 1.5 倍余量公式。
- **处理**：`lab/v14/data_audit.budget_proposal_check()` 从 Markdown 解析逐行数字并用
  真实 V12 单价重算；修正后的文档与 `docs/v14/budget-audit.md` 一致。
- **影响**：修正后逐行预估 ¥10.97（原 ¥9.08），方案 B ¥5.60（原 ¥4.19）；
  建议批准上限不变（A ¥5.00 / B ¥8.00 / C ¥15.00）。
- **后续要求**：任何 LIVE 申请前必须先跑 `scripts/audit_v14_data.py` 并确认
  `declared_total_matches = true`。

## DCR-V14-03 · `memory.v2.bottleneck()` 在 `env_write` 下用错分母

- **发现**：`memory.v2.bottleneck()` 在 `env_write` 模式把 `write_accepted`（写入**次数**）
  与 `route_length`（方位**个数**）比较。一次写入可以包含整段路线，于是"每次写入都完整"
  的臂会被判成 `RECORDED_TOO_SHORT`（离线 probe 实测：`write_accepted=2`、路线 4 步）。
- **影响**：V13 的 `memory-study.md` 里"记录过短"这一诊断标签在 `env_write` 臂上可能误报，
  会让人误以为策略记录不足，实际是分母口径错误。
- **处理**：V14 在分析层新增 `memory_bottleneck_v14()`，`env_write` 按"已写入方位数"
  判定；`memory.v2` 源码**未修改**（改它会牵动 `agent_config_hash` 之外的诊断输出与
  V13 报告，风险大于收益）。报告同时给出 `bottleneck_v13` 与投影值。
- **可回滚**：是（纯分析层）。

## DCR-V14-04 · LIVE Pilot 中 `reflection.v2` 零暴露

- **发现**（2026-10-27，真实 MiMo `mimo-v2.6-flash`，MAP-22 seed 0）：
  - `E3-control`（`reflection.v2`, `enabled=False`）：54 决策、61 请求、`MOVE_BUDGET_EXHAUSTED`，
    有 1 条 `reflection_disabled` 消融事件；
  - `E3-treatment`（`reflection.v2`, `enabled=True`, `trigger_only=False`）：54 决策、54 请求、
    `MOVE_BUDGET_EXHAUSTED`，**`agent_events` 为 0 条** —— 即 `eligible = triggered = 0`。
- **含义**：这一次运行里从未发生"反思干预"。按 V14 的暴露门禁，这是
  **`NO_TREATMENT_EXPOSURE`**，不能写成"反思无效"，也不能把两臂成功率差当作效果。
- **与 V13 的关系**：DCR-V12-05 记录过 `reflection.v1` 在 MAP-16 上零触发的同类问题；
  V13 用 SIMULATED 证明了 `reflection.v2` **可以**触发（冷却/额度/误触发都实测过），
  但真实 MiMo 在 MAP-22 上的行为仍然没有命中触发器。
- **触发器为什么不成立（公开可观察）**：本局的终止码是 `MOVE_BUDGET_EXHAUSTED`，
  说明 Agent 持续在移动；`repeated_rejection` 需要连续 2 次被拒、`repeated_action`
  需要连续 3 次同一动作、`no_progress` 需要公开进度连续 3 步不变。
  这次运行没有满足其中任何一条 —— 属于**触发器与真实行为不匹配**，不是"反思没用"。
- **处理**：
  1. 立即停止 E3 臂的扩展（不再消耗 16 局预算），Pilot 的 2 局保留；
  2. 不作任何"反思有效性"结论；
  3. 若要继续：**必须另立版本**（例如把触发器改成"预算消耗率"或"路径重复率"），
     或在有更长失败前缀的地图（MAP-19/20/29，需先做公开诊断）上重跑；
     不得在原实验上改阈值后继续（会污染对照）。
- **可回滚**：不适用（只是停止扩展，不删除任何数据）。

## DCR-V14-05 · E2-a 处理臂出现 Provider 错误（`unknown_spend`）→ 按规则停批

- **发现**（2026-10-27，真实 MiMo）：`web-20261027T121544Z-c91eeed2`（MAP-16, seed 1, rep 2,
  `planning.v2 enabled=True`）返回 **`PROVIDER_ERROR`**，消息 "Provider 内部错误，本次结果未确认"，
  `usage.cost_unknown = true`（13 请求 / 15 130 输入 token，费用按预留计入）。
- **触发的规则**：预注册停止条件第 1 条 "任一局 `unknown_spend` → 立即停止整个批次并封账"。
  脚本在完成 4 个父实验后停止，**没有重试该局**，也没有把它的费用当 0。
- **影响**：
  - `E2-a/on` 只执行了 6/9 局（另有 Pilot 的 1 局），缺 seed 1 rep2、seed 2 全部；
  - 该臂的 3 次成功全部来自 seed 0（rep1、rep2）与 seed 1（rep0）；
  - 停止时 `E3` 已按 DCR-V14-04 排除，未消耗额外预算。
- **账本口径**：该局 `cost_unknown=true`，按"未知消费保留预留"处理；**不**计入结算额，
  也不当作 0。
- **处理**：
  1. 批次封账，不重试；`E2-a` 的结论只能是"描述性 + 臂不完整"；
  2. 若要补足，需**另开实验**（新的 `experiment_id`/幂等键），并在文档里标为
     "补充实验"，不得与本次合并成 9/9；
  3. Provider 侧原因未查（无 Provider 控制台访问权限）→ 标 `BLOCKED_EXTERNAL`。
- **可回滚**：不适用（只是停止，不删除数据）。

## DCR-V14-06 · MAP-22 的瓶颈是移动预算，不是请求预算

- **发现**：90 → 150 请求上限的预算扩展实验里，失败局的终止码仍是
  `MOVE_BUDGET_EXHAUSTED`（决策数 46–70），MAP-22 的公开移动预算是 **44 步**。
  也就是说：提高请求上限**不会**延长可走步数。
- **为什么重要**：主矩阵在 90 请求下两臂都是 0/10，很容易被读成"记忆没用"；
  实际是"预算结构让这一档不可能成功"。真正的杠杆是"用更少移动完成任务"。
- **验证**：150 请求档里 `route_log=on` 的成功局只用 **15–25** 请求就走完，失败局要走 46+ 步；
  且效果只出现在 seed 2（见下）。
- **影响**：任何后续 MAP-22 实验必须同时报告"移动预算使用率"，否则无法区分
  "策略差"与"预算结构不允许"。

## DCR-V14-07 · `route_log` 的效果是"实例 × 预算"条件性的

- **数据**（MAP-22、`mimo-v2.6-flash`）：
  - 90 请求：off 0/10、on 0/10；
  - 150 请求：off 2/21、on 8/14；
  - 按 seed：seed 0 `0/6 vs 0/3`、seed 1 `0/6 vs 0/3`、seed 2 **`2/9 vs 8/8`**。
- **读法**：`route_log` 不是普遍增益，而是"在某个具体迷宫实例（seed 2）+ 足够请求预算"下
  把"走不完"变成"走得完"。seed 0/1 两臂都失败 → 那里缺的不是路线记忆。
- **处理**：报告必须给按 seed 的拆分；不得把 seed 2 的 8/8 写成"记忆提升了通过率"。
  下一步若要确认，应补 seed 3（MAP-22 有 4 个合法 seed）与更多重复，而不是继续加预算。

## DCR-V14-08 · 记忆的瓶颈是"记录未被使用"，不是"记不住"

- **数据**（`docs/v14/map22-instances.md`，只读公开轨迹，65 局 `memory.v2`）：

| 分桶 | 局数 | 成功 | 平均折返 | 平均重复访问步 | 平均 `route_recall` | 最大已用移动 |
|---|---:|---:|---:|---:|---:|---:|
| seed=2 on @150 | 8 | **8** | **5.0** | **18.1** | 0.253 | 30 |
| seed=2 off @150 | 9 | 2 | 16.4 | 42.8 | 0.057 | 44 |
| seed=3 on @150 | 5 | 0 | 24.4 | 45.8 | **0.695** | 44 |
| seed=3 off @150 | 5 | 0 | 25.0 | 42.6 | 0.045 | 44 |
| seed=0 on @150 | 3 | 0 | 28.7 | 45.7 | 0.189 | 44 |
| seed=1 on @150 | 3 | 0 | 28.3 | 45.3 | **1.0** | 44 |

- **发现**：`route_recall` 在所有 seed 上都能升到 0.19–1.0（**写入成功**），
  但"折返/重复访问"只在 **seed 2** 上显著下降（16.4→5.0 / 42.8→18.1）。
  seed 3 甚至 recall=0.695 却与 off 臂折返数几乎相同（24.4 vs 25.0）。
- **含义**：把记忆当作"能否记录"的问题是错的。真正的失败模式是
  **"记录了但没有据此改动作"**（行为层），这与 V13 的
  `RECORDED_NOT_REFERENCED` 瓶颈标签同源，但现在有了逐局公开轨迹证据。
- **修正后的说法**：
  - ✅ "`route_log` 让路线被完整写入公开记忆"（recall 0.19–1.0）；
  - ✅ "在 seed 2 上，写入同时带来了更少的折返，从而 8/8 成功"；
  - ❌ "记忆提升了通过率"（其它 3 个 seed 无变化）；
  - ❌ "模型记不住路"（recall 已证明记得住）。
- **可回滚**：不适用（只读分析）。

## DCR-V14-09 · 提高记录频率不能修复"记录了但不使用"（负向结果）

- **假设**（针对 DCR-V14-08）：`route_write_every=2` 让路线每 2 步才更新一次，
  模型看到的是过时路线 → 改成 `route_write_every=1`（每步写）应能提高利用率。
- **实验**：MAP-22 @150 请求，`route_log=True` 两臂，唯一变量 `route_write_every`（2 vs 1），
  seeds 0/1/3（seed 2 之外的全部实例）× 3 次重复 = 9 局/臂。
- **结果**：
  - 成功率：`we=2` 在 seeds 0/1/3 上 **0/11**；`we=1` **0/9** → 无差异（都是 0）；
  - `route_recall`：`we=1` 反而更高（seed 0 **0.977**、seed 3 0.682、seed 1 0.402）；
  - **折返数没有下降**：seed 0 `off 25.2` / `we=2 28.5` / `we=1 28.0`；
    seed 3 `off 25.0` / `we=2 23.5` / `we=1 20.0`（轻微下降但不转化成功）。
- **结论**：记忆**可用性**（写入完整度）不是瓶颈；把 recall 从 0.59 提到 0.98
  也没有改变折返行为。→ 瓶颈在**策略是否依据记忆改变动作**，不是配置能修好的。
- **处理**：`route_write_every` 不再作为候选修复项；若要继续，需要**策略侧改动**
  （例如显式的"按记录返程"子目标），且必须另立版本。
- **可回滚**：不适用（只读分析 + 已完成实验保留）。

## DCR-V14-10 · reflection 的"方向性正向"在扩大样本后消失（自我更正）

- **前一轮**（DCR 前的观察，n=13/臂）：`trigger_only` 3/13 vs `reflection_on` 7/13，
  Fisher p=0.226 → 当时写成 `TENTATIVE / IMPROVED（方向性）`。
- **本轮扩大样本**（契约限制 `replicates ≤ 10`，因此拆成 3 个独立父实验对，
  每对 10 次重复）：seed 2 上 `trigger_only` **16/36 (44.4%)** vs `reflection_on`
  **15/33 (45.5%)**，**Fisher p = 1.0**，Wilson 区间 [0.295,0.604] vs [0.298,0.620]。
- **结论**：早先的 3/13 vs 7/13 是**小样本噪声**，已在本轮如实更正为
  `effect_direction = NO_DIFFERENCE`。
- **功效说明**：33–36 局/臂足以检出 54% vs 23% 这种量级的差异（约需 37/臂），
  因此"没重现"是有信息量的；但要排除 15 个百分点内的效应，需要约 170 局/臂。
- **教训**：`n<15/臂` 的二项比例对比不能作为方向性证据；
  V14 后续任何"方向性"结论都必须附 Wilson 区间与功效估算。
- **可回滚**：不适用（只读分析；原始局全部保留）。

## D-V14-006 · `results/` 纳入版本库（改变既有仓库规则）

- **背景**：`AGENTS.md` 原规则是"`runs/` 和 `results/` 是本地生成物，默认不纳入 Git，
  除非未来 scope 明确改变该规则"。V14 收尾时用户提出：如果对其他人/AI 审计项目有用，是否该推。
- **评估**（实测）：
  - `results/` **7.8M / 152 文件**，内容全是 `benchmark_v3` + `evaluation_v2` 的聚合
    JSON/CSV（33 个 benchmark 文件 / 110 条 `rows`）+ 2 份 V3 Muse 的 `manifest.json`；
  - 密钥扫描：`sk-` / `Bearer` / `api_key=` / `OPENAI_API_KEY` **0 命中**；
  - 本机路径与用户名扫描：`D:\wenxvn` / `10556` / `C:\Users` **0 命中**；
  - 对比 `runs/` **487M**（其中 320M 是 V3 遗留）、`logs/` 3.8M，且 `runs/` 有 **164 个文件**
    含本机绝对路径 `.venv\Scripts\python`。
- **决定**（用户 2026-10-28）：**只推 `results/`**；`runs/` 与 `logs/` 继续不入库。
  排除运行时锁 `*.lock`（9 个 0 字节文件）、`__pycache__/`、`*.pyc`。
- **理由**：`docs/` 里 V1/V2/V3 阶段的历史基准数字需要可核对的原始聚合；
  原始逐局 trace 的审计缺口由 `docs/v14/stage2-closure.md` §8 明确标注为已知限制。
- **可回滚**：是（`git rm -r --cached results` 并恢复 `.gitignore`；历史仍会保留体积）。
- **同步**：`AGENTS.md` 项目约束、`docs/scope/scope.md` 第 26 项、`results/README.md`。
