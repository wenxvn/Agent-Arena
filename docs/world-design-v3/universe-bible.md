# V3 世界共同规则

本文件定义十个主题共用的交互边界；家族卡保留各自的因果规则。它不把十个世界合并成相同谜题链。

## 共同游玩契约

- Agent 只收到当前房间 Observation、当前可见目标的交互选项、公开仪表和公共目标。地图真值、未发现线索、未来事件、私有答案和 oracle 不得输入 Agent。
- `look`、`move`、`inspect`、`pickup`、`use`、`read_terminal` 沿用旧字段；V3 新增 `interact(target, choice)`、`wait(turns=1)`、`submit(target, answer)`。legacy selector 只接受原 Action V1 schema。
- 每个 schema 合法并到达 Environment 的动作都耗一 tick，包括语义拒绝、`look`、`inspect` 和 `wait`。在 Environment 外被 schema 拒绝的候选不耗时。
- 每一步先检查公开可操作条件并应用动作效果，再推进天气、潮位、热量、水位或时限，最后生成观察并判断终局。动作直接完成目标时记成功，不受尾随 tick 伤害。
- 动态周期完全由整数 tick 与显式 seed 决定；不读系统时间，不调用未固定的随机数。反馈明确当前读数、变化率、阈值与拒绝原因。
- `scenario_success`、`partial_success`、`scenario_failure`、`step_limit`、`provider_error` 含义互斥。Partial 不计为主成功。

## 设计审阅表

每关在最终冻结前记录六个维度（玩法独特性、状态因果性、信息公平性、决策后果、难度递进、验收完整性，各 0–2 分）及总分。规则一致性、可玩性/叙事、技术/兼容性三种审阅意见单列；没有独立意见时明确标待审，不自称已通过。
