# V8 地图运行时契约

本文件是 24 张新运行时的实现契约。实现者必须先读 `worlds/v4/MAP-XX/DESIGN.md`、
`oracle_trace.jsonl`、`acceptance.md`、`failure_traces/cases.yaml` 与
`docs/v7/maps/MAP-XX.md`，再按本契约写代码。每张图保留自己的状态机、动作前置、
结算顺序、失败码和指标；公共部分只允许复用生命周期、时钟、图边与哈希。

## 1. 文件

新建 `src/agent_arena/worlds/scenario_v8/maps/mapXX.py`，导出
`MapXXEnvironment(MapEnvironment)`。不得修改 `models.py`、`base.py`、`catalog.py`、
`oracle.py`、`v4_adapter.py` 或其他地图。

## 2. 必须实现的成员

```python
class MapXXEnvironment(MapEnvironment):
    map_id = "MAP-XX"
    title = "..."
    world = "..."           # spaceship/lighthouse/abyss/polar/pyramid/subway/volcano/jungle/lunar/castle
    level = "简单|中等|困难"  # 01/04/07/... 简单，02/05/... 中等，03/06/... 困难
    EDGES = {"edge_id": ("A", "B"), ...}
    EDGE_COST = {"edge_id": 2, ...}      # 可选，缺省 1
    SHAPES = {"move": {frozenset({"tool", "edge_id"})}, ...}
    PUBLIC_FIELDS = frozenset({...})     # 只列公开字段

    def __init__(self, *, seed=0, step_limit=160): super().__init__(...)
    def _reset_state(self, seed): ...    # 初始化 node/items/counters/私有状态
    def _public(self): ...               # 返回公开字段 dict
    def _apply(self, action): ...        # 返回结果码；可调用 self._succeed/_fail
    def judge_state(self): ...           # 私有裁判状态 dict
    def metrics(self): ...               # 见 §5
```

可选覆盖：`_after_tick()`、`_action_cost(action)`、`_invalid_action()`。

## 3. 生命周期

`base.step()` 的顺序是：校验形状 → `_apply` → `tick_count += cost` → `_after_tick`
→ 检查步数上限。因此：

- 先提交动作效果，再推进时钟，最后结算周期事件（潮汐、氧气、泄漏、温度、日结算）。
- 需要“同一 tick 先成功后失败”的图，在 `_after_tick` 中先判成功再判失败。
- `_succeed(reason)` / `_fail(reason)` 只设置终态，不自行加 tick。
- 所有 schema 合法动作默认耗 1 tick；移动/多 tick 动作在 `_action_cost` 中返回真实成本。
  多 tick 动作需要逐 tick 结算时，在 `_after_tick` 内用 `for _ in range(cost)`。
- 非法前置条件不改变状态，但照常耗 1 tick（多数图的设计要求）。

## 4. 动作

`V8Action` 是扁平严格模型；每张图用 `SHAPES` 精确声明允许的字段组合，例如

```python
SHAPES = {
    "move": {frozenset({"tool", "edge_id"})},
    "interact": {frozenset({"tool", "target_id", "operation"})},
    "wait": {frozenset({"tool", "ticks"})},
}
```

形状不匹配在 runner 中记为非法输出，不进入 `_apply`。地图内部仍需对
`target`/`operation` 的取值、地点、前置条件逐条校验并返回稳定结果码。

论文 Oracle 的不同方言（`name`/`action` 代替 `tool`、重复 `location`）由
`oracle.normalize_action_payload` 只在离线回放时归一化；运行时不得接受同义词。

## 5. 指标

只实现 `agent_arena.v7.metrics.registry.specs_for(map_id)` 中登记的 metric id，
不得新增或改名。返回值的形状：

- 比例类：`{"numerator": int, "denominator": int}`（分母为 0 表示 N/A）。
- 计数/刻度/0-1 类：直接返回 `int`/`float`。
- 单局无法计算的配对指标（如 `map06.value_of_information`）：返回 `None`。

指标必须来自真实私有状态或公开轨迹，不得返回常数伪装。至少有一个指标随不同
合法动作序列变化。分母、缺失和截尾规则写在地图模块顶部注释里，并与 V7 卡片一致。

## 6. Oracle 与 fixture

模块底部提供：

```python
ORACLE_CASES = (
    {"trace_id": "success", "seed": 0, "actions": [{...}, ...], "expect_success": True},
)
FIXTURES = (
    {"name": "...", "seed": 0, "actions": [{...}, ...],
     "expect": {"mapXX.metric_id": 期望值}},
)
```

- `ORACLE_CASES` 至少一条，来自设计文档的手写成功策略，逐动作真实 `step` 回放成功。
  若 `worlds/v4/MAP-XX/oracle_trace.jsonl` 已是动作列表，可直接把行内 `action`
  复制进来；若是日计划/控制帧/整份 Observation，必须自己翻译成逐步动作。
- `FIXTURES` 至少两条：一条成功或部分完成，一条机制特有失败/边界；期望值必须手算，
  不得先跑再抄。每条至少断言 1 个指标。

## 7. 泄漏与确定性

- `PUBLIC_FIELDS` 之外的字段不得出现在 `_public()`；私有真值（故障部件、隐藏天气、
  未来事件、判定阈值内部计数器）只能进 `judge_state()`。
- 同一初始状态、同一动作序列必须得到相同 `state_hash()` 与相同 Observation。
- 不得在 Observation、结果码或 prompt 中给出 Oracle 路线或答案表。

## 8. 自检命令

```powershell
.\.venv\Scripts\python.exe scripts/check_v8_map.py MAP-XX
```

必须输出 `MAP-XX: OK`：所有 oracle 回放成功、fixture 断言通过、公开字段无越界、
指标 id 与登记表完全一致。

## 9. 反换皮要求

同世界三图必须有不同的状态变量、动作因果和失败码。只改节点名的复制会被退回。
实现前先在模块 docstring 写一句“本图与同世界另两图的机制差异”。
