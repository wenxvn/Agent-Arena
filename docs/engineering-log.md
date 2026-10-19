# Agent Arena 工程事件记录

## 2026-10-16 V6 47 局真实 API 矩阵（MiMo）

事件：在用户授权下补齐任务书点名的缺口（MAP-18 第二个/第三个闭塞段、MAP-26 三个不同失败前缀、MAP-30 固定前缀纯召回变体、每实例 3 条边界动作），并跑完扩大后的 **47 局**真实矩阵（实验 `729f50b7-2d0a-4023-9687-c175a75d45c2`）。

结果：47/47 局完成，**17/47 成功**；492 次请求；报告费用 **CNY ¥0.29230284**；provider 墙钟 2169.045 秒。逐图：MAP-08 6/6、MAP-16 2/6、MAP-18 0/10、MAP-22 5/6、MAP-26 3/13、MAP-30 1/6。

关键新增信号：
- **MAP-22 L3 记忆消融出现条件差异**：`history5` 30 步截尾失败，`history5_graph_memory` 11 步成功（同实例配对）。
- **MAP-30 纯召回出现条件差异**：`history5_casebook` 一步 3/3 正确，`history5` 与 `history_full` 均 deadline 失败。
- 其余：MAP-08/L1-MAP-16/MAP-26-free 天花板，MAP-18/MAP-26-recovery/MAP-30 完整调查地板。

离线段改动：实例数 24 → 29；`validate_v6_instances.py` 边界检查 1 → 3 条/实例，回放 40/40 → 45/45；MAP-26 恢复前缀可生成（非仅注册前缀）；MAP-30 增加召回变体；MAP-22 `optimal_moves` 按实例最短路。

验证：`pytest -q` 559 passed；`ruff`、`mypy`、V4 oracle、V5 solvers、V6 instances、V6 leakage、V6 fake dry-run 全绿；门禁在提交 `04ac659` 冻结。

下一步：`docs/v6/next-24-gate.md` 维持 `HOLD`；人工审阅后对已出现差异的配对增加重复次数，再决定是否新增预算。

## 2026-10-16 V6 真实 API 复测（MiMo，24 局）

事件：用户授权使用 MiMo API 后，在冻结离线门禁下完成 V6 的 24 局真实矩阵（实验 `a4c916d8-b48e-4043-9122-bbb76754eceb`）。

结果：24/24 局完成，13/24 成功；281 次请求；报告费用 **CNY ¥0.17891580**；provider 墙钟 1510.348 秒。关键结论：**MAP-22 的 V5 0/6 确认为接口假象，修复后 4/4 成功**；MAP-08/22/26-free 出现天花板效应，MAP-18/26-recovery/30 出现地板效应，MAP-16 有干净梯度但两条件无差异。按提纲规则暂停扩矩阵。

过程：smoke 门禁连续拦下并修复了四类真实接口缺陷（DCR-007…010）：非启用条件的假设表草稿作废整条决策、MAP-08 丢失测试站语义、MAP-26 丢失合法 ID 清单（含循环提醒）、MAP-30 合法案卷条目 ID 未公开。每次停止均归档已停止 registry、新建独立账本，未触碰任何历史账本。

验证：`pytest -q` 554 passed；`ruff`、`mypy` 通过；`validate_v4_runtime.py`、`validate_v5_solvers.py`、`validate_v6_instances.py`、`validate_v6_leakage.py`、`run_v6_pilot.py --dry-run` 全绿。结果写入 `docs/v6/pilot-report.md`。

下一步：按 `docs/v6/next-24-gate.md` 保持 `HOLD`；先请人工审阅并重新定标（天花板图加难度、地板图降复杂度），再决定是否新增预算。

## 2026-10-16 V6 能力测量效度修复与泛化验证（离线段）

事件：按用户任务书《V6 能力测量修复与泛化验证》执行 Batch 0–7 的离线段：审计 V5 失败、参数化 V4 引擎、建立 V6 独立实例/求解器/泄漏检查，并给出可选 API 提案。全程离线，未调用任何收费 API。

原因：V5 39 局显示 MAP-16/18/22 几乎无成功，且 MAP-22 失败被怀疑是能力下限；用户要求先提升测量效度而不是通过率。

改动：
- `docs/specs/0019-v6-measurement-validity.md`、`docs/v6/*`（审计、DCR、矩阵、验收、API 提案、门槛）。
- `scripts/audit_v5_failures.py`（只读审计本机 V5 trace）、`scripts/validate_v6_instances.py`、`scripts/validate_v6_leakage.py`。
- `src/agent_arena/v6/`（scenes/catalog/solvers/prompts/leakage）、`tests/test_v6_instances.py`、`tests/test_v6_leakage.py`。
- `src/agent_arena/worlds/scenario_v4/map{08,16,18,22,26,30}.py`：向后兼容的实例参数化（DCR-002…006），默认行为不变。

关键发现：读原始 trace 确认 **MAP-22 history5 的 0/3 是接口缺陷支配**（非记忆条件仍宣传 `write_memory`，环境返回 `ACTION_NOT_AVAILABLE` 共 173 次；`return_to_camp` 只设目标不移动）。该缺陷已在 V6 契约层修复（DCR-001），V4 默认行为与 V5 结果未改。

结果：24 个独立 V6 实例（MAP-08/16/18/22 各 4、MAP-26 5、MAP-30 3）；40/40 实例-seed Oracle 在真实环境回放成功；MAP-16/22 由 BFS 证明最优；泄漏检查 0 命中。

验证：`pytest -q` 552 passed；`ruff`、`mypy` 通过；`validate_v4_runtime.py`、`validate_v5_solvers.py` 输出与基线一致；`validate_v6_instances.py`、`validate_v6_leakage.py` 通过。

限制：所有 V6 实例 `pending_human_review`；MAP-18 无最优性证明且闭塞载荷依赖发车时点；未接真实模型；其余 24 图维持 `HOLD`。

下一步：请用户完成人工审阅并决定是否批准小规模 smoke 预算；未批准前不执行付费实验、不扩展 24 图。

关联提交：本批提交（V6 代码、文档与测试）。

## 2026-10-16 V5 正式 39 局矩阵完成（第二次 pilot）

事件：用户明确授权后，归档已关闭 registry、在当前提交 HEAD 重新冻结 offline gate，并新建一次登记的 MiMo pilot，完成 V5 提纲的全部 39 局矩阵（每图 3 个 seed 标签的全部登记条件）。

原因：第一次 pilot 因系统性 `INVALID_ACTION_SCHEMA` fail-closed；用户要求继续执行提纲矩阵并逐图 3 seed 测试。已关闭账本按设计不可恢复或新建 successor，故本次作为新的登记 pilot 执行。

改动/执行：`runs/v5/pilot_registry.json` 旧记录归档至 `runs/v5/archived/pilot_registry.closed_d3f3d7be-c928-4433-b6aa-9a269d97f593.json`；`freeze_v5_offline_gate.py` 在 HEAD `aae5088` 全绿（gate `f0619e8059c3…`）；`run_v5_pilot.py --execute-paid --billing-currency CNY` 新建 experiment `0d0685c8-792d-4b3d-91f5-174d845dde65`，先 6 局 smoke 再跑余下 33 局。未改动 V3/Legacy，也未改写旧 V2/V5 账本内容。

结果：完成 39/39 episode，15/39 成功。逐图 3-seed：MAP-08 4/6（假设表 3/3、无表 1/3）、MAP-16 1/6、MAP-18 0/6、MAP-22 0/6（全部 step-limit 删失）、MAP-26 4/6、MAP-30 6/9（完整历史与案卷 3/3、最近 5 步 0/3）。689 次请求、0 provider error、0 unknown spend；provider 墙钟 3,017.406 秒；报告费用 ¥0.24287288，预留 ¥7.05536（CNY 硬上限 ¥37.50 未触发），ledger 未关闭。

验证：运行 artifacts 与账本保存在 ignored `runs/v5/`；逐图结果同步到 V5 pilot 报告、离线验收报告与效度边界文档。冻结时离线质量门禁全绿（scoped Ruff、mypy、pytest 518、Oracle replay、独立求解器、Fake dry-run）。

下一步：MAP-16/18/22 在当前条件下几乎无成功，须作为测量敏感性不足或任务过难候选，先修正测量设计再扩展；其余 24 图仍需独立立项与登记。不得把固定 scene 重复 seed 当作独立样本或模型排名。

关联提交：本次提交（文档记录；运行数据在 ignored `runs/v5/`）。

## 2026-10-16 V5 MiMo 实时复测与 MAP-08 编码澄清

事件：按用户明确指令，在 schema 修复提交 `eca264d` 后对 MAP-08/no_hypothesis_table/seed 0 做封账后实时复测，并为公开 Observation 编码补充提示词说明。

原因：原 pilot 因系统性 `INVALID_ACTION_SCHEMA` 停止；需在真实 MiMo 上验证提示词约束与同义动作键折叠是否解除该阻塞。复测不续跑 pilot、不改动 registry/ledger、不计入 39 局矩阵。

改动：`src/agent_arena/v5/prompts.py` 的 MAP-08 动作契约补充 `visible_edges` 每条为 `"edge_id:相邻节点"`、`move.edge_id` 取冒号前标识；`tests/test_v5_pilot_controls.py` 增加对应 prompt 回归用例。该说明只澄清公开编码，不改拓扑、胜负谓词或 Oracle。

发现：复测 A（3 个首步请求）3/3 schema 合法并规范使用 `tool`，费用 ¥0.00090248，表明 schema 阻塞已消除、同义键折叠未被触发。复测 B1（澄清前 8 步有界 episode）8/8 schema 合法但模型把相邻节点当 `edge_id`，连续 `INVALID_EDGE`。复测 B2（补充编码说明后同条件）MAP-08 seed 0 在 5 步内 `LEAK_SEALED`（tick 6），0 非法 Action，费用 ¥0.00287236。三组合计费用约 ¥0.00377，均为封账后用户授权诊断，摘要存于 ignored `runs/v5/diagnostics/`。

验证：全量 `pytest -q` 518 passed；`ruff check src scripts tests`、`mypy src`、`git diff --check` 通过。未恢复或新建 V5 ledger，未改动 `pilot_registry.json`；未保存原始模型文本或密钥。

下一步：正式 39 局矩阵续跑仍须在提交 HEAD 重新冻结 offline gate、重新登记预算并完成独立审查；单局成功不得解释为模型能力、smoke gate 通过或矩阵续跑。

关联提交：本次提交（提示词、回归测试与记录同一提交）。

## 2026-10-16 V5 provider 同义动作键折叠

事件：针对 V5 MiMo smoke 系统性 `INVALID_ACTION_SCHEMA`（封账后诊断确认为 Action 缺少 `tool`、改用 `verb`），在 V5 Runner 的 provider 边界增加同义动作键折叠，作为提示词约束之外的离线兜底。

原因：prompt 已补充要求使用 `tool` 并禁用 `verb`，但提示词不保证模型遵循；原运行时只要判别键名不是 `tool` 就把整个可执行意图记为 schema 错误，导致同一局连续 70 次 schema 拒绝。折叠只作用于判别键名，不改变任何地图契约或动作语义。

改动：`src/agent_arena/v5/runner.py` 新增 `_ACTION_DISCRIMINATOR_ALIASES` 与 `_normalize_action_discriminator`；`_clean_candidate` 在 Action 缺少 `tool` 且仅含一个已知同义键（`verb`/`name`/`action_name`/`tool_name`/`command`）时，先把该唯一同义键折叠为 `tool`，再走严格 V4 Action 校验与逐图字段形状 allowlist，并在 decision 行记录 `recovered_action_discriminator`。多个同义键、无已知同义键或折叠后仍非法的响应继续记录 `action:null` 并调用地图 `reject_invalid_action()`。未改地图规则、拓扑、胜负谓词、Observation、预算或账本逻辑。

验证：新增 3 项定向用例（同义键折叠、歧义/未知别名拒绝、runner 无 schema 失败的离线恢复）；全量 `pytest -q` 517 passed，`ruff check src scripts tests` 与 `mypy src`（79 source files）通过。未再次调用 MiMo；原 V5 ledger 仍封闭，不新建 successor ledger。

下一步：正式矩阵续跑仍须满足新的冻结、登记、预算与独立审查门禁；不得把本次离线修复当作已验证的 MiMo 结果。

关联提交：本次提交（runner、V5 定向测试与文档同一提交）。

## 2026-10-16 V5 六图 39 局矩阵离线实现与复审

事件：按用户提供的 V5 测量提纲建立获准六图的隔离运行时和完整能力对照矩阵。当前仅完成离线实现/复核，尚未发起真实模型请求。

范围：MAP-08、MAP-16、MAP-18、MAP-22、MAP-26、MAP-30；MAP-08 seed label 0/4/8，其余地图最多 0/1/2。MAP-30 按提纲登记完整历史、最近五步、最近五步加案卷三条件；MAP-26 将三个故障 seed 与 seed 0 三条恢复反馈支路分开计数。矩阵 39 局，6 局 seed 0 smoke 复用登记 episode，余下 33 局仅在 smoke 验收后释放。未扩展其余 24 图或 Stage D。

改动：新增 spec 0018、隔离 `scenario_v4` 六图环境和 V5 Runner/账本/pilot 门禁；锁定 3,662 次全局请求、33,748,992 token reservation，单币种 CNY ¥37.50 或 USD $5.25。Stage B 余数从登记矩阵与 smoke IDs 派生。MAP-30 的合法问询在 evidence 解锁时向所有条件返回同一公开 fact/witness payload；A 保留完整公开行动与证据历史，C 保留已记录结构化案卷，B 只保留滚动窗口。Episode manifest 按实际条件写入 context policy。用户原有 V1/V2/V4/V5 提纲未修改、未暂存。

