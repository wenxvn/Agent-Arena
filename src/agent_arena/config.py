"""Validated runtime configuration with explicit source precedence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class JsonDefaultsSource(PydanticBaseSettingsSource):
    """Load checked in, non secret defaults after environment based sources."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        defaults_file = getattr(settings_cls, "defaults_file", None)
        if not isinstance(defaults_file, Path):
            raise TypeError("Runtime settings must define a defaults_file path.")
        self._defaults_file = defaults_file

    def get_field_value(
        self,
        field: Any,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        try:
            raw_defaults = self._defaults_file.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise RuntimeError(f"Runtime defaults file is missing: {self._defaults_file}") from exc

        try:
            parsed_defaults = json.loads(raw_defaults)
        except json.JSONDecodeError as exc:
            message = f"Runtime defaults file is invalid JSON: {self._defaults_file}"
            raise RuntimeError(message) from exc

        if not isinstance(parsed_defaults, dict):
            raise RuntimeError("Runtime defaults must contain a JSON object.")
        return parsed_defaults


class RuntimeSettings(BaseSettings):
    """The one public configuration model for CLI and provider code."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGENT_ARENA_",
        extra="ignore",
        populate_by_name=True,
    )

    defaults_file: ClassVar[Path] = Path("config/runtime.defaults.json")

    provider: Literal["fake", "bailian"]
    world: str
    world_version: str
    agent: Literal["react", "memory"]
    seed: int
    runs_dir: Path
    results_dir: Path
    step_limit: int = Field(gt=0)
    request_timeout_seconds: int = Field(gt=0)
    retry_count: int = Field(ge=0)
    retry_backoff_seconds: list[int] = Field(default_factory=list)
    enable_thinking: bool
    model_name: str = Field(validation_alias=AliasChoices("OPENAI_MODEL", "model_name"))
    base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_BASE_URL", "base_url"),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    dashscope_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DASHSCOPE_API_KEY", "dashscope_api_key"),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            JsonDefaultsSource(settings_cls),
            file_secret_settings,
        )

    @model_validator(mode="after")
    def validate_retry_policy(self) -> RuntimeSettings:
        if len(self.retry_backoff_seconds) != self.retry_count:
            raise ValueError("retry_backoff_seconds must contain one delay for each retry.")
        if any(delay < 0 for delay in self.retry_backoff_seconds):
            raise ValueError("retry_backoff_seconds cannot contain negative delays.")
        return self

    @classmethod
    def load(
        cls,
        cli_overrides: dict[str, Any] | None = None,
        *,
        env_file: Path | None = Path(".env"),
    ) -> RuntimeSettings:
        """Load CLI, environment, local dotenv, then checked in defaults."""

        overrides = {
            name: value for name, value in (cli_overrides or {}).items() if value is not None
        }
        return cls(_env_file=env_file, **overrides)  # type: ignore[call-arg]

    def api_key_for_bailian(self) -> SecretStr:
        """Return the configured key while rejecting ambiguous credentials."""

        openai_key = self.openai_api_key.get_secret_value() if self.openai_api_key else None
        dashscope_key = (
            self.dashscope_api_key.get_secret_value() if self.dashscope_api_key else None
        )

        if openai_key and dashscope_key and openai_key != dashscope_key:
            raise ValueError("OPENAI_API_KEY and DASHSCOPE_API_KEY must match when both are set.")
        if openai_key:
            return SecretStr(openai_key)
        if dashscope_key:
            return SecretStr(dashscope_key)
        raise ValueError("Bailian requires OPENAI_API_KEY or DASHSCOPE_API_KEY.")

    def require_bailian(self) -> tuple[str, SecretStr]:
        """Validate Bailian only when a real provider is selected."""

        if not self.base_url:
            raise ValueError("Bailian requires OPENAI_BASE_URL.")
        return self.base_url, self.api_key_for_bailian()
