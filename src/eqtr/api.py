"""REST API for Kibana alerts."""

from __future__ import annotations

import importlib.metadata
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated, cast

import elasticapm
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from elasticapm.contrib.starlette import ElasticAPM
from elasticsearch.dsl import Search
from elasticsearch.dsl.query import Match
from elasticsearch.dsl.types import MatchQuery
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer

from eqtr.apm import capture_exception, capture_span, set_custom_context
from eqtr.clients import APM_CLIENT, ELASTICSEARCH_CLIENT
from eqtr.log import get_logger
from eqtr.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)

ALERT_QUERY_FIELDS = tuple(SETTINGS.elasticsearch.query_fields)
ALERT_QUERY_FIELDS_SET = frozenset(ALERT_QUERY_FIELDS)
_MISSING = object()
FILTERABLE_FIELDS = {
    "rule_name": "kibana.alert.rule.name",
    "severity": "kibana.alert.severity",
}


def _parse_requested_fields(fields: str | None) -> tuple[str, ...] | None:
    if fields is None:
        return None

    parsed_fields = tuple(dict.fromkeys(field.strip() for field in fields.split(",") if field.strip()))
    if not parsed_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one valid field is required")

    unknown_fields = [field for field in parsed_fields if field not in ALERT_QUERY_FIELDS_SET]
    if unknown_fields:
        allowed_fields = ", ".join(ALERT_QUERY_FIELDS)
        unknown_fields_str = ", ".join(unknown_fields)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported fields: {unknown_fields_str}. Allowed fields: {allowed_fields}",
        )

    return parsed_fields


def _get_nested_value(data: dict[str, object], dotted_path: str) -> object:
    current: object = data
    for key in dotted_path.split("."):
        if not isinstance(current, dict):
            return _MISSING

        current_dict = cast("dict[str, object]", current)
        if key not in current_dict:
            return _MISSING

        current = current_dict[key]
    return current


def _set_nested_value(target: dict[str, object], dotted_path: str, value: object) -> None:
    keys = dotted_path.split(".")
    current = target
    for key in keys[:-1]:
        nested_obj = current.get(key)
        if isinstance(nested_obj, dict):
            nested = cast("dict[str, object]", nested_obj)
        else:
            nested = {}
            current[key] = nested

        current = nested
    current[keys[-1]] = value


def _project_alert(alert: dict[str, object], requested_fields: tuple[str, ...]) -> dict[str, object]:
    projected: dict[str, object] = {}
    for field in requested_fields:
        value = _get_nested_value(alert, field)
        if value is not _MISSING:
            _set_nested_value(projected, field, value)
    return projected


def _validate_filterable_fields(selected_filters: dict[str, str]) -> None:
    unavailable = [
        FILTERABLE_FIELDS[filter_name]
        for filter_name in selected_filters
        if FILTERABLE_FIELDS[filter_name] not in ALERT_QUERY_FIELDS_SET
    ]
    if unavailable:
        unavailable_str = ", ".join(unavailable)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filtering unavailable for fields not present in ES_QUERY_FIELDS: {unavailable_str}",
        )


def _normalize_filter_value(name: str, value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if normalized:
        return normalized

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{name} must be non-empty")


def _filter_alerts(alerts: list[dict[str, object]], selected_filters: dict[str, str]) -> list[dict[str, object]]:
    if not selected_filters:
        return alerts

    filter_paths = {FILTERABLE_FIELDS[name]: value for name, value in selected_filters.items()}
    return [
        alert
        for alert in alerts
        if all(_get_nested_value(alert, path) == expected for path, expected in filter_paths.items())
    ]


async def refresh_data() -> None:
    """Fetch data from Elasticsearch and update the cache."""
    logger.info("Refreshing data from Elasticsearch.")
    apm_client = APM_CLIENT
    transaction_started = False

    if SETTINGS.apm.enabled and apm_client is not None:
        apm_client.begin_transaction("scheduled")
        elasticapm.set_transaction_name("refresh_data")
        transaction_started = True

    try:
        with capture_span("refresh_data.search", span_type="db.elasticsearch"):
            search = (
                Search(using=ELASTICSEARCH_CLIENT)
                .index(f".alerts-security.alerts-{SETTINGS.elasticsearch.space}")
                .query(
                    Match(
                        "kibana.alert.workflow_status",
                        MatchQuery(query=SETTINGS.elasticsearch.query_match_workflow_status),
                    ),
                )
                .source(fields=list(SETTINGS.elasticsearch.query_fields))
            )
            search = search.params(ignore_unavailable=True)
            app.state.cached_data = [hit.to_dict() for hit in search.scan()]

        with capture_span("refresh_data.cache_update", span_type="app"):
            app.state.health_status = "ok"
            set_custom_context(
                {
                    "cached_alerts_count": len(app.state.cached_data),
                    "refresh_status": "ok",
                },
            )
    except Exception:
        app.state.cached_data = []
        app.state.health_status = "degraded"
        capture_exception()
        set_custom_context({"cached_alerts_count": 0, "refresh_status": "degraded"})
        if transaction_started and apm_client is not None:
            elasticapm.set_transaction_result("failure")
            elasticapm.set_transaction_outcome("failure")
            apm_client.end_transaction()
        logger.exception("Failed to refresh data from Elasticsearch. Cache invalidated.")
        return

    if transaction_started and apm_client is not None:
        elasticapm.set_transaction_result("success")
        elasticapm.set_transaction_outcome("success")
        apm_client.end_transaction()

    logger.debug("Cache of alerts finished", extra={"num_alerts": len(app.state.cached_data)})


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_data, "interval", minutes=SETTINGS.refresh_interval_minutes)
    scheduler.start()

    await refresh_data()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=_lifespan)
security = HTTPBearer()
app.state.cached_data = []
app.state.health_status = "ok"

if SETTINGS.apm.enabled:
    app.add_middleware(ElasticAPM, client=APM_CLIENT)  # type: ignore[arg-type]


def verify_token(request: Request) -> bool:
    """Check if the Authorization header contains the expected Bearer token."""
    with capture_span("auth.verify_token", span_type="app"):
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.debug("Unauthorized access attempt with missing or invalid Authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
            )

        try:
            token = auth_header.split(" ")[1].lstrip()
        except IndexError as e:
            logger.debug(
                "Unauthorized access attempt with malformed Authorization header",
                extra={"auth_header": auth_header},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header",
            ) from e
        if token != SETTINGS.auth_bearer_token:
            logger.debug("Unauthorized access attempt with invalid token", extra={"token_length": len(token)})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        return True


@app.get("/kibana/alerts")
async def kibana_alerts(
    _: Annotated[str, Depends(verify_token)],
    fields: Annotated[str | None, Query()] = None,
    rule_name: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """Return cached Kibana alerts."""
    with capture_span("endpoint.kibana_alerts", span_type="app"):
        if app.state.health_status != "ok":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service degraded")

        selected_filters = {
            name: normalized
            for name, normalized in {
                "rule_name": _normalize_filter_value("rule_name", rule_name),
                "severity": _normalize_filter_value("severity", severity),
            }.items()
            if normalized is not None
        }
        _validate_filterable_fields(selected_filters)

        filtered_alerts = _filter_alerts(app.state.cached_data, selected_filters)
        requested_fields = _parse_requested_fields(fields)
        if requested_fields is None:
            return filtered_alerts

        return [_project_alert(alert, requested_fields) for alert in filtered_alerts]


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    with capture_span("endpoint.health", span_type="app"):
        return {
            "status": app.state.health_status,
            "version": importlib.metadata.version("eqtr"),
            "tagline": "You know, for alerts!",
        }
