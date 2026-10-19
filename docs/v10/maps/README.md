# V10 逐图审计卡（30 张）

- 由 `python -m agent_arena.v10.map_cards` 生成；数字来自 `runs/v10/` 可复算产物。
- 每张卡包含：目标构念、公开信息边界、合法动作、seed 与实例差异、主次指标、消融、
  MiMo 证据、结论与证据索引。
- 状态一律标 `agent_reviewed`；不得据此声称 `human_approved`。

| 图 | 世界 | 难度 | 构念 | 效度状态 | 运行时 |
|---|---|---|---|---|---|
| [MAP-01](MAP-01.md) | 飞船 | 简单 | FORCED | VALIDATED | `v10` |
| [MAP-02](MAP-02.md) | 飞船 | 中等 | FORCED | VALIDATED | `v10` |
| [MAP-03](MAP-03.md) | 飞船 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-04](MAP-04.md) | 灯塔 | 简单 | OPTIONAL | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-05](MAP-05.md) | 灯塔 | 中等 | FORCED | VALIDATED | `v10` |
| [MAP-06](MAP-06.md) | 灯塔 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-07](MAP-07.md) | 深海站 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-08](MAP-08.md) | 深海站 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-09](MAP-09.md) | 深海站 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-10](MAP-10.md) | 极地 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-11](MAP-11.md) | 极地 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-12](MAP-12.md) | 极地 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-13](MAP-13.md) | 金字塔 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-14](MAP-14.md) | 金字塔 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-15](MAP-15.md) | 金字塔 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-16](MAP-16.md) | 地铁 | 简单 | FORCED | VALIDATED | `v8` |
| [MAP-17](MAP-17.md) | 地铁 | 中等 | FORCED | VALIDATED | `v8` |
| [MAP-18](MAP-18.md) | 地铁 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-19](MAP-19.md) | 火山 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-20](MAP-20.md) | 火山 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-21](MAP-21.md) | 火山 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-22](MAP-22.md) | 丛林 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-23](MAP-23.md) | 丛林 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-24](MAP-24.md) | 丛林 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-25](MAP-25.md) | 月球 | 简单 | FORCED | VALIDATED | `v10` |
| [MAP-26](MAP-26.md) | 月球 | 中等 | OPTIONAL | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-27](MAP-27.md) | 月球 | 困难 | FORCED | VALIDATED | `v10` |
| [MAP-28](MAP-28.md) | 古堡 | 简单 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-29](MAP-29.md) | 古堡 | 中等 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |
| [MAP-30](MAP-30.md) | 古堡 | 困难 | FORCED | NEEDS_MORE_EVIDENCE | `v10` |

## 覆盖说明

- V10 原生运行时：28 张；V8 回退：2 张（01/02/05/16/17/25/27，3-seed 缺口见 `validated-regression.md`）。
