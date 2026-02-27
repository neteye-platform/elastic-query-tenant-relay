"""Logging configuration for the application."""

import logging

from elasticapm.handlers.logging import LoggingHandler

from eqtr.settings import APM_CLIENT, SETTINGS

APM_FORMATTER = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s trace.id=%(elasticapm_trace_id)s transaction.id=%(elasticapm_transaction_id)s",  # noqa: E501
)


def get_logger(logger_name: str) -> logging.Logger:
    """Get a logger instance."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(SETTINGS.log_level.upper())
    if SETTINGS.apm.enabled:
        apm_handler = LoggingHandler(client=APM_CLIENT)
        apm_handler.setFormatter(APM_FORMATTER)
        logger.addHandler(apm_handler)
    return logger
