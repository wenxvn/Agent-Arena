# 0008. 飞船扩建 v3 与步数不限模式

**日期**：2026-10-11
**状态**：Accepted（研究对照用）

## 摘要

把飞船世界扩建为 8 房（`spaceship-escape-v3-zh`），并增加 `step_limit=0` 表示步数不限，用于探索更大地图下的自主行为与探索效率。

## 决策

- v3 地图：控制室—走廊—维修间—反应堆—逃生舱主链不变；储物箱搬到货舱（维修间分支），走廊分支加观察甲板（诱饵），船员舱（诱饵）；箱内加诱饵物品 `duct_tape`（可拾取、无用）。
- 授权码换新 `BETA-512`，防止跨世界记忆串扰；功能 id（panel/fuse/terminal）与 v1 相同，复用全部规则代码。
- v3 复用 `SpaceshipEscapeEnvironment` 规则（子类只换 definition）；储物箱可见逻辑泛化为按容器所在房间判定（v1 行为不变，有测试锁定）。
- `step_limit=0` = 不限步数：非法输出上限、provider 错误仍可终止；CLI 显示“步数不限”；trace/benchmark 正常记录步数。探索运行由实验者监督，防止 API 空转。
- Fake provider 仍只覆盖 v1 演示路径；v3 真实对照使用 Muse 自主组合。

## 非目标

- 不新增工具、不新增规则类型；里程碑文本沿用飞船版（物品集合仍是 screwdriver/fuse，tape 不在清单内）。
- 不为 v3 定制 prompt、记忆或规划逻辑。

## 验收条件

- [x] 8 房、双向出口、读码前隐藏逃生舱的规则测试通过（`tests/test_spaceship_v2.py`）。
- [x] 19 步公开动作序列通关（`ESCAPED`）；诱饵（胶带/甲板/船员舱）不影响通关且可被拾取/查看（seed 3 拾取胶带后仍通关）。
- [x] `step_limit=0` 可加载运行，成功即停（`test_step_limit_zero_runs_until_success`）；旧测试全过（132 passed）。
- [x] Muse 自主组合（memory + history5 + recovery + phase，不限步）在 v3 完成 5 seeds 对照并独立归档：**5/5 成功**（152/125/153/93/65 步），见 `results/muse-shipv3-unlimited(-s24)/`。
