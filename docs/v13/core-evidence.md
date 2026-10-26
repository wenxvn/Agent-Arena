# 核心证据包：MAP-16 / MAP-18 / MAP-22（P0-6）

- 数据来源：**`HISTORICAL`**（V12 已公开的逐局 CSV，只读）
- 本轮新增真实付费请求：**0**
- 生成方式：`lab/v13/ablation.py::build_evidence_pack`，数字可复算

> 三张图各有不同的问题结构。把它们的成功率放在一起排名是**错的**——
> MAP-16 的梯度在 planning 侧，MAP-18 在 memory 侧，MAP-22 的旧结果还夹着接口假象。

## 1. MAP-16｜Planning 是唯一稳定信号，但代价是 3.6 倍请求

**研究问题**：Planning 在 MAP-16 上是否真的有效？

| 口径 | 值 |
|---|---|
| 总局数 | 35（含 seed 3 与重复实验） |
| 有效分母 | 35 |
| 成功 | 9 |
| 机制失败 | 25 |
| 预算截尾 | 1 |
| 已结算费用 | CNY 0.403642 |

| 实验臂 | 局数 | 有效 | 成功 | 截尾 | 平均请求 | 平均费用 CNY |
|---|---:|---:|---:|---:|---:|---:|
| `planning.v1` | 13 | 13 | 6 | 1 | 27.46 | 0.02395 |
| `reflection.v1` | 4 | 4 | 2 | 0 | 10.00 | 0.00158 |
| `basic.v1` | 9 | 9 | 1 | 0 | 7.67 | 0.00370 |
| `memory.v1` | 9 | 9 | 0 | 0 | 8.44 | 0.00585 |

**结论（`SUPPORTED`，但仅描述性）**：

- 唯一在 3 次观测下稳定成功的条件是 `planning.v1 @ seed=1`（**3/3**）；
- `planning.v1 @ seed=2` 是 2/3（第三次变成预算截尾）；
- 其他 12 个条件全是 0/3；
- **代价**：平均请求 27.46 vs basic 7.67（约 3.6 倍），平均费用也更高。

**反例（必须保留）**：seed 0 上 planning 与 basic 一样是 0/2（第 6 步 `DEADLOCK`）。
说明这张图的失败有一部分是**环境机制在早期锁死**，Planner 来不及介入。

## 2. MAP-18｜梯度在 Memory 侧，Planning 反而更差

**研究问题**：Memory 在 MAP-18 上是否真的有效？

| 口径 | 值 |
|---|---|
| 总局数 | 37（含 seed 3/4 补充） |
| 有效分母 | 37 |
| 成功 | 8 |
| 机制失败 | 29 |
| 预算截尾 | 0 |
| 已结算费用 | CNY 0.435326 |

| 实验臂 | 局数 | 有效 | 成功 | 截尾 | 平均请求 | 平均费用 CNY |
|---|---:|---:|---:|---:|---:|---:|
| `memory.v1` | 15 | 15 | 5 | 0 | 10.47 | 0.01418 |
| `basic.v1` | 11 | 11 | 2 | 0 | 9.18 | 0.00820 |
| `planning.v1` | 11 | 11 | 1 | 0 | 9.27 | 0.01204 |

**结论（`SUPPORTED`，但仅描述性）**：

- 方向与 MAP-16 **相反**：memory 有梯度、planning 反而最差；
- 3 次观测里 `memory.v1 @ seed=0` 是 2/3、`seed=2` 也是 2/3——**部分稳定**；
- 机制解释：MAP-18 的关键是"记住发车窗口与已封区段"，属于**状态追踪**，
  不是"下一步该干什么"。

**反例**：`memory.v1 @ seed=1` 是 0/3（`HEAD_ON_COLLISION` 反复出现），
说明记忆没有帮助它避开对撞。

## 3. MAP-22｜旧结果是接口假象，机制修复后才是真信号

**研究问题**：Memory 的路线记录是否真的被用于返程？

| 口径 | 值 |
|---|---|
| 总局数 | 21（含 `contract-2` 与 `route_log` 消融） |
| 有效分母 | 20 |
| 成功 | 3 |
| 机制失败 | 15 |
| 预算截尾 | 2 |
| 无效（取消/中断） | 1 |
| 已结算费用 | CNY 0.702374 |

