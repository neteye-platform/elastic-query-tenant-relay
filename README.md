# Elastic Query Tenant Relay

Elastic Query Tenant Relay (`eqtr`) pulls security alerts from Elasticsearch on
a schedule, keeps them in memory, and exposes them through a lightweight
FastAPI service.

## What It Does

- Fetches alerts from `.alerts-security.alerts-{ES_SPACE}`
- Filters by workflow status (default `open`)
- Caches results in memory and serves them via API
- Protects alert endpoint with a bearer token
- Supports Elastic APM instrumentation for traces and correlation

## API

- `GET /health` - public health endpoint
- `GET /kibana/alerts` - protected alerts endpoint

Example request:

```bash
curl -H "Authorization: Bearer $EQTR_AUTH_BEARER_TOKEN" \
  http://localhost:8000/kibana/alerts
```

You can also filter alerts with query parameters whose names match configured
`ES_QUERY_FIELDS`. For example, if `host.hostname` is included in
`ES_QUERY_FIELDS`, you can request:

```bash
curl -H "Authorization: Bearer $EQTR_AUTH_BEARER_TOKEN" \
  "http://localhost:8000/kibana/alerts?host.hostname=web-01"
```

If you send a filter for a field that is not present in `ES_QUERY_FIELDS`, the
API returns `400 Bad Request`.

## Run with Docker

The recommended way to run `eqtr` is with Docker.

```bash
docker compose up --build
```

## Environment Variables

### Required

| Variable                 | Description                               |
| ------------------------ | ----------------------------------------- |
| `ES_URL`                 | Elasticsearch base URL                    |
| `ES_API_KEY`             | Elasticsearch API key                     |
| `ES_SPACE`               | Elasticsearch space name                  |
| `EQTR_AUTH_BEARER_TOKEN` | Bearer token required by `/kibana/alerts` |

### Optional Elasticsearch Query Settings

| Variable                         | Default                                                   | Description                                    |
| -------------------------------- | --------------------------------------------------------- | ---------------------------------------------- |
| `ES_CA_CERTS_FILE_PATH`          | unset                                                     | CA certificate file path for Elasticsearch TLS |
| `ES_QUERY_FIELDS`                | `@timestamp,kibana.alert.rule.name,kibana.alert.severity` | Comma-separated fields returned by query       |
| `ES_QUERY_MATCH_WORKFLOW_STATUS` | `open`                                                    | Workflow status filter                         |

### Optional Service Settings

| Variable                        | Default | Description                         |
| ------------------------------- | ------- | ----------------------------------- |
| `EQTR_REFRESH_INTERVAL_MINUTES` | `5`     | Cache refresh interval (in minutes) |
| `EQTR_LOG_LEVEL`                | `info`  | Application log level               |

### Optional APM Settings

APM is enabled automatically when APM configuration is provided.

| Variable                 | Required if APM enabled | Description                          |
| ------------------------ | ----------------------- | ------------------------------------ |
| `APM_SERVICE_NAME`       | yes                     | APM service name                     |
| `APM_SERVER_URL`         | yes                     | APM server URL                       |
| `APM_SECRET_TOKEN`       | yes                     | APM secret token                     |
| `APM_ENVIRONMENT`        | yes                     | Environment label                    |
| `APM_SERVICE_NODE_NAME`  | no                      | Stable node/instance identifier      |
| `APM_CA_CERTS_FILE_PATH` | no                      | CA certificate file path for APM TLS |

## Development

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check .
```

Run type checks:

```bash
uv run ty check src
```

## CI/CD

- Tests workflow: `.github/workflows/tests.yaml`
- Release workflow (tag `v*.*.*`): `.github/workflows/release-image.yaml`
  - Builds and pushes image to `ghcr.io/<owner>/<repo>`
  - Creates/updates GitHub release for the tag
