# 0007. 第二世界：雾岛灯塔

**日期**：2026-10-11
**状态**：Accepted（研究对照用）

## 摘要

新增第二个确定性世界 `lighthouse-escape / lighthouse-escape-v1-zh`（雾岛灯塔），用于检验 Agent 能力是否迁移到未见过的新地图，而非背下飞船路线。它复用统一 Action/Observation 契约和六个公开工具，复用 `ToolReason` 语义，但地图、名称、授权码全部不同，拓扑也不同（链式 + 分支，而非 hub）。

## 决策

- 世界定义：`lighthouse_escape_v1`，6 房：`cliff_base`（起点）—`supply_shed`、`workshop_path`—`engine_cave`—`lamp_room` / `skiff_cove`（读码前不可见）。
- 物品：`wrench`、`spare_cell`（藏于 `tool_chest`，需 inspect 揭示）；谜题链：`engine_cover`（需 wrench）→ `burnt_cell`（需 spare_cell）→ 主电源 → `lamp_console` 读 `TIDE-2049` → `skiff_cove` 用码启动 `harbor_skiff`。
- 最优公开路径 15 步（已用规则动作验证，人可通关）。
- `create_environment` 注册第二对 selector，未知组合仍拒绝；旧世界行为与测试不受影响。
- 飞船专用的 `planner_assisted` 路线、`planner feedback` 不用于新世界；Memory 的通用字段（访问/事实/失败/问题）直接生效。
- 公开阶段上下文已泛化为世界声明的里程碑（`PublicMilestone`）：飞船与灯塔各自声明 5 个检查点文本，Runner 只负责跟踪与渲染，不再内置飞船知识；飞船旧文本逐字保留（有回归测试）。因此 `--phase-context` 可同样用于新世界，且仍属于自主变量（只给清单，不给路线动作）。
- Fake provider 仍只覆盖飞船演示路径；新世界真实对照使用 Muse 自主组合。

## 非目标

- 不改统一 Action schema，不改 Runner/Evaluation，不为新世界定制 prompt 或记忆字段。
- benchmark 的 `tools_collected` 仍按飞船物品判定（已知指标缺口，见 P1-3）；新世界阶段结论以 trace 人工统计为准。

## 验收条件

- [x] 6 房、双向出口、读码前隐藏 `skiff_cove` 的规则测试通过（`tests/test_lighthouse.py`）。
- [x] 15 步公开动作序列通关（`ESCAPED`），非法动作（无电读终端、错物品、错码、未读码启动）均被拒绝。
- [x] `create_environment` 拒绝未知组合；旧契约测试全过（全套 126 passed）。
- [x] Muse 自主组合（memory + history5 + recovery + 通用 phase）在新世界完成 5 seeds 对照并独立归档：5/5 成功（27/28/28/55/57 步），见 `results/muse-lighthouse-h5rp/` 与 `results/muse-lighthouse-h5rp-s14/`。
