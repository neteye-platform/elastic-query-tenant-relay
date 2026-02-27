"""Application settings management using Pydantic."""

from pathlib import Path

from elasticsearch import Elasticsearch
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class _ElasticsearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ES_", extra="ignore")

    url: str = Field(..., env="URL")
    api_key: str = Field(...)
    ca_file_path: Path = Path("/var/lib/eqtr/elasticsearch-ca.cer")

    query_fields: list[str] = Field(
        ["@timestamp", "kibana.alert.rule.name", "kibana.alert.severity"],
        validate_default=False,
    )

    query_match_workflow_status: str = "open"

    @field_validator("query_fields", mode="before")
    @classmethod
    def check_query_fields(cls, data: str) -> list[str]:
        """Validate that query_fields is a comma-separated string and convert it to a list."""
        if isinstance(data, str):
            return [field.strip() for field in data.split(",")]
        msg = "query_fields must be a comma-separated string"
        raise ValueError(msg)

    @model_validator(mode="after")
    def check_ca_file_exists(self) -> _ElasticsearchSettings:
        """Check if the CA file exists."""
        if not self.ca_file_path.is_file():
            msg = f"CA file not found at {self.ca_file_path}"
            raise ValueError(msg)
        return self


class _KibanaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KBN_", extra="ignore")

    space: str = Field(...)


class _APMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APM_", extra="ignore")

    enabled: bool = True

    service_name: str = Field(...)
    secret_token: str = Field(...)
    server_url: str = Field(...)


class MainSettings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(env_prefix="EQTR_", extra="ignore")

    elasticsearch: _ElasticsearchSettings = _ElasticsearchSettings()
    kibana: _KibanaSettings = _KibanaSettings()
    apm: _APMSettings = _APMSettings()

    auth_bearer_token: str = Field(...)
    refresh_interval_minutes: int = 5
    log_level: str = "info"


SETTINGS = MainSettings()


ca_certs = SETTINGS.elasticsearch.ca_file_path.read_text()
if not ca_certs:
    msg = f"CA certificate file at {SETTINGS.elasticsearch.ca_file_path} is empty or cannot be read."
    raise ValueError(msg)

ELASTICSEARCH_CLIENT = Elasticsearch(
    SETTINGS.elasticsearch.url,
    api_key=SETTINGS.elasticsearch.api_key,
    ca_certs=ca_certs,
)


APM_CLIENT = None

if SETTINGS.apm.enabled:
    from elasticapm.contrib.starlette import make_apm_client

    APM_CLIENT = make_apm_client(
        {
            "SERVICE_NAME": SETTINGS.apm.service_name,
            "SECRET_TOKEN": SETTINGS.apm.secret_token,
            "SERVER_URL": SETTINGS.apm.server_url,
        },
    )
