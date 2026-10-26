# V12 附加对照：Memory / Planning / Reflection 开关消融（真实 API）

对应执行提纲 §4.3 的三条附加对照。要求是：**同策略版本、同基线 prompt、同历史窗口，
只切换被消融的那个开关**。

- 日期：2026-10-26
- 模型 / Provider：`mimo-v2.6-flash` / `openai_compatible`
- 预算：单局 90 请求 / ¥0.20；单实验 ¥0.30
- 实际花费：**12 局 / 136 请求 / ¥0.09626428**，未知消费 ¥0

## 0. 方法说明（必须一起读）

`condition_key` 是 `map|seed|agent`，**不含 config hash**，所以"同 agent、不同 config"
的两个臂不能放进同一个实验（会被当成重复条件）。因此每个开关各建一个独立实验，
配对时按 `(map, seed)` 跨实验对齐。六个实验的版本指纹完全相同
（`v12-lab-1+agent_policy_v1+v12-contract-2`），唯一差异就是被消融的开关。

| 实验 | `experiment_id` | 地图 / seed | 配置 |
|---|---|---|---|
| memory-on | `lab-20261026T040533Z-155b5843` | MAP-18 / 0,1 | `memory.v1 {enabled: true}` |
| memory-off | `lab-20261026T040533Z-63c831a3` | MAP-18 / 0,1 | `memory.v1 {enabled: false}` |
| planning-on | `lab-20261026T040533Z-99a4d78b` | MAP-16 / 0,1 | `planning.v1 {enabled: true}` |
| planning-off | `lab-20261026T040533Z-f24959d9` | MAP-16 / 0,1 | `planning.v1 {enabled: false}` |
| reflection-on | `lab-20261026T040533Z-447523e3` | MAP-16 / 0,1 | `reflection.v1 {enabled: true}` |
| reflection-off | `lab-20261026T040534Z-2dd57d9e` | MAP-16 / 0,1 | `reflection.v1 {enabled: false}` |

**样本量**：每格 1 局、每个开关 2 局。已知同条件翻转率 22–25%，因此本节
**只作描述性对照**，不作显著性断言。

## 1. Memory 开启 / 关闭（MAP-18）

| seed | 开启：终态 | 关闭：终态 | 开启：决策 | 关闭：决策 | 开启：费用 | 关闭：费用 | 开启：Agent 事件 | 关闭：Agent 事件 |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 0 | FAILED `HEAD_ON_COLLISION` | FAILED `HEAD_ON_COLLISION` | 12 | 13 | 0.01800804 | 0.01491148 | 12 | 1 |
| 1 | FAILED `STATION_CAPACITY_EXCEEDED` | FAILED `STATION_CAPACITY_EXCEEDED` | 9 | 8 | 0.01233844 | 0.00660192 | 9 | 1 |

**结论**：两臂**结局完全相同**（同一终止码），记忆没有改变行为结果；
但开启记忆后 Agent 事件从 1 条增加到 9–12 条，费用从 ¥0.0215 升到 ¥0.0303。
也就是说：**记忆通道确实在工作（产生了真实 `memory_updated` 事件），但在
MAP-18 的这两个 seed 上，它没有带来可观测的收益，只带来了成本。**

与主矩阵一致：memory 在两个 seed 上都是机制失败（主矩阵里 MAP-18 memory 为 2/5，
成功出现在另外的 seed）。

## 2. Planning 开启 / 关闭（MAP-16）

| seed | 开启：终态 | 关闭：终态 | 开启：请求 | 关闭：请求 | 开启：费用 | 关闭：费用 |
|---:|---|---|---:|---:|---:|---:|
| 0 | FAILED `NODE_CAPACITY_CONFLICT` | FAILED `NODE_CAPACITY_CONFLICT` | 17 | 7 | 0.01543112 | 0.00268336 |
| 1 | **SUCCEEDED** `GATE_OPENED` | FAILED `NODE_CAPACITY_CONFLICT` | 18 | 12 | 0.01475252 | 0.00520300 |

**结论**：seed 1 上开启规划成功、关闭规划失败；seed 0 上两臂都失败。
方向与主矩阵一致（planning 在 MAP-16 是唯一正向梯度，种子扩展后 3/4），
但**代价清楚可见**：请求数 17–18 vs 7–12（Planner 额外调用全部计费），
费用约 3–6 倍。n=2，仍落在已知翻转率之内，不能当作"规划有效"的证据。

## 3. Reflection 开启 / 关闭（MAP-16）

| seed | 开启：终态 | 关闭：终态 | 开启：决策 | 关闭：决策 | 开启：反思触发 | 关闭：反思触发 |
|---:|---|---|---:|---:|---:|---:|
| 0 | FAILED `DEADLOCK` | FAILED `DEADLOCK` | 6 | 6 | **0** | 0 |
| 1 | **SUCCEEDED** `GATE_OPENED` | **SUCCEEDED** `GATE_OPENED` | 14 | 14 | **0** | 0 |

**结论**：**反思一次都没有触发**（两臂 `reflection_triggered` 均为 0 条）。
原因是 MAP-16 的失败来得太快（seed 0 在第 6 步就 `DEADLOCK`），
低于反思的公开触发器阈值（连续无进展 N 步 / 重复被拒 N 次）。
因此本组对照**无法回答"反思是否提效"**——它是"触发器未激活"，
不是"反思无效"。这是 DCR-V12-05 记录的事实。

要在有意的前提下测反思，需要先选一个**失败前缀足够长**的地图或 seed
（例如 MAP-22 的迷路局，决策数 40+），或调低触发阈值（但那会改变被比较的变量，
必须另开版本）。

## 4. 汇总

| 对照 | 结局是否不同 | 代价是否不同 | 能下的结论 |
|---|---|---|---|
| Memory on/off | 否（2/2 相同） | 是（费用 +41%，事件 1 → 9–12） | 记忆通道工作但不改变本组结果 |
| Planning on/off | 是（1/2 vs 0/2） | 是（请求约 2.4×，费用约 3–6×） | 方向为正，代价明确，样本不足 |
| Reflection on/off | 否（2/2 相同） | 微 | **触发器未激活，对照无效** |

## 5. 对提纲的意义

提纲 §4.3 的三条附加对照现在**都有真实产物**，但只有第 2 条给出了方向性信号；
第 1 条是"有机制、无收益"的负结果；第 3 条是"未激活"。三者都不支持任何
"某架构更好"的结论，与 `mimo-results.md` §4.2 的翻转率证据一致。

## 6. 复现

```bash
uv run python scripts/run_v12_ablations.py            # 预检，零请求
uv run python scripts/run_v12_ablations.py --submit   # 12 局，约 ¥0.10
```

原始逐局 CSV 见 `docs/v12/real-runs/ablation-*.csv`（每个实验一份）。
可读报告没有单独归档：`lab.export(<experiment_id>)` 能从落盘结果原样重新生成。
