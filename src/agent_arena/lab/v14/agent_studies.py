"""V14 Agent 机制研究（P0-4 / P0-5 / P0-6）。

本模块只做**离线机制验证 + 预检登记**，零模型请求：

- ``memory_offline_probe``：用确定性脚本驱动 ``memory.v2``，复现
  "被拒移动不写路线""回到起点仍能引用完整方位""记忆块不含隐藏真值"三条 fixture；
- ``memory_arm_configs``：把 on/off 与 ``route_mode`` 两两组合成**单开关**实验臂，
  并显式钉住其它配置，证明"只差一个变量"；
- ``memory_ablation_plan``：零请求预检登记（``PLANNED_ONLY``），含预算上界与停止条件。

设计约束：

- 不使用真实 Provider，不写账本，不产生任何网络调用；
- 所有结论都能由 ``tests/test_v14_agent_studies.py`` 重跑复算；
- 未获批准时 ``LIVE`` 字段一律 ``PLANNED_ONLY`` / ``LIVE_PENDING``。
"""

from __future__ import annotations

from typing import Any

from agent_arena.lab.adapters import (
    FORBIDDEN_PUBLIC_KEYS,
    AgentContext,
    PublicActionResult,
    PublicEpisodeContext,
    PublicObservation,
)
from agent_arena.lab.gateway import GatewayResponse
from agent_arena.lab.metrics_v12 import project_route_recall
from agent_arena.lab.policies import memory_v2
from agent_arena.lab.v13.comparability import single_switch_check

#: 研究投影的指标命名空间（与 V10 官方指标分列）。
V14_PROJECTION = "v14.projection"

#: 允许进入记忆的公开字段白名单前缀（与 memory.v2 的实现一致）。
MEMORY_KIND_PREFIXES = ("state.", "milestone.", "result.", "route.", "fact.", "episode.")

class _ScriptedGateway:
    """确定性网关替身：每次返回"当前"脚本动作，不联网、不计费。"""

    def __init__(self, candidate: dict[str, Any] | None = None) -> None:
        self.current: dict[str, Any] = dict(candidate or {"tool": "wait"})
        self.calls: list[dict[str, Any]] = []

    def ask(self, observation: PublicObservation, **kwargs: Any) -> GatewayResponse:
        index = len(self.calls)
        self.calls.append({"observation": observation, **kwargs})
        candidate = dict(self.current)
        return GatewayResponse(
            candidate=candidate,
            input_tokens=100,
            output_tokens=20,
            latency_ms=1,
            request_index=index,
        )

    def ask_json(
        self, observation: PublicObservation, **kwargs: Any
    ) -> tuple[dict[str, Any], GatewayResponse]:
        self.calls.append({"observation": observation, **kwargs})
        payload = {"current_subgoal": "沿已知方位回到起点"}
        response = GatewayResponse(
            candidate=payload,
            input_tokens=120,
            output_tokens=30,
            latency_ms=2,
            request_index=len(self.calls),
        )
        return payload, response

def _episode(map_id: str = "MAP-22", decisions: int = 24) -> PublicEpisodeContext:
    return PublicEpisodeContext(
        run_id="v14-probe",
        experiment_id=None,
        map_id=map_id,
        environment_seed=0,
        agent_id="memory.v2",
        agent_version="2.0.0",
        agent_config={},
        decision_budget=decisions,
        max_requests=decisions * 2,
        public_rules=(),
        action_contract="scenario_v4",
        system_prompt="sys",
        history_window=5,
        mode="simulated",
    )

def _observation(**fields: Any) -> PublicObservation:
    return PublicObservation.from_environment(
        {
            "map_id": "MAP-22",
            "terminal": False,
            "terminal_reason": None,
            "last_action_result": "READY",
            **fields,
        }
    )

