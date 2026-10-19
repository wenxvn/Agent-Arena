# V9 已 VALIDATED 图的防回归审计（含 V10 已原生化的图）

- 由 `python -m agent_arena.v10.regression` 生成；V8/V9 只读。
- 全部图均已有 V10 原生运行时（V8 回退为 0），本表按 V10 实例判定；
  `runtime=v8_fallback` 只保留为历史兼容值。
- `seed_effective` 用初始 Observation + 密封真值指纹比较 seed 0/1/2；三者全不同才算通过。

| 图 | 运行时 | 3 seed 实例不同 | scenario_hash | V9 Oracle | 防回归复跑 | 结论 |
|---|---|---|---|---|---|---|
| MAP-16 | v10 | 是 | 5228a6395f3d9fd7 / c6f8209e96f8ef5c / 2f7fbc072cca51c1 | 1/1 | 通过 | VALIDATED 维持 |

## 汇总

- 3 seed 实例确实不同：MAP-16
- 3 seed 未达标：无
- 防回归失败：无

若出现 3 seed 未达标的图，**不撤销** V9 的 VALIDATED（构念证据仍然成立），
但必须在最终报告中列为“多 seed 覆盖缺口”，不能声称完成 30/30 的 3-seed 验证。
本轮无未达标图。
