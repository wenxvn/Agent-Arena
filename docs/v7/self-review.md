# V7 机器自审与第二遍核对记录

> 日期：2026-10-17。基线提交：`6320660cbe2d7b774c44db5eb9dcee0d311a0410`。
> 性质：**执行模型的 self-review / second-pass check，不是人工签署**。30 张设计卡的
> `review_status` 仍为 `pending_human_review`，12 条 DCR 仍为 `proposed`。

## 1. 本轮实际执行的检查

| 检查 | 命令 | 结果 |
|---|---|---|
| 注册表与卡片一致性 | `.venv\Scripts\python.exe scripts\validate_v7_metrics.py` | 154 specs / 30 maps / 6 runtime / 24 design-only；29 个 V6 solver episode 离线回放通过 |
| 卡片结构自审 | `.venv\Scripts\python.exe scripts\audit_v7_cards.py` | 30 cards，13 个必需小节齐全，0 findings；154 条指标全部被卡片引用 |
| V7 定向测试 | `.venv\Scripts\python.exe -m pytest tests\test_v7_metrics.py tests\test_v7_map_metrics.py tests\test_v7_hand_traces.py tests\test_v7_leakage.py tests\test_v7_cards.py -q` | 90 passed |
| 泄漏与只读检查 | `.venv\Scripts\python.exe scripts\check_v7_leakage.py` | 12 个 V7 源文件、64 份 V7 文档，无禁止导入、无文件写入、无凭据形状文本 |
| 全量测试 | `.venv\Scripts\python.exe -m pytest -q` | 649 passed；详见 `docs/v7/validation-report.md` |

## 2. 六张运行图的手工校验覆盖

`tests/test_v7_hand_traces.py` 为 MAP-08/16/18/22/26/30 各写 6 条真实环境重放轨迹，
共 36 条；全部使用冻结 V4 环境与 V6 求解器/手写动作，不调用 provider，不写 `runs/`。

| 地图 | 成功 | 机制失败 | 边界/截尾 | 缺失态 | 关键断言示例 |
|---|---|---|---|---|---|
| MAP-08 | X-first、Y-first | 错误密封、超水位 | 7.0 恰好成功、截尾 | 只测试不修复 | `peak_core_water=7.0`、`wrong_repair=1` |
| MAP-16 | L1、L3 | 节点容量、相向交换 | 截尾、无预约 | 失败局 gap N/A | `makespan_gap=0`、`head_on_conflicts=1` |
| MAP-18 | 无故障、带恢复 | 相向碰撞、站容量 | 截尾、deadline | 无故障 first_reroute N/A | `first_reroute_delay=6`、`service_rate=0.0` |
| MAP-22 | L1 最短、30 步边界 | 预算耗尽 | 非法方位、截尾 | 失败局 path_gap N/A | `path_gap=22`、`repeated_public_edge_rate=0.3` |
| MAP-26 | 诊断后修复、纠错恢复 | 两次不同错误、同错重复、忽略反证 | 截尾 | 首次成功 recovery N/A | `repeat_error_rate=0.5`、`spares_remaining=0` |
| MAP-30 | 完整链、纯召回 | 连续猜人、缺 Q4、调换时间 | 截尾 | 无指控时 q4 CENSORED | `accusation_claim_precision=0.0`、`unsupported=2` |

## 3. 第二遍核对发现并修正的问题

1. **MAP-22 的 30 步 DFS 手算轨迹不可重放**：原卡路径在返回 A 时提前成功，且“15 条边各走两次、有向重复率 0”在 12 节点/15 边图上不成立（奇度节点使欧拉回路不存在）。已改为可重放的 30 步巡游，实测 `path_gap=22`、`repeated_public_edge_rate=0.3`。
2. **MAP-22 的 18 步轨迹重复率写错**：原卡把 3 条无向重复边写成有向重复率 0.1667；按当前公开签名代理，E/H 粗形与出口相同被并为一个位置，实测为 0.0556。已在卡片中注明代理局限。
3. **MAP-30 的 F03 精确率写错**：调换两事件后匹配 1 项、额外 2 项，按 `max(0, 1−2)/3` 应为 0.0，不是 1/3。已修正卡片。
4. **MAP-22 `path_gap` 计入了被拒绝的 move**：原实现按 `move` 动作数计，非法方位会把 gap 多加 1；已改为读取成功终局 observation 的 `movement_steps`，并补了非法方位 fixture。
5. **`MetricSpec` 缺 `valid_range`**：已增加字段与单位推导，154 条规范全部带非空合法范围；比例/0-1/水位/有符号损失分别显式处理。

这些修正只改 V7 卡片、V7 只读指标层和测试，不改 V4/V5/V6 的 Oracle、规则、账本、注册表或原始 trace。

## 4. 卡片独立性与批量生成检查

- 30 张卡片均有 13 个必需小节；每图 4–8 条独立指标；`audit_v7_cards.py` 0 findings。
- 154 条指标中，`completion_ticks`、`legal_action_rate`、`fuel_consumed`、`query_budget_overruns` 是预登记的通用成本/接口指标族；剔除这些通用族后，最高构念文本相似度为 0.8，出现在 MAP-07 `overpressure_ticks` 与 MAP-19 `critical_overheat_ticks`，两者是不同物理机制，不是同一公式换名。
- 逐图阻塞项、第一刀、指标契约和验收门槛已写入 `docs/v7/pending-runtime/MAP-XX.md`（24 份），`README.md` 只做总表与共同门槛。

## 5. 仍然不能由执行模型完成的事项

| 事项 | 状态 | 原因 |
|---|---|---|
| 30 张卡片人工签署 | `pending_human_review` | 需要人明确批准；执行模型不能代签 |
| `V7-DCR-001..012` | `proposed` | 涉及规则/字段/窗口裁定，必须人工决定 |
| 24 张设计图的运行时 | `design_only` | 本轮只交付设计卡、指标契约与准入说明 |
| 真实 V7 模型数据 | 无 | 默认全离线，未获单独付费授权 |
| 全仓 Ruff 绿 | 未达成 | 653 个既有错误全部在未修改的 `worlds/v4/MAP-*/planning/*.py`；V7 定向检查全绿；全仓 mypy 100 个源文件通过 |

## 6. 自审判定

机器侧可验证项已通过：结构、注册表、六图 36 条手算轨迹、缺失/截尾分支、只读与泄漏扫描、
24 图准入文件。**这不等于人工验收，也不等于 24 图已可运行。** 在人工签署 30 张卡并裁定
12 条 DCR 之前，V7 只能表述为“设计卡与六图离线指标层已交付，人工复核待完成”。