def _result(
    *,
    action: dict[str, Any] | None,
    result: str,
    rejected: bool = False,
    invalid: bool = False,
    decision_index: int = 1,
    observation: PublicObservation | None = None,
) -> PublicActionResult:
    return PublicActionResult(
        decision_index=decision_index,
        action=action,
        result=result,
        status="FAILED" if rejected else "SUCCEEDED",
        rejected=rejected,
        invalid=invalid,
        terminal=False,
        observation=observation or _observation(),
    )

def _context(gateway: Any, index: int) -> AgentContext:
    return AgentContext(
        decision_index=index,
        remaining_decisions=24 - index,
        history=(),
        gateway=gateway,
    )

def _notes_from_action(action: Any) -> list[dict[str, Any]]:
    """把一次公开 ``write_memory`` 动作转成"环境里的 notes"形状（只读）。"""

    if not isinstance(action, dict) or action.get("tool") != "write_memory":
        return []
    facts = action.get("facts")
    if not isinstance(facts, list):
        return []
    notes: list[dict[str, Any]] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        key = str(fact.get("key") or "")
        value = fact.get("value")
        # 环境把 ``write_memory(facts)`` 原样存进 ``agent_notes``：``{key, value}``。
        notes.append({"key": key, "value": value})
    return notes

def _leaks(block: str | None) -> list[str]:
    """记忆块里出现隐藏真值关键词即视为泄漏（保守检查）。"""

    if not block:
        return []
    lowered = block.lower()
    return [word for word in FORBIDDEN_PUBLIC_KEYS if word in lowered]

# ------------------------------------------------------ bottleneck projection
BOTTLENECK_NONE = memory_v2.BOTTLENECK_NONE
BOTTLENECK_SHORT = memory_v2.BOTTLENECK_SHORT
BOTTLENECK_UNREFERENCED = memory_v2.BOTTLENECK_UNREFERENCED
BOTTLENECK_OK = memory_v2.BOTTLENECK_OK
BOTTLENECK_WRITE_REJECTED = "WRITE_REJECTED_INTERFACE"

