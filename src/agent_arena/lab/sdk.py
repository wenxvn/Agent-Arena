"""V12 Lab 对外 SDK：第三方 Agent 接入与只读导入。

明确边界：

- 只加载**本机受信任**模块（allowlist 或仓库内 ``examples/``），不是安全沙箱；
- 插件只能看到公开 ``Observation`` 与 ``AgentContext``（含预算网关）；
- 导入只读公开运行文件做分析，**不**重建付费状态、不写账本、不改历史。
"""

from __future__ import annotations

import importlib
import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from agent_arena.lab.adapters import (
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
    assert_public,
)
from agent_arena.lab.contracts import AgentDecision, AgentEvent, AgentIdentity
from agent_arena.lab.policies.external import (
    ExternalPolicyAdapter,
    register_external_plugin,
)
from agent_arena.lab.registry import AgentRegistration, get_agent, registered_agent_ids

PLUGIN_ALLOWLIST_ENV = "AGENT_ARENA_LAB_PLUGIN_ALLOWLIST"
#: 仓库内受信任的示例模块前缀（仍然只加载本机代码）。
TRUSTED_PREFIXES: tuple[str, ...] = ("examples.",)
MAX_IMPORT_BYTES = 8 * 1024 * 1024
IMPORT_SCHEMAS = ("v11-web-replay-1", "v12-lab-replay-1", "v11-web-trace-1")


class PluginLoadError(RuntimeError):
    """插件不在 allowlist 或无法加载。"""


class ImportRejected(RuntimeError):
    """导入文件不满足只读分析的安全条件。"""


def plugin_allowlist() -> tuple[str, ...]:
    raw = os.environ.get(PLUGIN_ALLOWLIST_ENV, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_plugin(module: str, *, attribute: str = "make_policy") -> Any:
    """按 allowlist 加载本机插件工厂；默认拒绝未登记的模块。"""

    if not re.fullmatch(r"[A-Za-z0-9_.]+", module):
        raise PluginLoadError(f"非法的模块名：{module}")
    allowed = plugin_allowlist()
    trusted = module.startswith(TRUSTED_PREFIXES) or any(
        module == item or module.startswith(item + ".") for item in allowed
    )
    if not trusted:
        raise PluginLoadError(
            f"模块 {module} 不在 allowlist 中；请设置 {PLUGIN_ALLOWLIST_ENV} 或放在 examples/ 下。"
        )
    imported = importlib.import_module(module)
    factory = getattr(imported, attribute, None)
    if not callable(factory):
        raise PluginLoadError(f"{module}.{attribute} 不是可调用工厂。")
    return factory


def install_plugin(
    *,
    agent_id: str,
    module: str,
    attribute: str = "make_policy",
    version: str = "0.1.0",
    display_name: str = "",
    description: str = "",
    maps: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    default_config: dict[str, Any] | None = None,
    allowed_config_keys: tuple[str, ...] = (),
) -> AgentRegistration:
    """校验 allowlist 后注册插件，返回登记项。"""

    load_plugin(module, attribute=attribute)
    return register_external_plugin(
        agent_id=agent_id,
        module=module,
        attribute=attribute,
        version=version,
        display_name=display_name,
        description=description,
        capabilities=capabilities,
        maps=maps,
        default_config=default_config,
        allowed_config_keys=allowed_config_keys,
    )


# ------------------------------------------------------------------- read-only
def _forbidden_hits(payload: Any) -> list[str]:
    hits: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in {
                    "sealed_truth",
                    "judge_state",
                    "truth_seal",
                    "oracle_actions",
                    "answer_key",
                }:
                    hits.append(str(key))
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(payload)
    return sorted(set(hits))


def read_public_run_file(path: Path) -> dict[str, Any]:
    """读取一份**公开**运行/回放文件，做 schema、大小与泄漏校验。

    只返回分析用的只读视图：不写账本、不改变任何本地状态。
    """

    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise ImportRejected(f"文件不存在：{resolved}")
    size = resolved.stat().st_size
    if size > MAX_IMPORT_BYTES:
        raise ImportRejected(f"文件过大（{size} B > {MAX_IMPORT_BYTES} B）。")
    blob = resolved.read_bytes()
    digest = sha256(blob).hexdigest()
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ImportRejected("不是合法的 UTF-8 JSON。") from exc
    if not isinstance(payload, dict):
        raise ImportRejected("顶层必须是 JSON 对象。")
    schema = str(payload.get("schema_version") or payload.get("schema") or "")
    if schema not in IMPORT_SCHEMAS:
        raise ImportRejected(f"不支持的 schema：{schema or '缺失'}")
    hits = _forbidden_hits(payload)
    if hits:
        raise ImportRejected(f"文件含隐藏真值字段：{', '.join(hits)}")
    assert_public(payload, where="imported document")
    return {
        "path": str(resolved),
        "sha256": digest,
        "bytes": size,
        "schema_version": schema,
        "document": payload,
        "read_only": True,
    }


def replay_steps(document: dict[str, Any]) -> list[dict[str, Any]]:
    """从公开回放文档中取出 decision 事件（只读）。"""

    steps = document.get("steps")
    if isinstance(steps, list):
        return [dict(item) for item in steps if isinstance(item, dict)]
    events = document.get("events")
    if isinstance(events, list):
        return [
            dict(item)
            for item in events
            if isinstance(item, dict) and item.get("event") == "decision"
        ]
    return []


__all__ = [
    "IMPORT_SCHEMAS",
    "MAX_IMPORT_BYTES",
    "PLUGIN_ALLOWLIST_ENV",
    "TRUSTED_PREFIXES",
    "AgentContext",
    "AgentDecision",
    "AgentEvent",
    "AgentIdentity",
    "ExternalPolicyAdapter",
    "ImportRejected",
    "PluginLoadError",
    "PublicActionResult",
    "PublicEpisodeContext",
    "PublicObservation",
    "get_agent",
    "install_plugin",
    "load_plugin",
    "plugin_allowlist",
    "read_public_run_file",
    "registered_agent_ids",
    "replay_steps",
]
