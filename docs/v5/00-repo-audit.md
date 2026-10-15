# V5 仓库审计

日期：2026-10-15
审计基线：`21bb968fcad1f6155ee24357dfae5a7390832d16`
工作区：`main...origin/main`，跟踪文件无改动。`研究提纲/` 下现有的四份未跟踪材料均为用户文件，本任务保留原样。

## 范围与当前状态

本轮只接入 MAP-08、MAP-16、MAP-18、MAP-22、MAP-26、MAP-30。六张图在 `worlds/v4/` 中已有手工设计、map spec、规则证据、公开 Oracle、失败轨迹、验收记录与测试草案；它们均未实现为运行环境。`docs/v5/`、V4 runner、V4 注册表和 V5 pilot 脚本在基线中均不存在。

| 地图 | 主要测量能力 | 规则与隐私边界 | 离线设计证据 |
|---|---|---|---|
| MAP-08 | 主动诊断、信息增益和压力下停止 | 初态在 B/D/F 真值下相同；X/Y 测试才揭示签名；水位严格大于 7.0 才失败 | 28 行 Oracle、两种测试顺序、三条失败；先验覆盖种子 0–11 与偏置队列 |
| MAP-16 | 单线调度与死锁避免 | 预约不推进 tick；`move_train` 原子结算区段和泊位 | 32 行 Oracle、两种六 tick 时刻表、28 个可达位置状态的 BFS 审计、四条失败 |
| MAP-18 | 故障恢复调度与告警价值 | t4 告警不含区段；R2–R3 在 t5–t9 关闭、t10 前恢复；逐 tick 联合结算 | 36 行 Oracle、三种手写计划、乘客账本、三条失败和端点检查 |
| MAP-22 | 局部探索、空间记忆与返营 | 只公开当前路标和出口方位；记忆只能登记已检查地点或刚走过的边 | 18 行 Oracle、12 节点/15 边拓扑审计、18 步巡回、30 步边界路线及三条失败 |
| MAP-26 | 错误归因、反馈后纠错与备件预算 | 三种固定隐藏故障；测试读数只在执行后出现；回滚保留重试成本 | 12 行 Oracle、0/1/2 三个故障夹具、两条成功路线、三条失败和六项边界 |
| MAP-30 | 长间隔证据记忆与证据一致性 | 档案、三事件证据、条件证词和答案映射保持裁判私有，直至合法发现 | 26 行 Oracle、三条 25/32/34 tick 路线、三条失败、五项边界 |

逐图 `DESIGN.md`、`map_spec.yaml`、`evidence_or_rules.yaml`、`oracle_trace.jsonl`、`failure_traces/cases.yaml`、`acceptance.md`、`tests/ACCEPTANCE_CASES.md` 已核对。存在的 `planning/` 参考、手写路线和离线审计器也已检查；它们是设计来源，不可由运行时或 Agent 读取。

## 可复用的工程边界

- V3 有独立的 `ScenarioAction`、`ScenarioObservation` 和 `ScenarioEnvironment`，通过 selector 注册；其 action contract 固定为 `scenario_v3`。
- 现有 `EpisodeRunner`、Trace、`DecisionProvider`、OpenAI-compatible provider 和 fail-closed provider/token budget 可作为接口参考。V4 使用新 Action/Observation schema 与独立 episode trace，不复用 V3 的世界状态和转移逻辑。
- MemoryAgent 的实现只接受 Legacy `Action`，不能直接处理 `scenario_v4`。MAP-22、MAP-26、MAP-30 需要 V4 自己的 Agent-owned history/memory 渲染路径。
- Provider 配置读取自 `.env`。本机配置的 base URL 是 `https://api.xiaomimimo.com/v1`，model 是 `mimo-v2.6-flash`；密钥只确认已配置，不读取或记录。此前本任务未发起 Provider 请求。
- 项目 V2 S2 Gate 及 BUDGET-01/02/03 已关闭。V5 使用独立实验 ID 与本地账本，不重置、复用或扩展任何 V2 账本。

## 阻塞与实现边界

1. API pilot 必须等六图离线全绿，包括 Oracle 真回放、失败与边界、seed 重放、观察隔离、独立求解器和 V3/Legacy 回归。
2. 用户要求使用 Mimo，并将每图最多三 seed 作为范围。MAP-08 选 0/4/8 覆盖 B/D/F；MAP-26 使用 0/1/2 覆盖三类故障。MAP-16、18、22、30 的规格是无随机事件的固定场景，seed 0/1/2 只是重复运行标签，不能被解释为三个独立实例。
3. 真实调用须记录全局与单局请求/token/费用上限。价格按本机所连 Xiaomi MiMo 官方 API 费率估算，未知 spend 按请求预留额记账；超限前 fail closed。
4. 宿主 `uv` 命令当前不可用，系统 Python 为 3.11.9，而项目要求 Python 3.13。验证前需定位项目虚拟环境；否则报告缺失项，不将不兼容解释为测试通过。

预计新增边界：`worlds/scenario_v4/` 的隔离环境与注册表、`evaluation/v5/` 的 runner/指标/trace、V4 专用 prompt/provider 输入适配、`scripts/v5_validate.py` 与 `scripts/v5_pilot.py`、`tests/v5/`，以及 `docs/v5/` 报告。V3、Legacy、V4 手工设计资产及现有用户草稿保持不变。
