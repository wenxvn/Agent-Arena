# V10 逐图验收 Gate（Batch 9）

- 由 `python -m agent_arena.v10.validation` 从 `runs/v10/` 逐图判定，不手填。
- 8 个 Gate：`seeds`、`oracle`、`budget`、`mechanism`、`ablation`、`metric`、
  `independent`、`mimo`（判据见模块 docstring）。
- 全部 `agent_reviewed`；不声称 `human_approved`，也不用 Gate 结果替代用户复核。
- **Gate 不包含“模型成功”**：`mimo` Gate 只检查接口对模型可用（非法动作占比 ≤ 50%），
  即 `VALIDATED` 说明“测得住”，不说明“MiMo 能通关”。

| 图 | 运行时 | seeds | oracle | budget | mechanism | ablation | metric | independent | mimo | 判定 |
|---|---|---|---|---|---|---|---|---|---|---|
| MAP-01 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-02 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-03 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-04 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-05 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-06 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-07 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-08 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-09 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-10 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-11 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-12 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-13 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-14 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-15 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-16 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-17 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-18 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-19 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-20 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | `NEEDS_MORE_EVIDENCE` |
| MAP-21 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-22 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-23 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-24 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-25 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-26 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-27 | v8 | — | — | — | — | — | — | — | — | `VALIDATED`（V8 回退，3-seed 缺口） |
| MAP-28 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-29 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |
| MAP-30 | v10 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `VALIDATED` |

## 汇总

- `VALIDATED`（V10 原生，8 Gate 全过）：22 图 —— MAP-03、MAP-04、MAP-06、MAP-07、MAP-08、MAP-09、MAP-10、MAP-11、MAP-12、MAP-13、MAP-14、MAP-15、MAP-18、MAP-19、MAP-21、MAP-22、MAP-23、MAP-24、MAP-26、MAP-28、MAP-29、MAP-30
- `NEEDS_MORE_EVIDENCE`：1 图 —— MAP-20
- V8 回退维持 `VALIDATED`（记 3-seed 缺口）：7 图 —— MAP-01、MAP-02、MAP-05、MAP-16、MAP-17、MAP-25、MAP-27

## 未通过项明细

- **MAP-20**
  - Gate `mimo` 未通过：有效局 3；其中接口可用 0；非法率上限 0.5