| 实验臂（含配置指纹） | 局数 | 有效 | 成功 | 截尾 | 平均请求 | 平均费用 CNY |
|---|---:|---:|---:|---:|---:|---:|
| `basic.v1@fc6e1123` | 6 | 6 | 1 | 1 | 61.0 | 0.02184 |
| `memory.v1@fb8c4623` | 6 | 6 | 0 | 1 | 46.8 | 0.03979 |
| `planning.v1@d5a75e33` | 6 | 6 | 1 | 0 | 51.0 | 0.03553 |
| `memory.v1@59f5933b`（route_log） | 3 | 3 | 1 | 0 | — | — |

**必须写清的三件事**：

1. **主矩阵的 0/3 是接口假象**：`write_memory` 96.2% 被拒（`INVALID_MEMORY_PAYLOAD`），
   根因是公开契约没写清 `facts` 的字段形状（DCR-V12-01）；
2. **键名口径也对不上**：模型写 `path_to_here`，V10 指标只读 `bearing`/`path_state`
   （DCR-V12-02）；
3. **修好之后暴露的是策略问题**：模型只写 1–4 个方位，而真实路线 22–44 步
   （DCR-V12-03）；`route_log` 把 `route_recall` 拉到 0.45 / 0.75 / 1.0，
   `wasted_moves` 34 → 8，seed 2 通关。

**结论**：

- 接口层：`INTERFACE_CONTRACT` + `MEASUREMENT_COVERAGE`（不是能力）；
- 策略层：跨阶段状态维护能力不足（是能力，但只有 3 局，`TENTATIVE`）；
- **不能**把 MAP-22 的旧 0/3 当作"memory 在 MAP-22 无效"的证据。

## 4. 三张图放在一起看

| 图 | 主要失败层 | 有梯度的臂 | 证据强度 | 能不能用来排名 |
|---|---|---|---|---|
| MAP-16 | 环境机制（早期 `DEADLOCK`）+ 策略 | planning（3.6× 请求代价） | `SUPPORTED`（描述性） | 可以，但必须带代价 |
| MAP-18 | 策略（窗口/对撞） | memory | `SUPPORTED`（描述性） | 可以，方向与 MAP-16 相反 |
| MAP-22 | 接口（已修）+ 策略（路线太短） | route_log | `TENTATIVE`（3 局） | **不建议**，样本太少 |

**禁止的合并**：把三张图的成功数相加成"架构总分"。它们的机制不同、样本不同、
版本不同（MAP-22 跨了两次契约版本）。

## 5. 复算方式

```bash
uv run python -c "
import sys; sys.path.insert(0,'src')
from agent_arena.lab.v13.history import load_v12_history
from agent_arena.lab.v13.ablation import build_evidence_pack
recs = load_v12_history()
for m in ('MAP-16','MAP-18','MAP-22'):
    print(build_evidence_pack(m, recs, question='q', source='HISTORICAL').as_dict())
"
```

原始引用：`docs/v12/real-runs/*.csv`（逐局）、`docs/v12/mimo-results.md`（汇总）、
`docs/v12/dcr/DCR-V12-01…03`（缺陷）。

## 6. 下一轮 LIVE 待批准（PLANNED_ONLY）

| 组 | 目标 | 条件数 × 重复 | 单局上界 | 状态 |
|---|---|---|---|---|
| E0 | 采样复现 | 6 条件 × 3 | 90 请求 / 200k / ¥0.50 | `WAITING_USER_APPROVAL` |
| E1 | MAP-22 route_log | 4 条件 × 3 | 90 请求 / 200k / ¥0.50 | `WAITING_USER_APPROVAL` |
| E2 | MAP-16/18 planning | 12 条件 × 3 | 90 请求 / 200k / ¥0.50 | `WAITING_USER_APPROVAL` |

## 7. 不支持的主张

- ❌ "planning 是最优架构"——MAP-18 上它是 1/11；
- ❌ "memory 无效"——MAP-18 上它是 5/15，且 MAP-22 的旧 0/3 是接口假象；
- ❌ "route_log 提升通关率"——3 局、跨配置，只能算机制演示；
- ❌ "三图成功数相加可排名"——机制与样本都不同。