def memory_bottleneck_v14(
    *,
    enabled: bool,
    route_length: int,
    route_mode: str,
    write_attempts: int,
    write_accepted: int,
    written_bearings: int,
    render_count: int,
) -> dict[str, Any]:
    """V14 投影版瓶颈分类（只读，不修改 ``memory.v2``）。

    **为什么需要投影**（DCR-V14-03）：``memory.v2.bottleneck()`` 在
    ``env_write`` 模式下把"写入次数"（``write_accepted``）与"路线长度"比较，
    但一次写入可以包含整段路线。于是一个**每次写入都完整**的臂会被判成
    ``RECORDED_TOO_SHORT``。V14 改为比较"已写入的方位数"。

    这是**诊断口径**修正，不改变策略行为、不改变 prompt、不影响任何历史配置指纹。
    """

    if not enabled:
        return {"label": "DISABLED", "reason": "记忆关闭（消融臂）。"}
    if route_length == 0 and write_attempts == 0:
        return {"label": BOTTLENECK_NONE, "reason": "没有路线，也没有写入尝试。"}
    if write_attempts and write_accepted == 0:
        return {
            "label": BOTTLENECK_WRITE_REJECTED,
            "reason": "有写入尝试但全部被拒：属接口问题，不归因于策略能力。",
        }
    covered = written_bearings if route_mode == memory_v2.ROUTE_MODE_ENV_WRITE else route_length
    if route_length and covered < max(3, route_length // 2):
        return {
            "label": BOTTLENECK_SHORT,
            "reason": (
                f"已写入 {covered} 个方位（路线 {route_length}）：记录过短，"
                "回到起点后无法复述完整路径。"
            ),
        }
    if route_length and render_count == 0:
        return {
            "label": BOTTLENECK_UNREFERENCED,
            "reason": "有路线但从未渲染进 prompt：记录了却没被使用。",
        }
    return {"label": BOTTLENECK_OK, "reason": "记录且渲染。"}

# ------------------------------------------------------------------ probe
#: 脚本：接受 4 步（绕一圈回到起点），中间插 2 次被拒、1 次非法。
DEFAULT_SCRIPT: tuple[dict[str, Any], ...] = (
    {"tool": "move", "bearing": "north", "result": "MOVED", "rejected": False, "invalid": False},
    {
        "tool": "move",
        "bearing": "north",
        "result": "BEARING_NOT_AVAILABLE",
        "rejected": True,
        "invalid": False,
    },
    {"tool": "move", "bearing": "east", "result": "MOVED", "rejected": False, "invalid": False},
    {"tool": "move", "result": "<invalid>", "rejected": False, "invalid": True},
    {"tool": "move", "bearing": "south", "result": "MOVED", "rejected": False, "invalid": False},
    {"tool": "move", "bearing": "west", "result": "MOVED", "rejected": False, "invalid": False},
)

def memory_offline_probe(
    config: dict[str, Any] | None = None,
    *,
    script: tuple[dict[str, Any], ...] = DEFAULT_SCRIPT,
    map_id: str = "MAP-22",
) -> dict[str, Any]:
    """用确定性脚本跑一遍 ``memory.v2``，返回可复算的机制计数。

    步骤语义（与运行时一致）：

    1. ``decide`` → 可能返回一次 ``write_memory``（``env_write`` 模式）；
    2. 环境执行该动作（写入被接受的 notes 或返回拒绝）；
    3. ``observe_result`` 把**动作结果**喂回策略；
    4. 路线只从"被接受的 move"累积。
    """

    policy = memory_v2.MemoryV2Policy(config)
    policy.reset(_episode(map_id=map_id))
    gateway = _ScriptedGateway()
    notes: list[dict[str, Any]] = []
    decisions = 0
    requests = 0
    blocks: list[str] = []
    write_actions: list[dict[str, Any]] = []
    accepted_route: list[str] = []
    route_after_steps: list[str] = []

    decision_index = 0
    for step in script:
        # 先决策；``env_write`` 模式可能先返回一次 write_memory，占用一个决策。
        gateway.current = {
            "tool": step["tool"],
            **({"bearing": step["bearing"]} if "bearing" in step else {}),
        }
        decision = policy.decide(
            _observation(step=decision_index), _context(gateway, decision_index)
        )
        decisions += 1
        decision_index += 1
        requests += int(decision.requests or 0)
        action = decision.action
        if isinstance(action, dict) and action.get("tool") == "write_memory":
            write_actions.append(action)
            notes.extend(_notes_from_action(action))
            # 环境对记忆写入的公开结果（本 fixture 里写入合法 → 被接受）。
            policy.observe_result(
                _result(
                    action=action,
                    result="MEMORY_RECORDED",
                    decision_index=decision_index,
                )
            )
            # 再决策一次，拿到真正的 move（env_write 的代价：多吃一个决策）。
            decision = policy.decide(
                _observation(step=decision_index), _context(gateway, decision_index)
            )
            decisions += 1
            decision_index += 1
            requests += int(decision.requests or 0)
            action = decision.action
        if not isinstance(action, dict) or action.get("tool") != "write_memory":
            block = gateway.calls[-1].get("memory_data") if gateway.calls else None
            if block:
                blocks.append(str(block))

        outcome = _result(
            action=action,
            result=str(step["result"]),
            rejected=bool(step["rejected"]),
            invalid=bool(step["invalid"]),
            decision_index=decision_index,
        )
        policy.observe_result(outcome)
        if (
            isinstance(action, dict)
            and action.get("tool") == "move"
            and not step["rejected"]
            and not step["invalid"]
        ):
            accepted_route.append(str(action.get("bearing")))
        snapshot = policy.snapshot()
        route_after_steps.append(str(snapshot["route_preview"]))

    # 收尾渲染：脚本走完后**再决策一次**（wait），把"回到起点后的记忆块"抓下来。
    # 这一步同样计入决策与请求，不白拿。
    gateway.current = {"tool": "wait"}
    final_decision = policy.decide(
        _observation(step=decision_index), _context(gateway, decision_index)
    )
    decisions += 1
    requests += int(final_decision.requests or 0)
    final_block = gateway.calls[-1].get("memory_data") if gateway.calls else None
    if final_block:
        blocks.append(str(final_block))
    final_action = final_decision.action
    final_write_route = ""
    if isinstance(final_action, dict) and final_action.get("tool") == "write_memory":
        # env_write：这一轮不是模型请求，而是把完整路线写进环境（占 1 次决策）。
        write_actions.append(final_action)
        notes.extend(_notes_from_action(final_action))
        for fact in final_action.get("facts") or []:
            if isinstance(fact, dict) and fact.get("key") == "path_state":
                final_write_route = str(fact.get("value") or "")
        policy.observe_result(
            _result(
                action=final_action,
                result="MEMORY_RECORDED",
                decision_index=decision_index + 1,
            )
        )

    snapshot = policy.snapshot()
    projection = project_route_recall(notes=notes, route=accepted_route)
    last_block = str(final_block) if final_block else (blocks[-1] if blocks else None)
    return {
        "config": {
            "route_log": policy.route_log,
            "route_mode": policy.route_mode,
            "route_write_every": policy.route_write_every,
            "enabled": policy.enabled,
        },
        "decisions": decisions,
        "requests": requests,
        "accepted_route": accepted_route,
        "route_after_steps": route_after_steps,
        "route_length": snapshot["route_length"],
        "route_preview": snapshot["route_preview"],
        "rejected_moves": snapshot["rejected_moves"],
        "invalid_moves": snapshot["invalid_moves"],
        "loops": snapshot["loops"],
        "backtracks": snapshot["backtracks"],
        "write_attempts": snapshot["write_attempts"],
        "write_accepted": snapshot["write_accepted"],
        "write_rejected": snapshot["write_rejected"],
        "render_count": snapshot["render_count"],
        "block_chars": snapshot["block_chars"],
        "bottleneck_v13": snapshot["bottleneck"],
        "bottleneck": memory_bottleneck_v14(
            enabled=policy.enabled,
            route_length=int(snapshot["route_length"]),
            route_mode=policy.route_mode,
            write_attempts=int(snapshot["write_attempts"]),
            write_accepted=int(snapshot["write_accepted"]),
            written_bearings=len([item for item in final_write_route.split(",") if item]),
            render_count=int(snapshot["render_count"]),
        ),
        "write_actions": len(write_actions),
        "notes_written": len(notes),
        "route_recall_v14": projection,
        "route_recall_v10_note": (
            "V10 官方 route_recall 直接读环境 agent_notes；context_only 不写环境，"
            "因此该口径在本臂为 NOT_APPLICABLE，必须与 V14 投影分列。"
        ),
        "last_memory_block": last_block,
        "memory_block_leaks": _leaks(last_block),
        "final_action": final_action,
        "final_write_route": final_write_route,
        "expected_route": _expected_route(script),
        "route_matches_expected": _expected_route(script)
        == [item for item in str(snapshot["route_preview"]).split(",") if item],
        "final_block_has_all_bearings": all(
            bearing in (str(last_block or "") + final_write_route)
            for bearing in _expected_route(script)
        ),
    }

def _expected_route(script: tuple[dict[str, Any], ...]) -> list[str]:
    """被拒/非法 move 不得进入路线：只保留脚本里被接受的方位。"""

    return [
        str(step["bearing"])
        for step in script
        if step["tool"] == "move"
        and not step["rejected"]
        and not step["invalid"]
        and "bearing" in step
    ]

# --------------------------------------------------------------- arm registry
#: 钉住的公共配置：**两个臂除被测开关外完全一致**。
MEMORY_PINNED_BASE: dict[str, Any] = {
    "enabled": True,
    "capacity": 32,
    "max_chars": 1600,
    "history_window": 5,
    "route_log": True,
    "route_mode": memory_v2.ROUTE_MODE_CONTEXT_ONLY,
    "route_write_every": 2,
    "route_write_limit": 24,
    "compress": True,
    "dedupe": True,
    "relevance": True,
}

#: V14 Memory 消融臂：两组、各自只差一个开关。
MEMORY_ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm_id": "E1-a-control",
        "group": "E1-a",
        "label": "route_log off（route_mode=context_only）",
        "overrides": {"route_log": False},
    },
    {
        "arm_id": "E1-a-treatment",
        "group": "E1-a",
        "label": "route_log on（route_mode=context_only）",
        "overrides": {"route_log": True},
    },
    {
        "arm_id": "E1-b-control",
        "group": "E1-b",
        "label": "context_only（route_log on）",
        "overrides": {"route_log": True, "route_mode": memory_v2.ROUTE_MODE_CONTEXT_ONLY},
    },
    {
        "arm_id": "E1-b-treatment",
        "group": "E1-b",
        "label": "env_write（route_log on）",
        "overrides": {"route_log": True, "route_mode": memory_v2.ROUTE_MODE_ENV_WRITE},
    },
)

