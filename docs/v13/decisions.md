# V13 架构决策记录（ADR）

格式：编号 / 背景 / 决定 / 代价 / 备选与拒绝原因。

## ADR-V13-01：契约只增字段，不改 `schema_version`

- **背景**：V12 的 `experiment.json` / `manifest.json` 已经被 159 局真实实验与大量
  离线测试依赖。改 `schema_version` 会让所有历史读取路径都要迁移。
- **决定**：保持 `schema_version = v12-lab-1`，新增 `contract_version = v13-lab-1`、
  `replicates`、`sampling`、`protocol`、`experiment_kind`、`comparability_group`；
  旧文件缺字段时用默认值（`replicates=1` / `sampling.support=UNKNOWN` / `protocol=None`）。
- **代价**：读取器必须能处理"同一 schema 版本、两种字段集"；`ExperimentSpec._spec`
  需要剥掉 `public_dict` 追加的派生键（`deterministic_claim` / `fingerprint`）。
- **备选**：`schema_version = v13-lab-1` + 迁移脚本 → 拒绝：会逼所有历史读取改代码，
  且迁移必然改写历史文件（违反"不改历史"）。

## ADR-V13-02：`replicate_index` 只在新编号上改变条件键

- **背景**：`condition_key = map|seed|agent` 是 V12 的矩阵去重键与幂等键来源。
- **决定**：`replicate_index = 0` 时条件键**逐字不变**；`> 0` 时追加 `|rep=<n>`。
- **代价**：同一个 `(map, seed, agent)` 现在可能对应多条记录，聚合层必须显式按
  `replicate_index` 分组（已在 `compare.run_record` / `stability.group_records` 处理）。
- **备选**：把所有条件键都加上 `|rep=0` → 拒绝：会让 V12 的历史 `only_conditions`
  与脚本参数全部失配。

## ADR-V13-03：重复放在**同一实验内**，而不是每次一个新实验

- **背景**：V12 的 `create_replicate` 每次重复都新建一个父实验，重复分析必须跨实验拼接。
- **决定**：新增 `create_replicates(repeats=N)`，把 N 次重复放进同一个实验矩阵。
  保留 V12 的 `create_replicate`（一次重复）不动。
- **代价**：实验的矩阵会变大（`cells = conditions × replicates`），预检必须显示
  "条件数 × 重复数"，否则会被误读成"seed 变多了"。
- **备选**：只在报告层合并多个实验 → 拒绝：跨实验拼接容易混入版本差异（DCR-V12-06）。

## ADR-V13-04：不要求被测干预的 `prompt_hash` 相同

- **背景**：记忆/计划/反思文本本身是被测变量。如果要求它们 `prompt_hash` 相同，
  就等于禁止实验。
- **决定**：`base_prompt_hash`（共享提示主体）必须一致；`effective_prompt_hash`
  属"被测干预"，允许不同并记录。
- **代价**：`prompt_hash` 不能再用作"同条件"的判据；重复分析必须用
  `agent_config_hash` + 预算 + `base_prompt_hash`。
- **备选**：要求 `prompt_hash` 相同 → 拒绝：自相矛盾。

## ADR-V13-05：新增 `memory.v2` / `planning.v2` / `reflection.v2`，而不是改 v1

- **背景**：v1 的默认配置已经写进 159 局历史的 `agent_config_hash`。改默认值会让
  所有历史 `memory.v1` 的指纹变化（DCR-V12-06 的教训）。
- **决定**：v1 一字不动；新行为放进新 `agent_id`（`*.v2`），版本号 `2.0.0`。
  版本比较与单开关消融在 `classify_pair` 里被显式区分。
- **代价**：注册表从 4 个策略变成 7 个；UI 的默认选择仍是 v1，避免用户"不知不觉"
  换到新版本。
- **备选**：给 v1 加开关（像 `route_log` 那样）→ 只用于"默认关闭"的开关；
  默认值一变就必须升版本，这是 v2 存在的理由。

## ADR-V13-06：`memory.v2` 的路线写入有两种机制，必须显式区分

- **背景**：`env_write` 通过环境动作 `write_memory` 写 `path_state`（占决策预算）；
  `context_only` 只把路线渲染进 prompt（0 动作）。两者效果不同，但都很容易被
  当成"记忆有效"。
- **决定**：`route_mode` 是必填语义（默认 `env_write`），结果里 `mechanism` 字段
  记录实际机制；诊断层用不同瓶颈标签。
- **代价**：`env_write` 会消耗决策预算，成功率可能因"少走几步"而下降——这本身
  就是要测的代价。
- **备选**：只保留 `context_only` → 拒绝：无法验证"环境记忆通道"是否可用。

