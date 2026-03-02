"""Clients for external services."""

import os
from typing import cast

from elastic_transport.client_utils import DefaultType
from elasticsearch import Elasticsearch

from eqtr.settings import SETTINGS

ELASTICSEARCH_CLIENT = Elasticsearch(
    SETTINGS.elasticsearch.url,
    api_key=SETTINGS.elasticsearch.api_key,
    ca_certs=cast("str | DefaultType", SETTINGS.elasticsearch.ca_certs_file_path or DefaultType.value),
)


APM_CLIENT = None

if SETTINGS.apm.enabled:
    import elasticapm
    from elasticapm.contrib.starlette import make_apm_client

    apm_config = {
        "ENVIRONMENT": SETTINGS.apm.environment,
        "SECRET_TOKEN": SETTINGS.apm.secret_token,
        "SERVER_URL": SETTINGS.apm.server_url,
        "SERVICE_NAME": SETTINGS.apm.service_name,
    }

    service_node_name = SETTINGS.apm.service_node_name or os.getenv("HOSTNAME")
    if service_node_name:
        apm_config["SERVICE_NODE_NAME"] = service_node_name

    if SETTINGS.apm.ca_certs_file_path:
        apm_config["SERVER_CA_CERT_FILE"] = SETTINGS.apm.ca_certs_file_path

    APM_CLIENT = make_apm_client(apm_config)
    set_client = getattr(elasticapm, "set_client", None)
    if callable(set_client):
        set_client(APM_CLIENT)