def memory_arm_configs() -> list[dict[str, Any]]:
    """展开成完整 ``AgentArm`` 形状（``agent_id`` + 完整 config）。"""

    arms = []
    for spec in MEMORY_ARMS:
        config = {**MEMORY_PINNED_BASE, **spec["overrides"]}
        arms.append(
            {
                "arm_id": spec["arm_id"],
                "group": spec["group"],
                "label": spec["label"],
                "agent_id": "memory.v2",
                "config": config,
            }
        )
    return arms

def memory_single_factor_audit() -> dict[str, Any]:
    """用 V13 的 ``single_switch_check`` 证明每组只差一个开关。"""

    arms = memory_arm_configs()
    groups: dict[str, list[dict[str, Any]]] = {}
    for arm in arms:
        groups.setdefault(arm["group"], []).append(arm)
    checks = []
    for group, items in sorted(groups.items()):
        control, treatment = items[0], items[1]
        check = single_switch_check(control, treatment)
        checks.append(
            {
                "group": group,
                "control": control["arm_id"],
                "treatment": treatment["arm_id"],
                "ok": check.ok,
                "manipulated_variable": check.manipulated_variable,
                "changed_keys": list(check.changed_keys),
                "reasons": list(check.reasons),
                "pinned_keys": sorted(
                    key
                    for key in control["config"]
                    if key not in set(check.changed_keys)
                ),
            }
        )
    return {
        "schema": "v14-memory-arms-1",
        "arms": arms,
        "checks": checks,
        "all_single_factor": all(item["ok"] for item in checks),
        "note": (
            "每组只改一个配置键；``route_mode`` 在 E1-a 两组里被钉成 context_only，"
            "因此 E1-a 测的是 route_log 本身，不会混入写入机制的差异。"
        ),
    }

