# V3 世界设计与交付状态

V3 按 [spec 0017](../specs/0017-world-redesign-v3/index.md) 执行，原始逐关设计来源是仓库根目录 `研究提纲/V3世界设计提纲.md`。该提纲是人工规格，不代表代码已实现或模型已通关。

## 交付原则

- 十个主题家族各自拥有机制、状态转移、胜利条件和失败因果；easy 学习一个核心规则，medium 组合约束，hard 加入策略取舍。
- V3 使用新 Scenario 契约与 selector。旧世界、旧 Action schema、seeded holdout、V1/V2 Trace 和 provider ledger 均保持隔离。
- 关卡定义与参考轨迹逐关手工维护。测试 oracle 只能根据公开 Observation 选择下一步 Action。
- 当前范围为离线设计、确定性实现和测试；未发起任何真实 Provider 请求。

## 30 关目录与交付状态

| 家族 | 机制 | easy | medium | hard | 设计卡 | 进度 |
|---|---|---|---|---|---|---|
| 飞船 | 气压、隔舱、舱外氧气、风险隔离 | SP-E | SP-M | SP-H | [01 飞船](world-01-spaceship.md) | 已实现并验收 |
| 灯塔 | 潮汐、角度、分阶段信号、救援窗口 | LH-E | LH-M | LH-H | [02 灯塔](world-02-lighthouse.md) | 已实现并验收 |
| 深海站 | 水量、压强、阀门、泵与舱室取舍 | AB-E | AB-M | AB-H | [03 深海站](world-03-abyss.md) | 已实现并验收 |
| 极地站 | 体热、天气周期、燃料与同行者 | PO-E | PO-M | PO-H | [04 极地](world-04-polar.md) | 已实现并验收 |
| 金字塔 | 公开线索、约束推理、有限试错 | PY-E | PY-M | PY-H | [05 金字塔](world-05-pyramid.md) | 已实现并验收 |
| 地铁 | 列车调度、信号、共享区段和顺序 | SU-E | SU-M | SU-H | [06 地铁](world-06-subway.md) | 已实现并验收 |
| 火山站 | 热量递推、冷却流量、临界值 | VO-E | VO-M | VO-H | [07 火山](world-07-volcano.md) | 已实现并验收 |
| 丛林遗迹 | 局部地标、可变连边、返程导航 | JU-E | JU-M | JU-H | [08 丛林](world-08-jungle.md) | 已实现并验收 |
| 月球基地 | EVA 氧气、日照、电池和返航余量 | LU-E | LU-M | LU-H | [09 月球](world-09-lunar.md) | 已实现并验收 |
| 古堡 | NPC 对话、物证、证词和唯一结论 | CA-E | CA-M | CA-H | [10 古堡](world-10-castle.md) | 已实现并验收 |

## 阶段门

| Gate | 交付 | 状态 | 证据 |
|---|---|---|---|
| 0 | 冻结 HEAD、旧 selector/hash 基线、架构 spec、30 设计 ID、逐关静态核对 | 完成 | 基线 HEAD `e23fca0`；冻结 V2 seeded 文件未改；30 个 source_design_id 与手工卡逐一核对。依赖 lock 未改，当前无 `uv`，因此未运行 `uv lock --check` |
| 1 | Scenario 契约及 PY/SU/AB 纵向原型；Oracle、拒绝/失败与回放 | 完成 | 三家族规则测试、30 selector 公共 Observation 与 Oracle 覆盖见 [测试](../../tests/test_scenario_v3.py) 和 [规则测试](../../tests/test_scenario_v3_rules.py) |
| 2 | 其余七家族 easy 关卡 | 完成 | 10 个 easy 全部进入逐关 Oracle 报告 |
| 3 | 其余七家族 medium 关卡 | 完成 | 10 个 medium 全部进入逐关 Oracle 报告 |
| 4 | 十个 hard 关卡和有界公开策略可解性检查 | 完成 | 每关在 100 动作上限内由只读公开 Observation 策略完整成功；未将此解释为最短解或穷举证明 |
| 5 | 30/30 Oracle、机制多样性、评分、兼容及最终质量门禁 | 完成 | [逐关 Oracle 接受报告](oracle-acceptance.md)、[机制核对](mechanics-crosscheck.md)、[六维评分与审查范围](review-and-score.md)及最终质量记录 |

## 当前限制

- lockfile 专项命令未运行，因为当前 PowerShell PATH 没有 `uv`；本轮未更改依赖清单或锁文件。
- 三视角是规则测试、脚本公开路线回放和兼容性回归的模拟审阅；没有外部评审或真人试玩，不据此声称自然玩家体验。
- 全部验证均为离线确定性环境和 Fake provider；没有真实 Provider 请求、GPU 训练或模型能力结论。

## 最终验收记录（2026-10-14）

- `pytest -q`：466 passed；包含 30 个场景逐关公开 Oracle、机制负例、reset/hash/Observation allowlist、Trace 脱敏和 CLI Agent 隔离用例。
- `ruff check .`：通过；`mypy src`：64 个源文件通过；项目改动的 whitespace 检查通过。V3 原始提纲保留原样，其中 Markdown 硬换行的行尾空格不纳入改动检查。
- `scripts/replay_v3_oracles.py` 以 seed 31 分别运行两次，均为 30/30 完整成功、Oracle 拒绝动作 0；逐关 Replay SHA 与完整报告逐字一致。SHA 表见 [oracle-acceptance.md](oracle-acceptance.md)。
- `uv lock --check` 未执行：本机当前没有 `uv` 命令，且依赖文件未改动。质量门禁和该限制也记录在 `docs/engineering-log.md`。
- V2 的 0014/0015/0016 及 `docs/research/v2/` 是只读历史；BUDGET-01/02/03 均关闭，不在本 V3 范围内重试。