验证：第二模型复核 39 局矩阵为 Approve，Stage B 余数、canonical ID 可见性及 manifest Minor 均复查通过。全量 pytest 511 passed；V5/Runtime 定向用例 45 passed；scoped Ruff、mypy（79 source files）、六图 Oracle replay、六图独立求解器和 39 局 Fake dry-run 均通过。MAP-30 全历史 A 前缀请求界 7,880 bytes、再追加一条决策为 7,985 bytes，小于 8,192。dry-run 为六次 fake request、0 paid API call、无持久 dry-run 输出。V5 pilot registry 查询为 `None`；2026-10-16 再查 [官方价格页](https://mimo.mi.com/models/zh-CN/mimo-v2.6-flash)，CNY/USD 缓存/未缓存/输出费率与预登记值相同。宿主无 `uv`，未运行 `uv lock --check`；完整 gate 尚未在提交 HEAD 冻结。离线字节审查额外留下 ignored `runs/temporary-review-only.jsonl`，只有 `offline-fake-v5` 的 `pilot_created` 行，没有请求或 episode，位于正式 V5 registry 外，不得作为 paid ledger 复用。

下一步：确认当前 MiMo 官方费率，按文件白名单提交实现/研究记录；在提交 HEAD 运行冻结门禁。只有 gate 通过后执行 CNY 上限 ¥37.50 的 Stage B 六局 smoke；严格按账本验收后再执行余下 33 局。任何 unknown spend、上下文超限或预算关闭均按记录停止，不新建第二账本。

关联提交：待完成。

## 2026-10-15 V4 三十张手工地图设计完成

事件：完成用户V4提纲要求的30张独立地图设计与逐图离线审计。每张地图手工设定自身机制、成功路线、失败因果、边界和测量，不以批量随机布局或换主题文字代替设计。

原因：V4提纲要求三十张地图具有实质不同的拓扑、信息结构、决策机制、失败原因和能力测量；用户特别要求一张完成后再设计下一张。

改动：完成MAP-29提问预算与固定证人对照，以及MAP-30早期Q4跨时段案卷、依前序证据解锁的NPC记忆和午夜庭审。两图各有手写路线、失败与边界动作、私有规则、公开Oracle及逐图审计脚本。总表复核另修正MAP-01、02、04规则YAML的结构，并为MAP-20、21、22、27补齐各自的规则文件；补充后的规则分别表达对应地图的流量损耗、贝叶斯采样、记忆/拓扑策略、月面资源与货位约束，没有用公共模板替代逐图规则。30张地图均标为`DESIGN_COMPLETE_PENDING_RUNTIME`。新增V4运行时后续Scope第20项和`worlds/v4/AGENTS.md`设计边界。用户提供的V1、V2、V4提纲保持未修改、未暂存。

验证：30/30目录均含规格、设计说明、专属规则、公开Oracle、失败案例、验收与测试用例草案；V4目录内全部YAML/JSON/JSONL可解析，所有状态为`DESIGN_COMPLETE_PENDING_RUNTIME`，纸面设计自审无未勾项；README总表和逐图进度表各列30图。MAP-12–24逐图离线脚本均退出0（含MAP-23 9行Oracle，SHA-256=`01DCF7D5F3AEC83E7169C1A897AF8F33AF753CBBF102E979BD03CB639CF4E3E8`；MAP-24 11行Oracle，SHA-256=`33C3799D4977FA374C788DDB69F4381045E1A0EDE969482F37EE1801D992CFEF`）；MAP-25–28既有逐图审计通过。MAP-29两条成功、三条失败和六项边界通过，19/13 tick成功路线，14行Oracle双次SHA-256一致（`8D0B3CD1CFB19E1BD6BFC5F7F172E3B5ED8613C74B20F800A9DED14BDA02C931`）。MAP-30三条成功、三条失败和五项边界通过，25/32/34 tick成功路线，第40 tick正确提交端点通过，26行Oracle双次SHA-256一致（`D35E73E4094CFDCC35CFA4EEB7D23458EE9C73A28A82E4F696C864064E3DDBE4`）。早期MAP-01–14未勾项均在“尚需运行时验证”段，留待隔离运行时实现。没有运行pytest、V4运行时或真实模型；离线手工Oracle不证明运行时正确性、模型行为或Benchmark有效性。

下一步：按Scope第20项先设计并确认独立的`scenario_v4`运行时契约；不从当前离线Oracle推出模型能力结论。

关联提交：本条记录所在提交（本次V4设计交付）。

## 2026-10-15 文件审核与工作流规范

事件：完成目录文件分类审核、工作流入口整理和文档状态同步。

原因：流程分散于 AGENTS 与 Skill，V3 Scope 状态滞后，部分历史诊断与缺失结果链接容易被当作当前状态。

改动：新增 workflow、Skill 索引与审核记录；精简重复流程，标注历史边界，修复链接和 Action contract 表述，V3 第 19 项同步 done；删除已无用途的 prompt 空占位。CI 增加权限、并发、超时和依赖锁检查。用户原有 V1/V2 未提交提纲保留。

验证：pytest 466 passed，Ruff 与 mypy（64 个源文件）通过；51 JSON、10 CSV、2 TOML/lock 格式检查及正文链接、diff 检查通过。本机无 uv，未执行 lock 一致性检查；远端 CI 结果不包含在本地结论中。详见 [审核记录](maintenance/2026-10-15-file-audit.md)。

下一步：按新入口维护；V2 S2 Gate 仍未通过，不发起模型请求或新预算尝试。

关联提交：本条记录所在提交，可用 `git log -1 -- docs/maintenance/2026-10-15-file-audit.md` 查询。

## 2026-10-14 V3 世界设计 Gate 0 启动

事件：开始执行用户已提供的 V3 世界设计提纲，目标为 10 家族 × 3 难度的 30 关独立确定性场景。

原因：既有 10×3 地图虽然拓扑不同，仍主要共享维修、供电、读码与逃生链；V3 需要将主题机制落实为独立动作、状态转移、成功谓词与失败反馈。

改动：新增 spec 0017 与 V3 状态页；确认旧 `Action`、Legacy selector、Trace 和 V2 ledger/seeded holdout 的隔离边界。用户提供的 `研究提纲/V3世界设计提纲.md` 保持原文，作为本轮采用的设计输入。

验证：HEAD 为 `e23fca0ac2b7cf339c6f16dc21872ea456d45a54`，工作树起初没有 tracked 改动；冻结的 seeded v3 manifest 仍由 spec 0016 与测试锁定。V3 代码开始前基线 Ruff 通过、mypy 49 个源文件通过、pytest 364 passed。当前 Python 3.13 虚拟环境没有 `uv` 命令，`uv lock --check` 未执行；没有 Provider API 请求、GPU 任务或账本改动。

下一步：完成 30 张设计卡与参考策略静态核对；按 spec 0017 的 Gate 1 建立版本化 Scenario 契约和 PY/SU/AB 纵向原型。

关联提交：待完成。

## 2026-10-13 V2 末轮只读失败诊断

事件：按用户要求完成最后一轮 V2 探索；S2 matched-pilot Gate 仍未通过，进一步核查三份 provider failure 的安全 ledger、BUDGET-03 的 timeout 覆盖和 adapter 异常分类。

原因：决定是否存在可在不新增 API 尝试的情况下解除 S2 阻塞，并把可证实的失败原因与不可恢复部分分开。

改动：在 V2 run registry、Memory v3 报告和 Scope 中记录失败事件的 30/30/10 秒账本间隔、BUDGET-03 120 秒配置传递证据，以及 `provider_error` 仍可能对应无输出响应或未分类 SDK/网关异常的限制。BUDGET-01 的 schema 1 不含分类，不能由 30 秒间隔补判为 timeout。没有改写或扩充任何 ledger，也未修改用户未跟踪的 `研究提纲/`。

验证：只读复核三份 ledger 的计数、usage/reservation、关闭状态和 in-flight 状态；检查 `RuntimeSettings` 环境前缀、OpenAI SDK timeout 传参与异常分类代码。无 provider API 请求、无 GPU 运行。`git diff --check` 待提交前执行。

下一步：不创建 BUDGET-04、不推进 S3–S6；只有出现新的合规 S2 Gate 条件后才恢复行为评估。

关联提交：`d66065b`（本诊断记录提交）。

## 2026-10-13 V2 定时维护阶段性暂停

事件：在当前没有其他可独立推进且已获准的提纲任务后，按用户指示暂停 V2 heartbeat automation。

原因：S0/S1 已完成；S2 的 Memory v3 离线实现与验收、停止后 ledger 复核和预算口径同步已完成，但 matched-pilot Gate 未通过。BUDGET-01/02/03 均关闭，v2 为 0/2 完成、v3 未启动；不得复用账本、创建 BUDGET-04 或对原矩阵再次请求。S3 依既有停止指令暂缓，S4、S5 行为验证和 S6 依赖前序正向 Gate/受控证据。

改动：记录当前已完成范围、未解决问题和暂停后的恢复条件。既有 `scope.md` 与 V2 run registry 已保留阶段状态和详细账本证据；用户未跟踪的 `研究提纲/` 未修改。

验证：复核当前 Git 状态及远端 SHA；`git diff --check` 通过。未调用 provider API、未运行 GPU、未推进 S3。定时任务在本次文档提交推送后暂停，周期配置保留为每 30 分钟。

下一步：暂停期间不自动开展维护。恢复时从 S2 Gate 与已记录的停止条件重新核对；不得把离线实现验证写成模型收益或研究 Gate 通过。

关联提交：`eac4f2e`（本条暂停记录首版，已推送）。

## 2026-10-13 V2 预算用量口径同步

事件：将 Scope 中 S2 pilot 的本地记账总额拆分为 provider 返回的 usage 与未知实际扣费的 reservation。

原因：运行登记表的只读 ledger 复核已确认三份账本各项 counter；Scope 旧摘要的总 token 数可能被误读为 provider 确认用量。

改动：逐项同步 BUDGET-01/02/03 的 usage、reservation 和本地记账小计，并明确 26,926 tokens 为已返回 usage、73,211 tokens 为 reservation、100,137 tokens 为本地记账总额；三个 reservation 的 provider 实际扣费未知。

验证：逐项与 `docs/research/v2/00-run-registry.md` 的停止后 ledger 复核一致；`git diff --check` 通过。未调用 provider API、未运行 GPU，用户未跟踪的 `研究提纲/` 未修改。

下一步：S2 Gate 仍未通过；不得重试或重置 BUDGET-01/02/03、不得创建 BUDGET-04。当前授权边界内无后续阶段可执行项，待新的允许条件或用户停止指令。

关联提交：`76a261d`（Scope 口径同步首版；已推送）。

## 2026-10-13 V3 seeded 冻结清单完整性回归补强

事件：补齐冻结清单中 oracle 路线长度、难度桶 split 数量及生成脚本覆盖保护的回归约束。

原因：检查 S5.2 自动化时发现，测试此前从 CSV 读取 `minimum_actions` 再计算难度，且只检查每桶都出现 dev/test；因此 oracle 标签或精确分层数量漂移仍可能通过。

改动：pytest 与 `--verify-runtime` 现在校验规范化 manifest SHA-256、lunar/pyramid 路线长度直方图及每个难度桶的精确 dev/test 数；增加篡改 manifest 必须失败的用例。候选清单生成要求显式新 `--output`，拒绝写入或覆盖冻结 CSV。更正冻结记录中的 BFS oracle 源 blob SHA-256 笔误。

验证：全量 pytest 364 passed；Ruff 全仓通过；mypy 49 个源文件无问题；`--verify-runtime` 在 lunar 90/90、pyramid 30/30 上匹配冻结定义；`git diff --check` 通过。GitHub Actions CI #98 对实现提交全绿（[run #98](https://github.com/wenxvn/Agent-Arena/actions/runs/38402688442)）。未运行 provider API 或 GPU；本轮未重跑完整 BFS oracle。

下一步：S2 matched-pilot 仍为 v2 0/2、v3 未启动，BUDGET-01/02/03 均关闭；遵守停止规则，不新增矩阵请求或推进 S3。继续做提纲允许的离线审计，行为评估等待 S2 Gate。

关联提交：`f1d45ba87332172ac5737c8e1dfcddbae8a0d035`。

## 2026-10-13 V3 seeded holdout 冻结顺序审计

事件：核对 S5.4 要求的实例全集与 dev/test split 是否先于新运行时实现冻结。

原因：Scope 将 S5.2 标为已冻结；需要用 Git 对象和提交顺序支持“先冻结、后开发”的 provenance 结论，并明确 test 暴露限制仍在。

改动：V2-02 记录冻结提交 `f01b38d35029ea16a90c338fcd6911b753bd5b39`（20:28 +08:00）已含 spec、清单和生成脚本但不含 V3 seeded JSON；实现提交 `fac58fe0df226d14903573c6d778e91e67553949`（20:37 +08:00）随后加入两个 JSON。报告同时保留“test placements 仓库可见、仅属程序性 holdout”的限制。

验证：`git log` 核对提交顺序，`git ls-tree` 核对两个提交的文件清单；`git diff --check` 通过。仅审阅 Git 元数据和 tracked 文档，无代码、provider 请求或 GPU 变更。

下一步：遵守冻结 split；S5.2 行为评估继续等待 S2 Gate，不用 test 调 prompt、机制、阈值或生成器。

关联提交：冻结 `f01b38d35029ea16a90c338fcd6911b753bd5b39`；运行时 `fac58fe0df226d14903573c6d778e91e67553949`。

## 2026-10-13 V3 seeded 回归覆盖与本地质量门禁

事件：为冻结的 120 个 V3 seeded 布局补充自动回归覆盖，并完成全仓本地门禁。

原因：前一轮只用离线 manifest audit 对照运行时；需把 hash、seed 周期、布局和 holdout 契约锁入 pytest，避免后续改动静默改变预注册实例。

改动：新增 `tests/test_flex_v3_seeded.py`，逐行比对 120 个冻结实例的 hash、placement、difficulty、split、激活容器和 seed 周期，并断言非激活候选不进入公开房间对象、负 seed 拒绝。扩展 `tests/test_flex_world_identity.py`，在不同 `PYTHONHASHSEED` 子进程核对两个版本的 hash 和周期。

验证：定向 pytest 5 passed；全量 pytest 361 passed；Ruff 全仓通过；mypy 49 个源文件无问题；manifest runtime audit 在 `PYTHONHASHSEED=42` 下仍为 120/120 一致。未运行 provider API 或 GPU。GitHub Actions CI #93 对提交 `b3010512023323609196412f2a4915fa738ded4a` 全绿（[run #93](https://github.com/wenxvn/Agent-Arena/actions/runs/38399647555)）。

下一步：按原提纲检查尚可离线推进的 S5/S6 项；S5.3 需等 S2–S4 正向机制证据，在线行为评估仍受 S2 Gate 阻塞。

关联提交：测试 `0ac83f2c2bd93acb0113efb7b51bea0c90c04006`；本地记录及 CI 确认 `b3010512023323609196412f2a4915fa738ded4a`。

## 2026-10-13 V2 S5.2 seeded v3 实例全集与 holdout 冻结

事件：确定并冻结 seeded v3 的候选实例全集、路线难度标签与程序性 dev/test 边界。

原因：现有 v2 每图只有两种布局且没有 difficulty；必须保留旧世界，并在模型或 Agent 模块开发前冻结新实例身份和留出拆分。

改动：新增 spec 0016、全量布局 oracle/manifest 脚本与 120 行冻结 CSV；每图 6 个候选容器、每实例激活 2 个，覆盖 lunar 90 种和 pyramid 30 种唯一布局。Scope 与 V2-02 记录两档地图内 oracle 难度、分层 split 以及 test placement 在仓库可见、因此不属于盲测的限制。未修改 v2 或运行时世界代码。

验证：当前 FlexEnvironment BFS 对 120/120 个候选定义找到成功路径；清单核对 120 个唯一 hash、seed 0–89 / 0–29 各覆盖全集一次、跨版本 hash 碰撞 0。split 为 lunar 60 dev / 30 test、pyramid 20 dev / 10 test，四个地图内难度桶均同时含 dev/test。Ruff、`MYPYPATH=src` 下脚本 mypy、`git diff --cached --check` 通过。未运行 pytest、provider API 或 GPU。规则源 SHA-256=`11393734c890312a3ae5e19057ae809a8a5c976c4bd43a91e6c4152304a51752`；BFS oracle 源 blob SHA-256=`908faf6ff181557a885041be747dd245ac1f86ce6b9fd2346d446a26d0a5e556`。

下一步：该冻结提交后的计划是实现两个新 selector 并逐 seed 核对 hash；已在紧接的运行时事件中完成。test 实例仍不得用于 prompt 或机制调整，在线矩阵等待 S2 matched-pilot Gate。

关联提交：`f01b38d35029ea16a90c338fcd6911b753bd5b39`。

## 2026-10-13 V2 S5.2 seeded v3 运行时 identity 对照

事件：实现两个 seeded v3 world selector 和冻结布局 seed 映射，并对照 120 个预注册实例。

原因：离线全集与 dev/test 边界已先冻结；运行时必须复现相同 definition hash 和 placement，才能进入后续行为评估。

改动：新增 lunar/pyramid 六容器 v3 JSON、`LunarV3SeededEnvironment`、`PyramidV3SeededEnvironment`、确定性 affine seed permutation、稳定 hash 排序及 selector 注册。非激活容器从该实例公开房间对象中移除；v2 文件、v2 seed builder 和 FlexEnvironment 动作规则未修改。Scope、README、spec 0016 与 V2-02 更新到运行时实现状态；冻结脚本增加 `--verify-runtime`。

验证：对 frozen CSV 的 90 个 lunar 与 30 个 pyramid seed 逐项核对运行时 stable hash、工具放置、激活容器、非激活容器隐藏和 seed+全集大小周期，120/120 匹配；默认进程及 `PYTHONHASHSEED=1/42` 进程均一致。Ruff 与 `MYPYPATH=src` 下 mypy 50 个源文件通过，`git diff --cached --check` 通过。未运行 pytest、provider API 或 GPU；身份匹配不是模型表现证据。

下一步：保留 test 作为未触碰的程序性 holdout；待 S2 matched-pilot Gate 通过后再按预登记预算运行 dev/test 行为评估。当前不得调整 prompt 或机制来适配 test。

关联提交：`fac58fe0df226d14903573c6d778e91e67553949`。

## 2026-10-13 V2 S5.2 seeded 布局覆盖缺口

事件：将 S5.2 从“长尾分析完成”更正为部分完成，并量化现有 lunar/pyramid seeded 生成器的可用实例多样性。

原因：原提纲要求不同 seed 具备足够多的不同实例、逐实例可解且难度与 oracle 可计算。单看已有 10 条 Trace 不能证明生成器满足这些条件。

改动：扩展 `scripts/audit_v2_seeded_overhead.py` 输出 seed 0–999 的布局覆盖 CSV；保留旧 v2 定义，并在 V2-02、Scope 明确记录两图均只有两种工具布局、没有预设 difficulty 标签，以及后续需新 `world_version` 和先冻结 dev/test instance hash。

验证：本机离线盘点每图 1000 个 seed 各得到两种布局，频数 497/503；四种布局均由当前规则 BFS 求解，lunar/pyramid 最短动作分别为 22/16。原有 10 条长尾 Trace 分解仍可复算；Ruff、脚本 mypy、`git diff --check` 均通过。未运行 pytest、provider API 或 GPU。

下一步：在动生成器前为扩展容器/实例划分写出版本化决策，并保留旧 v2 作为历史对照；S2 Gate 仍未通过，不推进 S3。

关联实现提交：`c24b098c15fdbce7a9dc1d545fcc2876955bd350`。

## 2026-10-13 V2 S5.2 seeded 长尾离线分解

事件：完成 lunar 与 pyramid seeded 长尾的逐局最短动作和额外行为开销核算。

原因：S5.2 要区分最短可行路线与 agent 行为开销；旧 Trace 的 seeded `world_definition_hash` 曾受 `frozenset` 序列化顺序影响，不能直接用当前稳定 hash 作匹配键。

改动：新增 `scripts/audit_v2_seeded_overhead.py` 和逐局 CSV，覆盖两个地图各 5 个 seed；以公开容器 Observation 和 pickup 房间核对全部 10 个实例布局，再对当前 `FlexEnvironment` 做有限状态 BFS。V2-02 与 Scope 记录最短步数、移动动作差值、工具房回访、重复 look、阶段拒绝和重复失败重试，并保留 Trace 未记录环境规则 SHA 的限制。

验证：仓库临时环境 Ruff 与针对脚本的 mypy 均通过；脚本读取 10 条成功 Trace，所有布局逐局匹配。lunar/pyramid 长尾分别为 232/22 与 159/16 动作，`git diff --check` 通过。未运行 pytest、provider API 或 GPU。

下一步：S2 pilot Gate 仍未通过且登记矩阵已停止请求；不推进 S3，继续处理可离线完成的 V2 提纲任务。

关联实现提交：`08dd59a2e26cca291fa530be501b09c309c66138`。

## 2026-10-13 V2 S1.3 固定地图参考路径比值补充

事件：重新核对 S1.3 的 optimality gap 要求与项目接受的地图 spec，发现 42 个固定地图 selector 在 spec 0011–0013 中已有最短公开路径步数。

原因：此前 S1 报告将缺少 oracle 与地图身份匹配概括为全部不可计算；Trace 实际保留 world version、definition ID 和 definition hash，允许对参考路径和当前地图 identity 做严格三元组匹配。

改动：新增 `scripts/audit_v2_oracle_ratios.py`，按 42 个 spec 路径参考与精确 map identity 生成逐 Trace 和分条件 CSV；V2-02 与 Scope 补入可匹配范围、未匹配样本和术语边界，并将深海/灯塔/飞船三条既有长尾案例与其参考步数并列。只计算成功 outcome；不将 seeded/hash 不匹配记录填零，也不将混合分布用于方法比较。

验证：474 条源记录中 439 条精确匹配登记地图 identity；227/262 条成功 trace 匹配到路径参考，分布于 50 个条件。独立复算明细和汇总无差异；无成功动作数低于 spec 声明参考步数的情况。Ruff 检查和 `git diff --check` 通过；未运行 pytest/provider/GPU。Trace 缺少环境规则代码 SHA，因此参考比值不等同于对历史规则实现的独立证明。

下一步：用有精确 map+reference 身份的分层结果定位固定地图长尾；S2 Gate 仍未通过，不推进 S3。

关联提交：`eb2f0f1bc838ebbf067284c4158b34a45cfd7b42`。关联证据：spec 0011、0012、0013；Trace identity 见 V2-02。

## 2026-10-13 V2 研究基线文档一致性复核

事件：按 V2 提纲 §1.2 复核 README 与 Scope 中历史成功口径、E1 条件和火山难度均值。

发现与改动：Scope 保留 45/45 是 9 个配置各至少一条成功、原始唯一尝试 46/51、150/150 是补跑后配置覆盖；新七世界仅火山困难均值 31.4 低于中等 35.4。README 的对应摘要与上述范围一致，但其 Memory v3 状态仍称预算门禁“尚未实现”。依据 spec 0015 和运行登记表，将其改为门禁已实现、三次隔离 pilot 未完成 episode 并 fail-closed、v2 0/2 且 v3 未启动。

验证：逐项对照 README、Scope、V2-01、V2-03、spec 0015 与 run registry；历史指标未改写，也未将未提及的 E1-OFF 结果补成 README 结论。无 provider API 调用、GPU 或 pytest；`git diff --check` 通过。

下一步：维持 S2 matched-pilot Gate 未通过及不推进 S3 的边界；继续检查离线资料与持久文档的一致性。

关联提交：`c2a7e735f43b2a2a226fd67d3e91afce7a5b0962`。关联证据：V2-01、V2-03、spec 0015、`docs/research/v2/00-run-registry.md`。

## 2026-10-13 V2 S1.3 分层分布与里程碑间隔补充

事件：从已完成的逐 episode 审计 CSV 补齐长尾 P50/P75/P90/max、executor token/延迟分布和公开里程碑间隔。

原因：原始 V2 提纲 S1.3 要求长尾分位数及阶段相邻里程碑耗时；原汇总缺少 P75 与可按实验条件复算的区间分布，无法完整呈现旧 Trace 的可观察范围。

改动：新增 `scripts/summarize_v2_distributions.py` 与 `condition-distributions.csv`，按实验批次、world version、配置签名分组；在 V2-02 解释分位数口径、总体混合样本限制、成本删失和非认知阶段间隔，并更新 scope。无代码行为或实验配置变更。

验证：92 个条件与既有审计 JSON 的 attempts/success/P50/P90/max 全部一致；独立从 474 条 CSV 复算得到 262 条成功、252/10 两类里程碑顺序，独立复算 57 个条件输出指标无差异。Ruff 脚本检查和 `git diff --check` 通过；没有 provider API 调用、GPU 运行或 pytest。

结论与下一步：S1.3 可由旧 Trace 支持的分层描述已补齐；没有 oracle/地图版本匹配证据，optimality gap 不可计算。BUDGET-01/02/03 保持关闭，S2 matched-pilot Gate 未通过，不推进 S3。

关联基线：`807d46ce03cba0b1d86213e5c8feeb400cc4eccd`。

## 2026-10-13 V2 S1 逐家族 Trace 案例复核

事件：按 V2 原始提纲 S1.4 对深海站、古堡、丛林、灯塔、月球、极地、金字塔、飞船、地铁、火山逐家族复核代表性 Trace。

原因：此前 V2-02 有总体统计和长尾假设，但没有覆盖全部世界家族的短成功、长尾及异常/删失样本索引，无法核对不同家族是否呈现同类症状。

改动：新增 `docs/research/v2/assets/trace-case-review.csv`，索引 31 条 episode；更新 V2-02，列明选样规则、逐步公开事件、outcome 分类和 Trace 可观测性限制，并将既有长尾表拆分 `world_version` 与 `world_definition_id`。

验证：31 条索引的 episode_id 唯一且本地源路径均存在，10 个家族各有最短/长尾成功样本；8 个家族仅选 provider-error 删失，灯塔含 step_limit，飞船含 step_limit 与 invalid_action_limit。474 条 Trace 的 `memory_statistics` 均缺失，422 条启用 world-declared phase context；所选 20 条成功 Trace 的 subgoal/suggested-action/planner-feedback 记录为空。仅复核公开 Observation/Action/ToolResult/progress，不读取或导出 `decision_reason`。无 provider API 调用、无 GPU 运行。

结论：S1 离线瓶颈定位与可观察案例复核完成；旧 Trace 不能证明记忆遗忘或自主阶段判断的内部根因。S2 matched-pilot Gate 仍未通过，BUDGET-01/02/03 保持关闭，不推进 S3。

关联复核基线：`a7843067746350d5d2afb0ca017cd66196ab130b`；案例复核提交 `5cb3353f5a05a5b139d9d29c7c0486f77375c8aa` 的 [GitHub Actions run #85](https://github.com/wenxvn/Agent-Arena/actions/runs/38386424743) 成功。

## 2026-10-13 S1 Trace 审计可复现性复核

事件：重新运行 V2 S1 离线 Trace 审计，并将输出写入独立临时目录，与版本库中的 CSV/JSON 逐字节比较。

原因：在 S2 matched-pilot Gate 未通过期间，确认既有离线瓶颈分析仍对应当前本地 runs/ 与 results/ 输入，避免将过期审计产物作为阶段依据。

改动：V2-02 记录本次复核方法与结果；未覆盖已提交审计产物，也未触碰用户未跟踪目录。

验证：审计得到 518 个文件、474 个唯一 episode、44 个副本、0 个 ID 冲突、0 个不可读或非法 Trace；outcome 为 success 262、step_limit 76、provider_error 135、invalid_action_limit 1。生成的 CSV 和 JSON 均与已提交产物字节级一致。未调用 provider API、未运行 GPU。

下一步：S1 结论保持有效；S2 在线 Gate 仍未通过，依照关闭的 BUDGET-01/02/03 停止规则，不发送新请求、不推进 S3。

关联复核基线：`5ff001e396a3e0fb7899dd8d218cf0a5a9e49ff3`。

## 2026-10-13 S2.4 公开事实更正与负例补充

事件：离线审计 S2.4 fixture 时发现 v3 同一房间的不同 Observation 描述会累积为普通事实，重复里程碑事件摘要也可能在事件记录之外残留。

改动：v3 按 room 键保存最新 Observation 描述，同房间更正替换旧值并计为 update；allowlisted 事件摘要只保存在事件记录中。渲染压缩可省略非当前房间的旧 room facts，但保留当前房间描述。新增非法候选/correction request、已读码后移动回程、单向出口、事件摘要更正及 Observation 更正 fixtures；v2 路径未改。

验证：加入 room-fact 压缩回归，确认超限时省略旧房间描述并保留当前房间描述；普通事实压缩用例精确断言 24 条中省略 8 条、保留 16 条、20 条失败动作仍在且 omission map 计数准确。新增默认 v2 provider memory-data golden fixture，并让 legacy trace fixture 移除 `memory_statistics` 后验证读取兼容。全量 pytest 357 passed、`ruff check .` 通过、`mypy src` 49 个源文件通过、`git diff --check` 通过。实现提交 `b29fe93f92761808cccff918071b742f908cde45` 的 [GitHub Actions run #76](https://github.com/wenxvn/Agent-Arena/actions/runs/38381561646) 和既有 fixture 补充提交 `077a8a346222242be51acb087e9d29b3b0846e56` 的 [GitHub Actions run #78](https://github.com/wenxvn/Agent-Arena/actions/runs/38382016747) 均通过；本轮验收夹具提交 `29d6917c8f2825b175735f92443d1692b14e843d` 的 [GitHub Actions run #81](https://github.com/wenxvn/Agent-Arena/actions/runs/38383303143) 成功。依赖未改动；未调用 provider API。

下一步：继续核对 S2 离线验收与研究报告的一致性；在线 Gate 未通过，按 BUDGET-03 停止规则不再发起矩阵请求，不推进 S3。

关联实现提交：`b29fe93f92761808cccff918071b742f908cde45`；fixture 补充提交：`077a8a346222242be51acb087e9d29b3b0846e56`。

## 2026-10-13 完整覆盖 Memory v3 insertion/update 计数

事件：继续审计全部持久记忆字段时，发现初始化时的 `revealed_items`、后续新增 open question、题目解决、current-room 指针和里程碑状态变化未进入统计。

改动：扩展 insertion/update 计数，初始化和增量分别纳入 revealed items、questions 等集合记录；inventory/current-room/milestone/event/question 生命周期变化计为 updates。spec 0014 写明计数口径：M1 的 invalidations 专指显式事实失效，保持为 0；成功后关闭问题计作 update。新增针对初始记忆、发现物品、拒绝/修复动作和重复事件的统计回归。

验证：Python 3.13.3 本地全量 pytest 350 passed、`ruff check .`、`mypy src`（49 个源文件）和 `git diff --check` 通过。`uv` 不可用，未运行 `uv lock --check`，依赖文件未改动。提交 `a336bd68768f32a35e5c6a906b60045571b63669` 的 [GitHub Actions run #74](https://github.com/wenxvn/Agent-Arena/actions/runs/38379921434) 成功。没有 provider 请求。

下一步：继续 S2 离线验收；维持 S2 在线 Gate 未通过、当前矩阵停止，不推进 S3。

关联实现提交：`a336bd68768f32a35e5c6a906b60045571b63669`。

## 2026-10-13 修正 Memory v3 容量边界的 insertion 统计

事件：离线复核发现 v2 的 12 项访问地点列表填满后，v3 仍能新增 `visited_rooms`，但累计 `insertions` 少记新房间。

改动：v3 insertion 统计改为比较独立的 episode 房间集合；容量边界 fixture 在 12 项列表已满时再进入一个房间，断言这一步准确记录房间、事实、出口和成功边共 4 项新增。

验证：回归测试先在旧逻辑下失败（实际记 3，预期 4），修复后全量 pytest 349 passed、`ruff check .` 和 `mypy src`（49 个源文件）通过，`git diff --check` 通过。`uv` 命令不可用，未运行 `uv lock --check`，依赖文件未改动。提交 `8e4217241f848887bb7040e40865db6b0a075070` 的 [GitHub Actions run #72](https://github.com/wenxvn/Agent-Arena/actions/runs/38379141983) 成功。没有 provider 请求。

下一步：核验本次提交的远端 Actions；继续 S2 离线审计，保持模型收益结论与 S3 推进关闭。

关联实现提交：`8e4217241f848887bb7040e40865db6b0a075070`。

## 2026-10-13 V2 S2 完整 Trace 的确定性记忆摘要

事件：离线审计发现 spec 0014 要求完整公开 Trace 重放应得到稳定 memory digest，但实现仅有手工状态渲染对照，没有 digest 接口或落盘 Trace 回放验收。

改动：`MemoryV3State` 新增基于规范化 JSON 的 SHA-256 `memory_digest`，排除派生统计计数器；测试将 10 步公开 Trace 落盘并重新读取，独立重放两次，比较 digest、frontier 和因果事件顺序。更新 V2 S2 研究记录与 scope。没有发起 provider 请求。

验证：Python 3.13.3 本地环境执行全量 pytest（349 passed）、`ruff check .`、`mypy src`（49 个源文件）均通过；提交 `e907237ca4c1dd4f06a48690a44a59c8568865c2` 的 [GitHub Actions run #70](https://github.com/wenxvn/Agent-Arena/actions/runs/38378309801) 通过。`uv` 命令当前不可用，未运行 `uv lock --check`，且依赖文件未修改。S2 在线 Gate 仍未通过，三份失败 ledger 和 partial 输出保持原样，不推进 S3。

下一步：遵守当前矩阵停止规则，继续做不触及预算 ledger 的离线工作；没有匹配 v2/v3 完整 episode 前不报告机制收益。

关联实现提交：`e907237ca4c1dd4f06a48690a44a59c8568865c2`。

## 2026-10-13 修复 Linux CI 的 mypy 平台类型误报

事件：GitHub Actions run #65/#66 的 Ruff 通过，但 `mypy src` 失败并跳过 pytest。job annotations 未包含 stderr，日志下载需仓库高权限；本地 clean checkout 复现定位未依赖该日志。

改动：`budget.py` 的 Windows-only `msvcrt` 分支与已存在的 Linux `fcntl` 分支一致，在动态平台 API 边界增加 `cast(Any, ...)`；运行实现不变。

验证：锁定依赖的干净临时环境中，Windows 默认与 `--platform linux` 的 `mypy --no-incremental src` 均通过（各 49 个源文件）；Ruff 通过、全量 pytest 348 passed、`uv lock --check` 和 `git diff --check` 通过。实现提交 `4ec5bb1442037543f2f01656bc956f78df546e85` 的 [GitHub Actions run #67](https://github.com/wenxvn/Agent-Arena/actions/runs/38376965970) 中 sync、Ruff、mypy、pytest 全部通过。

下一步：S0 跨平台质量门禁已恢复；继续 V2 离线维护，保持 S2 的 API 停止状态。

关联实现提交：`4ec5bb1442037543f2f01656bc956f78df546e85`。

## 2026-10-13 BUDGET-03 通用 provider error，停止在线尝试

事件：最后一次登记的恢复运行 BUDGET-03 使用进程级 120 秒 request timeout；首个 v2 episode 的第 7 次请求以 `error_category=provider_error` fail closed。此前 6 次 usage 合计 10,043 tokens；失败请求按 25,156-token reservation 记账。账本为 7/488 requests、35,199 locally charged tokens，v2 汇总 0/2，v3 未启动。

改动与边界：BUDGET-01/02/03 的账本和 partial JSON/CSV 都保留。三账本合计 19/500 requests、100,137/4,000,000 locally charged tokens；三次失败 reservation 都不是 provider 实际 usage 证明。无 HTTP status；`provider_error` 无法从保存的 allowlisted 元数据进一步还原根因。按预登记不创建 BUDGET-04，不再发起该矩阵的 provider API 调用；S2 Gate 未完成，不推进 S3。

验证：读取 BUDGET-03 账本中的计数、状态、错误类别、预留额，以及 partial JSON 的零结果行；确认无 in-flight request、v3 目录不存在。没有追加 provider 请求。

下一步：保持三次失败尝试与预算记账在 registry 中可追溯；继续离线审计 V2 提纲和可完成的非 S3 工作。S2 在线证据仍不充分。

关联登记提交：`894f860`；BUDGET-03 执行使用推送 HEAD `d55ce2e`。

## 2026-10-13 BUDGET-02 timeout 与最后一次受限恢复登记

事件：使用安全错误分类实施 SHA `e884688e48c357eafc27251b994e3f6c805acb64` 启动 BUDGET-02；第一个 v2 episode 第 10 次请求被分类为 timeout，预算门禁封账并以 exit 2 停止。前 9 次 usage 合计 15,374 tokens，第 10 次按 25,478-token reservation 记账；BUDGET-02 合计 10 次 / 40,852 本地记账 tokens，v2 0/2，v3 未启动。和 BUDGET-01 合并为 12/500 requests、64,938/4,000,000 本地记账 tokens。

诊断：当前 OpenAI SDK request timeout 配置为 30 秒；budgeted CLI 强制 retries=0。timeout 类别来自保存的异常链分类，实际 provider usage 对第 10 次请求未知。原 BUDGET-02 登记规定错误后不再创建账本；基于本次已知 timeout 证据、仍未超出原总 cap/截止时间及用户要求继续维护，明确将该总体停止点修订为只再允许一个隔离的 BUDGET-03，不允许 BUDGET-04。

改动：BUDGET-02 ledger 和部分 JSON/CSV 原样保留；新预登记 BUDGET-03 使用剩余 488 requests / 3,935,062 tokens，唯一运行参数调整为进程级单请求 timeout 120 秒，其余条件和截止时间不变。新账本、输出目录、实现 SHA 与串行命令已写入 run registry。S2 Gate 仍未完成。

验证：仅读取 ledger 安全计数/状态、partial JSON 顶层摘要和 timeout 配置；未启动 v3 或其他 API 调用。待对 BUDGET-03 登记 commit/push 后，执行最后一次受限恢复；如果发生 provider error 则停止所有后续 API 尝试。

关联登记提交：`894f860`。

## 2026-10-13 provider error 安全分类与预算内恢复登记

事件：原 S2 M1 pilot 的第二次 provider 请求 unknown spend 封账；现有记录不足以区分 HTTP、连接或超时故障。

改动：budget ledger 新增 schema 2，采用固定错误类别与可选 4xx/5xx status；CLI 只显示这两个 allowlisted 字段，不记录或输出异常文本、response body、headers、prompt 或 credential。旧 schema 1 ledger 可验证后迁移；类别为基于异常链的 best-effort 诊断。独立复审没有硬性问题，补齐未知类别、无效/缺失状态码及类别不匹配的 fail-closed 负例。

验证：新增未知错误、HTTP status/敏感文本隔离、connection/timeout/invalid-response 分类、schema-1 迁移及篡改账本拒绝覆盖。定向测试 23 passed；全量 pytest 348 passed，Ruff 全仓、mypy 49 个源文件、`uv lock --check` 与 `git diff --check` 通过；没有 provider API 请求。

恢复安排：单独预登记 BUDGET-02，只使用原 request/token cap 的剩余 498 次和 3,975,914 tokens；绝对截止不晚于 BUDGET-01 的 deadline，使用新 ledger 与结果目录。登记 SHA、提交推送并完成门禁核对后再启动；发生新 provider error 时停止，不创建第三账本。

下一步：完成实施复审、冻结 SHA 和提交/推送 recovery 登记，再按原矩阵串行执行。S2 Gate 保持未完成。

关联实现提交：待提交。

## 2026-10-13 V2 S2 M1 pilot 因 provider error fail closed

事件：按冻结登记启动 Memory v2 的 seed 1；第 2 次 provider 请求报错后，budget guard 关闭账本并以 exit code 2 停止串行矩阵。

证据：请求 `af4ea921-3723-477a-b5e9-2b5a44d9d76e` 完成，usage 为 input 749 / output 760；请求 `087ee418-82cf-4a67-8cad-7e2f6bd21c33` 状态为 `unknown_spend_after_provider_error`，按预留 22,577 tokens 记账。ledger 为 2/500 requests、24,086/4,000,000 tokens，`provider_error_unknown_spend`，无 in-flight request。该 token 总额是本地预算记账，不代表 provider 确认消耗。

结果：v2 benchmark 汇总 0/2 episode、0 条结果行、无完成 trace；v2 seed 2 与 v3 两个 seed 未启动。部分 JSON/CSV、ledger 与请求 ID 均保留在本地 `results/`，不重置、不以同一 budget experiment ID 重试。没有 GPU 运行。

只读核查：OpenAI adapter 将 SDK exception 包装成通用 `DecisionProviderError`，budget wrapper 再包装成通用 `ProviderBudgetExceeded`；ledger 按 spec 不保留 provider 响应或异常元数据。因此无法从当前运行证据确定根因；该分类缺口与实际 provider 侧故障是两件事。

下一步：先评估是否需要添加仅含 allowlisted exception class / HTTP status 的安全分类，再单独登记任何恢复运行；不重置当前 ledger。S2 Gate 保持未完成，不能据此计算模型成效。

关联实现提交：`0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`；运行状态登记提交：`23b1bf2e9ad909370f9a2a2b34599b73750f71ca`。

## 2026-10-13 V2 seeded world identity hash 稳定性修复

事件：pilot 的两次 CLI 前置检查均在 world identity 门禁被拒绝；未到 provider adapter，没有 API 请求、预算账本或 benchmark 输出。

原因：同一 seeded flex world 在不同 Python 进程中得到不同 hash。隔离 `PYTHONHASHSEED=1/2` 后复现为 Pydantic 将 `FlexMilestone.key_items` 这个 `frozenset` 按迭代顺序序列化为数组。

改动：hash 前对 `key_items` 和 `trigger_reasons` 排序；新增跨进程、跨 hash seed 回归；运行登记表将使用修复后实测的稳定 hash。

验证：跨进程 `PYTHONHASHSEED=1/2/3` 下，seed 1、2 均得到 `bd1f77eabdcd032e80dbbaaad29163e85cbea34caf7486c22babcb3b85cb8373`；Ruff、mypy 49 个源文件、`uv lock --check` 通过，全量 pytest 339 passed，`git diff --check` 通过。没有真实 provider API 请求。

下一步：登记并发布修复后的源代码 SHA，随后启动同一组预算受限 pilot。

关联实现提交：`0d3bb0ba0b81ca682ea714941de7b5bd17fd03f9`。

## 2026-10-13 V2 S2 Provider Budget Guard 与 pilot 前置门禁

事件：完成 fail-closed provider request/token 预算门禁，并修复 provider 身份校验、活跃请求恢复和未完成 episode Trace 边界。

原因：S2 受限真实 pilot 需要跨 episode、跨 CLI invocation 的共享额度；并发启动不能误关正在运行的账本，预算或 provider 失败也不能伪装成完成局。

改动：新增持久化预算账本、请求输出上限、expected provider/model/world/prompt 身份冻结、OS invocation/request leases、terminal status 与关闭原因校验、截止时间后 usage 记账、预算异常传播、不落未完成 Trace，以及预算中断或后续 cell 身份不匹配时保留已完成 benchmark 汇总并非零退出；登记表记录共享 cap 与执行命令，并要求 pilot 后逐条核对账本事件。

验证：Ruff 通过；mypy 49 个源文件无问题；全量 pytest 338 passed；`uv lock --check` 通过；`git diff --check` 通过。未发起真实 provider API 请求，未读取或输出 `.env` 内容。

下一步：按登记表启动共享预算内的 Memory v2/v3 配对 pilot；pilot 结果仍须以真实 trace 和账本逐条核验。

关联实现提交：`0a09a4f479cd8b6ba49dd0eeefed80a47d623c06`。

前置核验更正：以 `118e8e…` 和随后单进程计算值 `418ccc…` 启动的两次 CLI 检查均因 world identity 不匹配而拒绝；API 尝试数为 0，未创建账本或结果目录。复现发现两值都不是稳定 identity，根因与修复见上方“V2 seeded world identity hash 稳定性修复”事件。provider/model 与 prompt 身份检查匹配。

## 2026-10-13 V2 S2 Memory v3 离线实现与 pilot 门禁

事件：按 S1 seeded 长尾证据实现可选 Memory v3 Spatial/Event，并完成离线验证。

原因：V2 提纲要求先验证公开房间/边/frontier 与因果事件记忆，同时保持 Memory v2 默认行为；真实实验必须有可执行的全局请求数和 Token 预算。

改动：新增 spec 0014、Memory v3 reducer/renderer、CLI/config 版本选择、可选逐步记忆统计、审计表统计字段和离线回归 fixture；补充 V2-03 报告及 S2 pilot 预登记。另保留有界的完整公开访问房间集合，避免 v2 的 12 项有损地点列表漏掉已访问房间后误报 frontier。

验证：Ruff、mypy（48 个源文件）通过，pytest 316 passed；Trace 审计仍为 518 个文件、474 个唯一 episode。没有真实模型调用或 GPU 运行。检查 provider 代码确认目前不存在跨局 request/token 预留器，且非所有决策 provider 都有单请求输出上限，因此 pilot 明确 blocked。

下一步：补齐 fail-closed 全局预算门禁并验证所选网关遵守输出限制；完成受限 pilot 前不推进 S3。

关联实现提交：`5cea009`。

## 2026-10-13 V2 S1 既有 Trace 离线审计完成

事件：完成 V2 S1 离线瓶颈盘点，产出可复现脚本、CSV/JSON 审计产物和 Top 5 假设报告。

原因：需要将本机既有 trace 按 attempt、配置、地图家族、seed 角色分层，避免将网关中断、重跑和行为结果合并成单一成功率。

改动：新增 scripts/audit_v2_traces.py 与对应测试；扫描 runs/ 和 results/ 下 518 个文件，去重为 474 个 episode_id，44 个副本无冲突；生成 docs/research/v2/assets/trace-audit.csv、trace-audit.json 和 02-bottleneck-audit.md。产物排除 decision_reason；报告区分 provider_error、step_limit 与成功 trace，记录 seeded 长尾、终端读取、use 工具配对、重复失败动作及 progress 代理指标。

验证：Ruff 通过；mypy 48 个源文件通过；pytest 305 passed；GitHub Actions #57 quality job 全部通过。审计为离线读取，0 次 LLM 调用、0 次 GPU 运行。

下一步：S2 先验证 M1 空间/边/frontier 与公开里程碑的 Memory v3 假设；配置固定前不启动对照。

关联实现提交：a372dce。报告和聚合产物随本记录提交。

## 2026-10-13 V2 S0 CI 门禁修复并通过

事件：清理基线 HEAD 的 Ruff 与 mypy 问题，并使 CI 测试不依赖本机生成数据。

原因：初始 Actions #54 的 Ruff 失败阻止 mypy/pytest；修复后的 #55 暴露 9 项测试依赖被 Git 忽略的 runs/ 与 results/。

改动：完成类型与 Ruff 修复；将 UI 测试输入改为临时目录和合成 trace/CSV，保留本机生成数据和用户目录。

验证：本地 Python 3.13.16 / uv 0.13.0 临时环境的 Ruff、mypy（48 个源文件）、pytest（303 passed）、uv lock --check 和 git diff --check 均通过。GitHub Actions #56 quality job 全部通过。

下一步：进行既有 Trace 的 S1 离线审计，按来源和条件拆分首条记录代理、删失与行为结果。

关联提交：d9d13e4、d40f3e6；[run #56](https://github.com/wenxvn/Agent-Arena/actions/runs/38358490666)。

## 2026-10-13 只读研究 UI 维护与边界收紧

事件：修复空步骤 Trace 的分页边界，并收紧只读 UI 对 Trace 与 benchmark CSV 的文件路径边界。

原因：真实启动时单页滑块因 `min_value == max_value` 抛错；代码审查发现 CSV 可指向任意路径、Trace 符号链接可能越出实验目录，且 CSV 深度需遵守一级子目录约定。

改动：单页直接使用第 1 页；Trace 校验最终路径并限制为实验目录直接子文件；CSV 仅允许 `runs/`、`results/` 根目录或一级子目录；README、架构、scope 与 Agent 上下文同步只读 UI 能力、启动方式和最新状态。

验证：`PYTHONPATH=src py -3.11 -m pytest -q` 为 304 passed；浏览器页面可见，Streamlit health 返回 HTTP 200；`git diff --check` 通过；两项独立审查复查无新增问题。当前主机未安装 `uv`、Ruff、mypy，标准 Python 3.13 检查未运行。

下一步：扩大 seeded 实例覆盖并分析长尾步数；新在线实验需先登记预算和固定对照条件。

关联提交：`1bae22c`。

## 2026-10-11 V1 缺口续作：T6 跨任务证据、E1 新世界验证、UI 四视图

事件：V1 收官后并行会话续作三项——flex pilot 真实 30/30 + seeded 15/15
（跨任务迁移成立，seeded 长尾 232/159 步）；187 成功 trace 离线 E1 扫描
（终点误用 0、重读 4 次，E1 泛化成立但无新世界对照组）；UI 只读 MVP 升级
4 视图（回放分页/矩阵总览+Success@K/错误热点/条件对照）。
原因：SUMMARY 点名的三项未做（跨任务泛化、E1 新世界复验、前端优化）；
T7-Reflection deferred 为合法终态，不硬做。
改动：新增 `docs/research/v1/08-cross-task-and-e1.md`（不碰已冻结 00–07
与 SUMMARY）；`ui/present.py` +4 纯函数、`ui/app.py` 4 视图；
UI 测试 10 新增/同步。
验证：`PYTHONPATH=src python -m pytest -q` 全套通过；E1 扫描零新调用。
下一步：全量 seeded 推广与跨任务泛化讨论（V1 T6）；commit/push。
关联提交：`a3ec4f5`。

## 2026-10-11 pilot/seeded 7 配置真实模型 35/35 通关

事件：6 张 flex pilot + 飞船 seeded 共 7 配置 × 5 seeds 获 35/35 成功；
seeded 图出现 232/159 步长尾（工具分置双容器迫使多趟奔波），固定图无此现象。
原因：用户要求把剩下的图全部跑完；同获胜组合，21 并发池一次通过，
无网关限流、无补跑。
改动：仅实验运行；新增 `scripts/run_flex_matrix.py`；trace 在
`runs/muse-flex-*`（本地生成物）；spec 0012、scope §K 更新。
验证：逐局 trace 离线汇总：月球分支 35.8/seeded 97.0、古堡并行 47.6/
seeded 48.6、金字塔反转 35.6/seeded 62.8、飞船 seeded 41.0，非法输出 0。
下一步：全量 seeded 推广与跨任务泛化讨论（V1 T6）。
关联提交：`9a2d9d1`。

## 2026-10-11 旧三世界 9 张重制图建成，全套 293 passed

事件：边集审计确认旧 9 图换皮后，用 9 张独立拓扑新版本替换它们在 10×3
矩阵中的位置（旧图冻结，selector 保留）；途中修好新旧版本 selector
撞车（abyss/light 走各家序列号）与两处测试路线 bug。
原因：用户要求去换皮，否则测试没意思；新 10×3 = 9 重制 + 21 新世界图。
改动：9 个 JSON + 三引擎各追加 V4/V5/V6（abyss 为 V2/V3/V4）定义与环境类
+ `worlds/__init__.py` 新增 9 对 selector + 3 个新测试文件（22 项）+
spec 0013；旧 30+6 图一字节未动。
验证：`PYTHONPATH=src python -m pytest -q` 293 passed；9 图公开通关
（20/13/12、22/21/16、24/19/17），诱饵/门禁/陷阱项全过。
下一步：9 重制 × 5 seeds 真实模型矩阵（45 局，21 并发池，不停到全通），
再与 105/105 合并为新 150 局报告；commit/push。
关联提交：`98d50ab`。

## 2026-10-11 新 10×3 矩阵 150/150 完成

事件：9 张重制图 45/45（第一波 42/45，3 局网关中断第二波补齐），
与 21 图 105/105（同条件：memory + history5 + recovery + phase + 不限步 +
`muse-spark`，seeds 0–4）合并为新 10×3 矩阵 150/150。
原因：用户要求去换皮后跑满 10×3×5，不停到完；21 图沿用已有 105/105，
只新跑 9 重制 45 局。
改动：仅实验运行；`scripts/run_redesign_matrix.py`（多轮池式执行）已提交；
trace 在 `runs/muse-redesign-*`（本地生成物）；scope §L 更新。
验证：逐局 trace 离线汇总：重制三图均值飞船 31.6/38.4/44.4、
灯塔 24.2/41.2/51.2、深海 24.2/33.4/34.4，全部随难度单调递增，
非法输出 0；旧 9 图 45/45 封存。
下一步：pilot/seeded 图真实模型对照（预算登记后）。
关联提交：`59064c5`。

## 2026-10-11 flex 引擎与 6 张 pilot 图建成，全套 271 passed

事件：按用户确认的四个优化方向交付：flex 参数化引擎（分支/并行/反转）、
难度三杠杆打标（spec 0012 表格，离线）、3 张 pilot 图各带 1 个深诱饵、
3 张 seeded 图（工具双容器分配）。
原因：105/105 证明单链已无瓶颈，需验证换任务结构后能力是否还在；
全部走新版本，旧 30 图与 V1 基线不受影响。
改动：`worlds/flex.py` + 6 个 JSON + `worlds/__init__.py` 新增 6 对 selector
+ `arena/models.py` 加 `CELL_STAGED`（加法）+ 3 个新测试文件（22 项）+
spec 0012；测试抓到 `_escape` 不查电源的旧假设 bug 并修复。
验证：`PYTHONPATH=src python -m pytest -q` 271 passed；6 图公开通关
（19/22/16）、分支任一供电、并行缺件断电、无电读码/无电禁逃、
seeded 确定性/差异性/可解性全部通过；本机无 ruff/mypy/uv。
下一步：pilot 图真实模型对照（预算登记后）；全量 seeded 推广待定。
关联提交：`6577388`。

## 2026-10-11 新 21 图真实模型 105/105 通关

事件：Muse 自主组合（memory + history5 + recovery + phase，不限步）在 7 个
新世界 21 配置 × 5 seeds 获 105/105 成功，七图均值步数全部随难度单调递增。
原因：验证新图可通关且难度梯度成立；首波 105 并发触发网关系统性限流，
104 局开局中断，全部 trace 保留并降并发重跑。
改动：仅实验运行，无代码改动；新增 `scripts/run_21maps_matrix.ps1`、
`scripts/run_episode.py`、`scripts/rerun_21maps_pool.py`、
`scripts/summarize_21maps.py`；trace 在 `runs/muse-21maps-*`（本地生成物，
不进 Git）；scope §J 更新。
验证：离线汇总 21 配置全部 5/5，非法输出总共 1 次；尝试分母=首波 105 +
重跑 104 + 补跑 4（含 1 冒烟，另计）。
下一步：把 105/105 纳入 V1 提纲 T2 离线重评与 T6 泛化讨论；commit/push。
关联提交：`452d2b1`。

## 2026-10-11 十世界三十图建成，全套 249 passed

事件：新增极地/金字塔/地铁/火山/丛林/月球/古堡 7 个世界，各分三档难度，
共 21 张新图；每张图独立拓扑与读码点，最优公开路径 11–22 步。
原因：用户要求从 3 世界扩到 10 世界，且明确不要纯换皮。
改动：`worlds/{polar,pyramid,subway,volcano,jungle,lunar,castle}.py`（规则复用，
只换 definition）+ 21 个版本化 JSON + `worlds/__init__.py` 新增 21 对 selector
+ 7 个新测试文件（56 项）+ spec 0011；旧 9 图一字节未动。
验证：`PYTHONPATH=src python -m pytest -q` 249 passed（含 56 项新测试）；
21 张图全部公开动作序列通关，新码生效、诱饵不挡路；本机无 ruff/mypy/uv，
只跑了 pytest。
下一步：真实模型新图 benchmark（预算登记后执行）；commit/push 本轮全部改动。
关联提交：`e8da39d`。

## 2026-10-11 V1 提纲在线收官（33 次尝试，全部提交）

事件：用户批准在线对照后，完成 C011/C010/React-C111/E1/Pctx/SeedSmoke 全部在线格；
T7-B UI MVP 实现；与并行会话的 7 世界扩展兼容共存。
原因：离线审计已定位缺口，低成本 pilot 逐个验证契约后放量。
改动：`docs/research/v1/`（00–07 + SUMMARY 定稿）、E1 prompt 第 7 条（保留）、
`worlds/variants.py` + seeded JSON + 注册、`ui/present.py` + `ui/app.py`、
7 个新测试文件；`docs/scope/scope.md` 收官状态。
验证：`PYTHONPATH=src pytest` 249 passed；在线 33 尝试全部记账；
`git diff --check` 通过；ruff/mypy 待 CI。
下一步：CI 全绿确认；E1 与消融结论在 7 新世界的复验；跨任务泛化与 Streamlit 部署。
关联提交：`050a31a/abafbe6/15834c2/5cb869e/ac9da24/7286a69/c733c45/a0166b3` + 本批收官。

## 2026-10-11 V1 提纲 S0–S1 完成、S2–S6 部分（离线先行、在线阻塞）

事件：按 `研究提纲/V1研究提纲.md` 执行 T1–T7；T1 CI 红灯修复与运行台账、T2 离线重评完成；T3–T7 审计/设计/离线契约测试完成，在线补测阻塞。
原因：把“45/45”从叙述变为可追溯证据；成本控制要求先离线后在线，不重跑已有完整实验。
改动：`tests/test_phase_tracker.py` 去未使用导入；新增 `docs/research/v1/`（00/01/02/03/04/05/06/07/SUMMARY + assets）；新增 `scripts/build_run_register.py`；新增 `tests/test_success_at_k.py`、`test_terminal_contract.py`、`test_phase_prior_audit.py`、`test_seed_replicate.py`；`docs/scope/scope.md` 加 V1 状态。
验证：`PYTHONPATH=src python -m pytest -q` 173 passed（159+14 新）；`build_run_register.py` 生成 144 行台账；`ruff/mypy/uv` 本机缺装，CI 全绿待 push 后确认；在线实验 0 次新调用。
下一步：push 后取 CI 链接；登记预算后补 C011/React-C111、E1 在线、P-v1-context、新实例冒烟。
关联提交：待提交（分 T1/T2/T3–T4/T5–T7 四批独立 commit）。

这份记录只保存重要的工程事件，不替代 scope、spec 或 Git 历史。

记录范围包括：阶段开始或完成、架构决策确认或修改、重要验证结果、阻塞及解决、开发优先级调整。

每条记录使用以下结构：

```text
## 日期 事件名称

事件：发生了什么
原因：为什么做
改动：主要文件或范围
验证：运行了什么，结果如何
下一步：接下来做什么
关联提交：Git commit，若有
```

## 2026-10-11 三图难度对齐地图完成，实跑进行中

事件：灯塔扩建为 8 房 v2（工具箱搬进地窖、诱饵房/物、新授权码），新增第三世界
深海站 v1（8 房飞船形拓扑、新名称新授权码）；三张图最优公开路径 16–19 步。

原因：此前只有飞船 v3（8 房难图）和灯塔 v1（6 房简单图），用户要求 3 张难度
相当的地图做测试，并把简单的灯塔加难。

改动：`worlds/data/lighthouse_escape_v2.json` + `LighthouseV2Definition`/
`LighthouseV2Environment`（规则复用）、灯塔储物箱可见逻辑按容器房间泛化、
`worlds/abyss.py` + `data/abyss_escape_v1.json`（新 id 新谜题文本，同规则形状）、
`worlds/__init__.py` 注册两对 selector、`cli.py` 类型标注；
`tests/test_lighthouse_v2.py`、`tests/test_abyss.py`；`docs/specs/0009-*`。

验证：全套 `pytest` 143 passed（含 11 项新测试）；灯塔 v2 16 步、深海站 19 步
公开路径通关测试通过，旧码/诱饵/隐藏出口拒绝行为均覆盖；本机无 ruff/mypy/uv，
只跑了 pytest。Muse 自主组合（memory + history5 + recovery + phase，不限步）
三张图 seed 0 实跑已在后台启动。

下一步：等三局实跑结果，成功则扩到 5 seeds 并归档，失败则分析 trace；
commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 三图自主通关对照完成

事件：Muse 自主组合（memory + history5 + recovery + phase，不限步）在三张
8 房图上全部取得通关样本：深海站 seed 0（41 步）、灯塔 v2 seed 0（56 步）、
飞船 v3 seed 2（113 步）/ seed 1（180 步）。

原因：验证三图难度对齐后 AI 是否都能自主通关。

改动：仅实验运行，无代码改动；trace 在 `runs/muse-3maps-*`（本地生成物，
不进 Git）。

验证：4 个 success trace（0 非法输出）+ 2 个飞船 seed 0 `provider_error`
trace（73/76 步，0 非法输出）。关键发现：飞船 seed 1 重读授权码 20 次、
游荡 150+ 步才逃生，不限步数是通关前提；新图一次过证明能力迁移而非背路线；
灯塔 v2 终点模型 3 次对小艇用错 `read_terminal`（inspect 文本措辞可优化）。

下一步：三图各补到 5 seeds 归档；考虑把逃生舱 inspect 文本改得更动作导向；
commit/push 本轮全部改动。

关联提交：`6deee65`。

## 2026-10-11 三档难度建成与 9 局全覆盖 9/9 成功

事件：每张地图设简单/中等/困难三档（简单复用 6 房图，困难新建 4 张 10 房图），
Muse 自主组合 9 局全覆盖（3 图 × 3 难度 × seed 0，不限步）9/9 成功。

原因：用户要求每图三档难度（当前 8 房为中等）并做多 AI 并行探索。

改动：4 个新地图 JSON（飞船 v4、灯塔 v3、深海简单/困难）、4 个规则复用
环境子类、`create_environment` 新增 4 对 selector（spec 0010）、4 个新测试文件；
9 并行实跑（独立网关 session），trace 在 `runs/muse-9maps-*`（本地生成物）。

验证：全套 `pytest` 159 passed（含 16 项新测试）；9 配置 × 5 seeds = 45/45 成功，
均值步数飞船 70.4/140.8/165.4、灯塔 39.8/49.4/105.8、深海 26.8/42.2/83.6
（三图均值全部单调递增，中位数飞船 42/147/100）。6 次网关 `provider_error`
重跑均恢复；37 并行未触发系统性限流。

下一步：终点 `read_terminal` 误用与读码后迷路的 prompt/文本消融；
Planning 配相同公开上下文；commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 飞船扩建 v3 与不限步数 5/5

事件：飞船扩建为 8 房 v3（诱饵 + 新授权码），`step_limit=0` 支持不限步数；Muse 自主组合在 v3 以 5/5 成功逃生。

原因：检验更大地图与诱饵下的探索效率；此前成功路径 35–57 步，30 步预算成为人为瓶颈。

改动：`worlds/data/spaceship_escape_v2.json`、`SpaceshipV2Definition`/`SpaceshipV2Environment`（规则复用，仅换 definition）、储物箱可见逻辑按容器房间泛化、`config` 允许 `step_limit=0`、Runner 循环与 CLI 显示适配；`tests/test_spaceship_v2.py`。

验证：全套 `pytest` 132 passed；19 步公开路径通关测试通过；Muse 自主组合 v3 5 seeds 5/5（152/125/153/93/65 步），trace 归档于 `results/muse-shipv3-unlimited(-s24)/`。中途一次后台进程静默死亡（seed 2–4 未跑），改用 `-u` 无缓冲输出并凭进程与 trace 双重确认存活后重跑解决。

下一步：Planning 配相同公开上下文；ReflectionAgent；Streamlit；commit/push 本轮全部改动。

关联提交：待提交。

## 2026-10-11 雾岛灯塔世界与迁移 5/5

事件：新增第二个确定性世界（雾岛灯塔，spec 0007），Muse 自主组合在新地图 5/5 成功逃生；阶段上下文泛化为世界声明里程碑，Runner 不再内置飞船知识。

原因：检验通关能力是否迁移到未见地图，而非背下飞船路线；灯塔首轮无 phase 时 0/5（死法与飞船一致），证明阶段标签不可或缺，倒逼其泛化。

改动：`worlds/lighthouse.py` + `data/lighthouse_escape_v1.json`、`worlds/__init__.py` 注册、`arena/models.py` 新增 `PublicMilestone`、`arena/environment.py` 新增 `public_milestones` 默认空、`evaluation/runner.py` 的 tracker 改里程碑驱动（飞船旧文本逐字保留）、`agents/planning.py` 不变、`cli.py` 类型标注更新；`tests/test_lighthouse.py` + `tests/test_phase_tracker.py`。

验证：全套 `pytest` 126 passed；灯塔 15 步公开路径通关测试通过；Muse 自主组合灯塔 5 seeds 5/5（27/28/28/55/57 步），trace 与 failure_analysis 归档于 `results/muse-lighthouse-h5rp(-s14)/`。

下一步：压缩成功路径回 30 步预算；Planning 配相同公开上下文；ReflectionAgent；Streamlit。

关联提交：待提交。

## 2026-10-11 首个真正自主通关

事件：Muse Memory 在 `--autonomous` 下 5 seeds 获 3/5 成功逃生（seed 0/1/4，36/35/45 步），全部 Action 由模型自主返回并校验。

原因：Phase 1–3 逐个证伪预算/历史/卡死恢复都不充分；Phase 4 加入公开阶段上下文后模型首次把授权码与逃生舱绑定，此前 15 局全倒在这一步。

改动：仅实验变量组合（history5 + stuck_recovery + phase_context + 60 步），无代码改动；结果归档于 `results/muse-memory-s60-h5rp/`（benchmark JSON/CSV + failure_analysis + traces）。

验证：trace `outcome=success`、`agent=memory`、终局动作为模型输出的 `use(ALPHA-731 → escape_pod)`；provenance 中 hints/candidates/selection/guard 全关；全新 seeds 5–9 复验 2/5（seed 5/9，均 57 步），可重复性确认；消融矩阵：history-only 0/5、phase-only 0/5、history+phase 1/5、三者组合 3/5。

下一步：单变量消融已完成（history/phase/recovery 互补）。后续方向：把成功路径压缩回 30 步预算（当前需 35–57 步）、PlanningAgent 配相同公开上下文、ReflectionAgent，以及 Streamlit。

关联提交：待提交。

## 2026-10-10 Windows + Muse provider 切换与自主基线

事件：真实实验 provider 从 Mac 本地 Ollama（`qwen2.5:7b`）切换为 Windows 下 OpenCode Zen 网关的 `muse-spark-1.3-contributor`；完成 React/Memory 各 5 seeds 自主对照，并适配网关严格 schema。

原因：换到 Windows 后本地 Ollama 需重装且 Python 仅 3.11（项目要求 3.13 + uv）；用更强 API 模型能更快取得首个深阶段样本，验证瓶颈是 grounding 还是模型规模。

改动：`src/agent_arena/config.py` 新增 `openai_session_id`（网关强制 `x-opencode-session` 请求头）、`src/agent_arena/llm/openai.py` 注入该头并把验证输出上限调到 1024（推理模型空回复问题）、`src/agent_arena/llm/protocol.py` 新增无 `$ref` 的 `decision_response_schema_strict()` 和全 required 的 `planner_response_schema_strict()`、`src/agent_arena/agents/planning.py` 增加 `""`→`None` 归一化；`.env`（本机）与 `.env.example` 更新；`docs/current-issues.md` 登记 Muse 基线。

验证：`verify-model --provider openai` 通过；Muse React 0/5（控制室/走廊循环，非法输出 0）、Memory 0/5（工具 3/5、电源 2/5、读码 1/5）；`uv` 不可用故用本机 Python 3.11 + `PYTHONPATH=src` 跑 `pytest`：118 passed。附带修好两个测试问题：本机 `.env` 会污染 CLI 测试（改走真实 provider 并挂起网络），新增 `tests/conftest.py` 做 env/dotenv 双隔离；验证输出上限 32→1024（推理模型空回复），同步更新 `test_openai_provider.py` 断言。Planning 5 seeds 曾因 Planner schema 被网关 400 而 `provider_error`，修复后正在重跑。

下一步：Muse 三组对照已完成（React/Memory/Planning 均为 0/5，无可重复成功样本）。下一步是失败步骤人工抽样 + 单变量消融（优先：PlanMonitor 重规划阈值、Executor grounding 约束），再决定 PlanningAgent v2、ReflectionAgent 和 Streamlit 的顺序。

关联提交：待提交。

## 2026-09-10 Planning v1 Failure Analysis 与 Evaluation v2 完成

事件：完成 PlanningAgent v1 的失败分析基础设施、Evaluation v2 和真实 5 seeds 独立重跑；v1 Planner→Executor 核心保持冻结。

原因：原始 Planning v1 在 `qwen2.5:7b` 下 0/5 成功，单纯的 persistent-state no-progress 指标无法区分首次获得公开事实与重复已知结果，必须先提高测量有效性再决定是否改 Agent。

改动：新增 episode-local `PublicFact`/`EpisodeKnowledge`、State/Epistemic Progress、结构化 `SuccessCriterion` 及 legacy evaluator、规则 Failure taxonomy、Trace schema v2、`analyze-trace(s)` CLI 和 Evaluation v2 benchmark 字段；生成 JSON/CSV 失败分析报告，并同步 scope、架构、研究摘要和当前问题记录。未引入 ReflectionAgent、Streamlit、第二个 world 或 PlanningAgent v2。

验证：`uv run ruff check .`、`uv run mypy src`、`uv run pytest -q`（116 passed）、`uv lock --check` 和 `git diff --check` 全部通过。Evaluation v2 固定 `qwen2.5:7b`、seed 0–4、30 步、autonomous 重跑为 0/5 成功；平均 Planner call ratio 85.3%、State Progress 0、Epistemic Progress 1、无进展动作 29、同子目标重复 Action 26。每局自动识别 3 次 rejected action 和 2 次 repeated failure。

下一步：扩展已完成的人工抽样到每局完整的 replan 后首个 Action，区分 vague/wrong subgoal、wrong action、forgotten fact 与 ineffective replan；随后在保持 v1、模型、world 和 prompt 不变的条件下进行单变量 grounding 或 exploration/recovery 验证，再决定是否创建 PlanningAgent v2 spec。

关联提交：`6504db8`。

## 2026-09-10 文档同步与 PlanningAgent 真实五个 seed 对照

事件：修正文档中已过期的实验契约描述，并完成 PlanningAgent v1 的本地真实模型固定 5 seeds 对照。
原因：`a308dd5` 和 `07f7457` 已关闭 world selector、公开循环状态、benchmark 指标和 planner feedback hash 等工程缺口，但持续文档仍将它们列为未完成；PlanningAgent 的真实研究验收也需要实际结果。
改动：更新 `README.md`、`研究总纲.md`、`docs/scope/scope.md`、`docs/current-issues.md`、`docs/autonomous-escape-experiment-plan.md`、`docs/model-passage-options.md` 和 Planning spec 验证记录；Ollama loopback 请求绕过系统代理，并补充 provider 回归适配。
验证：标准 `uv run agent-arena verify-model --provider ollama` 通过；`qwen2.5:7b`、`spaceship-escape-v2-zh`、temperature 0、30 步、seed 0 至 4、`--autonomous` 的 Planning benchmark 为 0/5 成功，平均重复动作比例 93.3%、连续 `look` 26 次、唯一公开状态 1 个、Planner 调用 28 次、子目标完成率 0%、总 token 141,445；96 项 pytest、Ruff、mypy 通过。
下一步：公开并分析 React、Memory、Planning 的成功/失败 trace，优先研究高层子目标到有效移动/工具动作的桥接；在取得可重复成功前，Reflection 和 Streamlit 继续后置。
关联提交：`a7aedf5`。

## 2026-09-09 PlanningAgent v1 工程闭环完成

事件：完成 PlanningAgent v1 的工程实现，形成独立的 Planner、结构化 PlanState、PlanMonitor、Executor integration、计划生命周期 Trace 和 Benchmark v3 指标。
原因：ReactAgent、MemoryAgent 和公开规则辅助已经显示长程任务缺少稳定子目标表示，需要在不读取 WorldState、不绕过 Action schema 的前提下验证显式 Planning 变量。
改动：新增 `src/agent_arena/planning/`、`PlanningAgent`、`planning_v1`/`planning_executor_v1` prompts；扩展 DecisionProvider 的 Planner contract；接入 Runner、Trace、Benchmark、CLI `--agent planning`；新增 0006 spec 和 Planning 专项测试。
验证：96 项 pytest、Ruff、mypy 全部通过；Fake provider seed 0 完成 20 个 Executor Action、4 个子目标；Fake 5 seeds benchmark 全部成功并写出计划成本和生命周期指标。随后探测本机 Ollama，`verify-model` 未通过，因此没有伪造真实模型结果。
下一步：使用真实本地模型在固定 5 seeds 下运行 React、Memory、Planning 和 `planner_assisted` 对照。Fake 成功不代表 Planning 自主能力，Reflection 和 Streamlit 继续后置。
关联提交：`07f7457`。

## 2026-08-19 研究状态文档同步

事件：同步日常研究摘要、scope 和当前问题记录，使其反映 Release 2 已完成以及纯模型自主通关基线已完成但未通过的事实。

原因：`研究总纲.md` 仍描述项目尚未创建源代码，scope 和问题记录的下一步也仍写为重新建立已完成的真实 Ollama 对照，容易使新对话从过期阶段开始工作。

改动：将当前阶段改为已完成 Foundation 至 Release 2；记录 `qwen2.5:7b` 下 ReactAgent 与 MemoryAgent 各 5 局、均未成功的通用 prompt 基线；将下一步收敛为不含谜题答案的通用运行时上下文或受控短期历史实验，并保留 Streamlit、PlanningAgent 和 ReflectionAgent 的后置条件。

验证：`uv run ruff check .`、`uv run mypy src` 和 `uv run pytest` 通过；pytest 共 49 项通过。

下一步：为通用运行时上下文或受控短期历史建立独立技术设计和公平实验对照，不能将结果并入纯模型基线。

关联提交：待提交。

## 2026-08-19 Hiyo 自主逃生复验与候选选择实验

事件：使用 Hiyo `gpt-5.6-terra` 复验纯 React/Memory，并实现公开候选选择 Agent 作为新的受限辅助变量。

原因：此前 Ollama 实验显示上下文提示和里程碑不能改变循环，需要确认更强模型是否能自主完成阶段转换，并分离输出协议、状态转移和动作语义三个失败层。

改动：新增 `candidate_select` Agent、候选选择 JSON contract、公开候选枚举与重复/拒绝动作排除、trace provenance 标记和 Fake 回归；补充 A7 实验记录。

验证：Hiyo React A0 seed 0 在 3 个有效动作后因 5 次 `missing_argument` 终止；Hiyo planner-assisted seed 0 19 步成功；候选选择 seed 0 无阶段上下文恢复主电源但 30 步未通关，加入公开阶段上下文后读取授权码但将授权码用于错误目标，仍 30 步未通关。代码验证通过 68 项 pytest、Ruff、mypy 和 `git diff --check`。

结论：更强模型改善了局部探索和协议稳定性，但没有形成可执行的长程状态转移。自主失败首要原因不是模型规模，而是缺少阶段目标到动作语义的桥接；`planner_assisted` 成功只能作为辅助上界。

下一步：先独立修复/测量 Hiyo 的结构化输出，再实验带目标类型约束的公开语义 guard，并固定 5 个 seed 运行 A7 组合变量。

关联提交：待提交。

## 2026-08-19 Hiyo Responses provider 与自主通关复验

事件：接入 Hiyo OpenAI-compatible relay 的原生 Responses API，并复验 `gpt-5.6-terra` 的辅助和纯自主逃生表现。

原因：CCSwitch 配置声明该中转站使用 `wire_api = responses`；此前 Chat Completions 兼容调用虽然可连接，但纯 Agent 在错误工具反馈后频繁输出非法 Action，不能排除协议适配差异。

改动：新增显式 `openai` provider，使用 `/v1/responses`、结构化 JSON 输出和 `store=false`；更新本机 `.env`、远程验证脚本及配置文档。保留 Fake 为仓库默认，避免无密钥 CI 误发真实请求。

验证：`gpt-5.6-terra` 模型验证通过；`planner_assisted` seed 0/1/2 共 3 局均在 19 步成功逃生、0 次非法输出；ReactAgent 和 MemoryAgent 的通用 `--autonomous` seed 0 均在第 2 步后达到 `invalid_action_limit`。Ruff、mypy 和 52 项 pytest 通过。

结论：该模型适合当前公开规划辅助演示，但尚不能作为纯自主通关模型。后续 benchmark 必须分开记录辅助与自主结果。

关联提交：待提交。

## 2026-08-19 自主失败变量拆解与环境恢复修复

事件：执行环境恢复、推理强度、公开动作候选和输出格式分类四项受控实验，定位自主逃生失败原因。

原因：此前自主基线在第一次错误工具后因终端永久从 Observation 消失而进入矛盾状态，且 trace 无法区分非法 Action 的具体结构原因。

改动：错误终端动作不再修改可见性；新增 `missing_argument` 等脱敏非法输出类别、`reasoning_effort`、`guarded` 公开动作候选开关和 Responses JSON Schema 可选模式。由于 Hiyo relay 对 JSON Schema 返回 400，默认保留 `json_object`，格式修正请求会收到安全的缺参类别。

验证：环境修复后纯自主 React 达到 30 步但仍循环；`reasoning=high` 达到 10 步后仍循环；`guarded` 能到储藏室并检查密封箱但在拾取前因缺参终止。Ruff、mypy 和 57 项 pytest 通过。

结论：当前主因是模型在公开拒绝反馈后的任务分解和状态更新不足，结构化输出约束不足是次要但可测因素；增加推理预算没有显示改善。下一步应优先做可公开验证的阶段/候选动作实验，并保持与纯自主结果分开。

关联提交：待提交。

## 2026-08-19 A1/A2 公开上下文实验

事件：将自主逃生失败分析固化为可复现实验设计，并实现有限公开历史（A1）和结构化里程碑记忆（A2）。

原因：需要区分上下文不足、状态表示不足与规划能力不足，避免继续堆叠 Spaceship 专用 prompt。

改动：新增实验记录 `docs/autonomous-escape-experiment-plan.md`；DecisionRequest 支持最近公开轨迹；Runner 支持窗口化历史并将开关写入 trace provenance；MemoryState 增加公开可推导的物品发现、面板、电源和授权码里程碑；CLI 增加 `--recent-history` 与 `--structured-milestones`。

验证：60 项 pytest、Ruff、mypy 全部通过。Ollama `qwen2.5:7b` 固定 seed 0 至 4、30 步实验中，A1 为 0/5，平均 9 次环境拒绝；A2 为 0/5，平均 5 次环境拒绝。A1 能到达反应堆但未稳定拾取工具，A2 在储藏室重复检查。

结论：有限历史改善了早期导航但不足以完成任务；单纯增加结构化字段没有改善行动选择。下一步优先实现公开动作约束和卡死恢复，并继续独立记录实验变量。

关联提交：待提交。

## 2026-08-19 A3/A4 公开约束与卡死恢复实验

事件：实现并复验公开语义动作校验（A3）和独立卡死恢复提醒（A4）。

原因：A1/A2 未改变成功率，需要区分动作参数非法与参数合法但无进展两类失败。

改动：Runner 新增 `--semantic-guard` 和 `--stuck-recovery`，trace provenance 记录两项开关；guard 只检查公开出口、可见目标和背包约束，不执行被拒绝 Action；新增独立决策预算防止 guard 循环无限请求。

验证：63 项 pytest、Ruff、mypy 通过。A3 seed 0 探针 30 步全部为环境拒绝，0 次语义 guard 拒绝；A4 seed 0 至 4 为 0/5，全部进入储藏室后重复检查密封箱。

结论：A3 不能处理公开参数合法但阶段无进展的循环；A4 能打破控制室初始循环并改善探索，但未完成工具拾取。下一步需要阶段状态与候选动作集合，或进入真正 PlanningAgent 实验。

关联提交：待提交。

## 2026-08-19 A5 公开具体候选动作实验

事件：新增 A5 `--candidate-actions`，将当前 Observation 可构造的具体 Action 参数列给模型。

原因：A3 只能拒绝公开非法动作，需要独立测量具体候选是否能减少缺参和不可见目标输出。

改动：Runner 根据公开出口、可见对象、背包和公开终端授权码生成候选列表；不提供路线、阶段或隐藏前置条件；trace provenance 增加候选开关。

验证：65 项 pytest、Ruff、mypy 通过。Ollama `qwen2.5:7b` seed 0/1 探针均 30 步到达 `step_limit`，0 次非法输出，仍在控制终端循环；因单局耗时较长，剩余 seed 未扩展。

结论：具体候选动作不能改变参数合法但阶段无进展的循环。下一步应进入公开阶段状态/候选集合实验或 PlanningAgent，而不是继续扩大动作格式提示。

关联提交：待提交。

## 2026-08-19 调整自主通关优先级并暂缓 14B

事件：确认 ReactAgent 和 MemoryAgent 的代码实现、Fake provider 路线和公平对照测试已经完成，但真实 Ollama 的纯模型自主通关仍未完成。用户使用 Mac M5 Air，`qwen2.5:14b` 暂不继续测试。

原因：`planner_assisted` 的成功依赖确定性公开阶段和下一动作建议，不能证明模型在没有谜题攻略式提示时具备自主规划能力。继续堆 Spaceship 专用提示词会把实验变成人工攻略执行，削弱研究结论。

改动：将“不依赖谜题攻略式提示的纯 ReactAgent 与 MemoryAgent 自主通关验收”提升为当前首要未完成任务，要求使用通用 prompt、相同 seed 和预算，并独立保存成功与失败 trace。将 14B 标记为受 M5 Air 资源限制而暂缓，不纳入当前实验矩阵。

验证：复核 `docs/scope/scope.md`、`docs/current-issues.md`、`docs/model-passage-options.md`、ReactAgent 与 MemoryAgent spec 及历史记录，确认两者已完成实现级验证，但真实自主通关验收没有完成。

下一步：先完成通用 prompt 下的 ReactAgent 与 MemoryAgent 真实 Ollama 对照，再根据 trace 决定是否需要运行时循环检测或其他独立实验变量；之后才进入 Streamlit。

关联提交：待提交。

## 2026-08-19 通用 Prompt 纯模型自主基线未通过

事件：完成 ReactAgent 与 MemoryAgent 的纯模型自主对照，各运行 5 局真实 Ollama 实验。

原因：验证模型能否不依赖 Spaceship 专用攻略提示、规划辅助或运行时循环提醒，仅根据公开 Observation 和结构化 Memory 完成任务。

改动：新增 `react_v12_autonomous` 通用 prompt。ReactAgent 和 MemoryAgent 默认使用该 prompt。新增 CLI `--autonomous`，关闭 Runner 的循环提醒，并在 trace provenance 中记录 `runtime_feedback_enabled=false`。`planner_assisted` 继续使用独立的 `react_v11` 和辅助路径。

验证：`qwen2.5:7b`、seed 0 至 4、每局 30 步。ReactAgent 0/5 成功，平均 30 步，每局 2 次环境拒绝，非法输出 0。MemoryAgent 0/5 成功，平均 30 步，每局 15 次环境拒绝，非法输出 0。Ruff、mypy 和 49 项 pytest 全部通过。

结论：纯模型自主通关仍未完成，但失败基线已经真实且可重复。ReactAgent 在初始观察后连续重复 `look`，MemoryAgent 在控制室和走廊之间反复读取不可见终端。问题集中在公开 Observation 的行动选择和失败后的状态更新，不是连接或 JSON 格式问题。

下一步：先设计不含谜题答案的通用运行时上下文或受控短期历史实验，并将其与当前基线独立比较；不得直接恢复 Spaceship 专用路线提示。

关联提交：待提交。

## 2026-08-17 架构决策确认

事件：项目采用 Python 3.13、uv、本地分层单体、CLI 和本地 JSON 文件作为第一版基础架构。

原因：先建立一个可重复的本地 Agent 研究闭环，避免过早引入服务、数据库和复杂编排。

改动：接受 `docs/specs/0001-project-architecture/`，明确 Environment、Agent、LLM、Evaluation 和 UI 的边界。

验证：架构检查清单已建立，真实模型调用被明确为手动验证，不进入默认 CI。

下一步：完成 Foundation scaffold。

关联提交：`c630729`

## 2026-08-17 Foundation scaffold 完成

事件：项目已经可以安装、运行 CLI、生成 Fake episode，并执行自动质量检查。

原因：为确定性的 Spaceship Escape 环境提供稳定的代码和测试基础。

改动：新增 `pyproject.toml`、`uv.lock`、`src/agent_arena`、RuntimeSettings、Fake provider、CLI、测试和 GitHub Actions。

验证：`uv lock --check`、Ruff、mypy 和 10 项 pytest 全部通过。`uv run agent-arena run` 成功生成 JSON episode，百炼模型验证也成功返回确认文本。

下一步：运行 `/architect Spaceship Escape 环境`，定义房间、工具、物品、非法动作和胜利条件。

关联提交：`fe42515`

## 记录规则建立

事件：增加工程事件记录文件和对应 workflow 规则。

原因：scope 只保留当前状态，spec 只保留技术决策，Git 只保留代码差异，三者无法单独表达重要事件的原因、验证和下一步。

改动：新增本文件，并在根 `AGENTS.md` 中定义记录范围、模板和提交前流程。

验证：`git diff --check` 已通过，工作区只包含预期的 `AGENTS.md` 和本文件改动。

下一步：后续每个重要阶段完成时追加一条简短记录。

## 2026-08-17 Spaceship Escape 环境设计确认

事件：确认第一个确定性世界的地图、公开工具、信息边界、谜题状态和逃生条件。

原因：环境规则必须先稳定，后续 Agent Loop、trace 和 benchmark 才有可信对照。

改动：新增 `docs/specs/0002-spaceship-escape/`，并将 scope 中的 Spaceship Escape 环境改为设计完成和实现中。

验证：完成设计访谈与独立只读交叉检查。九项契约空白已补齐，`git diff --check` 通过。

下一步：运行 `/develop Spaceship Escape 环境`，实现配置、Environment 和规则测试。

关联提交：待提交。

## 2026-08-18 本地模型规划辅助通关验证

事件：在保留纯模型失败基线的前提下，完成 `qwen2.5:7b` 的 `planner_assisted` 公开规划辅助通关。

原因：纯 ReactAgent 和 MemoryAgent 在收集工具、恢复电源后会重复公开动作；同时旧 prompt 错误要求所有 `use.item` 必须在背包，和控制终端返回授权码后使用授权码的环境规则冲突。用户目标是让 agent 实际完成逃生，因此需要验证公开辅助是否能稳定解决循环，同时不能把辅助结果伪装成纯模型结果。

改动：新增 `react_v11` prompt，区分维修物品与公开读取的授权码；新增独立的 `PlannerAssistedAgent` 和 CLI `--agent planner_assisted`。规划器只使用公开 Observation、ToolResult 和结构化 Memory 生成阶段/下一动作建议，模型仍选择并返回每个 Action；授权码仅在收到公开 `CODE_READ` 结果后提取。储物室规划优先拾取已出现物品，阶段建议放入最新公开请求，并在 trace 中用独立 agent/prompt 版本标记。

验证：Ruff、mypy 和 48 项 pytest 通过。`qwen2.5:7b`、`planner_assisted_v2`、seed 0/1/2 的 Ollama benchmark 为 3/3 成功，平均 19 步、0 次非法输出、0 次环境拒绝；结果文件为 `/tmp/agent-arena-planner-v11-benchmark/benchmark_20260818T080152Z_planner_assisted_3-seeds_3-episodes_defcc08a.json`。纯模型 MemoryAgent 的失败结果仍保持为独立基线。

下一步：规划辅助结果只用于稳定通关和演示，继续与纯 React/Memory 对照分开统计；若研究需要纯模型成功率，应单独研究更强模型或公开循环保护，不得把规划建议视为模型自主规划。

关联提交：待提交。

## 2026-08-18 用户本机复验与通关记录补充

事件：用户使用 `OLLAMA_MODEL=qwen2.5:7b` 和 `--agent planner_assisted` 在本机连续运行两次，均以 19 步成功逃生。

原因：确认前一轮实验不是临时环境或 Fake provider 结果，并为后续复现明确区分真实模型执行与规划器辅助。

改动：将完整问题、排查步骤、最终路线、复现命令、已完成能力和待办写入 `docs/model-passage-options.md`。确认两份 trace 的模型为 `qwen2.5:7b`、Agent 为 `planner_assisted_v2`，每个执行 Action 都经过模型响应和环境校验；没有程序代替模型执行动作。

验证：两份用户 trace 均为 `success`、19 个 `action_validated`、0 次非法输出、0 次环境拒绝。复核发现 `PublicLoopDetector` 仍可能因状态键缺少 `available_exits` 和 `last_action_result` 而误报合法回程，该问题列入后续任务，不影响本次通关结果。

下一步：先修复循环检测状态键并增加回归测试，再独立实现 `guarded` 模式；继续将纯模型、规则保护和规划辅助结果分开统计。

关联提交：待提交。

## 2026-08-18 本地模型策略验收

事件：完成 Ollama 原生 `/api/chat`、关闭思考、JSON Schema、逐步终端回显和本地模型对照验收。

原因：用户明确只使用本地模型，并希望关闭思考以降低每步延迟；需要区分接口故障与模型策略能力不足。

改动：将 Ollama 默认模型更新为 `qwen2.5:7b`；新增原生请求回归测试；调整 Memory 消息顺序；提示词升级到 `react_v8`，明确公开环境中的关键前置条件和重复动作限制。

验证：`qwen3:8b` 与 `qwen2.5:7b` 的 `verify-model --provider ollama` 均通过，40 项 pytest、Ruff、mypy 通过。`qwen3:8b` 和 `qwen2.5:7b` 均能输出合法动作，但在关闭思考时单局 30 步都未完成逃生；7B 在 `react_v8` 下能走到存储室并发现物品，随后仍会重复移动。当时 14B 下载因长时间网络停滞中止；后续已完成安装，结果见 2026-08-18 的复验记录。

下一步：当前验收结论为本地链路和可观测性通过，自动逃生策略未通过；后续应优先改进 Agent Loop 的重复动作约束或采用已验证的更强本地模型，而不是把失败局写成成功。

关联提交：待提交。

## 2026-08-18 轻量化链路与 14B 复验

事件：完成紧凑提示词、公开循环检测、运行时提醒、MemoryAgent 请求接入和 Spaceship Escape 无效目标收敛；随后复验已安装的 `qwen2.5:14b`。

原因：用户希望降低 16G Mac 的运行压力，同时确认 14B 是否能解决 7B 的长程循环问题。

改动：新增 `react_v9`，默认 Ollama 输出上限调整为 256 token；`DecisionRequest`、Runner、两种 provider 和 trace 增加公开运行时提醒；Environment 在终端误用、目标完成和授权码前置条件不满足时减少无效观察目标；新增循环检测及回归测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 45 项 pytest 全部通过；`qwen2.5:14b` 的 `verify-model` 通过。固定 seed=0、MemoryAgent、30 步真实运行执行 30 步、0 次非法模型输出，但在恢复主电源后重复读取诊断终端，结果为 `step_limit`，未完成逃生。

下一步：将当前结果作为诚实的失败基线；若产品必须保证通关，应另行设计确定性任务阶段/Action Guard，不能继续只堆提示词规则。默认开发模型保持 `qwen2.5:7b`，14B 仅作对照。

关联提交：待提交。

## 2026-08-17 Spaceship Escape 环境完成

事件：完成第一个可手动通关的确定性 Spaceship Escape 环境。

原因：为后续 Agent Loop、Episode Trace 和 benchmark 建立可重复的环境基线。

改动：新增严格 Action 与 Observation 契约、六房间 JSON 定义、环境状态转换和规则测试。

验证：`uv run ruff check .`、`uv run mypy src` 和 25 项 pytest 通过，公开工具路径在 20 步内完成逃生。

下一步：设计 ReactAgent 与 Agent Loop。

关联提交：待提交。

## 2026-08-17 Release 1 Agent Loop 完成

事件：Release 1 的 ReactAgent、受限 Episode Runner、JSON Episode Trace 和 CLI 运行闭环完成。

原因：在进入 Memory 与 benchmark 前，需要一个可重复、可复盘且不会将不可信模型原文写入 trace 的基线 Agent。

改动：新增 `0003-react-agent-loop` spec、`ReactAgent`、百炼结构化决策适配、20 步 Fake 通关路径、Runner 状态机、脱敏原子 trace 写入和端到端测试；CLI `run` 不再生成 scaffold episode。

验证：`uv run ruff check .`、`uv run mypy src` 和 30 项 pytest 通过；`uv run agent-arena run --output-dir <temporary-directory>` 生成 `success` trace，含 20 个已执行动作和 0 个非法输出。

下一步：设计规则驱动的 MemoryAgent，并在固定世界、模型、提示词与步数预算下建立 Release 2 对照。

关联提交：待提交。

## 2026-08-17 百炼 Action 格式修复

事件：真实百炼运行曾连续输出带 `args` 包装的动作，现已通过 `react_v3` prompt 改为直接在 `action` 内提供工具参数。

原因：严格 Action schema 正确拒绝了非约定格式，但旧 prompt 只给出无参数工具示例，模型稳定选择了通用包装格式。

改动：升级 prompt 版本并列出六种工具的完整扁平 JSON 示例，明确禁止 `args`、`arguments` 和 `parameters` 包装字段；增加 prompt 约束回归测试。

验证：Ruff、mypy 和 31 项 pytest 通过。真实百炼运行从 3 次非法输出、0 个执行动作变为 0 次非法输出、30 个有效动作；该局因反复探索无电控制终端达到步数上限，说明格式问题已修复，而基线策略仍是后续 MemoryAgent 的研究对象。

下一步：设计 MemoryAgent，用结构化记忆降低重复观察和重复失败动作。

关联提交：待提交。

## 2026-08-17 Release 2 MemoryAgent 完成

事件：完成规则驱动的结构化 MemoryAgent，并建立与 ReactAgent 的可复现单局对照。

原因：在 benchmark 前先固定唯一实验变量，避免完整历史、隐藏状态或第二次模型调用影响结果。

改动：增加公开记忆 reducer、脱敏、失败动作与问题映射、Agent 生命周期、结构化 provider 请求与响应、token 用量、trace 实验来源和 CLI `--agent` 选择。

验证：Ruff、mypy 和 33 项 pytest 全部通过。ReactAgent 与 MemoryAgent 的 Fake CLI 均在 20 步成功逃生，Memory trace 包含版本化来源字段。

下一步：实现 benchmark 命令，使用持久化 trace 输出 ReactAgent 和 MemoryAgent 的 JSON、CSV 指标对照。

关联提交：待提交。

## 2026-08-17 Release 2 Benchmark 与指标完成

事件：完成多局 benchmark 命令，以及基于持久化 trace 的 JSON、CSV 指标输出。

原因：MemoryAgent 需要与 ReactAgent 在相同世界、seed 和预算下进行可复现对照，才能解释后续实验结果。

改动：新增 benchmark 行和聚合计算、原子 JSON/CSV 写入、trace 重读校验；CLI 支持单 Agent 或默认双 Agent 对照。

验证：Ruff、mypy 和 36 项 pytest 通过。`agent-arena benchmark --episodes 1` 使用 Fake provider 生成两份 trace，CSV 按 React、Memory 顺序输出，JSON 聚合成功率为 1.0。

下一步：在 benchmark 结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 Benchmark 反馈与文件命名改进

事件：为 episode trace 和 benchmark 结果加入可读文件名，并让 benchmark 实时显示运行进度。

原因：原始 UUID 文件名难以按实验辨认；真实百炼 benchmark 默认运行 React 与 Memory 两组，原 CLI 在所有局完成前没有任何输出，容易被误判为卡住。

改动：输出名称包含 UTC 时间、Agent、seed 或局数和短 ID；真实模型会在每次决策请求前输出当前步数，benchmark 还会输出开始、每局开始和每局结束状态。

验证：Fake provider 端到端运行确认新名称和进度输出。`uv run ruff check .`、`uv run mypy src` 和 37 项 pytest 全部通过。

下一步：以小局数真实 benchmark 观察新进度信息和实际响应时长，再在结果稳定后设计 Streamlit 实验界面。

关联提交：待提交。

## 2026-08-17 本地 Ollama 与逐步复盘支持

事件：将真实实验工作流扩展为本地 Ollama `qwen3:4b`，并在终端逐步显示简短理由、动作、环境结果和对应 trace 路径。

原因：百炼的 3 seed React、Memory 对照均达到步数上限。Trace 显示 React 重复读取无电终端，Memory 虽减少拒绝动作但在维修室和反应堆室之间循环；原 benchmark 终端未展示已记录的步骤，难以直接诊断。

改动：新增 `ollama` provider、无密钥本地验证、独立 Ollama 配置、`react_v4` 探索规则和逐步终端回显。完整步骤继续存入 `runs/`，`results/` 保持指标职责。

验证：Ollama 服务可访问但模型列表为空，因此真实本地模型验证明确失败，未伪造通过结果。Ruff、mypy 和 39 项 pytest 全部通过；Fake benchmark 验证逐步输出和 trace 路径。

下一步：在本机下载 `qwen3:4b` 后运行 `verify-model --provider ollama`，再以单局和同 seed 对照检验 `react_v4` 的真实模型表现。

关联提交：待提交。

## 2026-08-19 A6 公开阶段状态实验

事件：新增 `--phase-context`，将公开背包和公开 ToolResult 压缩为阶段与未完成条件，不提供路径或下一动作。

原因：A5 证明具体参数候选不能改变策略循环，需要测量阶段摘要是否能改善长程任务分解。

改动：新增公开 `PublicPhaseTracker`，只记录面板打开、主电源恢复、授权码读取等公开成功结果；trace provenance 记录阶段上下文开关。

验证：66 项 pytest、Ruff、mypy 通过。Ollama `qwen2.5:7b` seed 0 探针 30 步均在控制室终端循环，未发生阶段推进。

结论：阶段标签不提供从阶段到动作的桥接，不能解决自主逃生。后续停止继续堆自然语言提示变量，转向真正 PlanningAgent 或明确标记的辅助候选策略。

关联提交：待提交。

## 2026-09-05 当前问题盘点与实验契约登记

事件：完成当前研究、配置、trace 和 benchmark 契约的只读盘点，并将未完成项写回持续文档。

原因：纯模型自主通关仍未验收，需明确区分已确认的实现缺口、尚未验证的行为和辅助模式的研究边界，避免后续实验误读配置或混合结论。

改动：更新 `docs/current-issues.md`、`docs/scope/scope.md` 和 `docs/autonomous-escape-experiment-plan.md`，登记固定 world 加载、循环检测回归、缺失指标、planner feedback 可复盘、生命周期测试和远程 provider 凭据阻塞。

验证：只读确认传入任意 `world`/`world_version` 时环境仍加载 `spaceship_escape_v1 / v2-zh`；`uv run pytest` 为 68 passed，Ruff 和 mypy 通过。

下一步：先设计并实现 world 加载契约、循环检测修复及指标补齐，再验证 guarded 和 planner 生命周期；纯模型与辅助模式继续独立统计。

关联提交：`29cb000`。

## 2026-10-14 V3 世界设计提纲交付

事件：完成研究提纲中的十家族 30 个 Scenario 关卡，实现、逐关公开 Oracle、规则边界、设计审计和 Legacy/Trace 兼容收口。

原因：将 V3 从设计输入推进为可运行且可复播的离线工程交付，同时保留 V2 seeded 定义、provider ledger 和 holdout 的冻结边界。

改动：新增 Scenario Action/Observation、显式 selector、十家族规则、V3 prompt/Runner/Trace/CLI/UI 适配、30 关设计卡、机制交叉核对、六维评分与 hash 验收报告。修正 PO-H 六相天气/共享燃料/单人护送，及 SU-H 由 B 车入线触发的维护锁。旧 Action 运行时判断与 subclass prompt 版本标识保留 Legacy 兼容。

验证：全量 `pytest -q` 为 466 passed；`ruff check .` 通过；`mypy src` 对 64 个源文件无问题；项目改动通过 staged whitespace 检查。V3 原始提纲保留原样，其 Markdown 硬换行行尾空格未纳入改动检查。公开 Oracle 在 seed 31 下分两次独立执行均为 30/30 成功、拒绝动作 0，逐关 Replay SHA 与报告相同。当前 shell 无 `uv`，未执行 `uv lock --check`；依赖文件未修改。没有真实 Provider 请求或 GPU 运行。

下一步：交付提交推送后，任何 V3 模型行为比较另行设计并登记，不从离线 Oracle 推断模型通关能力。

关联提交：`63a06f1`。

## 2026-10-16 V5 MiMo smoke 系统性 schema 失败

事件：在冻结离线门禁通过后启动唯一登记的 `mimo-v2.6-flash` Stage B smoke；按研究提纲的接口失败停止条件终止运行，没有启动 Stage C。

原因：MAP-08/no_hypothesis_table/seed 0 的 70 次已结算决策全部被运行时记录为 `INVALID_ACTION_SCHEMA`，未产生合法 Action。第 71 次请求已预留但进程中断时没有 usage 回执；V5 ledger 审计因此写入 `UNKNOWN_SPEND_AFTER_INTERRUPTED_REQUEST` 并 fail-closed。实际 schema 失败类别无法从现有 trace 进一步细分，因为原始模型文本不落盘。

证据与费用：run `d3f3d7be-c928-4433-b6aa-9a269d97f593`；冻结 commit `e440cc1b599a5de4a57650f418d78b03c4746399`，gate hash `664e2d1210f77c30a5fe486ac8d80808f4c0f71a10a2b35311b7f866dabe6813`。71 次 reservation、70 次 settlement、1 次 unknown；已报告 usage 为 input 38,976、output 2,936、cached input 34,176 tokens（部分 settled 请求未提供缓存字段）。70 次已报告 usage 计算费用 ¥0.01135552；总 reservation ¥0.72704，含未知的第 71 次完整 reservation ¥0.01024；单币种上限 ¥37.50。episode 完成 0/39，smoke gate 未通过，Stage C 0/33。

验证：冻结脚本在运行 commit 上全绿：scoped Ruff、mypy、全量 pytest、V4 Oracle replay、独立 solver、Fake API dry-run、git diff check 均通过；`uv lock --check` 因宿主无 `uv` 未运行。关闭后加固通过全量 pytest 513 passed、V5 定向测试 26 passed、Ruff 和 mypy；没有重连 MiMo，故真实运行结果不属于离线验证结论。

下一步：继续只做离线协议审计。MiMo JSON mode 要求显式完整定义字段层级和类型；付费运行所用 prompt 顶层示意包含省略号，现已补全；连续三次 schema 拒绝现在会 fail-closed。精确根因与修复效果仍未由 MiMo 复测确认。原 V5 ledger 已关闭，不恢复或新建 successor ledger；本轮数据不构成模型能力结论。

关联提交：运行实现 `e440cc1`；停止记录与离线加固 `474fbe8`。

## 2026-10-16 V5 pilot 封账后用户授权诊断

事件：用户明确批准后，对 MAP-08/no_hypothesis_table/seed 0 执行一次 MiMo 诊断请求；正式 pilot ledger 保持封闭，不恢复或新建账本，该请求不计入 39 局矩阵。

原因：用户要求重新调用，以区分 MAP-08 地图转移缺陷与 provider/prompt/Action 协议问题。遵照授权仅发出一次请求，未恢复正式实验。

发现与证据：顶层 JSON 键符合约定，但 `action` 缺少必需的 `tool` 字段并多出不允许的 `verb`，未进入环境执行。Usage 为 510 input、48 output、0 cached tokens；按 MiMo 官方费率计算 ¥0.000606。未保存原始响应；去标识化摘要位于 ignored `runs/v5/diagnostics/authorized_map08_probe_20261016T004942Z.json`。原 pilot 的 70 个失败响应没有原文留存，因此不能据此推断它们全部同因。该探针未显示 MAP-08 状态转移缺陷，当前证据指向 prompt 与 Action 字段契约边界，但结论仅适用于此次请求。

改动：V5 prompt 明确要求 Action 使用 `tool`、禁止 `verb`，并压缩 MAP-30 重复任务描述以满足完整历史输入上限；增加六图 prompt 契约回归测试。同步更新 V5 pilot 和离线验收报告，注明新 prompt 未再次用 MiMo 验证，正式 pilot 仍为 0/39 完成、Stage C 未启动。

验证：提交前复核全量 `pytest -q` 为 514 passed；scoped Ruff 与 `git diff --check` 通过。提示词修正后此前另有 29 项 V5 pilot controls、MAP-08 测试和六图 Oracle replay 验证通过。没有再次调用 MiMo。既有 V5 ledger 继续封闭。

下一步：提交并推送本次五个相关文件。任何正式矩阵续跑仍须满足新的冻结、登记、预算和独立审查门禁；本次单次诊断及离线回归不构成续跑授权。

关联提交：本次提交（提示词、回归测试与记录同一提交）。

## 2026-10-17 V7 30 图分层能力评测离线层

事件：按 `研究提纲/V7：30张地图分层能力评测与指标体系.md` 交付逐图能力构念、专属指标、确定性计分器与评测协议；6 张已有运行时的图落地 extractor，其余 24 图交付设计卡与运行时准入表。

原因：V2–V6 的结果指标仍以通关率和步数为主，无法区分“移动预算内最优”“安全约束”“失败归因”和“成本”。V7 把这些量拆成逐图预登记、可由 trace 确定性复算的指标，同时保持历史资产只读。

改动：新增只读层 `src/agent_arena/v7/metrics/`（`schema`、`common`、`references`、`registry`、六图独立 extractor），不修改 V4/V5/V6 环境、Action 契约、trace 写出器、prompt 或账本。注册 154 条 `MetricSpec`：6 图 44 条 implemented，24 图 110 条 design-only；design-only 图调用 `compute_metrics` 抛 `NotImplementedError`。交付 30 张 `docs/v7/maps/MAP-XX.md`、`pending-runtime/README.md`、`measurement-principles`、`difficulty-rubric`、`experiment-protocol`、`map-review-checklist`、`design-change-requests` 与 `validation-report`。指标缺失采用五态 `valid / not_applicable / censored / unavailable / invalid_trace`，不补 0。MAP-30 的 casebook 可见性歧义在 extractor 内用 judge 标志或 condition_id 区分，空 casebook 不再被误算为 0。

验证：`.venv\Scripts\python.exe scripts\validate_v7_metrics.py` 通过，输出为 154 specs / 30 maps / 6 runtime-backed / 24 design-only / 29 solver episodes replayed offline；30 卡 front-matter 哈希与冻结 V4 源文件一致。V7 范围 `ruff check` 与 `ruff format --check` 通过；`mypy src/agent_arena/v7` 对 12 个源文件无问题；V7 定向 `pytest` 为 49 passed，全量 `pytest -q` 为 608 passed。六图回放使用 V6 求解器在真实 V4 环境执行，未调用 provider、未写 `runs/` 或账本。全仓 `ruff check .` 仍有 653 个既有错误，全部位于本轮未修改的 `worlds/v4/MAP-*/planning/*_audit.py`，未批量改写冻结审计脚本。

边界：24 图仍无运行时；没有真实模型 V7 结果；30 卡维持 `pending_human_review`，V6 的 29 个实例状态不变；规则冲突只登记为 `V7-DCR-001 … 012`（proposed）。MAP-18 部分实例的故障在求解器完成交付后才出现，改线指标按预登记规则记 N/A，不把“未触发”记成“0 tick 恢复”。

下一步：按 `pending-runtime/README.md` 逐图接入运行时；优先处理 MAP-18 故障绑定、MAP-26 恢复条件与 MAP-30 记忆条件的指标稳定性，再由人工复核 DCR 与 30 张卡。

关联提交：待提交。

## 2026-10-17 V7 六图手算 fixture、合法范围与机器自审补齐

事件：补齐 V7 离线层的可执行验收缺口：6 张运行图各 6 条真实环境手算轨迹、154 条 `MetricSpec.valid_range`、V7 只读/泄漏扫描、30 卡结构自审，以及 24 张设计图的逐图 `pending-runtime/MAP-XX.md`。

原因：上一轮已交付注册表、30 卡与六图 extractor，但手算轨迹尚未全部变成测试断言，`MetricSpec` 缺合法范围，24 图只有总表；这些都使“可复算”与“逐图接入”缺少可执行证据。

改动：新增 `tests/test_v7_hand_traces.py`（6 图 × 6 条，覆盖成功/机制失败/边界/截尾/N/A）、`tests/test_v7_leakage.py`、`tests/test_v7_cards.py`、`scripts/audit_v7_cards.py`、`scripts/check_v7_leakage.py`；`MetricSpec` 增加 `valid_range` 并在缺失时按单位推导；修复 `map22.path_gap` 把被拒绝 move 计入 gap 的缺陷；修正 MAP-22 不可重放的 30 步手算轨迹、MAP-22 18 步轨迹重复率与 MAP-30 F03 精确率；为 24 张设计图各生成一份 `docs/v7/pending-runtime/MAP-XX.md`，总表保留共同门槛。

验证：`scripts/validate_v7_metrics.py` 通过（154 specs / 30 maps / 29 solver episodes）；`scripts/audit_v7_cards.py` 为 0 findings，30 卡 13 小节齐全，剔除通用指标族后最高构念相似度 0.8；`scripts/check_v7_leakage.py` 检查 12 个 V7 源文件、64 份文档，无禁止导入/写文件/凭据形状文本；V7 定向 `pytest` 为 90 passed，全量 `pytest -q` 为 649 passed；V7 scoped Ruff、format、mypy 通过。全仓 Ruff 仍有 653 个既有错误，全部在未修改的 V4 审计脚本。

边界：30 卡仍为 `pending_human_review`，12 条 DCR 仍为 `proposed`；24 图仍无运行时；没有真实 V7 模型结果；本轮 0 次付费 API、0 个新账本、未写 `runs/` 或 `results/`。机器自审不能替代人工签署。

下一步：等待人工复核 30 卡与 DCR；按逐图 `pending-runtime/MAP-XX.md` 的阻塞项选择下一张运行时切片；若需要全仓 Ruff 绿，单独整理冻结 V4 审计脚本的既有格式问题。

关联提交：`01b95ff862a6ea55b48b3ca00d3146ec1c4324e2`。

## 2026-10-17 V7 真实 MiMo trace 二次复算

事件：在不新增付费调用、不新建账本的前提下，用已完成的 V6 真实 MiMo 47 局 trace 复算 V7 六图指标，得到六图在真实模型轨迹上的首份 V7 数值。

原因：用户询问可以用 MiMo API 跑 V7。按 `experiment-protocol.md`，新的 V7 真实实验必须在 30 张卡人工冻结后单独登记预算、样本、停止规则和门禁；当前 30 卡仍为 `pending_human_review`，直接新跑会绕过预注册。已有 V6 trace 是真实 MiMo API 数据，适合先做只读二次分析，也能避免重复付费。

改动：新增 `docs/v7/real-trace-rescore.md`，记录数据源、复算命令、六图汇总、逐图读法、五态缺失与不可外推边界；在 `docs/v7/README.md` 和 `docs/v7/validation-report.md` 增加交叉引用。未修改 V7 extractor、V6 环境、Action 契约、Trace 写出器、prompt 或任何历史账本。

验证：`scripts/report_v7_metrics.py` 处理 47 条 trace，输出 47 computed、0 design_only、0 invalid_trace。原始 V6 数据为 17/47 成功、492 次请求、CNY ¥0.29230284、provider 墙钟 2169.045 秒。复算关键值包括：MAP-08 `diagnosis_accuracy` 全 1.0；MAP-16 L1 两条件 `makespan_gap=0`、L2/L3 四局 `makespan_gap=N/A` 且 `node_capacity_conflicts=1`；MAP-18 `service_rate` 0–0.333（9 有效、1 censored），改线指标 10 局全 N/A；MAP-22 L3 `history5` 失败、`history5_graph_memory` 成功且 `path_gap=3`；MAP-26 `free_diagnosis` 3/4 修复、`recovery_*` 0/9 修复；MAP-30 完整调查 0/3 证据链覆盖率为 0，纯召回 casebook 1/1 覆盖率为 1。没有用 0 填补 N/A、censored 或 unavailable。

边界：该结果是真实 trace 的 post-hoc 二次分析（E3-post-hoc），不是新的 V7 API 主实验；每条件只有 1 局，不能做显著性、排名或跨模型推断；24 图仍无运行时；30 卡仍由人工复核。本轮 0 次新增付费 API、0 个新账本、未写 `runs/` 或 `results/`。

下一步：先完成 30 卡人工冻结与 DCR 裁定；若要跑新的 V7 真实实验，再单独登记六图多实例配对矩阵、预算上限和停止规则，不在当前状态下直接调用 API。

关联提交：本次提交。

## 2026-10-17 V7 30 卡人工复核记录

事件：用户明确表示已复核 V7 的 30 张逐图指标卡；据此把 30 张卡的 `review_status` 从 `pending_human_review` 更新为 `human_approved`，并记录 `reviewed_at: 2026-10-17`、`reviewed_by: human`。

原因：V7 协议要求人工复核不得由执行模型代签。此前 `pending_human_review` 是初始离线层的唯一人工门禁；用户确认后，应把复核事实写入卡片与验收文档，而不是继续停留在待审状态。

改动：更新 `docs/v7/maps/MAP-01.md … MAP-30.md` 的 front matter 与相关正文状态；更新 `map-review-checklist.md`、`README.md`、`validation-report.md`、`self-review.md`、`source-audit.md`、`experiment-protocol.md`、`real-trace-rescore.md`、`AGENTS.md` 与 `docs/scope/scope.md`。`scripts/validate_v7_metrics.py` 接受 `pending_human_review` 或 `human_approved`。12 条 `V7-DCR` 仍保持 `proposed`，只把“已复核”与“规则变更已批准”分开记录。

验证：`scripts/validate_v7_metrics.py` 通过（154 specs / 30 maps / 29 solver episodes）；`scripts/audit_v7_cards.py` 为 0 findings；`scripts/check_v7_leakage.py` 通过（12 源文件 / 65 文档）。

边界：本次只记录人工复核，不修改任何 V4/V5/V6 规则、Oracle、账本、注册表或原始 trace；24 图仍无运行时；12 条 DCR 的规则变更仍未批准，继续作为对应地图运行时接入前的准入项。

下一步：按 `docs/v7/pending-runtime/README.md` 推进 24 图运行时切片；DCR 在对应地图接入前逐条决定。

关联提交：本次提交。

## 2026-10-17 V7 Pilot-001 六图 12 局真实 API 探针（按 unknown spend 停止）

事件：30 卡人工复核后，按 `docs/v7/pilot-001-registration.md` 运行 V7 六图 12 局 MiMo pilot。实际启动 10 局、9 局完整结束；MAP-26 `recovery_full` 第 8 次请求返回 `APIConnectionError`，provider 未给出可确认结算，账本按 `UNKNOWN_PROVIDER_SPEND` 关闭，MAP-30 两局未启动。

原因：用户已授权使用 MiMo API，且 30 卡已完成人工复核。预登记明确要求新实验单独登记预算、样本、停止规则和冻结 gate；本 pilot 只覆盖有运行时的六图，不触碰 24 图设计态，也不把 V6 历史结果当作新实验数据。

改动：新增 `docs/v7/pilot-001-registration.md`、`docs/v7/pilot-001-report.md`、`scripts/run_v7_pilot.py` 与 `tests/test_v7_pilot.py`；在 `docs/v7/README.md`、`docs/scope/scope.md`、`AGENTS.md` 记录 pilot 状态。运行使用新的 `runs/v7` registry、账本与目录，不打开或追加 V2/V5/V6 账本；运行前重新冻结 V6 offline gate（`5d97a589…`），gate 绑定 `877dc01`。

结果：10 局启动、9 局完整、1 局中断；67 次请求、46,044 input / 7,614 output tokens、实际 CNY `0.05086048`、预留 CNY `0.68608`、provider 墙钟 398.718 秒；操作上限 CNY `2.00`、账本硬上限 CNY `11.00`。V7 复算 10 条 trace：10 `computed`、0 `invalid_trace`；MAP-26 中断局 `repair_success=censored`，不作为完整样本。关键读数：MAP-08 两局成功；MAP-16 L1 `makespan_gap=0`、L3 `node_capacity_conflicts=1` 且 `makespan_gap=N/A`；MAP-18 两局失败、`service_rate` 0–0.166667；MAP-22 L3 graph memory 成功、`path_gap=3`；MAP-26 free diagnosis 成功、recovery 中断；MAP-30 无数据。

验证：`scripts/report_v7_metrics.py` 处理 10 条 trace 全部成功；V7 定向测试 90 passed；pilot 选择测试 2 passed；`scripts/validate_v7_metrics.py`、`audit_v7_cards.py`、`check_v7_leakage.py` 保持通过。对 `runs/v7` 扫描 API 密钥、Bearer 授权头、密钥环境变量赋值与常见密钥前缀文本为 0 hits。全量冻结 gate 检查在运行前全绿。

边界：pilot 未完成 12 局，不能计算成功率、均值或显著性；单 seed、每条件 1 局，且多组条件对使用不同实例；MAP-30 无新数据；24 图仍无运行时；12 条 DCR 仍为 `proposed`。账本已关闭，不续跑、不新建 successor ledger；pilot 绑定的 gate 仅认证 `877dc01`，报告提交后已按当前 HEAD 重新冻结新 gate，但新 gate 不回溯认证本次 pilot，后续新实验仍须重新登记。

下一步：先确认 provider 连接稳定性；若要完成 12 局或扩到 30 图，必须新建预登记、预算与冻结 gate，不复用本次账本。

关联提交：本次提交。

## 2026-10-17 V7 Pilot-001R 六图 12 局完整重跑

事件：在用户明确授权继续后，使用新的 V7 账本和运行目录重跑 `pilot-001-registration.md` 的同一 12 局矩阵。Pilot-001 的旧账本保持关闭且未追加、未改写；新 run 完成 12/12 局，未再出现 `APIConnectionError` 或 `unknown_provider_spend`。

原因：Pilot-001 在 MAP-26 `recovery_full` 第 8 次请求中断后按规则封账，只留下 9 局完整样本，无法覆盖 MAP-26 recovery 和 MAP-30 两局。用户明确要求继续并授予全部权限；本次沿用同一预登记矩阵、预算和停止规则，不新增假设、不修改 V4/V5/V6 规则，也不把重跑冒充新的主实验。

改动：新增 `docs/v7/pilot-001r-report.md`，记录逐局结果、逐图读法、与 Pilot-001/V6 post-hoc 的对照、费用、哈希和边界；同步更新 `docs/v7/README.md`、`docs/v7/validation-report.md`、`docs/scope/scope.md` 与 `AGENTS.md`。旧 `pilot-001-report.md` 保持原样，旧 `runs/v7/pilot_registry.json` 归档为 `runs/v7/archived/pilot_registry.pilot-001.json`；新 registry 指向新 run。未修改 V7 extractor、V6 环境、Action 契约、Trace 写出器或历史账本。

结果：12/12 完整；实验 ID `77ad5559-c8c0-44f0-bac5-b3c67d0aa5a4`；运行目录 `runs/v7/experiments/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2`；账本 `runs/v7/ledgers/v7_pilot_001_20261017T050540Z_82dcd2c1dee847438cee96e4bdc1a8d2.jsonl`。109 次请求、83,556 input / 10,740 output tokens、实际 CNY `0.08521648`、预留 CNY `1.11616`、provider 墙钟 558.349 秒；操作上限 CNY `2.00`、账本硬上限 CNY `11.00`。冻结 gate `5da2640…` 绑定运行时 commit `e67fe0b`。逐图成功数为 MAP-08 2/2、MAP-16 1/2、MAP-18 0/2、MAP-22 2/2、MAP-26 0/2、MAP-30 1/2；该计数只用于核对矩阵完整性，不是能力排名。关键新数据：MAP-18 `alert_off` 首步 `STATION_CAPACITY_EXCEEDED`、`service_rate=0`，`alert_on` 交付 6/18 后 `HEAD_ON_COLLISION`；MAP-22 L3 graph memory 成功、`path_gap=1`、写入 10 条记忆事实；MAP-26 free 与 recovery 均 `SPARES_EXHAUSTED`，recovery 的诊断正确但修复失败；MAP-30 完整调查 44 步 `DEADLINE_REACHED`、覆盖 0.25，纯召回 1 步成功、覆盖 1.0。

验证：`scripts/report_v7_metrics.py` 处理 12 条 trace，12 `computed`、0 `design_only`、0 `invalid_trace`；`v7_metrics_all.json` SHA-256 `5390ab8e43a6168ea25c06bb2069b0646e24f9ea5dfb1a2d1e50a80e9ed673c1`，`run_manifest.json` SHA-256 `28d2241b262b8278a75e88b8d5da169fc3951b0545c1a3769fce34bedc385a6b`，账本 SHA-256 `ea8158ec60e37f3492c277cefd11118ccdb63258c4a8c3e26b863936d87525f5`。`runs/v7` 密钥/授权头/密钥前缀扫描 0 hits。Pilot-001 与 Pilot-001R 的同一矩阵结果出现方向性波动（MAP-26 free 成败、MAP-18 失败机制、MAP-22 `path_gap`、MAP-30 时长），因此本次仍不能当作条件效应或主实验结论。

边界：仍是 E3-pilot；单 seed、每条件 1 局，多数条件对使用不同实例；没有 30 图正式矩阵、没有 24 图运行时、没有 12 条 DCR 的规则批准。Pilot-001R 使用独立新账本，但不重开 Pilot-001 旧账本；两次 pilot 的费用分别为 CNY `0.05086048` 与 `0.08521648`，合计 `0.13607696`。

下一步：若要形成 V7 主实验，需新预登记同实例多 seed/重复配对矩阵，并单独冻结预算、停止规则与 gate；24 图运行时继续按 `docs/v7/pending-runtime/MAP-XX.md` 逐图接入。

关联提交：本次提交。

## 2026-10-17 V9 30 图难度定标、失败归因与能力区分度

事件：按用户提供的 V9 提纲完成 30 图逐图能力构念审计、失败归因、独立基线、指标第二路径与有界 MiMo 复测。V8 90 局、账本、冻结 hash 与规则保持只读；V9 新增独立代码、文档、账本与实验 ID。

原因：V8 的 0/3 与 3/3 不能直接解释为能力；需要先区分公开信息/接口/预算/场景可解性，再判断哪些图达到研究级测量。

改动：新增 `src/agent_arena/v9/`（审计、证据包、120 条独立指标复算、30 个公开启发式/消融、独立 ¥10 账本、有界 runner、公开信息补充与指标叠加）、`docs/v9/`（30 份逐图审计、14 份 DCR、状态矩阵、最终报告）、`tests/test_v9_*.py` 与 `scripts/v9_*`。10 张图补充公开信息（05/07/08/09/10/11/12/16/25/26），9 图新增只读指标叠加；V8 规则、账本与 Trace 零改动。

结果：Batch 0 复算 90/90，17/90 成功，22 张 0/3；正式费用 ¥1.27464628，全部账本三口径为 ¥1.27464628 / ¥1.39004496 / ¥1.45502656。30 图审计结论：**7 张 VALIDATED、8 张 NEEDS_MORE_EVIDENCE、13 张 NEEDS_REDESIGN、2 张 BLOCKED**；11 张存在构念旁路（MAP-06 seed 0、MAP-15 goal 泄露、MAP-21 直达撤离等），至少 13 张 0/3 首因是公开信息/接口而非能力。基线：55/55 Oracle、600 次随机 11 成功（仅 MAP-15/21）、30/30 公开启发式、120/120 独立指标复算。MiMo V9 预登记 29 条记录，settled **¥0.34049884**、512 请求、2 次 `InternalServerError` unknown spend；主账本与 supplement_001 按规则封账、未重开，剩余局在 supplement_002 完成。MAP-10/11 0/2→2/2、MAP-07/26 0/1→1/1、MAP-09 从 2 决策短路后移到 12 决策缺氧；MAP-12 `v9_fixed` 两次中断后停止，未完成。

验证：`pytest` 888 passed；`ruff check src/agent_arena/v9 tests/test_v9_*.py scripts/v9_*.py scripts/run_v9_mimo.py` 通过；`mypy src` 166 个源文件 0 issues；`git diff --check` 通过；V8 冻结 hash 与 90 局 Trace 未改。

边界：MiMo 是 E3-pilot，样本小、单实例 seed、模型单一，不作显著性/排名；30 份审计是 `agent_reviewed`，没有 `human_approved`；`runs/` 是本地生成物。V9 只证明 7 张图当前可用于研究级测量，其余仍需接口/指标/构念修复。

下一步：先处理 MAP-18 horizon、MAP-03 记忆通道、MAP-06 cohort、MAP-15 goal、MAP-21 判据；再对 07/08/09/10/11/12/26 做多 seed 复核；把 9 条 overlay 指标提升为 V10 正式指标。

关联提交：本次提交。

## 2026-10-19 V10 Batch 8/9 有界 MiMo 复测、8 Gate 验收与 30 张逐图审计卡

事件：按用户授权完成 V10 剩余批次——Batch 8（有界 MiMo 复测）与 Batch 9（最终验收）。V8/V9 全部文件只读，`freeze verify` 每次 9/9 `unchanged`。

原因：Batch 0–7 只完成离线 Gate；30 张 V10 原生图缺真实模型证据，30 张逐图审计卡与成本账本审计也缺失，无法回答“MiMo 的失败来自策略、接口、预算、资源还是随机场景”。

改动：新增 `src/agent_arena/v10/ledger.py`（V10 独立 append-only 账本，登记输入上限 16384、`prior_spend` 全局共享、未知消费立即封账）、`contract.py`（按 `V8Action` 注解渲染公开动作契约类型）、`validation.py`（8 项 Gate 机器判定）、`map_cards.py` / `mimo_report.py` / `construct_validity.py` / `independent_check.py`，重写 `scripts/run_v10_mimo.py`（幂等续跑、逐局 trace/judge/manifest），新增 `tests/test_v10_batch8*.py`、`tests/test_v10_batch9*.py`，新增 `docs/v10/` 下 30 张 `maps/MAP-XX.md`、`validation-gates.md`、`mimo-results.md`、`cost-ledger-audit.md`、`baseline-results.md`、`construct-validity.md`、`design-principles.md`、`independent-metric-check.md`、`DCR-V10-23/24` 与重写的 `final-report.md`、`README.md`。

结果：MiMo 23 张原生图 × 3 环境 seed，82 局记录（77 有效 + 5 中断保留），成功 36/77；结算 CNY `1.74110332` + 未知预留 `0.11468800` = `1.85579132`（上限 ¥10，剩余 `8.14420868`），1886 次请求预留，11 个账本一个未删未改。发现并修复**一类系统性接口假象**：契约只列字段名不列类型，模型把 `operations`/`claims`/`forecast_next`/`set_flow_tenths` 写成错误形状被判非法动作（DCR-V10-24）；修复后 MAP-18 非法动作 20/20→0、MAP-28 seed0 由“从未提交”变为成功、MAP-19 非法 121/180→0。指标独立复核 23 图 × 116 seed 实例：状态-取值违规 4→0（DCR-V10-23 修复 MAP-12 `research_completion` 取值域）、回放确定性 23/23、seed 互异 23/23。30 图状态：**29 VALIDATED**（22 张原生图 8 Gate 全过 + 7 张 V8 回退图沿用 V9 并记 3-seed 缺口）、**1 NEEDS_MORE_EVIDENCE（MAP-20）**、0 NEEDS_REDESIGN、0 BLOCKED；构念 FORCED 28 / OPTIONAL 2（MAP-04 依证据改判）/ BYPASS 0 / BLOCKED 0。

验证：`pytest` 1070 passed；`mypy src` 236 文件 0 issues；scoped `ruff` clean；`freeze verify` 9/9 unchanged；真实数字全部由 `runs/v10/` 复算（`mimo_report`、`validation`、`difficulty`、`status`、`map_cards`）。

边界：MiMo 单模型、单 replicate、3 环境 seed，只作描述，不作显著性断言与跨模型排名；Batch 8 的 `metric_schema_hash` 为 `b3fc3317…`（DCR-V10-23 之前），逐局 manifest 已固化，不得与新值混算；MAP-20 的接口结构只由 runner 提示补全、未写进地图 `public_rules()`，阶段 3b 补跑因 provider 退化未完成，维持 `NEEDS_MORE_EVIDENCE`；全部结论为 `agent_reviewed`，无 `human_approved`。

下一步（V11）：先修 MAP-20 的公开接口并补 3 seed MiMo；把 7 张 V8 回退图参数化为 V10 原生运行时；补比值类主指标的公式级独立复算；对 MAP-14/19/22/29 的“未触发机制”做 trace 级归因；再评估古堡三图决策预算。

关联提交：`ed063de`（分支 `v10-validity`，已推送）。

## 2026-10-19 V10 续跑：MAP-20 公开接口补全（DCR-V10-25）与 trace 级失败归因

事件：接续上一轮的缺口清单，完成 MAP-20 的接口规则化、阶段 4 真实模型复验，并新增逐局 trace 级失败归因。V8/V9 仍只读。

原因：MAP-20 是上一轮唯一未过 `mimo` Gate 的图（Batch 8 三局 168/168 非法动作）；同时“模型为何没触发核心机制”只有汇总层解释，缺逐局证据。

改动：`v10/runtime/map20.py` 把 `set_flow_tenths`/`adjust_loads`/`open_bypasses` 的结构与取值集合写进 `public_rules()`（`RULE_VERSION` `v10.map20.1`→`v10.map20.2`，`rule_hash` `81eb7439…`→`e677a0ac…`），并删除 runner 层对该图的临时提示；新增 `src/agent_arena/v10/attribution.py`（逐局回放 trace，输出 `TRIGGERED`/`CONTRACT_ARTIFACT`/`KEY_ACTION_NEVER_ATTEMPTED`/`KEY_ACTION_ATTEMPTED_REJECTED`/`KEY_ACTION_USED_NO_TRIGGER`，兼容早期单文件布局）；新增 `docs/v10/dcr/DCR-V10-25.md`、`docs/v10/failure-attribution.md`、`tests/test_v10_batch9_attribution.py`（8 条）。

结果：阶段 4（`-j2`）MAP-20 三局**非法动作 168/168 → 0/168**，`mimo` Gate 通过 ⇒ **30/30 图 `VALIDATED`**（23 张原生图 8 项 Gate 全过 + 7 张 V8 回退图沿用 V9 并记 3-seed 缺口），`NEEDS_MORE_EVIDENCE`/`NEEDS_REDESIGN`/`BLOCKED`/`BYPASS` 全为 0；MAP-20 仍 `decision_budget_exhausted`、主指标恒 0（转为策略/难度结论）。归因分布（85 局）：`TRIGGERED` 47、`KEY_ACTION_USED_NO_TRIGGER` 22、`CONTRACT_ARTIFACT` 9、`KEY_ACTION_NEVER_ATTEMPTED` 5、`KEY_ACTION_ATTEMPTED_REJECTED` 2。累计费用：结算 CNY `1.77142820` + 未知预留 `0.11468800` = `1.88611620`（上限 ¥10，剩 `8.11388380`）；12 个账本全部保留。新增阶段 4 账本 `ledger_v10_008.jsonl`（168 请求、0 失败、未关闭）。

验证：`pytest` 1085 passed；`mypy src` 237 文件 0 issues；scoped `ruff` clean；`freeze verify` 9/9 unchanged；`validation`、`mimo_report`、`attribution`、`difficulty`、`map_cards`、`status` 全部重算。

边界：MAP-20 的 3 局仍不能说明能力高低（单模型、单 replicate、3 seed、主指标恒 0 只说明模型未产出产能）；`KEY_ACTION_USED_NO_TRIGGER` 的 22 局需逐图判读；早期 9 局的 trace 为单文件布局（归因器已兼容，引用时注明）。

关联提交：本次提交（分支 `v10-validity`）。

## 2026-10-19 V10 续跑 2：主指标公式级第二套实现（DCR-V10-26）

事件：接续缺口清单第 2 项，为 23 张 V10 原生图的**主指标**写第二套独立实现并逐局比对；过程中查出并修复一处系统性五态口径缺陷。

原因：此前只有「规格驱动五态核对 + 回放确定性 + seed 差异性」，没有用第二套实现重算分子/分母，无法证明指标数学本身正确。

改动：新增 `src/agent_arena/v10/recompute.py`（只用「公开初始 Observation 的实例参数」+「`judge_state()` 原始计数器」重算，覆盖 17/23 图；6 图因依赖密封真值/未暴露字段列入 `SKIP_REASONS` 并逐条说明）、`v10/metrics/governance.py::truncation_censored`（按规格文本把被决策预算截断的局改判 `CENSORED`）、`tests/test_v10_batch9_truncation.py`（6 条）；`baselines/runner.py`、`scripts/run_v10_mimo.py`、`recompute._replay` 接入归一；新增 `docs/v10/dcr/DCR-V10-26.md`、`docs/v10/metric-recompute.md`；更新 `tests/test_v10_batch3.py` 的 MAP-30 断言（区分截断 `CENSORED` 与终局指控被拒 `NOT_APPLICABLE`）。

结果：第一轮 633 次检查出现 **53 处不一致**，全部同一根因——各图 `v10_metrics()` 只检查环境的 `step_limit_reached`，而 V10 的真实截断来自 runner 决策预算（环境停在 `running`），于是截断局仍报 `VALID 0`（MAP-10 16、MAP-20 1、MAP-22 16、MAP-23 8）或 `NOT_APPLICABLE`（MAP-28 12），与规格声明的「截尾 → CENSORED」冲突；这同时解释了基线里 `legal_random` 主指标均值长期为 `0.0`。归一后重跑：**633 次检查全部一致（17 图、0 不一致）**。离线基线已重跑（23 图），截断局的 `VALID 0` 变为 `CENSORED`、相应均值变为 `null`/按已结算局计算。Batch 8 的 85 局 MiMo 记录**不回写**（历史证据，逐局 manifest 保留旧口径）。

验证：`pytest` 1084 passed；`mypy src` 238 文件 0 issues；scoped `ruff` clean；`freeze verify` 9/9 unchanged；`recompute`、`baselines.suite`、`validation`、`difficulty`、`map_cards`、`status`、`attribution`、`mimo_report` 全部重算。

边界：复算仍是「同一套公开输入下两套实现一致」，不等于构念效度；剩余 6 图（03/13/14/21/24/26）需先把真值或判据字段纳入 `judge_state` 才能覆盖；截尾归一改变了 2026-10-19 之后的离线基线与新局记录，跨日比较需注明口径。

关联提交：本次提交（分支 `v10-validity`）。
