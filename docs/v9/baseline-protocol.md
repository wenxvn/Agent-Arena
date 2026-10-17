# V9 基线协议与可复现性

## 1. 四类基线

| 基线 | 目的 | 读什么 | 不得做什么 |
|---|---|---|---|
| `Oracle` | 证明存在合法成功路径 | 设计稿 `ORACLE_CASES` / V4 独立 solver | 不得当作“公开策略”或模型能力 |
| `legal_random` | 下界与运气检验 | 当前公开 Observation + 动作 schema | 不读 judge_state、不读 Oracle |
| `public_heuristic` | 证明“仅凭公开信息”可执行 | Observation + 自己的历史 | 不读 Environment、Oracle、指标 |
| `no_key_mechanism` | 消融核心能力 | 同一公开面，显式移除一个机制 | 不得改任务或隐藏信息 |

实现：`src/agent_arena/v9/baselines.py`、`src/agent_arena/v9/policies/world_*.py`。
运行：`python -m agent_arena.v9.baseline_run [MAP-XX ...]`，输出 `runs/v9/baselines/MAP-XX.json`。

## 2. 独立性保证

1. 策略只收到 `public_observation()` 的深拷贝，不含 `judge_state`、`oracle_trace` 或环境对象。
2. `legal_random` 的环境 seed 固定为注册实例（默认 0），只改变策略 RNG 种子；否则 V4 适配图会拒绝未注册 seed。
3. **确定性修复**：`ShapeSampler.from_environment` 对 `SHAPES` 的 set 迭代做显式排序。修复前同一策略在不同进程会因 `PYTHONHASHSEED` 得到不同拒绝计数（MAP-10 353/362、MAP-11 45/50）；修复后两进程一致。
4. Oracle 回放使用与 V8 离线门禁相同的来源：原生图读 `ORACLE_CASES`，V4 适配图读 `adapter_cases.oracle_cases`；不再用通用 jsonl 解析（MAP-12 的“每天一行、`actions` 数组”格式曾导致 0/2 的假失败）。

## 3. 结果汇总

完整表见 `docs/v9/baselines.md`（由逐图 JSON 生成，避免 `summary.json` 被单批覆盖）。

- Oracle：**55/55** 用例真实回放成功；30/30 图至少 1 个用例。
- `legal_random`：**11/600** 次成功（30 图 × 20 seed）；成功只出现在 MAP-15（5/20）与 MAP-21（6/20）。
- `public_heuristic`：**30/30** 图有可复现成功记录；最小 1 决策（MAP-21），最大 60 决策（MAP-12）。
- 消融：至少 12 张图存在“移除机制仍成功”的消融，逐图审计 §9 区分“旁路”与“可替代策略”。

## 4. 关键读法

- **random 成功率不是难度**：MAP-15/21 的 25–30% 说明通过条件可被猜中，是构念问题。
- **Oracle 成功不是可发现性**：MAP-10/12/26 的 Oracle 成功但公开面缺参数/边名，属于接口阻塞。
- **heuristic 成功不是模型能力**：策略作者可以使用设计稿中的规则常量；审计 §3 标注了哪些常量未公开。
- **n=3 不是统计样本**：V8 三局同 seed、同 prompt；V9 基线每图 1 个 heuristic 种子、20 个 random 种子。

## 5. 复现命令

```powershell
# 全部地图
.\.venv\Scripts\python.exe -m agent_arena.v9.baseline_run

# 单图
.\.venv\Scripts\python.exe -m agent_arena.v9.baseline_run MAP-09

# 调试策略
.\.venv\Scripts\python.exe scripts/v9_try_policy.py MAP-09

# 生成文档表
.\.venv\Scripts\python.exe scripts/v9_report_baselines.py
```

## 6. 限制

- 策略作者知道规则；严格“只看 prompt 的模型”不一定能推出同样的策略。V9 用“策略代码只读 Observation”保证运行时边界，但不宣称“人类可发现性”。
- `legal_random` 只保证动作形状合法，语义合法性由环境裁决；拒绝计数包含“形状非法”和“语义非法”两类，逐图 JSON 分别记录 `invalid_actions` 与 `rejected_actions`。
- V4 适配图的无效动作可能不推进世界时钟（MAP-08），与原生 V8 地图不同；这属于适配层语义，已在审计中标注。
