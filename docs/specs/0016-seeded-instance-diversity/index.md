# 0016. Seeded 实例多样性与预注册 holdout

**日期**：2026-10-13

**状态**：Accepted（运行时 hash 与冻结清单一致；模型评估待 S2 Gate）

## 背景

V2 S5.2 的长尾分析发现，现有 lunar/pyramid seeded v2 在 seed 0–999 各只有
2 种布局，未声明 difficulty。原 v2 与 trace 必须保留，不能通过重写旧定义或
筛除长尾实例来补覆盖。本决策建立两个独立的新版本，并要求在任何 prompt 或
Agent 模块调整前冻结实例 hash、oracle 难度标签和 dev/test 划分。

## 决策

### 版本与布局全集

- 新选择器为 `lunar-escape / lunar-escape-v3-seeded-zh` 与
  `pyramid-escape / pyramid-escape-v3-seeded-zh`。现有 v2 seeded 选择器、定义、
  历史 Trace 和 seed→布局映射保持不变。
- 两张新图沿用 v2 的房间、出口、谜题与规则。每张图定义 6 个候选工具容器，
  每个实例启用其中 2 个；每个激活容器分得一半工具。未激活容器不进入该实例
  房间的 `object_ids`，因此不会出现在公开 Observation 中，也不会表现成空容器。
- lunar 候选点：`depot_crate` / `depot_store`、`spare_crate` / `cupola`、
  `tunnel_cache` / `regolith_tunnel`、`telemetry_case` / `telemetry_nook`、
  `reactor_cache` / `reactor_bay`、`auxiliary_crate` / `aux_bay`。
- pyramid 候选点：`relic_chest` / `relic_store`、`sand_crate` / `mural_hall`、
  `tunnel_cache` / `sand_tunnel`、`survey_case` / `survey_nook`、
  `crypt_crate` / `engine_crypt`、`priest_coffer` / `priest_cell`。
- 全集按候选容器对与工具分配穷举：lunar 为
  `C(6,2) × C(4,2) = 90` 个实例；pyramid 为 `C(6,2) × 2 = 30` 个实例。
  seed 不进入 `instance_hash`；相同完整世界定义必须得到同一个稳定 hash。
- 先按规范化的完整世界定义计算 stable hash，再按 hash 排序构成布局全集。
  seed 到全集索引使用 world-version 派生的固定 affine permutation；步长与全集
  大小互质，所以 seed `0..N-1` 一一覆盖 N 个布局，后续 seed 周期重复。算法
  不依赖 Python `random` 或进程 hash 顺序。

### Oracle 难度与 holdout

- 难度只在同一地图版本内比较，以当前 FlexEnvironment 规则下 BFS 的最少动作数
  预先标记 `simple` / `complex`；不得使用模型成功、步数或 Trace 选择阈值。
- 六点全集离线原型结果：lunar 的最少动作数为 17/18/19/20/22，频数分别为
  24/12/6/36/12；pyramid 为 12/14/16/18，频数分别为 6/12/10/2。由该完整
  离线全集固定阈值：lunar `simple ≤18`、`complex ≥19`；pyramid `simple ≤14`、
  `complex ≥16`。它们是地图内的路线难度标签，不能解释成跨地图难度等价。
- 每个唯一 `instance_hash` 只属于一个 split。分别在
  `world_version × difficulty_label` 桶内按固定 SHA-256 排序，约 1/3 标为 test、
  其余标为 dev；每个 seed 继承其布局 hash 的唯一 split。清单在模型运行和任何
  prompt/模块开发前生成、提交并冻结。test 结果只用于预先声明的最终评估，不用于
  prompt、记忆策略、动作机制、难度阈值或实例生成规则调整。
- 清单会包含 world version、seed、stable instance hash、difficulty、当前规则下
  的最少动作数、active containers、tool placement 与 split，确保可以审计复现。
  这是预注册的开发/留出边界，不声称对外部地图或新规则的泛化。

## 离线原型证据与边界

按上述 6 个候选点，将激活容器显式加入所在房间的公开对象集合，并对每个布局
运行现有 BFS oracle；lunar 90/90、pyramid 30/30 唯一布局均找到成功路径。动作数
分布见上文。`LunarV3SeededEnvironment`、`PyramidV3SeededEnvironment` 和两个
selector 已实现；`scripts/audit_v3_seeded_layout_freeze.py --verify-runtime` 对全部
120 个 seed 核对 stable hash、工具放置、active containers 和 seed 周期，结果全匹配。
在独立进程以 `PYTHONHASHSEED=1`、`42` 重复核对也均为 120/120。新运行时只改变
布局生成和版本注册，`FlexEnvironment` 动作转移规则未改。冻结清单由同脚本生成。
这些结果证明运行时身份映射符合冻结预注册，不是模型能力、泛化或收益证据。

## S2 与在线运行边界

本 spec 仅授权离线布局设计、oracle 清单和实现准备。BUDGET-01/02/03 已关闭且
S2 matched-pilot Gate 未通过；不重置或复用 ledger，不新增 provider 请求，不运行
GPU，不推进 S3。S2 Gate 通过前，不能运行新 v3 seeded 模型矩阵。

## 验收条件

1. 冻结清单恰含 90 个 lunar 与 30 个 pyramid 唯一 stable hash，所有实例在当前
   规则 BFS 下可解，hash、route length、difficulty 和 split 可复现。
2. seed 0..89 与 0..29 分别一一覆盖各自全集；同 seed 跨进程结果相同，seed 大于
   全集大小按已声明周期重复。
3. dev/test 没有共享 instance hash；两个 difficulty 桶均在每张图内出现；test
   实例及阈值在任何 prompt/模块调整前冻结。
4. 原 v2 seeded 的定义、identity、Trace 解析和 seed 布局不变。
5. 完成清单前不做模型或 Agent 模块开发；完成清单也不授予在线实验或 GPU 权限。

## 后续

冻结清单及运行时 identity 核对已完成。S5.2 仍为 partial，直到在不查看 test 结果
调参的前提下完成预登记的 dev/test 行为评估；该评估须等待 S2 matched-pilot Gate，
并另行使用预登记预算。
