# Elastic Query Tenant Relay

This repo contains a Python app that periodically queries the Elasticsearch
APIs to fetch the latest Kibana alerts, which are then exposed via a REST API
endpoint.

## Deployment

Install the dependencies:

```bash
uv sync
```

Install pre-commit hooks:

```bash
prek install
```
