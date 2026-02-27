"""REST API for Kibana alerts."""

import importlib.metadata
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Annotated

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from elasticapm.contrib.starlette import ElasticAPM
from elasticsearch.dsl import Search
from elasticsearch.dsl.query import Match
from elasticsearch.dsl.types import MatchQuery
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPBearer

from eqtr.log import get_logger
from eqtr.settings import APM_CLIENT, ELASTICSEARCH_CLIENT, SETTINGS

if TYPE_CHECKING:
    import types

logger = get_logger(__name__)


async def refresh_data() -> None:
    """Fetch data from Elasticsearch and update the cache."""
    logger.info("Refreshing data from Elasticsearch...")

    # Query elasticsearch (keeping pagination in mind if there are many alerts)
    search = (
        Search(using=ELASTICSEARCH_CLIENT)
        .index(f".alerts-security.alerts-{os.environ['KIBANA_SPACE']}")
        .query(
            Match(
                "kibana.alert.workflow_status",
                MatchQuery(query=SETTINGS.elasticsearch.query_match_workflow_status),
            ),
        )
        .source(fields=list(SETTINGS.elasticsearch.query_fields))
    )
    search = search.params(ignore_unavailable=True)

    # Get results
    result = search.scan()

    app.state.cached_data = [hit.to_dict() for hit in result]
    logger.debug("Cache of alerts finished", extra={"num_alerts": len(app.state.cached_data)})


@asynccontextmanager
async def _lifespan(_: FastAPI) -> types.AsyncGeneratorType:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_data, "interval", minutes=SETTINGS.refresh_interval_minutes)
    scheduler.start()

    # Run once at startup
    await refresh_data()

    yield
    scheduler.shutdown()


app = FastAPI(lifespan=_lifespan)
security = HTTPBearer()

if SETTINGS.apm.enabled:
    app.add_middleware(ElasticAPM, client=APM_CLIENT)  # type: ignore[arg-type]


def verify_token(request: Request) -> bool:
    """Check if the Authorization header contains the expected Bearer token."""
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        logger.debug("Unauthorized access attempt with missing or invalid Authorization header")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = auth_header.split(" ")[1]
    if token != SETTINGS.auth_bearer_token:
        logger.debug("Unauthorized access attempt with invalid token", extra={"provided_token": token})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return True


@app.get("/kibana/alerts")
async def kibana_alerts(_: Annotated[str, Depends(verify_token)]) -> list[dict]:
    """Return cached Kibana alerts."""
    return app.state.cached_data.get("alerts", [])


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": importlib.metadata.version("eqtr"), "tagline": "You know, for alerts!"}
