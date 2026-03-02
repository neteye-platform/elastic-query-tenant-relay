"""Clients for external services."""

from elasticsearch import Elasticsearch

from eqtr.settings import SETTINGS

ELASTICSEARCH_CLIENT = Elasticsearch(
    SETTINGS.elasticsearch.url,
    api_key=SETTINGS.elasticsearch.api_key,
    ca_certs=SETTINGS.elasticsearch.ca_certs_file_path,
)


APM_CLIENT = None

if SETTINGS.apm.enabled:
    from elasticapm.contrib.starlette import make_apm_client

    APM_CLIENT = make_apm_client(
        {
            "SERVICE_NAME": SETTINGS.apm.service_name,
            "SECRET_TOKEN": SETTINGS.apm.secret_token,
            "SERVER_URL": SETTINGS.apm.server_url,
            "SERVER_CA_CERT_FILE": SETTINGS.apm.ca_certs_file_path,
        },
    )