# -------------------------------------------------------------- ablation plan
def memory_ablation_plan() -> dict[str, Any]:
    """零请求预检登记：矩阵、预算上界、指标、停止条件。"""

    arms = memory_arm_configs()
    seeds = [0, 1, 2]
    replicates = 3
    groups = sorted({arm["group"] for arm in arms})
    runs = len(groups) * 2 * len(seeds) * replicates
    return {
        "schema": "v14-memory-plan-1",
        "status": "PLANNED_ONLY",
        "live_status": "LIVE_PENDING",
        "maps": ["MAP-22"],
        "seeds": seeds,
        "replicates": replicates,
        "groups": groups,
        "arms": [arm["arm_id"] for arm in arms],
        "runs": runs,
        "budget": {
            "per_run_request_cap": 90,
            "per_run_input_token_cap": 200_000,
            "per_run_cost_cap_cny": 0.50,
            "experiment_cost_cap_cny": 5.00,
        },
        "primary_metrics": [
            "completed_success",
            "v14.projection.route_recall",
            "map22.v10.route_recall",
            "wasted_moves",
            "route_length",
            "backtracks",
        ],
        "cost_metrics": ["requests", "input_tokens", "decisions", "cost_cny"],
        "stop_rules": [
            "任一局 unknown_spend → 立即停止并封账",
            "累计结算达批准上限 90% → 停止未开始子局",
            "Provider 连续 3 次错误 → 停止",
            "发现契约/接口缺陷 → 停止并写 DCR",
            "平均单局费用超过预估 2 倍 → 停止并重新申请",
        ],
        "comparison_rule": (
            "同一总预算、同一 memory.v2 版本、同一 prompt 主体、同一 seed；"
            "只允许被测开关不同（E1-a 改 route_log，E1-b 改 route_mode）。"
        ),
        "no_go_note": (
            "V14 未获用户对模型/矩阵/总额的批准，因此本计划不得执行；"
            "``scripts/run_v12_matrix.py --ablation`` 只允许在默认预检模式下运行。"
        ),
    }

