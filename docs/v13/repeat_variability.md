# 重复稳定性

- 数据来源：`HISTORICAL`（不是本次新跑的真实模型结果）
- 记录数：90；条件分组：54
- 可比分组（观测 ≥ 2）：12
- 出现结局翻转的分组：3
- 翻转率：**0.25**（Wilson 95% 描述区间 0.0889–0.5323）
- 因版本/预算/模型/模式不一致被排除的分组：6

## 统计单位（先读这一节）

- 分组 = `(map_id, environment_seed, agent_id)`；一次观测 = 一次独立重采样。
- **重复不是新的环境 seed**：同一 seed 的 3 次重复只说明抽样波动，
  不能当作 3 张地图实例，也不能据此声称地图泛化能力。
- 只有同 `agent_config_hash` / 同 `agent_version` / 同预算的观测计入翻转率；
  其余标 `跨版本` / `跨预算` 并排除（DCR-V12-06）。
- 观测数 < 3 一律 `DESCRIPTIVE_ONLY`；翻转率不是显著性结论。

## 逐条件明细

| 条件 | 次数 | 有效 | 成功 | 截尾 | 结局序列 | 可比 | 证据 | 费用区间 CNY |
|---|---:|---:|---:|---:|---|---|---|---|
| `MAP-08|seed=0|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.001892–0.001892 |
| `MAP-08|seed=0|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.002605–0.002605 |
| `MAP-08|seed=0|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.003093–0.003093 |
| `MAP-08|seed=1|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.001886–0.001886 |
| `MAP-08|seed=1|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.002784–0.002784 |
| `MAP-08|seed=1|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.005039–0.005039 |
| `MAP-08|seed=2|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.002337–0.002337 |
| `MAP-08|seed=2|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.003036–0.003036 |
| `MAP-08|seed=2|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.004596–0.004596 |
| `MAP-16|seed=0|basic.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.002507–0.004048 |
| `MAP-16|seed=0|memory.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 跨版本 | `NOT_COMPARABLE` | 0.005627–0.010614 |
| `MAP-16|seed=0|planning.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.012169–0.014056 |
| `MAP-16|seed=1|basic.v1` | 3 | 3 | 1 | 0 | 机制失败 → 完成且成功 → 机制失败 | 是 | `REPEATED_FLIPPED` | 0.004061–0.010310 |
| `MAP-16|seed=1|memory.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 跨版本 | `NOT_COMPARABLE` | 0.002738–0.008433 |
| `MAP-16|seed=1|planning.v1` | 3 | 3 | 3 | 0 | 完成且成功 → 完成且成功 → 完成且成功 | 是 | `REPEATED_CONSISTENT` | 0.013527–0.043196 |
| `MAP-16|seed=2|basic.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.000615–0.001180 |
| `MAP-16|seed=2|memory.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 跨版本 | `NOT_COMPARABLE` | 0.001960–0.004853 |
| `MAP-16|seed=2|planning.v1` | 3 | 3 | 2 | 1 | 完成且成功 → 完成且成功 → 预算截尾 | 是 | `REPEATED_FLIPPED` | 0.025722–0.075264 |
| `MAP-18|seed=0|basic.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.007738–0.014846 |
| `MAP-18|seed=0|memory.v1` | 3 | 3 | 2 | 0 | 完成且成功 → 机制失败 → 完成且成功 | 跨版本 | `NOT_COMPARABLE` | 0.013304–0.025542 |
| `MAP-18|seed=0|planning.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.014917–0.016960 |
| `MAP-18|seed=1|basic.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.004267–0.004577 |
| `MAP-18|seed=1|memory.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 跨版本 | `NOT_COMPARABLE` | 0.004881–0.012595 |
| `MAP-18|seed=1|planning.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.006576–0.010083 |
| `MAP-18|seed=2|basic.v1` | 3 | 3 | 1 | 0 | 机制失败 → 完成且成功 → 机制失败 | 是 | `REPEATED_FLIPPED` | 0.006881–0.010612 |
| `MAP-18|seed=2|memory.v1` | 3 | 3 | 2 | 0 | 完成且成功 → 机制失败 → 完成且成功 | 跨版本 | `NOT_COMPARABLE` | 0.010850–0.020643 |
| `MAP-18|seed=2|planning.v1` | 3 | 3 | 0 | 0 | 机制失败 → 机制失败 → 机制失败 | 是 | `REPEATED_CONSISTENT` | 0.009848–0.013537 |
| `MAP-22|seed=0|basic.v1` | 1 | 1 | 0 | 0 | 机制失败 | 是 | `SINGLE_OBSERVATION` | 0.038997–0.038997 |
| `MAP-22|seed=0|memory.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.089510–0.089510 |
| `MAP-22|seed=0|planning.v1` | 1 | 1 | 0 | 0 | 机制失败 | 是 | `SINGLE_OBSERVATION` | 0.054012–0.054012 |
| `MAP-22|seed=1|basic.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.017318–0.017318 |
| `MAP-22|seed=1|memory.v1` | 1 | 1 | 0 | 0 | 机制失败 | 是 | `SINGLE_OBSERVATION` | 0.038161–0.038161 |
| `MAP-22|seed=1|planning.v1` | 1 | 1 | 0 | 0 | 机制失败 | 是 | `SINGLE_OBSERVATION` | 0.034282–0.034282 |
| `MAP-22|seed=2|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.022233–0.022233 |
| `MAP-22|seed=2|memory.v1` | 1 | 0 | 0 | 0 | 已取消 | 是 | `SINGLE_OBSERVATION` | 0.006880–0.006880 |
| `MAP-22|seed=2|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.019726–0.019726 |
| `MAP-26|seed=0|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.000222–0.000222 |
| `MAP-26|seed=0|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.001511–0.001511 |
| `MAP-26|seed=0|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.002309–0.002309 |
| `MAP-26|seed=1|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.001978–0.001978 |
| `MAP-26|seed=1|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.003018–0.003018 |
| `MAP-26|seed=1|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.002658–0.002658 |
| `MAP-26|seed=2|basic.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.001225–0.001225 |
| `MAP-26|seed=2|memory.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.003016–0.003016 |
| `MAP-26|seed=2|planning.v1` | 1 | 1 | 1 | 0 | 完成且成功 | 是 | `SINGLE_OBSERVATION` | 0.003028–0.003028 |
| `MAP-30|seed=0|basic.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.079034–0.079034 |
| `MAP-30|seed=0|memory.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.118685–0.118685 |
| `MAP-30|seed=0|planning.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.113380–0.113380 |
| `MAP-30|seed=1|basic.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.077825–0.077825 |
| `MAP-30|seed=1|memory.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.118183–0.118183 |
| `MAP-30|seed=1|planning.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.115591–0.115591 |
| `MAP-30|seed=2|basic.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.086281–0.086281 |
| `MAP-30|seed=2|memory.v1` | 1 | 1 | 0 | 1 | 预算截尾 | 是 | `SINGLE_OBSERVATION` | 0.130972–0.130972 |
| `MAP-30|seed=2|planning.v1` | 1 | 1 | 0 | 0 | 机制失败 | 是 | `SINGLE_OBSERVATION` | 0.047154–0.047154 |

## 逐图翻转率

| 地图 | 可比分组 | 翻转分组 | 翻转率 | 观测数 |
|---|---:|---:|---:|---:|
| MAP-16 | 6 | 2 | 0.3333 | 18 |
| MAP-18 | 6 | 1 | 0.1667 | 18 |

## 稳定成功条件（≥3 次全成功）

- `MAP-16|seed=1|planning.v1`

## 限制

- Wilson 区间假设每组「是否翻转」近似独立二项；组之间共享同一模型与提示，因此区间偏窄，仅作描述性参考，不作显著性断言。
- 历史观测来自 V12 的不同衍生实验；跨实验拼接只按同条件同版本进行。
- 未观测到的翻转不代表不会发生；观测到的翻转也不等于机制差异。
