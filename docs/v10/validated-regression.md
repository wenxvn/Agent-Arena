# V9 已 VALIDATED 图的防回归审计（含 V10 已原生化的图）

- 由 `python -m agent_arena.v10.regression` 生成；V8/V9 只读。
- `runtime=v8_fallback` 的图在 V10 尚无原生运行时；已原生化的图（如 MAP-05）
  按 V10 实例判定。
- `seed_effective` 用初始 Observation + 密封真值指纹比较 seed 0/1/2；三者全不同才算通过。

| 图 | 运行时 | 3 seed 实例不同 | scenario_hash | V9 Oracle | 防回归复跑 | 结论 |
|---|---|---|---|---|---|---|
| MAP-16 | v8_fallback | **否** | 2f25fdbd4bf599fb / 2d8480e21efa3919 / 221a96e8e7796745 | 1/1 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |
| MAP-17 | v8_fallback | **否** | d58ab92b846182d5 / 314cae80157d8a14 / 33a129b0f15a2847 | 2/2 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |

## 汇总

- 3 seed 实例确实不同：无
- 3 seed 未达标：MAP-16、MAP-17
- 防回归失败：无

3 seed 未达标的图**不撤销** V9 的 VALIDATED（它们的构念证据仍然成立），
但必须在最终报告中列为“多 seed 覆盖缺口”，不能声称已完成 30/30 的 3-seed 验证。
