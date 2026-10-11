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
| C011 | 0 | 1 | 1 | **0/5（本轮新跑，见 §8）** | `results/exp-C011-pilot` + `results/exp-C011` + `results/exp-C011-retry` |
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

- `tests/test_phase_prior_audit.py` 通过（见 `01`）。在线补测见 §8（C011 已完成 0/5；C010 仍缺）、§9（React-C111 pilot 完成）。

## 8. 在线补测进展（2026-10-11 EXP-C011，已完成）

- EXP-C011-pilot（memory, H0 R1 P1, B60, 飞船 v1, seed 0）：**`step_limit` 失败**，60 步未逃生。
  trace `runs/episode_20261011T095424Z_memory_seed-0_a7a65f95.json`（provenance verified：
  `recent_history_enabled=false/window 0, stuck_recovery=true, public_phase_context=true, step_limit=60,
  memory_v2, muse-spark-1.3-contributor`）。
  行为：第 20 步读到码（`CODE_READ ALPHA-731`），随后 corridor↔control_room 往返，
  `CODE_READ` 共 9 次（steps 20/21/26/30/32/43/49/52/58），从未前往逃生链。
- EXP-C011（seeds 1–4）+ seed 1 重跑：**C011 格 0/5**（全部 `step_limit`，60 步）。
  seed 1 首跑在 26 步后 `provider_error` 中断（censored，trace `…_seed-1_9c3f5737.json`），
  按停止规则重跑一次仍 `step_limit`（trace `runs/episode_20261011T102929Z_memory_seed-1_04a8d68e.json`）。

| seed | outcome | 重读码 | look | input/output tokens | trace |
|---|---|---|---|---|---|
| 0 | step_limit | 9 次 | 14 | 53k/46k | `runs/episode_20261011T095424Z_memory_seed-0_a7a65f95.json` |
| 1 | step_limit（首跑 provider_error→重跑） | 9 次 | 22 | 55k/29k | `runs/episode_20261011T102929Z_memory_seed-1_04a8d68e.json` |
| 2 | step_limit | 6 次 | 26 | 52k/36k | `runs/episode_20261011T100904Z_memory_seed-2_beabe31e.json` |
| 3 | step_limit | 8 次 | 23 | 52k/38k | `runs/episode_20261011T101536Z_memory_seed-3_0efdf13a.json` |
| 4 | step_limit | 8 次 | 19 | 53k/39k | `runs/episode_20261011T102235Z_memory_seed-4_dfe5a650.json` |

- 交互结论更新：C101（H+P）1/5 vs C011（R+P）**0/5** vs C111（H+R+P）3/5。
  R 在无 H 时不能替代 H（0/5），R 只在有 H 时把 1/5 抬到 3/5——**R 是 H 的放大器，不是独立驱动**。
  H 必要性成立（无 H 的 C000/C010 未测但 C001/C011 均为 0/5；C010 仍缺，R 主效应不可单独判定）。
- 附带观察（reported，需后续验证）：C011 后半程 `decision_reason` 质量坍缩，
  出现 `placeholder`/`abc`/`123`/`1234567890` 等无意义短理由（尤其 seed 3/4 的 look 簇），
  但 Action 仍合法（`invalid_output=0`）。长循环下理由字段先退化，动作接地随后停滞。
- 成本：6 次尝试（含 1 censored 重跑）≈ input 265k / output 188k tokens，模型耗时约 33 分钟。

## 9. M 消融对照（EXP-ReactC111，2026-10-11，已完成）

- EXP-ReactC111-pilot（react, H5 R1 P1, B60, 飞船 v1, seed 0）：**`step_limit` 失败**。
  trace `runs/episode_20261011T103502Z_react_seed-0_e980e788.json`。
- EXP-ReactC111（seeds 1–4）+ seed 4 重跑：**0/4 完成**（seed 4 两次 `provider_error` 记 censored）。
  seeds 0–3 全部 `step_limit`，60 步。

| seed | outcome | 读码次数 | 终点误用 | input/output tokens | trace |
|---|---|---|---|---|---|
| 0 | step_limit | 1 | 1（+`use(screwdriver→pod)` 错码） | 69k/52k | `runs/episode_20261011T103502Z_react_seed-0_e980e788.json` |
| 1 | step_limit | 1 | 1 | 69k/58k | `runs/episode_20261011T104347Z_react_seed-1_8aae6f1f.json` |
| 2 | step_limit | 1 | 1 | 69k/55k | `runs/episode_20261011T105453Z_react_seed-2_00dbbae8.json` |
| 3 | step_limit | 1 | 1 | 69k/53k | `runs/episode_20261011T110329Z_react_seed-3_cc85f548.json` |
| 4 | censored（2×provider_error） | 1/1 | 0/1 | — | `runs/episode_20261011T111523Z_react_seed-4_9ae5ccd6.json` + `…112425Z…_7d6c86b2.json` |

- 统一失败模式（4/4 完成局一致）：22 步前后读到码**恰好 1 次**，随后 reactor_room↔escape_pod
  往返 + 反复 `inspect(escape_pod)`，**忘记授权码内容**——`read_terminal(escape_pod)→wrong_target`
  每局 ≥1 次；seed 0 更以 `use(screwdriver→escape_pod)→incorrect_code`（拿螺丝刀当码）。
  失败分类：`FORGOTTEN_FACT`。与 C011 系（memory 无 H：读码 6–9 次、corridor↔control_room 空转）
  形成双分离：**H 给推进、M 保事实**——React 能走到终点但保不住码，Memory 保住码但无 H 时到不了终点。
- M 主效应结论：同 H5/R1/P1/B60 下，memory（C111 历史 3/5）vs react（本轮 0/4）。
  **M 增益成立**（效应方向明确，n 小，只报效应不报显著性）。
  可比性声明：C111 3/5 为 10-11 早前同模型同条件历史数据，非同日并跑；prompt 差异
  （`memory_v2` vs `react_v12`）即待测变量本身。
- 成本：7 次尝试（含 2 censored）≈ input 460k / output 350k tokens。
