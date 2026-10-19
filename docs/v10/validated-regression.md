# V9 已 VALIDATED 图的防回归审计（含 V10 已原生化的图）

- 由 `python -m agent_arena.v10.regression` 生成；V8/V9 只读。
- `runtime=v8_fallback` 的图在 V10 尚无原生运行时；已原生化的图（如 MAP-05）
  按 V10 实例判定。
- `seed_effective` 用初始 Observation + 密封真值指纹比较 seed 0/1/2；三者全不同才算通过。

| 图 | 运行时 | 3 seed 实例不同 | scenario_hash | V9 Oracle | 防回归复跑 | 结论 |
|---|---|---|---|---|---|---|
| MAP-01 | v8_fallback | **否** | c481427b85fca3f9 / 9039732a5bde4c36 / 2fcf352f970700ac | 1/1 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |
| MAP-02 | v10 | 是 | c4700fddb130e1fe / 2990b619abe86949 / eb53782d9d2d44b3 | 2/2 | 通过 | VALIDATED 维持 |
| MAP-05 | v10 | 是 | ea4eaf320fe58f59 / 8fc26a0b58f00988 / d3fd078468758b23 | 2/2 | 通过 | VALIDATED 维持 |
| MAP-16 | v8_fallback | **否** | 2f25fdbd4bf599fb / 2d8480e21efa3919 / 221a96e8e7796745 | 1/1 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |
| MAP-17 | v8_fallback | **否** | d58ab92b846182d5 / 314cae80157d8a14 / 33a129b0f15a2847 | 2/2 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |
| MAP-25 | v8_fallback | **否** | ea0423c71c51c14a / 3fa3a282ce93d510 / 7856e47aee9ab627 | 2/2 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |
| MAP-27 | v8_fallback | **否** | 78e380de815a1e07 / c7333d6e941ce89a / 5b9a8fc58d5e3c29 | 2/2 | 通过 | **3-seed 未达标（保留 VALIDATED 但记缺口）** |

## 汇总

- 3 seed 实例确实不同：MAP-02、MAP-05
- 3 seed 未达标：MAP-01、MAP-16、MAP-17、MAP-25、MAP-27
- 防回归失败：无

3 seed 未达标的图**不撤销** V9 的 VALIDATED（它们的构念证据仍然成立），
但必须在最终报告中列为“多 seed 覆盖缺口”，不能声称已完成 30/30 的 3-seed 验证。
