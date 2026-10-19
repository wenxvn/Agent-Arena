# V10 重复运行一致性（同一 map/seed 的第二局）

- 由 `python -m agent_arena.v10.replicate` 生成；只读本地 MiMo 结果。
- 首局 = 有效证据（replicate 0），第二局 = 阶段 15（`-x2-v2`，replicate 1）。
- temperature=0、环境确定；差异只来自 provider 非确定性。n=2，只作描述。

- 计划 90 对；实际第二局 37 局（中断 1），有效配对 **36** 个，覆盖 MAP-01–MAP-12。
- 阶段 15 因全局请求上限（`GLOBAL_REQUEST_LIMIT`）停止；未运行的部分不回写、不补跑，本表只描述已完成的配对。
- 两局都成功 18、都不成功 14；
  成功翻转 2 升 / 2 降；成功率一致 **0.8889**。
- 两局都 `VALID` 的主指标配对 33 个，平均绝对差 `0.121212`。
- 第二局结算 CNY `0.17568800`。

## 1. 逐世界一致性

| 世界 | 配对 | 成功一致 | 翻转 |
|---|---:|---:|---:|
| abyss | 9 | 9 | 0 |
| lighthouse | 9 | 8 | 1 |
| polar | 9 | 9 | 0 |
| spaceship | 9 | 6 | 3 |

## 2. 发生翻转的配对

| 图 | seed | 首局 | 第二局 | 首局主指标 | 第二局主指标 |
|---|---:|---|---|---:|---:|
| MAP-02 | 0 | 失败 | 成功 | 0.0 | 1.0 |
| MAP-03 | 1 | 成功 | 失败 | 1.0 | None |
| MAP-03 | 2 | 成功 | 失败 | 1.0 | None |
| MAP-04 | 1 | 失败 | 成功 | 0.0 | 3.0 |

## 3. 逐配对明细

| 图 | seed | 首局成功 | 第二局成功 | Δ主指标 | Δ非法动作 | Δ决策 |
|---|---:|---|---|---:|---:|---:|
| MAP-01 | 0 | False | False | 0.0 | 0 | 0 |
| MAP-01 | 1 | False | False | 0.0 | 0 | 0 |
| MAP-01 | 2 | False | False | 0.0 | 0 | 0 |
| MAP-02 | 0 | False | True | 1.0 | 0 | -1 |
| MAP-02 | 1 | False | False | 0.0 | 0 | 0 |
| MAP-02 | 2 | False | False | 0.0 | 0 | 0 |
| MAP-03 | 0 | False | False | None | 0 | 0 |
| MAP-03 | 1 | True | False | None | 0 | 2 |
| MAP-03 | 2 | True | False | None | -1 | 1 |
| MAP-04 | 0 | False | False | 0.0 | -1 | -5 |
| MAP-04 | 1 | False | True | 3.0 | 0 | -1 |
| MAP-04 | 2 | False | False | 0.0 | 0 | 0 |
| MAP-05 | 0 | False | False | 0.0 | -2 | 0 |
| MAP-05 | 1 | False | False | 0.0 | -3 | -7 |
| MAP-05 | 2 | False | False | 0.0 | -1 | 1 |
| MAP-06 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-06 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-06 | 2 | True | True | 0.0 | 0 | 0 |
| MAP-07 | 0 | True | True | 0.0 | 0 | 1 |
| MAP-07 | 1 | False | False | 0.0 | 0 | 0 |
| MAP-07 | 2 | False | False | 0.0 | 0 | 0 |
| MAP-08 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-08 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-08 | 2 | True | True | 0.0 | 0 | 0 |
| MAP-09 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-09 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-09 | 2 | True | True | 0.0 | 0 | 0 |
| MAP-10 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-10 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-10 | 2 | True | True | 0.0 | 0 | 0 |
| MAP-11 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-11 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-11 | 2 | True | True | 0.0 | 0 | 0 |
| MAP-12 | 0 | True | True | 0.0 | 0 | 0 |
| MAP-12 | 1 | True | True | 0.0 | 0 | 0 |
| MAP-12 | 2 | False | False | 0.0 | 0 | 2 |

## 4. 结论与边界

- 一致性只说明「同实例、同温度下重复运行的可重复程度」，不替代多 seed 或跨模型证据。
- 翻转与主指标差都只作描述；n=2 不足以估计方差或做显著性检验。

## 5. 复现

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.replicate
```
