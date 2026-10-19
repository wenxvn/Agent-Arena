# V10 动作循环扫描（重复动作 + tick 不推进）

- 由 `python -m agent_arena.v10.trace_scan` 生成；只读本地 MiMo trace。
- 判据：连续 ≥8 次完全相同的动作，且期间 `tick` 不变；
  `invalid_output` 归为接口/格式问题。
- `current_rules=是` 表示该局使用的 `rule_hash` 与当前地图一致，属于**仍可行动**的缺陷；
  历史局（`rule_hash` 不同）只作记录，不回写。

- 扫描 **122** 局；命中 **10** 局（免费动作循环 7、无效输出循环 3）；其中当前规则下仍有 **0** 局免费动作循环。

## 1. 命中局

| 图 | run_id | 决策 | 最长重复 | tick 跨度 | 判定 | 当前规则 |
|---|---|---:|---:|---:|---|---|
| MAP-18 | `V10-MAP-18-S0-p0` | 20 | 20 | 0 | `INVALID_OUTPUT_LOOP` | 是 |
| MAP-18 | `V10-MAP-18-S1-p0` | 20 | 20 | 0 | `INVALID_OUTPUT_LOOP` | 是 |
| MAP-18 | `V10-MAP-18-S2-p0` | 20 | 20 | 0 | `INVALID_OUTPUT_LOOP` | 是 |
| MAP-19 | `V10-MAP-19-S0-i2` | 60 | 50 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-19 | `V10-MAP-19-S1-i2` | 60 | 57 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-19 | `V10-MAP-19-S2-ext-r2` | 60 | 59 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-19 | `V10-MAP-19-S2-i2` | 43 | 39 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-20 | `V10-MAP-20-S0-j2` | 56 | 56 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-20 | `V10-MAP-20-S1-j2` | 56 | 56 | 0 | `FREE_ACTION_LOOP` | 否 |
| MAP-20 | `V10-MAP-20-S2-j2` | 56 | 56 | 0 | `FREE_ACTION_LOOP` | 否 |

## 2. 逐图分布

| 图 | 免费动作循环 | 无效输出循环 |
|---|---:|---:|
| MAP-18 | 0 | 3 |
| MAP-19 | 4 | 0 |
| MAP-20 | 3 | 0 |

## 3. 结论

- 真正的免费动作循环只出现在 MAP-19 与 MAP-20；两图已分别在 DCR-V10-39 / DCR-V10-38
  的公开规则中补上“只有 wait 推进时间”，当前规则下不再命中。
- MAP-18/28 的命中是旧动作契约下的 `invalid_output` 循环，已由 DCR-V10-24 修复；
  历史局保留，不回写。
- MAP-12 的重复 `assign` 每天正常结算（tick/日期在推进），不属于本缺陷。

## 4. 复现

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.trace_scan
.venv\Scripts\python.exe -m agent_arena.v10.trace_scan --check
```
