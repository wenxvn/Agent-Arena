# V10 古堡三图的决策预算剖面

- 由 `python -m agent_arena.v10.trigger_gap` 生成；只读既有 MiMo trace 与基线产物。
- 目的：判断 28/29/30 的失败是“预算过紧”还是“策略在案卷链上打转”。

| 图 | seed | 决策/预算 | Oracle 动作 | 终止 | 机制触发 | 主指标 | 动作直方图 |
|---|---:|---|---:|---|---|---|---|
| MAP-28 | 0 | 20/30 | 18 | ALL_CLAIMS_SUPPORTED_AND_CORRECT | 是 | 1.0 | `interview`×1、`investigate`×2、`move`×10、`read_record`×1、`record`×5、`submit`×1 |
| MAP-28 | 1 | 30/30 | 18 | decision_budget_exhausted | 否 | None | `interview`×1、`investigate`×4、`move`×17、`read_record`×2、`record`×5、`submit`×1 |
| MAP-28 | 2 | 30/30 | 18 | decision_budget_exhausted | 否 | None | `interview`×5、`investigate`×3、`move`×18、`read_record`×1、`record`×3 |
| MAP-29 | 0 | 38/38 | 22 | decision_budget_exhausted | 否 | 0.0 | `ask`×8、`compare_testimony`×1、`investigate`×16、`move`×13 |
| MAP-29 | 1 | 38/38 | 22 | decision_budget_exhausted | 否 | 0.0 | `ask`×8、`compare_testimony`×1、`investigate`×12、`move`×17 |
| MAP-29 | 2 | 38/38 | 22 | decision_budget_exhausted | 否 | 0.0 | `ask`×8、`compare_testimony`×3、`investigate`×6、`move`×21 |
| MAP-30 | 0 | 46/46 | 31 | decision_budget_exhausted | 是 | 0.75 | `compare_records`×5、`inspect`×4、`interview`×6、`move`×17、`record`×14 |
| MAP-30 | 1 | 46/46 | 31 | decision_budget_exhausted | 是 | 0.5 | `inspect`×8、`interview`×6、`move`×21、`record`×11 |
| MAP-30 | 2 | 46/46 | 31 | decision_budget_exhausted | 是 | 0.5 | `compare_records`×1、`inspect`×7、`interview`×4、`move`×21、`record`×13 |

## 最后 5 个动作（每局）

- `V10-MAP-28-S0-i2`：
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - submit→ALL_CLAIMS_SUPPORTED_AND_CORRECT
- `V10-MAP-28-S1-i2`：
  - submit→INVALID_LOCATION
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
- `V10-MAP-28-S2-i2`：
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - interview→TARGET_NOT_VISIBLE
  - move→MOVE_SUCCEEDED
- `V10-MAP-29-S0-castle`：
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
- `V10-MAP-29-S1-castle`：
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
  - investigate→TARGET_NOT_VISIBLE
- `V10-MAP-29-S2-castle`：
  - compare_testimony→INSUFFICIENT
  - move→MOVE_SUCCEEDED
  - move→MOVE_SUCCEEDED
  - ask→NO_ADDITIONAL_KNOWLEDGE
  - ask→ANSWER_RECEIVED:B_TIME_BASIS_STOPPED_0005
- `V10-MAP-30-S0-castle`：
  - record→ENTRY_RECORDED:EVENT_3_SIGNAL
  - move→MOVE_SUCCEEDED
  - record→ENTRY_RECORDED:EVENT_1_HANDOFF
  - record→ENTRY_RECORDED:Q4_CODEBOOK
  - compare_records→CHAIN_INCOMPLETE
- `V10-MAP-30-S1-castle`：
  - inspect→EVIDENCE_ALREADY_TAKEN
  - interview→ANSWER_RECEIVED:T_WITNESS_ROPE_ROUTE
  - record→ENTRY_RECORDED:EVENT_2_WAX
  - move→INVALID_MOVE
  - move→MOVE_SUCCEEDED
- `V10-MAP-30-S2-castle`：
  - record→EVIDENCE_NOT_AVAILABLE
  - move→INVALID_MOVE
  - move→MOVE_SUCCEEDED
  - inspect→EVIDENCE_ALREADY_TAKEN
  - record→ENTRY_RECORDED:EVENT_3_SIGNAL

## 判读

- 若 `决策/预算` 用满且 Oracle 动作数明显更少 ⇒ 预算是绑定约束，
  但“更少的动作就能完成”说明
  模型在案卷链上打转（重复 investigate / move / record），属策略问题而非地图不可解。
- 若主指标已非 0（如 MAP-30 的 0.5–0.75）而终止是预算耗尽 ⇒ 目标是可被部分完成的，
  缺的是“收尾提交”这一步。
- 结论用于 V11 的预算与提示设计，不改变本阶段的难度标签。

## 复算

```powershell
.venv\Scripts\python.exe -m agent_arena.v10.trigger_gap
```
