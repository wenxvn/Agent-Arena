# V13 第三方 Agent SDK 指南（P2-5）

- SDK 模块：`agent_arena.lab.sdk`（V12 接口不变）
- 自检模块：`agent_arena.lab.v13.sdkcheck`
- 示例：`examples/custom_agent/`
- 契约版本：`agent_policy_v1`（V13 未改）

> **这不是沙箱。** V13 只支持**本机受信任**插件：通过 allowlist 或 `examples/`
> 目录加载你自己的 Python 代码。不支持把任意代码上传到公网运行。

## 1. 最小可运行插件（30 行）

```python
# my_agent/policy.py
from typing import Any


class MyPolicy:
    """只读公开 Observation；不碰 Environment、不碰 Provider。"""

    def reset(self) -> None:
        self.history: list[dict[str, Any]] = []

    def decide(self, observation: dict[str, Any], context: Any) -> dict[str, Any]:
        # 只允许看 observation 里的公开字段
        tests = observation.get("available_tests") or []
        done = observation.get("test_results") or {}
        unused = [t for t in tests if t not in done]
        if unused:
            return {"tool": "run_test", "test_id": unused[0]}
        return {"tool": "wait"}

    def observe_result(self, outcome: Any) -> None:
        entry = getattr(outcome, "history_entry", None)
        if callable(entry):
            self.history.append(entry())

    def close(self) -> None:
        self.history = []


def make_policy(config: dict[str, Any] | None = None) -> MyPolicy:
    del config
    return MyPolicy()
```

## 2. 注册

```python
from agent_arena.lab.sdk import install_plugin

install_plugin(
    agent_id="my_agent.v1",
    module="my_agent.policy",          # 必须在 allowlist 或 examples/ 下
    attribute="make_policy",
    version="0.1.0",
    display_name="My Agent",
    description="先读公开测试再动手的最小策略。",
    capabilities=("public_observation", "external_plugin"),
    maps=("MAP-08", "MAP-26"),         # 空元组 = 适用于全部 30 图
    default_config={},
    allowed_config_keys=(),
)
```

**allowlist**：

```bash
# Windows PowerShell
$env:AGENT_ARENA_LAB_PLUGIN_ALLOWLIST = "my_agent.policy"
```

不加 allowlist 时，只有 `examples.` 前缀的模块可以加载。

## 3. 运行（离线，零费用）

```python
from decimal import Decimal
from agent_arena.lab.runner import run_lab_episode
from agent_arena.lab.simulated import SimulatedDecisionProvider
from agent_arena.v10.runtime.catalog import create_environment
from agent_arena.web.schemas import (
    SIMULATED_MODEL, SIMULATED_PROVIDER, RunConfig, RunMode,
)

env = create_environment("MAP-08", environment_seed=0)
outcome = run_lab_episode(
    RunConfig(
        map_id="MAP-08", environment_seed=0, mode=RunMode.SIMULATED,
        provider_id=SIMULATED_PROVIDER, model=SIMULATED_MODEL,
        agent="my_agent.v1", max_decisions=20, max_requests=40,
        max_input_tokens=200_000, max_output_tokens=8_000,
        max_cost_cny=Decimal("0.10"),
    ),
    provider=SimulatedDecisionProvider(map_id="MAP-08", shapes=env.SHAPES),
)
print(outcome.state, outcome.result["decision_count"])
```

## 4. 接入自检（8 项）

```bash
uv run python -c "
import sys; sys.path.insert(0,'src')
from agent_arena.lab.v13.sdkcheck import run_sdk_checks
import json; print(json.dumps(run_sdk_checks(), ensure_ascii=False, indent=1))
"
```

| 检查 | 验证什么 | 失败时的常见原因 |
|---|---|---|
| `contract_version` | `agent_policy_v1` 仍有效 | 你改了 `AGENT_CONTRACT_VERSION` |
| `public_observation_only` | 插件看不到 `sealed_truth` / `judge_state` / `oracle` | 你直接读了 Environment |
| `lifecycle_hooks` | `reset` / `decide` / `observe_result` / `close` 都被调用 | 钩子签名不匹配 |
| `version_identity` | 结果里带 `agent_version` 与契约版本 | 注册时没给 `version` |
| `invalid_action_isolated` | 非法动作计入 `invalid_actions` 而不是崩溃 | 你 `raise` 了而不是返回非法动作 |
| `budget_and_simulated` | SIMULATED 下费用为 0、不写付费账本 | 你直接调了 Provider |
| `exception_isolated` | 插件抛错 → `policy_error`，敏感串被截断 | 你把异常吞掉后继续 |
| `legacy_act_signature` | `act(observation, history)` 旧签名仍可用 | — |

## 5. 常见错误与提示

| 报错 | 含义 | 怎么修 |
|---|---|---|
| `PluginLoadError` | 模块不在 allowlist | 设置 `AGENT_ARENA_LAB_PLUGIN_ALLOWLIST` 或放到 `examples/` |
| `TypeError: 插件必须实现...` | 没有 `decide` 也没有 `act` | 加其中一个 |
| `policy_error` | 插件抛异常 | 检查是否读了 `observation` 里不存在的字段 |
| `invalid_actions` 很高 | 动作形状不对 | 返回**平铺**对象 `{"tool": ...}`，不要包成 `{"action": {...}}` |
| `cost_unknown` | Provider 没返回 usage | 不要自己造 usage；让网关 fail-closed |

`agent_arena.lab.v13.sdkcheck.error_hint(message)` 会把这些映射成一句话提示。

## 6. 受信任边界（重要）

| 允许 | 不允许 |
|---|---|
| 本机 `examples/` 下的模块 | 公网下载的任意代码 |
| allowlist 里显式列出的模块 | 用户上传的 zip/py |
| 只读公开 Observation | 读 `Environment` / `WorldState` / `judge_state` |
| 通过 `context.gateway` 请求模型 | 自己 import Provider SDK、自己拿 API key |
| 返回动作候选 | 直接调用 `environment.step()` |

**为什么不做沙箱**：Python 沙箱在进程内不可靠（`ctypes`、`importlib`、`os` 都能逃逸）。
V13 的选择是"明确不做"，而不是"做一个看起来安全的假沙箱"。

## 7. 异常隔离与预算

- 插件在 `decide` 里抛异常 → 本局 `FAILED` / `policy_error`，**其他 run 不受影响**；
- 插件在 `reset` / `observe_result` 里抛异常 → 同样落到 `policy_error`；
- 插件返回的 `requests` 会被计入，但**真实请求只能通过 `context.gateway`**，
  因此无法绕过 `RunBudget`；
- 错误消息经过 `sanitize_text`，`sk-` 之类会被截断。

## 8. 兼容性

| 旧写法 | V13 是否支持 |
|---|---|
| `decide(observation, context)` | ✅ |
| `act(observation, history)` | ✅（适配器转接） |
| `reset()` 无参 | ✅（`call_hook` 兼容） |
| `reset(context)` | ✅ |
| 返回 `AgentDecision` | ✅ |
| 返回 `{"action": {...}}` | ✅ |
| 返回 `{"tool": ...}` | ✅ |
| 直接返回 `Observation` 对象 | ❌（必须是 dict 或 AgentDecision） |

## 9. 相关文档

- `docs/v12/adapter-api.md`：V12 的完整字段说明（V13 未改）
- `examples/custom_agent/README.md`：可直接运行的示例
- `docs/v13/diagnosis-taxonomy.md`：插件失败会被归到哪一层
