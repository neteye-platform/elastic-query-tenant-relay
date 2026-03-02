import pytest

from eqtr.settings import _APMSettings, _ElasticsearchSettings


def test_elasticsearch_query_fields_from_comma_separated_string() -> None:
    settings = _ElasticsearchSettings.model_validate(
        {
            "url": "http://localhost:9200",
            "api_key": "test-api-key",
            "query_fields": "@timestamp, kibana.alert.rule.name",
        },
    )

    assert settings.query_fields == ["@timestamp", "kibana.alert.rule.name"]


def test_elasticsearch_query_fields_rejects_non_string_input() -> None:
    with pytest.raises(ValueError, match="query_fields must be a comma-separated string"):
        _ElasticsearchSettings.model_validate(
            {
                "url": "http://localhost:9200",
                "api_key": "test-api-key",
                "query_fields": ["@timestamp"],
            },
        )


def test_elasticsearch_accepts_existing_ca_certs_file_path(tmp_path) -> None:
    certs_file = tmp_path / "ca.crt"
    certs_file.write_text("cert", encoding="utf-8")

    settings = _ElasticsearchSettings.model_validate(
        {
            "url": "http://localhost:9200",
            "api_key": "test-api-key",
            "ca_certs_file_path": str(certs_file),
        },
    )

    assert settings.ca_certs_file_path == str(certs_file)


def test_elasticsearch_rejects_missing_ca_certs_file_path() -> None:
    with pytest.raises(ValueError, match="CA certs file path does not exist"):
        _ElasticsearchSettings.model_validate(
            {
                "url": "http://localhost:9200",
                "api_key": "test-api-key",
                "ca_certs_file_path": "/path/does/not/exist.crt",
            },
        )


def test_apm_auto_enables_when_any_apm_field_is_present() -> None:
    with pytest.raises(ValueError, match="APM is enabled but the following environment variables are missing"):
        _APMSettings(service_name="eqtr")


def test_apm_enabled_with_all_required_fields_is_valid() -> None:
    settings = _APMSettings(
        enabled=True,
        service_name="eqtr",
        secret_token="secret",
        server_url="http://apm.local",
        environment="production",
    )

    assert settings.enabled is True
    assert settings.service_name == "eqtr"
