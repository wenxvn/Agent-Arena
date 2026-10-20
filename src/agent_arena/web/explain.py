"""把运行状态、终止码与指标五态翻译成普通用户能读懂的中文。

只使用环境已记录的终止码与指标状态；不对模型意图做猜测。
"""

from __future__ import annotations

from typing import Any

from agent_arena.web.schemas import RunMode, RunState

STATE_LABELS: dict[str, str] = {
    RunState.CREATED.value: "已创建",
    RunState.QUEUED.value: "排队中",
    RunState.RUNNING.value: "运行中",
    RunState.SUCCEEDED.value: "成功",
    RunState.FAILED.value: "失败",
    RunState.BUDGET_REACHED.value: "预算耗尽",
    RunState.CANCELLED.value: "已取消",
    RunState.PROVIDER_ERROR.value: "Provider 错误",
    RunState.INTERRUPTED.value: "已中断",
}

MODE_LABELS: dict[str, str] = {
    RunMode.OFFLINE.value: "离线演示（公开规则策略，非模型挑战）",
    RunMode.LIVE.value: "真实模型挑战",
}

METRIC_STATE_LABELS: dict[str, str] = {
    "VALID": "有效",
    "CENSORED": "截尾（未在预算内结束）",
    "NOT_APPLICABLE": "不适用",
    "MISSING": "缺失",
    "INVALID": "非法",
}

TERMINATION_TEXT: dict[str, str] = {
    "decision_budget_exhausted": "达到本局决策上限，环境尚未结算。",
    "ACTION_LIMIT_REACHED": "达到环境动作上限，按截尾处理，不记为成功或失败。",
    "request_limit_exceeded": "达到本局请求数上限，已停止。",
    "input_token_limit_exceeded": "达到本局输入 token 上限，已停止。",
    "output_token_limit_exceeded": "达到本局输出 token 上限，已停止。",
    "cost_limit_exceeded": "达到本局费用上限，已停止。",
    "provider_usage_exceeded_registered_cap": "Provider 返回的 usage 超出登记上限，已按超限停止。",
    "unknown_provider_usage": "Provider 未返回可确认的 usage，按未知消费停止。",
    "cancelled_by_user": "用户在运行中请求停止；已在当前步骤结束后退出。",
    "interrupted_on_restart": "进程在运行中终止；恢复后标记为中断，已保留可读部分。",
    "FLOODED": "水位超过公开上限。",
    "LOST_POWER": "电力归零。",
    "LOST_OXYGEN": "供氧归零。",
    "TOO_MUCH_WATER": "修复前水位仍高于公开阈值。",
    "OXYGEN_TOO_LOW": "修复前供氧低于公开阈值。",
    "STARVED": "食物归零。",
    "STATION_LOST": "站体完整度归零。",
    "OUT_OF_FUEL": "燃料不足，运输失败。",
    "PHASE_OUT_OF_ORDER": "动作跳过了公开阶段顺序。",
    "EVIDENCE_MISSING": "指控引用了未记录或未观察的证据。",
    "CLAIM_CONTRADICTS_RECORDED_EVIDENCE": "指控值被已记录证据排除。",
    "ACCUSATION_WITHOUT_TWO_SOURCES": "指控字段的来源类别不足两种。",
    "CASE_REJECTED": "法庭拒绝了这次指控，具体原因见环境返回码。",
}


def state_label(state: str) -> str:
    return STATE_LABELS.get(state, state)


def mode_label(mode: str) -> str:
    return MODE_LABELS.get(mode, mode)


def metric_state_label(state: str) -> str:
    return METRIC_STATE_LABELS.get(state, state)


def explain_termination(termination: str | None, *, state: str | None = None) -> str:
    if not termination:
        return "环境没有返回终止码。"
    if termination in TERMINATION_TEXT:
        return TERMINATION_TEXT[termination]
    if state == RunState.INTERRUPTED.value:
        return TERMINATION_TEXT["interrupted_on_restart"]
    return f"环境按公开规则结束，终止码：{termination}。"


def failure_summary(result: dict[str, Any]) -> dict[str, str]:
    """结果页失败解释：标题 + 依据；不编造模型动机。"""

    state = str(result.get("state") or "")
    termination = result.get("termination")
    termination_text = str(termination) if termination else ""
    success = bool(result.get("success"))

    if state == RunState.SUCCEEDED.value or success:
        headline = "挑战成功"
        detail = "环境已返回成功终局。"
    elif state == RunState.CANCELLED.value:
        headline = "运行已取消"
        detail = "本次运行由用户停止，未完成终局判定。"
    elif state == RunState.INTERRUPTED.value:
        headline = "运行被中断"
        detail = "进程在运行中退出；已保留中断前的公开动作记录。"
    elif state == RunState.PROVIDER_ERROR.value:
        headline = "Provider 错误"
        detail = str(result.get("message") or "连接或响应异常，已 fail-closed 停止。")
    elif state == RunState.BUDGET_REACHED.value:
        headline = "预算或截尾"
        detail = explain_termination(termination_text or None, state=state)
    elif state == RunState.FAILED.value:
        headline = "挑战失败"
        detail = explain_termination(termination_text or None, state=state)
    else:
        headline = "未完成"
        detail = "运行尚未产生终局结果。"

    primary_state = str(result.get("primary_metric_state") or "")
    source = (
        f"主指标 {result.get('primary_metric') or 'N/A'}："
        f"{metric_state_label(primary_state) if primary_state else 'N/A'}"
        f"（{result.get('primary_metric_value')}）"
    )
    return {"headline": headline, "detail": detail, "source": source}


__all__ = [
    "MODE_LABELS",
    "STATE_LABELS",
    "explain_termination",
    "failure_summary",
    "metric_state_label",
    "mode_label",
    "state_label",
]
