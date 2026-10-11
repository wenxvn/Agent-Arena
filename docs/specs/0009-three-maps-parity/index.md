# 0009. 三图对照：灯塔扩建 v2 与深海站 v1

**日期**：2026-10-11
**状态**：Accepted（研究对照用）

## 摘要

把三张测试地图的难度拉齐：灯塔由 6 房扩建为 8 房 v2（工具箱搬进地窖深一跳、
加诱饵房/诱饵物/新授权码），新增第三世界深海站 v1（8 房飞船形拓扑、
新名称新授权码）。三张图均为 8 房、双工具链、含诱饵，最优公开路径
16–19 步，全部复用统一 Action/Observation 契约和六个公开工具。

## 决策

- 灯塔 v2（`lighthouse-escape / lighthouse-escape-v2-zh`，`world_id=lighthouse_escape_v2`）：
  8 房：`cliff_base`—`supply_shed`（旧提灯诱饵）—`storage_cellar`（工具箱搬至此，
  含诱饵 `barnacle_glue`）、`workshop_path`—`engine_cave`—`lamp_room` / `skiff_cove`
  （读码前隐藏）、`tide_pool`（礁石诱饵房）。
  授权码换新 `TIDE-3160`，防止跨世界记忆串扰；最优公开路径 16 步。
- 灯塔储物箱可见逻辑泛化为按容器所在房间判定（v1 行为不变，有测试锁定），
  与飞船 v3 同 pattern；`LighthouseV2Environment` 复用全部规则代码，只换 definition。
- 深海站 v1（`abyss-escape / abyss-escape-v1-zh`，`world_id=abyss_escape_v1`）：
  8 房飞船形拓扑：`docking_bay`（起点，`command_console` 读码 + `status_board`
  无电诱饵终端）—`central_tunnel`—`repair_nook`（`sonar_terminal` 诊断）—
  `reactor_trench`（`hatch_cover` 需 `torque_wrench` → `flooded_cell` 需 `fusion_cell`）
  —`escape_capsule`（读码前隐藏）；`cargo_hold`（`supply_crate` 藏双工具 + 诱饵
  `kelp_tape`）；`lookout_dome`—`bunk_pod` 诱饵链。
  授权码 `ABYSS-618`；最优公开路径 19 步，与飞船 v3 持平。
- 深海站规则复用灯塔形谜题链（诊断/开盖/换芯/读码/逃生），里程碑文本用深海措辞，
  `key_items={torque_wrench, fusion_cell}`（诱饵不在清单内）。
- `create_environment` 注册两对新 selector，未知组合仍拒绝；旧世界行为与测试不受影响。
- Fake provider 仍只覆盖飞船 v1 演示路径；新世界真实对照使用 Muse 自主组合
  （memory + history5 + recovery + phase，不限步）。

## 非目标

- 不新增工具、不新增规则类型；不为新世界定制 prompt、记忆或规划逻辑。
- benchmark 的 `tools_collected` 仍按飞船物品判定（已知指标缺口，见 P1-3）；
  新世界阶段结论以 trace 人工统计为准。

## 验收条件

- [x] 灯塔 v2：8 房、双向出口、读码前隐藏 `skiff_cove` 的规则测试通过
  （`tests/test_lighthouse_v2.py`）。
- [x] 灯塔 v2：16 步公开动作序列通关（`ESCAPED`），新码 `TIDE-3160` 生效、
  旧码 `TIDE-2049` 被拒绝为 `INCORRECT_CODE`；诱饵不影响通关。
- [x] 深海站：8 房、双向出口、读码前隐藏 `escape_capsule` 的规则测试通过
  （`tests/test_abyss.py`）。
- [x] 深海站：19 步公开动作序列通关（`ESCAPED`）；无电读码/状态板被拒绝，
  诱饵（穹顶/睡舱/海带胶带）不影响通关。
- [x] `create_environment` 拒绝未知组合；全套 143 passed（含 11 项新测试）。
- [x] Muse 自主组合在三张图完成对照并独立归档：深海站 seed 0（41 步）、
  灯塔 v2 seed 0（56 步）、飞船 v3 seed 2（113 步）/ seed 1（180 步），
  另有飞船 seed 0 两次网关 `provider_error`（73/76 步）；trace 见
  `runs/muse-3maps-*/`（本地生成物）。
