# V14 数据口径与构念效度修正

- 来源：`docs/v12/real-runs/*.csv`（只读，未修改）
- 历史局数：138
- 真实付费请求：**0**

## 1. `UNKNOWN` 与 `0` 分开（P0-2）

V13 的 `validity_markdown()` 用 `mechanism_triggered_runs / runs` 渲染机制触发列。
历史 CSV 根本没有 `mechanism_triggered` 列，于是**缺失**被打印成 `0/N`，
等价于把"没测过"写成"测过且为假"。V14 改为三档计数：
`observed_true` / `observed_false` / `unknown`，只有观测子集才进分母。

| 地图 | 协议分组 | 分组状态 | 局数 | 机制触发（V14 口径） | 状态 |
|---|---:|---|---:|---|---|
| MAP-08 | 1 | `SINGLE_PROTOCOL` | 9 | 0/0 observed，9 unknown | `UNKNOWN` |
| MAP-16 | 7 | `POOLED_ACROSS_PROTOCOLS` | 35 | 0/0 observed，35 unknown | `UNKNOWN` |
| MAP-18 | 6 | `POOLED_ACROSS_PROTOCOLS` | 37 | 0/0 observed，37 unknown | `UNKNOWN` |
| MAP-22 | 3 | `POOLED_ACROSS_PROTOCOLS` | 21 | 0/0 observed，21 unknown | `UNKNOWN` |
| MAP-26 | 1 | `SINGLE_PROTOCOL` | 9 | 0/0 observed，9 unknown | `UNKNOWN` |
| MAP-30 | 3 | `POOLED_ACROSS_PROTOCOLS` | 27 | 0/0 observed，27 unknown | `UNKNOWN` |

## 2. 版本 / 协议隔离（P0-2 / P0-3）

- 多协议并存、禁止合并求均值的图：MAP-16, MAP-18, MAP-22, MAP-30
- 机制触发全未知的图：MAP-08, MAP-16, MAP-18, MAP-22, MAP-26, MAP-30

### 2.1 MAP-22 的分组明细

| 实验类型 | 文件 | 指纹 | 局数 | 有效 | 成功 | 截尾 | 成功率 |
|---|---|---|---:|---:|---:|---:|---:|
| ablation | `map22-route-log-runs.csv` | `d11f8428e4f9` | 3 | 3 | 1 | 0 | 0.3333 |
| matrix | `main-54-runs.csv` | `d11f8428e4f9` | 9 | 8 | 2 | 2 | 0.25 |
| version_rerun | `map22-contract2-runs.csv` | `d11f8428e4f9` | 9 | 9 | 0 | 0 | 0.0 |

> ``POOLED_ACROSS_PROTOCOLS`` 的图不允许给出单一成功率；机制触发全未知的图必须显示 UNKNOWN，不能显示 0/n。

## 3. 六图标签差异（V13 → V14）

| 地图 | V13 标签 | V14 标签 | V13 有效分母 | V14 有效分母 | 变化 |
|---|---|---|---:|---:|---|
| MAP-08 | `CEILING` | `CEILING` | 9 | 9 | 机制触发 0/9 → UNKNOWN (0 observed / 9 runs) |
| MAP-16 | `SUITABLE` | `SUITABLE` | 35 | 35 | 机制触发 0/35 → UNKNOWN (0 observed / 35 runs) |
| MAP-18 | `SUITABLE` | `SUITABLE` | 37 | 37 | 机制触发 0/37 → UNKNOWN (0 observed / 37 runs) |
| MAP-22 | `SUITABLE` | `SUITABLE` | 20 | 20 | 机制触发 0/21 → UNKNOWN (0 observed / 21 runs) |
| MAP-26 | `CEILING` | `CEILING` | 9 | 9 | 机制触发 0/9 → UNKNOWN (0 observed / 9 runs) |
| MAP-30 | `CENSORED` | `CENSORED` | 27 | 27 | 机制触发 0/27 → UNKNOWN (0 observed / 27 runs) |

> 差异只来自**展示口径**修正（未知不再算 0）与有效分母重算；原始历史数据未被修改。

## 4. LIVE 预算表算术复核

- 逐行子局合计：**221**（文件声明 221，一致）
- 逐行原预估合计：¥10.97
- 按 1.5 倍公式重算：¥10.97

| 方案 | 子局 | 上界 CNY | 原预估 | 重算预估 |
|---|---:|---:|---:|---:|
| A | 54 | 27.00 | 2.11 | 2.11 |
| B | 186 | 93.00 | 5.60 | 5.60 |
| C | 221 | 103.75 | 10.97 | 10.97 |

> ``recomputed_estimate_cny`` 按文档自己声明的 1.5 倍余量公式（子局数 × V12 实测均价 × 余量）重算；与 ``estimate_cny`` 不一致的行说明原表未统一使用该公式。

## 5. 适用限制

- `SUITABLE` 只表示**现有样本里出现了成功率梯度**，不构成构念效度充分或因果证据；
- `CEILING` / `CENSORED` 只描述样本形态，不评价地图设计质量；
- 历史 CSV 缺 `prompt_hash` / `contract_version`（DCR-V14-01），
  跨契约隔离只能按实验登记文件进行，不能声称数据层已证明契约一致。