def memory_study_report() -> dict[str, Any]:
    """Memory 段的完整证据包：机制 probe + 单因子审计 + 预检登记。"""

    probes = {
        "context_only_on": memory_offline_probe(
            {"route_mode": memory_v2.ROUTE_MODE_CONTEXT_ONLY, "route_log": True}
        ),
        "context_only_off": memory_offline_probe(
            {"route_mode": memory_v2.ROUTE_MODE_CONTEXT_ONLY, "route_log": False}
        ),
        "env_write_on": memory_offline_probe(
            {"route_mode": memory_v2.ROUTE_MODE_ENV_WRITE, "route_log": True}
        ),
        "disabled": memory_offline_probe({"enabled": False}),
    }
    return {
        "schema": "v14-memory-study-1",
        "probes": probes,
        "arms": memory_single_factor_audit(),
        "plan": memory_ablation_plan(),
        "note": (
            "以上全部为 SIMULATED 机制证据，零模型请求；"
            "真实模型收益一律 LIVE_PENDING。"
        ),
    }

def memory_markdown(report: dict[str, Any]) -> str:
    """Memory 段（P0-4）的 Markdown 证据包。"""

    probes = report["probes"]
    arms = report["arms"]
    plan = report["plan"]
    lines = [
        "## 1. Memory（P0-4）",
        "",
        "### 1.1 离线机制 probe（SIMULATED，零模型请求）",
        "",
        "脚本：`north`（接受）→ `north`（被拒）→ `east`（接受）→ 缺 `bearing`（非法）"
        "→ `south`（接受）→ `west`（接受）→ 收尾 `wait` 一次以抓取最终记忆块。",
        "",
        "| 臂 | 决策 | 请求 | 路线 | 被拒 | 非法 | 写入尝试 | 写入接受 | 渲染 | 瓶颈 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---|",
    ]
    for name, probe in probes.items():
        lines.append(
            f"| `{name}` | {probe['decisions']} | {probe['requests']} | "
            f"`{probe['route_preview'] or '—'}` | {probe['rejected_moves']} | "
            f"{probe['invalid_moves']} | {probe['write_attempts']} | "
            f"{probe['write_accepted']} | {probe['render_count']} | "
            f"`{probe['bottleneck']['label']}` |"
        )
    lines += [
        "",
        "> 瓶颈列是 **V14 投影**（`memory_bottleneck_v14`）："
        "``env_write`` 按「已写入方位数」判定。",
        "> ``memory.v2.bottleneck()`` 原口径把「写入次数」与路线长度比较，"
        "一次写入整段路线时会被误判为 `RECORDED_TOO_SHORT`（DCR-V14-03）。",
        "",
        "三条 fixture（全部可在 `tests/test_v14_agent_studies.py` 复算）：",
        "",
        "1. **被拒/非法移动不进路线**：`route_preview` 恒等于"
        "脚本里被接受的方位序列（`route_matches_expected`）；",
        "2. **回到起点仍能引用完整方位**：`context_only` 的最终记忆块与"
        "`env_write` 的写入载荷都包含 `north,east,south,west`"
        "（`final_block_has_all_bearings`）；",
        "3. **不写答案**：记忆块里没有隐藏真值关键词（`memory_block_leaks` 为空），"
        "路线只来自公开 `move` 结果。",
        "",
        "### 1.2 写入机制的代价（不可互相冒充）",
        "",
        "| 臂 | 决策 | 请求 | 说明 |",
        "|---|---:|---:|---|",
        f"| `context_only_on` | {probes['context_only_on']['decisions']} | "
        f"{probes['context_only_on']['requests']} | 不发动作，路线只进 prompt |",
        f"| `env_write_on` | {probes['env_write_on']['decisions']} | "
        f"{probes['env_write_on']['requests']} | 每次写入占 1 次决策、0 次请求 |",
        "",
        f"- `env_write` 写入载荷：`{probes['env_write_on']['final_write_route'] or '—'}`；"
        f"V14 投影 `route_recall = {probes['env_write_on']['route_recall_v14']['value']}`"
        f"（`{probes['env_write_on']['route_recall_v14']['state']}`）。",
        "- `context_only` 不写环境，V10 官方 `route_recall` 在本臂为 "
        "`NOT_APPLICABLE`——必须与 V14 投影分列，不能混算。",
        "",
        "### 1.3 单因子审计",
        "",
        "| 组 | 对照 | 处理 | 唯一变化键 | 单开关 |",
        "|---|---|---|---|---|",
    ]
    for check in arms["checks"]:
        lines.append(
            f"| {check['group']} | `{check['control']}` | `{check['treatment']}` | "
            f"`{check['manipulated_variable']}` | "
            f"{'是' if check['ok'] else '**否**'} |"
        )
    lines += [
        "",
        f"- 全部单因子：{'是' if arms['all_single_factor'] else '**否**'}",
        f"- {arms['note']}",
        "",
        "### 1.4 预检登记（`PLANNED_ONLY`，零请求）",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 地图 | {', '.join(plan['maps'])} |",
        f"| seed | {plan['seeds']} |",
        f"| 重复 | {plan['replicates']} |",
        f"| 组 | {', '.join(plan['groups'])} |",
        f"| 子局 | {plan['runs']} |",
        f"| 单局预算 | {plan['budget']['per_run_request_cap']} 请求 / "
        f"{plan['budget']['per_run_input_token_cap']} token / "
        f"¥{plan['budget']['per_run_cost_cap_cny']} |",
        f"| 实验费用上限 | ¥{plan['budget']['experiment_cost_cap_cny']} |",
        f"| 状态 | `{plan['status']}` / `{plan['live_status']}` |",
        "",
        f"- 比较口径：{plan['comparison_rule']}",
        f"- {plan['no_go_note']}",
        "",
    ]
    return "\n".join(lines)

__all__ = [
    "DEFAULT_SCRIPT",
    "MEMORY_ARMS",
    "MEMORY_KIND_PREFIXES",
    "MEMORY_PINNED_BASE",
    "V14_PROJECTION",
    "BOTTLENECK_OK",
    "BOTTLENECK_SHORT",
    "memory_ablation_plan",
    "memory_bottleneck_v14",
    "memory_markdown",
    "memory_arm_configs",
    "memory_offline_probe",
    "memory_single_factor_audit",
    "memory_study_report",
]
