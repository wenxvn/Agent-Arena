"""V11 安全边界：预算常量、密钥脱敏、路径限制与错误解释。

本模块不导入 Streamlit，也不读取网络；只做纯函数校验，便于单元测试。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

#: 单局硬上限。页面与 API 都不得突破这些值。
MAX_DECISIONS = 200
MAX_REQUESTS = 200
MAX_INPUT_TOKENS = 2_000_000
MAX_OUTPUT_TOKENS = 200_000
MAX_COST_CNY = 20.0
DEFAULT_COST_CNY = 1.0

RUN_ID_PATTERN = re.compile(r"^web-\d{8}T\d{6}Z-[0-9a-f]{8}$")

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def is_valid_run_id(run_id: str) -> bool:
    return bool(RUN_ID_PATTERN.fullmatch(run_id))


def safe_child(base: Path, name: str) -> Path:
    """只允许 ``base`` 的直接子目录；拒绝 ``..``、绝对路径和符号链接。"""

    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError("非法的子目录名。")
    candidate = base / name
    resolved_base = base.resolve()
    resolved = candidate.resolve()
    if resolved.parent != resolved_base or not resolved.is_dir():
        raise ValueError("目录不存在或越界。")
    return resolved


def safe_run_dir(base: Path, run_id: str) -> Path:
    if not is_valid_run_id(run_id):
        raise ValueError("非法的 run_id。")
    return safe_child(base, run_id)


def sanitize_text(value: Any, *, limit: int = 600, secrets: Iterable[str] = ()) -> str:
    """把任意值压成可安全写入 trace/页面的短文本。"""

    text = value if isinstance(value, str) else str(value)
    text = _CONTROL.sub("", text)
    for secret in secrets:
        if secret and len(secret) >= 4:
            text = text.replace(secret, "***")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("***", text)
    return text[:limit]


def sanitize_payload(value: Any, *, depth: int = 0, secrets: Iterable[str] = ()) -> Any:
    """递归脱敏；限制深度与列表长度，避免把巨大响应写进结果文件。"""

    if depth >= 8:
        return "…"
    if isinstance(value, str):
        return sanitize_text(value, limit=2_000, secrets=secrets)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            sanitize_text(key, limit=80, secrets=secrets): sanitize_payload(
                item, depth=depth + 1, secrets=secrets
            )
            for key, item in list(value.items())[:100]
        }
    if isinstance(value, (list, tuple)):
        return [
            sanitize_payload(item, depth=depth + 1, secrets=secrets)
            for item in list(value)[:200]
        ]
    return sanitize_text(value, secrets=secrets)


def mask_secret(value: str | None) -> str:
    """只报告“是否配置”，不回显任何长度或前后缀。"""

    return "已配置" if value and value.strip() else "未配置"


def clamp_int(value: int, *, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def clamp_cost(value: float, *, low: float = 0.01, high: float = MAX_COST_CNY) -> float:
    return round(max(low, min(high, float(value))), 2)


ERROR_HINTS: dict[str, str] = {
    "AuthenticationError": "API Key 无效或已过期，请检查本机 .env。",
    "PermissionDeniedError": "该密钥没有访问此模型的权限。",
    "NotFoundError": "模型或接口地址不存在，请检查 OPENAI_MODEL / OPENAI_BASE_URL。",
    "APIConnectionError": "无法连接 Provider；本次结果未确认，已按未知消费封账。",
    "APITimeoutError": "Provider 超时；本次结果未确认，已按未知消费封账。",
    "RateLimitError": "Provider 限流，请稍后手动重试（不会自动重试）。",
    "InternalServerError": "Provider 内部错误，本次结果未确认。",
    "InsufficientQuotaError": "账户额度不足，请充值或改用离线演示。",
    "PermissionError": "本机权限拒绝写入运行目录。",
    "missing_api_key": "未配置 OPENAI_API_KEY；离线演示不受影响。",
    "missing_base_url": "未配置 OPENAI_BASE_URL；离线演示不受影响。",
    "ActionValidationError": "模型输出不符合公开动作契约，本步记为非法动作。",
    "BudgetExceeded": "已达到本局请求 / token / 费用硬上限，运行已停止。",
    "unknown": "Provider 返回了无法确认的结果；为防重复计费，已停止且不自动重试。",
}


def error_hint(category: str) -> str:
    """把错误类别映射成可操作的中文提示；未知类别给保守说明。"""

    return ERROR_HINTS.get(category, ERROR_HINTS["unknown"])


def classify_exception(exc: BaseException) -> str:
    """只取异常类型名，不读取异常正文（正文可能含请求头或密钥）。"""

    name = type(exc).__name__
    return name if name in ERROR_HINTS else "unknown"


__all__ = [
    "DEFAULT_COST_CNY",
    "ERROR_HINTS",
    "MAX_COST_CNY",
    "MAX_DECISIONS",
    "MAX_INPUT_TOKENS",
    "MAX_OUTPUT_TOKENS",
    "MAX_REQUESTS",
    "RUN_ID_PATTERN",
    "clamp_cost",
    "clamp_int",
    "classify_exception",
    "error_hint",
    "is_valid_run_id",
    "mask_secret",
    "safe_child",
    "safe_run_dir",
    "sanitize_payload",
    "sanitize_text",
]