## ADR-V13-07：TTL 是下限，被延迟的触发必须留证据

- **背景**：`min_steps_between_plans` 会推迟重规划。如果只在"计划过期"时静默跳过，
  就会把"节流"误读成"没有触发"。
- **决定**：被 TTL 挡下时写 `planner_deferred_ttl` 事件（含 `trigger`、`steps_since_plan`）；
  被预算挡下时写 `planner_skipped_budget`。
- **代价**：事件变多，日志更长。
- **备选**：静默跳过 → 拒绝：不可审计。

## ADR-V13-08：Reflection 用"暴露"而不是"效果"作为第一判据

- **背景**：DCR-V12-05 的教训是 `triggered=0` 时对照无效，但报告当时只能写"无效"。
- **决定**：`eligible` / `triggered` / `blocked_cooldown` / `blocked_quota` /
  `false_triggers` / `recoveries` 分开计数；`triggered=0` 输出 `NO_TREATMENT_EXPOSURE`。
- **代价**：`activation_rate` 与 `recovery_rate` 都有分母为 0 的情况，必须显示 `None`
  而不是 0。
- **备选**：只报 `reflections` 次数 → 拒绝：无法区分"没触发"和"触发了没效果"。

## ADR-V13-09：分层归因的主层按"最不怪 Agent"排序

- **背景**：一个失败局可能同时命中接口、预算、策略三类规则。
- **决定**：优先级 `PROVIDER > INTERFACE > MEASUREMENT > BUDGET > MECHANISM > POLICY > UNKNOWN`。
  接口与测量问题永不计入能力分母。
- **代价**：主层可能"看起来对 Agent 太宽容"；因此逐局仍保留全部次层与证据锚。
- **备选**：按命中数量取最多 → 拒绝：接口问题往往一次命中很多条，会压过真实原因。

## ADR-V13-10：能力画像按机制维度，不做指标平均

- **背景**：326 个指标量纲与方向各异（成功率、步数、覆盖率、布尔标志）。
- **决定**：6 个机制维度（信息搜集 / 记忆追踪 / 规划重规划 / 资源约束 / 故障恢复 /
  证据推理），每个维度只在"适用地图"内统计，缺失机制 `score=None`。
- **代价**：无法给出"总分"；跨维度不可比。
- **备选**：指标 z-score 平均 → 拒绝：会把"读地图"和"抗预算"混成一个无意义分数。

## ADR-V13-11：历史列表用懒加载 + 增量索引

- **背景**：`RunService.list_runs` 每次 `discover()` 全量解析 manifest；5 000 局时
  页面打开会明显变慢。
- **决定**：`web/index.py`：无筛选的第一页只 stat 目录 + 读当前页；带筛选才全量解析；
  全量解析时按 mtime 复用缓存（`reused_entries`）。
- **代价**：`run_id` 必须可排序（`web-YYYYMMDDTHHMMSSZ-xxxxxxxx`），否则回退全量。
- **备选**：引入 SQLite → 拒绝：V13 明确不引入数据库，且会带来迁移与锁问题。

## ADR-V13-12：报告零 LLM

- **背景**：提纲允许"可选 LLM 润色"，但任何 LLM 解说都可能杜撰结论。
- **决定**：报告完全模板化；每个数字带锚点；结论分级只由证据结构决定。
  LLM 润色不实现（V12 也未实现）。
- **代价**：措辞机械。
- **备选**：LLM 润色 → 拒绝：需要额外费用授权，且无法保证不覆盖基础报告。

## ADR-V13-13：`verify_v13.py` 不写真实 runs/

- **背景**：验收脚本如果往 `runs/` 写数据，会污染用户的历史与账本。
- **决定**：所有检查在 `tempfile.TemporaryDirectory` 里跑；只有"只读历史复算"读
  `docs/v12/real-runs/*.csv` 与 `runs/web/_ledger`（只读）。
- **代价**：验收不覆盖"真实写入路径"，这部分由 V11/V12 的测试覆盖。
- **备选**：写 `runs/v13/selfcheck` → 允许（只写自检报告 JSON，不写 run 目录）。

## ADR-V13-14：CI 的 E2E 暂不设为阻断门禁

- **背景**：V12 的 `continue-on-error` 是因为首次运行需要 `playwright install`。
- **决定**：本轮**没有**取得"CI 连续可靠通过"的证据（无法在本地触发 GitHub Actions），
  因此保留非阻断，并在 `gap-audit.md` 显式记录为 `PARTIAL`。
- **代价**：E2E 失败不会阻断合并。
- **备选**：直接改成阻断 → 拒绝：未验证就阻断会把 CI 变成随机红灯。
