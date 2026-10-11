# V1-03 因子消融 H/R/P（T3）

## 1. 研究问题与假设

- 问题：Memory+H5+R+P+unlimited 的成功中，哪个变量有效、哪些互补？是真实策略改善，还是更大预算/任务先验？
- 假设：H/R/P 有主效应与交互；P 含世界声明先验，需单独审计。

## 2. 条件（冻结对照）

- 模型 `muse-spark-1.3-contributor`；world 飞船 v1（`spaceship-escape-v2-zh`）；prompt `memory_v2/base react_v12_autonomous`；预算 B=60（除注明）；seeds 0–4。
- 变量定义（verified，实现位置）：
  - M：`agents/memory.py:61-167` 规则结构化记忆（对比 `react` vs `memory`）。
  - H：`evaluation/runner.py:52,67,175,358-360,830-842` 最近 5 步公开观察-动作-结果。
  - R：`evaluation/loop.py:14-89` 公开循环检测 + `runner.py:343-348` 反馈（注意 CLI 联动 `runtime_feedback`，`cli.py:164,169`）。
  - P：`evaluation/runner.py:57,71,86-88,791-827` + `arena/models.py:94-112` 世界声明里程碑。
  - B：`config.py:67`（0=不限），`runner.py:177,398-406`。

## 3. Phase 先验审计（verified）

- P **含未探索物品名**：首里程碑 `missing=key_items - inventory` 直接报精确 ID（飞船 `{screwdriver,replacement_fuse}` 见 `worlds/spaceship_escape.py:126-132`；灯塔/深海同理）。即使从未 inspect，也提前获知存在与 ID。
- P **含阶段顺序先验**：5 段 stage/done/undone 即任务分解骨架（飞船 `:133-156` 收集→开板→电源→读码→逃生）。
- P **不含**：房间/容器映射、授权码值（码仅经 `CODE_READ` 公开）、`WorldState`。
- 自主性等级（本报告起执行）：
  1. 纯 observation（H/R 关闭、P 关闭）；
  2. observation-derived（H/R 开：只能从已见事实归纳）；
  3. **world-declared guidance（P 开：世界预定义任务辅助）**——主成绩 `C111` 属此档，不得称“纯自主规划”；
  4. 给定路线/动作建议（`planner_assisted`/guarded，不计入自主）。
- 测试锁定：`tests/test_phase_prior_audit.py` 断言 P 文本在零探索时即含关键物品名与固定阶段顺序。

## 4. 八格矩阵（M=1，B=60，飞船 v1，verified）

| 条件 | H | R | P | 结果 | 目录 |
|---|---|---|---|---|---|
| C000 | 0 | 0 | 0 | 0/5 | `results/muse-memory-s60` |
| C100 | 1 | 0 | 0 | 0/5 | `results/muse-memory-s60-h5` |
| C010 | 0 | 1 | 0 | **缺失** | 需补 |
| C001 | 0 | 0 | 1 | 0/5 | `results/muse-memory-s60-p` |
| C110 | 1 | 1 | 0 | 0/5 | `results/muse-memory-s60-h5r` |
| C101 | 1 | 0 | 1 | 1/5 | `results/muse-memory-s60-h5p` |
| C011 | 0 | 1 | 1 | **缺失（最关键）** | 需补 |
| C111 | 1 | 1 | 1 | 3/5（复验 seeds5-9：2/5） | `results/muse-memory-s60-h5rp(-s59)` |

不可比（verified）：`muse-memory-s30-h5rp`（B30 0/5）、`shipv3-unlimited`（B0 3/3）、灯塔/深渊各格（地图不同）均不得并入上表。
Memory vs React（M 主效应）：代码正交（`cli.py:417-431` agent 选择与 H/R/P 开关独立；`runner.py:427-433` 同一调用路径），但实证缺失——现有 `muse-react-autonomous` 仅 C000/B30 0/5，无 `React-C111`。**not verifiable**，需补。

## 5. 结论（可判/不可判）

- 可判：单变量 H-only/P-only/H+R 均为 0/5（B60），P 必须与 H 联动才有 1/5（C101）；C111 3/5 高出 C101 2/5，疑为 R 贡献，但 R 从未在无 H 下测过——**交互不可判**，缺 C011。
- 可判：预算效应独立存在（C111 在 B30 0/5、B60 3/5、unlimited 主成绩 45/45），不得把跨预算差值当架构收益。
- 不可判：M 本身增益（缺 React-C111）；P 中“物品名”与“阶段顺序”各自贡献（需第二层拆分：`no phase` vs `observation-derived progress` vs `world-declared milestone`，后者已立项未跑）。
- 小样本声明：n=5，只报效应大小与逐局轨迹，不做显著性包装。

## 6. 最小补测（登记后执行，本轮未跑）

1. 首选 `C011`（H0 R1 P1，B60，飞船 v1，seeds0-4）：闭合三阶交互缺环。若 >0 则 R+P 可部分替代 H；若 =0 则 R 必须与 H 联动。
2. 次选 `React-C111`（同 H/R/P/B，agent=react）：隔离 M 主效应。
3. 命令形（示意）：`benchmark --agent memory --recent-history 0 --stuck-recovery --phase-context`（B60，seeds0-4，`--autonomous` 基座）。
4. 预算表：每格 5 局 × 均值 60 步 × 单步 1 模型调用 ≈ 300 调用 + Planner 外；`provider_error` 中断单列重跑，不混分母。

## 7. 测试与 CI

- `tests/test_phase_prior_audit.py` 通过（见 `01`）。消融新跑 0 局（blocked：需模型预算与 `00` 登记；本轮只交付矩阵与审计）。
