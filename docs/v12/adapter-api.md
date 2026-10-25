# V12 第三方 Agent 接入 API

- **SDK 模块**：`agent_arena.lab.sdk`
- **示例**：`examples/custom_agent/`（`test_first.v1`）
- **契约版本**：`agent_policy_v1`

## 1. 最小接口

```python
class AgentPolicy(Protocol):
    @property
    def identity(self) -> AgentIdentity: ...
    def reset(self, context: PublicEpisodeContext) -> None: ...
    def decide(self, observation: PublicObservation, context: AgentContext) -> AgentDecision: ...
    def observe_result(self, outcome: PublicActionResult) -> None: ...
    def close(self) -> None: ...
```

第三方插件**只需实现其中一部分**：适配器 `ExternalPolicyAdapter` 接受

- `decide(observation: dict, context) -> AgentDecision | dict`，或
- `act(observation: dict, history: list[dict]) -> dict`（V9/V10 风格）。

钩子 `reset()` / `observe_result(outcome)` / `close()` 都是可选的，且**无参与有参两种写法都接受**
（`lab/policies/base.py::call_hook`）。

## 2. 策略能看到什么

`PublicObservation`：

```python
{
  "map_id": "MAP-22",
  "terminal": False,
  "terminal_reason": None,
  "last_action_result": "READY",
  # 以下为该图 PUBLIC_FIELDS 里的公开字段
  "current_sign": "camp",
  "bearings": ["west"],
  "agent_notes": [],
  ...
}
```

`AgentContext`：

| 字段 | 说明 |
|---|---|
| `decision_index` | 本局第几次决策（从 0 起） |
| `remaining_decisions` | 剩余决策数 |
| `history` | `PublicActionResult` 元组（含 action/result/status/rejected/invalid） |
| `gateway` | `DecisionGateway`，**唯一**模型出口 |
| `invalid_streak` / `reject_streak` / `invalid_total` | 公开连续计数 |

`PublicEpisodeContext`（`reset` 时给）：`run_id`、`experiment_id`、`map_id`、
`environment_seed`、`agent_id`、`agent_version`、`agent_config`、`decision_budget`、
`max_requests`、`public_rules`、`action_contract`、`system_prompt`、`history_window`、`mode`。

## 3. 策略看不到什么（硬边界）

- Environment 对象、`WorldState`、`judge_state`、`sealed_truth`、`truth_seal`；
- Oracle 动作序列、答案键；
- `DecisionProvider` / SDK 客户端（只能通过 `context.gateway`）；
- 其它子局的任何数据。

`lab/adapters.py::assert_public` 会扫描键名（不区分大小写，子串匹配
`sealed_truth` / `truth_seal` / `judge_state` / `oracle` / `answer_key` / `ground_truth` /
`hidden_solution` / `solution_path`），命中即抛 `LeakageError`。

## 4. 模型调用必须走网关

```python
response = context.gateway.ask(
    observation,
    purpose="decision",          # 或 "planner" / "reflection"
    recent_history=context.recent_history_text(limit=5),
    memory_data=None,            # 可选：注入公开记忆
    plan_data=None,              # 可选：注入公开计划
    correction=context.invalid_total > 0,
)
action = response.candidate      # 平铺的动作对象，仍需 V8Action 校验
```

网关行为：

- 每次请求先 `RunBudget.reserve` 再 `settle`；请求/token/费用三道门禁；
- 未知 usage → `GatewayProviderError(unknown_spend=True)`，**不重试**；
- 预算耗尽 → `GatewayBudgetExceeded`；
- `estimate_text` 可传入"完整历史"以复刻 V11 的 token 预估口径。

**绕过网关 = 该实验不可信**：`AgentPolicy` 拿不到 Provider，测试也覆盖这一点。

## 5. 注册

```python
from agent_arena.lab.sdk import install_plugin

install_plugin(
    agent_id="test_first.v1",
    module="examples.custom_agent.policy",
    attribute="make_policy",
    version="0.1.0",
    display_name="TestFirst · 第三方示例",
    description="先测后动手的公开规则策略（示例）。",
    default_config={"use_model": False},
    allowed_config_keys=("use_model",),
)
```

allowlist 规则（`AGENT_ARENA_LAB_PLUGIN_ALLOWLIST`，逗号分隔）：

- 仓库内 `examples.` 前缀默认受信任；
- 其它模块必须显式写入环境变量；
- 模块名必须是 `[A-Za-z0-9_.]+`，防止路径注入。

**V12 明确不提供公网代码沙箱**：只支持本机受信任插件。

## 6. 卸载

```python
from agent_arena.lab.registry import clear_external_agents
clear_external_agents()
```

内置策略不受影响；已落盘历史仍可读。

## 7. 只读导入公开运行文件

```python
from agent_arena.lab.sdk import read_public_run_file, replay_steps

imported = read_public_run_file(Path("runs/web/<run_id>/replay.json"))
steps = replay_steps(imported["document"])
```

校验：

| 检查 | 规则 |
|---|---|
| 大小 | ≤ 8 MiB（`MAX_IMPORT_BYTES`） |
| 编码 | 合法 UTF-8 JSON，顶层为对象 |
| schema | `v11-web-replay-1` / `v12-lab-replay-1` / `v11-web-trace-1` |
| 泄漏 | 无隐藏真值键（同上扫描） |

导入**不会**：

- 写账本、重建付费状态、修改本地历史；
- 覆盖已有 run；
- 让外部数据进入 Agent 输入。

## 8. 常见问题

**Q：插件抛异常会怎样？**
运行落 `FAILED / policy_error`，父实验继续下一个子局（除非是未知消费）。异常类型写入 `termination`，
不泄露异常正文（正文可能含敏感信息）。

**Q：插件能用 Oracle 动作吗？**
技术上能写死任何动作，但那是作弊而不是接入。V12 用三重约束降低风险：
(1) 插件拿不到真值；(2) `diagnostics` 会标出"脚本化/重复"行为；
(3) 结果里 `agent_id`/`version`/`config_hash` 全程可审计。

**Q：如何证明我的插件和内置策略遵守同一动作边界？**
跑 `uv run pytest tests/test_v12_sdk.py -q`：示例插件与 `basic.v1` 在同一
`V8Action` 校验、同一网关、同一预算下执行。
