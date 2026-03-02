"""REST API for Kibana alerts."""

import importlib.metadata
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated

import elasticapm
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from elasticapm.contrib.starlette import ElasticAPM
from elasticsearch.dsl import Search
from elasticsearch.dsl.query import Match
from elasticsearch.dsl.types import MatchQuery
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPBearer

from eqtr.apm import capture_exception, capture_span, set_custom_context
from eqtr.clients import APM_CLIENT, ELASTICSEARCH_CLIENT
from eqtr.log import get_logger
from eqtr.settings import SETTINGS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = get_logger(__name__)


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
                .index(f".alerts-security.alerts-{SETTINGS.kibana.space}")
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

        token = auth_header.split(" ")[1]
        if token != SETTINGS.auth_bearer_token:
            logger.debug("Unauthorized access attempt with invalid token", extra={"provided_token": token})
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        return True


@app.get("/kibana/alerts")
async def kibana_alerts(_: Annotated[str, Depends(verify_token)]) -> list[dict]:
    """Return cached Kibana alerts."""
    with capture_span("endpoint.kibana_alerts", span_type="app"):
        if app.state.health_status != "ok":
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Service degraded")

        return app.state.cached_data


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    with capture_span("endpoint.health", span_type="app"):
        return {
            "status": app.state.health_status,
            "version": importlib.metadata.version("eqtr"),
            "tagline": "You know, for alerts!",
        }
