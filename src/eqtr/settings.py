"""Application settings management using Pydantic."""

import logging
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)  # custom logger is not available in this module, using standard logging


class _CACertsFileSettings:
    ca_certs_file_path: str | None = None

    @field_validator("ca_certs_file_path")
    @classmethod
    def validate_ca_certs_file_path(cls, value: str | None) -> str | None:
        """Validate that the provided CA certs file path exists and is a file."""
        if value is None:
            return value

        as_path = Path(value)

        if not as_path.exists():
            msg = f"CA certs file path does not exist: {value}"
            raise ValueError(msg)
        if not as_path.is_file():
            msg = f"CA certs file path is not a file: {value}"
            raise ValueError(msg)

        return value


class _ElasticsearchSettings(_CACertsFileSettings, BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ES_")

    url: str = Field(...)
    api_key: str = Field(...)

    query_fields: list[str] = Field(
        ["@timestamp", "kibana.alert.rule.name", "kibana.alert.severity"],
        validate_default=False,
    )
    query_match_workflow_status: str = "open"

    space: str = Field(...)

    @field_validator("query_fields", mode="before")
    @classmethod
    def check_query_fields(cls, data: str) -> list[str]:
        """Validate that query_fields is a comma-separated string and convert it to a list."""
        if isinstance(data, str):
            return [field.strip() for field in data.split(",")]
        msg = "query_fields must be a comma-separated string"
        raise ValueError(msg)


class _APMSettings(_CACertsFileSettings, BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APM_")

    enabled: bool | None = None

    service_name: str | None = None
    service_node_name: str | None = None
    secret_token: str | None = None
    server_url: str | None = None
    environment: str | None = None

    @model_validator(mode="after")
    def check_apm_settings(self) -> _APMSettings:
        """Validate that if APM is enabled, all required settings are provided.

        Also, if enable is not explicitly set, if any of the APM settings are provided, we will assume APM is enabled.
        """
        # Override enabled to True if any of the APM settings are provided, otherwise keep it as is (which could be None
        # or False)
        if self.enabled is None:
            self.enabled = self.enabled or any(
                [self.service_name, self.secret_token, self.server_url, self.environment],
            )

        if self.enabled:
            missing_fields = []
            if not self.service_name:
                missing_fields.append("service_name")
            if not self.secret_token:
                missing_fields.append("secret_token")
            if not self.server_url:
                missing_fields.append("server_url")
            if not self.environment:
                missing_fields.append("environment")

            missing_envs_str = ", ".join([f"APM_{field.upper()}" for field in missing_fields])
            if missing_fields:
                msg = f"APM is enabled but the following environment variables are missing: {missing_envs_str}"
                raise ValueError(msg)

        return self


class MainSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_prefix="EQTR_")

    elasticsearch: _ElasticsearchSettings = _ElasticsearchSettings()
    apm: _APMSettings = _APMSettings()

    auth_bearer_token: str = Field(...)
    refresh_interval_minutes: int = 5
    log_level: str = "info"


SETTINGS = MainSettings()
