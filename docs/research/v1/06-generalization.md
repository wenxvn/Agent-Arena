# V1-06 随机 seed 与泛化（T6）

## 1. 研究目的

区分“同一固定地图重跑成功” vs “不同实例成功”；区分“换背景名” vs “任务结构变化”。

## 2. seed 审计（verified）

- 三世界 `_initial_state(seed)` 均只 `WorldState(seed=seed, current_room=start)`（飞船 `worlds/spaceship_escape.py:222-223`、灯塔 `:186-187`、深海 `:206-207`），无 `random`/`hash(seed)`，`definition` 为 frozen Pydantic，构造时已定。
- 当前“5 seeds”=**同一固定地图的 5 次模型尝试（replicate id）**，不是 5 个随机地图。`benchmark` 按 seed 循环但环境 definition 不变（`cli.py:279-281`、`runner.py:83`）。
- 测试锁定：`tests/test_seed_replicate.py` 断言同 seed 可复现、异 seed 同地图（房间数/授权码不变）。

## 3. 版本机制（verified）

- 9 JSON 均无 hash 字段；`identity=(world, world_version, definition_id, sha256(definition))`（飞船 `:168-176`），任一字符改动即换 hash。
- `create_environment` 9 分支白名单 + 双重校验（`worlds/__init__.py:60-96`、`runner.py:80-82`），未知组合 `ValueError`（回归 `test_experiment_contract.py:29-55`）。
- 旧九图测试锁定房间数/双向连通/精确路线/授权码/诱饵/里程碑文案（见 `00` 引用的 10+ 测试文件）。**随机化必须走新 world version，不改旧 JSON 一字节。**

## 4. 最小随机化方案（已实施，见 §7）

- 维度（一次只做一个）：首选**工具/物品位置置换**（`random.Random(seed).shuffle` 分配关键工具+诱饵到候选容器，保证两工具不在同一容器）；次选岔路开关（`seed%2` 封堵等长旁路之一）；再次选诱饵分布。
- 要求：固定 seed 可复现（纯函数 `build_variant_definition`，同 `(version,seed)` hash 相等）；异 seed 异实例（20 seeds 去重 hash>1）；每实例 BFS oracle 有合法公开解（≤30 步）+ 脚本化 oracle `is_success` + `CODE_UNREAD` 门未绕过。
- 位置：新建 `worlds/variants.py` + `*RandomDefinition/*RandomEnvironment`（继承复用规则，规则零改动）；`benchmark.py:143-152` 的 condition 已含 hash，聚合展示需按 hash 分面。
- 本轮交付：生成器/测试/冒烟 **not run**（blocked：需新 spec + 旧九图回归网全过；资源不足时先完成设计）。

## 5. 新任务结构族（设计）

- `supply-triage` 小图（5–6 房）：氧/电双约束资源优先级 + 双逃生路线互斥分支（成本随 seed 翻转）+ 氧/电/通讯多条件并行收集。仍用 6-tool 同一 `Action` schema，只改世界规则与里程碑。
- `PublicMilestone` 防泄漏：`key_items` 只放已进包物品名、`trigger_reasons` 只用公开 `ToolReason`、阶段文本只讲“已完成/未完成”不讲“去哪”（机制见 `arena/models.py:94-111` + `runner.py:791-827`）。

## 6. 评估维度

固定环境重跑可靠性 / seed 实例迁移 / 任务结构迁移三层分别汇报，绝不合并成“泛化成功率”。本轮：审计 + 设计完成，独立评测 **not run**。

## 7. 在线验证（2026-10-11 EXP-SeedSmoke，已完成）

- 实现：`spaceship-escape-v5-zh-seeded`（`worlds/variants.py` + 新 JSON + 注册表；
  三候选容器取二、固定 seed 可复现、20 seeds 多哈希；oracle 程序化通关 seeds 0–4；
  旧九图零改动）。提交 `ac9da24`。
- EXP-SeedSmoke（memory+E1, H5 R1 P1, B60, seeds 0–2）：**3/3 成功**（32/57/42 步，
  `invalid=0`）。布局：seed0（储藏箱+维修箱）、seed1/2（走廊柜+维修箱，同一哈希）——
  2 种未见过的新布局全部一次通过，57 步的 seed1 显示布局难度确有差异。
- benchmark 按 `world_definition_hash` 自动分成 2 个 condition（`aggregates=null`），
  恰好验证了审计中的警告：多实例均值无意义，必须按 hash 分面汇报，此处只报逐实例结果。
- 结论边界：支持“同任务结构下的实例迁移”（n=2 布局）；不支持跨任务结构泛化
  （`supply-triage` 族仍为设计，未实施）；授权码沿用 ALPHA-731，如实披露。
- 成本：3 局 ≈ input 192k / output 86k tokens，无中断。
