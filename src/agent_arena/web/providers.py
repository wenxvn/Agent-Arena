"""Provider 配置读取与构造。

安全边界：

- API Key、base URL 只从本机 ``.env`` / 环境变量读取，网页不接收自定义 URL；
- 页面只显示“已配置/未配置”和 URL 的 hostname，不回显密钥；
- 真实调用前可做一次显式最小连接检查；检查本身也会产生少量费用。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_arena.config import RuntimeSettings
from agent_arena.llm.bailian import ModelVerificationError
from agent_arena.llm.ollama import OllamaDecisionProvider, OllamaModelVerifier
from agent_arena.llm.openai import OpenAIDecisionProvider, OpenAIModelVerifier
from agent_arena.llm.protocol import DecisionProvider
from agent_arena.web.safety import classify_exception, mask_secret
from agent_arena.web.schemas import OFFLINE_MODEL, OFFLINE_PROVIDER, RunConfig, RunMode


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    label: str
    configured: bool
    model: str
    base_url_host: str
    key_state: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "configured": self.configured,
            "model": self.model,
            "base_url_host": self.base_url_host,
            "key_state": self.key_state,
            "detail": self.detail,
        }


def load_settings() -> RuntimeSettings:
    """只读加载本机配置；不发送网络请求。"""

    return RuntimeSettings.load()


def _host(value: str | None) -> str:
    if not value:
        return ""
    try:
        return urlparse(value).hostname or ""
    except ValueError:
        return ""


def provider_statuses() -> list[ProviderStatus]:
    settings = load_settings()
    openai_ready = bool(settings.openai_api_key and settings.base_url)
    ollama_host = _host(settings.ollama_native_base_url) or "127.0.0.1"
    return [
        ProviderStatus(
            provider_id="openai_compatible",
            label="OpenAI-compatible / MiMo",
            configured=openai_ready,
            model=settings.model_name,
            base_url_host=_host(settings.base_url),
            key_state=mask_secret(
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            ),
            detail=(
                "已从本机 .env 读取密钥与地址；网页不会显示或回传密钥。"
                if openai_ready
                else "未配置 OPENAI_API_KEY / OPENAI_BASE_URL；仍可使用离线演示。"
            ),
        ),
        ProviderStatus(
            provider_id="ollama",
            label="本地 Ollama",
            configured=True,
            model=settings.ollama_model,
            base_url_host=ollama_host,
            key_state="不需要",
            detail=(
                "本地原生 API；需要先启动 Ollama 并拉取模型。"
                "网页只检查配置，不主动探测端口。"
            ),
        ),
        ProviderStatus(
            provider_id=OFFLINE_PROVIDER,
            label="离线演示（公开规则策略）",
            configured=True,
            model=OFFLINE_MODEL,
            base_url_host="",
            key_state="不需要",
            detail="不发送任何网络请求，也不是模型挑战。",
        ),
    ]


def _settings_for(config: RunConfig) -> RuntimeSettings:
    overrides: dict[str, Any] = {
        "provider": "openai" if config.provider_id == "openai_compatible" else "ollama",
        "retry_count": 0,
        "retry_backoff_seconds": [],
        "request_timeout_seconds": 60,
        "step_limit": 200,
        "response_format": "json_object",
        "runs_dir": Path("runs/web"),
        "results_dir": Path("results/web"),
    }
    if config.provider_id == "openai_compatible":
        overrides["model_name"] = config.model
    else:
        overrides["ollama_model"] = config.model
    return RuntimeSettings.load(overrides)


def build_live_provider(config: RunConfig) -> DecisionProvider:
    if config.mode is not RunMode.LIVE:
        raise ValueError("离线模式不构造 Provider。")
    settings = _settings_for(config)
    if config.provider_id == "openai_compatible":
        if not settings.openai_api_key:
            raise ValueError("missing_api_key")
        if not settings.base_url:
            raise ValueError("missing_base_url")
        return OpenAIDecisionProvider(settings)
    return OllamaDecisionProvider(settings)


def configuration_check(config: RunConfig | None = None) -> dict[str, Any]:
    """零网络检查：配置是否齐全、是否存在明显阻塞。"""

    statuses = {item.provider_id: item for item in provider_statuses()}
    if config is None:
        return {"ok": True, "providers": [item.to_dict() for item in statuses.values()]}
    if config.mode is RunMode.OFFLINE:
        return {"ok": True, "mode": "offline", "detail": "离线演示不需要任何密钥。"}
    status = statuses.get(config.provider_id)
    if status is None:
        return {"ok": False, "mode": "live", "detail": "未知的 Provider。"}
    if config.provider_id == "openai_compatible" and not status.configured:
        return {"ok": False, "mode": "live", "detail": status.detail}
    return {
        "ok": True,
        "mode": "live",
        "detail": f"配置完整：{status.label} · {config.model}。首次真实请求会验证连通性。",
    }


def probe_live_provider(config: RunConfig) -> dict[str, Any]:
    """显式最小连接检查；只应在用户确认可能产生少量费用后调用。"""

    if config.mode is not RunMode.LIVE:
        return {"ok": False, "detail": "离线模式不需要连接检查。"}
    settings = _settings_for(config)
    result: Any
    try:
        if config.provider_id == "openai_compatible":
            if not settings.openai_api_key:
                return {"ok": False, "detail": "未配置 OPENAI_API_KEY。"}
            if not settings.base_url:
                return {"ok": False, "detail": "未配置 OPENAI_BASE_URL。"}
            result = OpenAIModelVerifier(settings).verify()
        else:
            result = OllamaModelVerifier(settings).verify()
    except ModelVerificationError:
        return {"ok": False, "detail": "连接检查失败；请确认服务、地址与密钥。"}
    except Exception as exc:  # noqa: BLE001 - do not echo provider body
        return {"ok": False, "detail": f"连接检查失败（{classify_exception(exc)}）。"}
    return {
        "ok": True,
        "model": result.model,
        "detail": "连接检查成功；该检查本身可能产生极少量费用。",
    }


__all__ = [
    "ProviderStatus",
    "build_live_provider",
    "configuration_check",
    "load_settings",
    "probe_live_provider",
    "provider_statuses",
]
