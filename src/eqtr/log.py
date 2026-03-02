"""Logging configuration for the application."""

import logging

from elasticapm.handlers.logging import LoggingFilter

from eqtr.settings import SETTINGS


def _has_filter_type(logger: logging.Logger, filter_type: type[logging.Filter]) -> bool:
    return any(isinstance(current_filter, filter_type) for current_filter in logger.filters)


def _resolve_console_handlers() -> list[logging.Handler]:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    if uvicorn_error_logger.handlers:
        return list(uvicorn_error_logger.handlers)

    uvicorn_logger = logging.getLogger("uvicorn")
    if uvicorn_logger.handlers:
        return list(uvicorn_logger.handlers)

    return [logging.StreamHandler()]


def _configure_apm_log_correlation(logger: logging.Logger) -> None:
    if SETTINGS.apm.enabled and not _has_filter_type(logger, LoggingFilter):
        logger.addFilter(LoggingFilter())


def get_logger(logger_name: str) -> logging.Logger:
    """Get a logger instance."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(SETTINGS.log_level.upper())

    logger.handlers = []
    for handler in _resolve_console_handlers():
        logger.addHandler(handler)

    _configure_apm_log_correlation(logger)

    logger.propagate = False
    return logger
