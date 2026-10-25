"""第三方 Agent 接入示例：``test_first.v1``。

## 它做什么

一个**只读公开 Observation** 的确定性策略：先跑完公开测试，再在候选集缩成唯一
时封存诊断/换件/维修，否则观察或移动。默认不调用模型，因此零费用、可离线复现。

## 它不能做什么

- 拿不到 Environment、`judge_state`、`sealed_truth` 或 Oracle 动作；
- 不能绕过预算网关（``context.gateway`` 是唯一模型出口）；
- 不能把任意代码上传到网页执行：只加载本机 allowlist 内的模块。

## 接入步骤

1. 在本机安装并确认模块可导入（示例在仓库根目录下，因此直接可用）：

```bash
uv run python -c "import examples.custom_agent.policy as p; print(p.make_policy({}))"
```

2. 在实验脚本/网页里注册：

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

3. 用 ``AgentArm(agent_id="test_first.v1")`` 放进 ``ExperimentSpec``。实验里会记录
   ``agent_id`` / ``agent_version`` / ``agent_config_hash``，与内置策略一样参与
   版本门禁；缺少必需事件字段时只降级展示，不伪造数据。

## 卸载

```python
from agent_arena.lab.registry import clear_external_agents
clear_external_agents()
```

内置策略不受影响；已落盘的历史结果仍然可读。

## 常见问题

- **为什么默认不调用模型？** 为了让示例在无 Key、无网络、零费用的情况下可运行；
  设 ``use_model=True`` 才会经网关请求，并计入请求/token/费用。
- **能保证安全隔离吗？** 不能。V12 只支持本机受信任插件；公网任意代码沙箱不在范围。
- **动作被拒怎么办？** 环境拒绝是合法结果，会计入 ``rejected_actions`` 并由诊断层
  给出证据；插件不会因此获得额外信息。
"""

from __future__ import annotations

__all__: list[str] = []
