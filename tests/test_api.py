import asyncio
import importlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request


@pytest.fixture
def api_module():
    return importlib.import_module("eqtr.api")


def _build_request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "headers": headers})


class DummyApmClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def begin_transaction(self, transaction_type: str) -> None:
        self.calls.append(("begin", transaction_type))

    def end_transaction(self) -> None:
        self.calls.append(("end", None))


class SuccessfulSearch:
    def __init__(self, *, using):
        self.using = using

    def index(self, _):
        return self

    def query(self, _):
        return self

    def source(self, *, fields):
        self.fields = fields
        return self

    def params(self, **_):
        return self

    def scan(self):
        return [SimpleNamespace(to_dict=lambda: {"alert": "fresh"})]


class FailingSearch:
    def __init__(self, *, using):
        self.using = using

    def index(self, _):
        return self

    def query(self, _):
        return self

    def source(self, *, fields):
        self.fields = fields
        return self

    def params(self, **_):
        return self

    def scan(self):
        msg = "upstream error"
        raise RuntimeError(msg)


def test_verify_token_accepts_valid_bearer_token(api_module) -> None:
    request = _build_request([(b"authorization", b"Bearer secret-token")])

    result = api_module.verify_token(request)

    assert result is True


def test_verify_token_rejects_missing_authorization_header(api_module) -> None:
    request = _build_request([])

    with pytest.raises(HTTPException, match="Missing or invalid Authorization header"):
        api_module.verify_token(request)


def test_verify_token_rejects_invalid_bearer_token(api_module) -> None:
    request = _build_request([(b"authorization", b"Bearer wrong-token")])

    with pytest.raises(HTTPException, match="Invalid token"):
        api_module.verify_token(request)


def test_kibana_alerts_returns_cached_data_list(api_module) -> None:
    cached_data = [{"alert": "one"}, {"alert": "two"}]
    api_module.app.state.cached_data = cached_data
    api_module.app.state.health_status = "ok"

    result = asyncio.run(api_module.kibana_alerts("token", None, None, None))

    assert result == cached_data


def test_kibana_alerts_returns_500_when_service_is_degraded(api_module) -> None:
    api_module.app.state.health_status = "degraded"
    api_module.app.state.cached_data = []

    with pytest.raises(HTTPException, match="Service degraded"):
        asyncio.run(api_module.kibana_alerts("token", None, None, None))


def test_kibana_alerts_filters_requested_fields(api_module) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = [
        {
            "@timestamp": "2026-03-02T00:00:00Z",
            "kibana": {"alert": {"rule": {"name": "Rule 1"}, "severity": "high"}},
        },
    ]

    result = asyncio.run(api_module.kibana_alerts("token", "@timestamp,kibana.alert.severity", None, None))

    assert result == [
        {
            "@timestamp": "2026-03-02T00:00:00Z",
            "kibana": {"alert": {"severity": "high"}},
        },
    ]


def test_kibana_alerts_rejects_unsupported_fields(api_module) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = []

    with pytest.raises(HTTPException, match="Unsupported fields"):
        asyncio.run(api_module.kibana_alerts("token", "kibana.alert.unknown", None, None))


def test_kibana_alerts_filters_by_rule_name(api_module) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = [
        {"kibana": {"alert": {"rule": {"name": "Rule 1"}, "severity": "high"}}},
        {"kibana": {"alert": {"rule": {"name": "Rule 2"}, "severity": "low"}}},
    ]

    result = asyncio.run(api_module.kibana_alerts("token", None, "Rule 2", None))

    assert result == [{"kibana": {"alert": {"rule": {"name": "Rule 2"}, "severity": "low"}}}]


def test_kibana_alerts_filters_by_rule_name_and_severity(api_module) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = [
        {"kibana": {"alert": {"rule": {"name": "Rule 1"}, "severity": "high"}}},
        {"kibana": {"alert": {"rule": {"name": "Rule 1"}, "severity": "low"}}},
    ]

    result = asyncio.run(api_module.kibana_alerts("token", None, "Rule 1", "high"))

    assert result == [{"kibana": {"alert": {"rule": {"name": "Rule 1"}, "severity": "high"}}}]


def test_kibana_alerts_rejects_empty_filter_values(api_module) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = []

    with pytest.raises(HTTPException, match="rule_name must be non-empty"):
        asyncio.run(api_module.kibana_alerts("token", None, "   ", None))


def test_kibana_alerts_rejects_rule_filter_if_field_not_available(api_module, monkeypatch) -> None:
    api_module.app.state.health_status = "ok"
    api_module.app.state.cached_data = []
    monkeypatch.setattr(api_module, "ALERT_QUERY_FIELDS_SET", frozenset({"@timestamp", "kibana.alert.severity"}))

    with pytest.raises(HTTPException, match="Filtering unavailable"):
        asyncio.run(api_module.kibana_alerts("token", None, "Rule 1", None))


def test_health_reports_degraded_status(api_module, monkeypatch) -> None:
    api_module.app.state.health_status = "degraded"
    monkeypatch.setattr(api_module.importlib.metadata, "version", lambda _: "1.2.3")

    result = asyncio.run(api_module.health())

    assert result["status"] == "degraded"
    assert result["version"] == "1.2.3"


def test_refresh_data_invalidates_cache_when_search_fails(api_module, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "Search", FailingSearch)
    api_module.app.state.cached_data = [{"stale": "value"}]
    api_module.app.state.health_status = "ok"

    asyncio.run(api_module.refresh_data())

    assert api_module.app.state.cached_data == []
    assert api_module.app.state.health_status == "degraded"


def test_refresh_data_recovers_and_sets_status_ok(api_module, monkeypatch) -> None:
    monkeypatch.setattr(api_module, "Search", SuccessfulSearch)
    api_module.app.state.cached_data = []
    api_module.app.state.health_status = "degraded"

    asyncio.run(api_module.refresh_data())

    assert api_module.app.state.cached_data == [{"alert": "fresh"}]
    assert api_module.app.state.health_status == "ok"


def test_refresh_data_starts_and_ends_apm_transaction_on_success(api_module, monkeypatch) -> None:
    apm_client = DummyApmClient()
    names: list[str] = []
    results: list[str] = []
    outcomes: list[str] = []

    monkeypatch.setattr(api_module, "APM_CLIENT", apm_client)
    monkeypatch.setattr(api_module.SETTINGS.apm, "enabled", True)
    monkeypatch.setattr(api_module, "Search", SuccessfulSearch)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_name", names.append)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_result", results.append)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_outcome", outcomes.append)

    asyncio.run(api_module.refresh_data())

    assert apm_client.calls == [
        ("begin", "scheduled"),
        ("end", None),
    ]
    assert names == ["refresh_data"]
    assert results == ["success"]
    assert outcomes == ["success"]


def test_refresh_data_ends_apm_transaction_as_failure(api_module, monkeypatch) -> None:
    apm_client = DummyApmClient()
    names: list[str] = []
    results: list[str] = []
    outcomes: list[str] = []

    monkeypatch.setattr(api_module, "APM_CLIENT", apm_client)
    monkeypatch.setattr(api_module.SETTINGS.apm, "enabled", True)
    monkeypatch.setattr(api_module, "Search", FailingSearch)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_name", names.append)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_result", results.append)
    monkeypatch.setattr(api_module.elasticapm, "set_transaction_outcome", outcomes.append)

    asyncio.run(api_module.refresh_data())

    assert apm_client.calls == [
        ("begin", "scheduled"),
        ("end", None),
    ]
    assert names == ["refresh_data"]
    assert results == ["failure"]
    assert outcomes == ["failure"]
