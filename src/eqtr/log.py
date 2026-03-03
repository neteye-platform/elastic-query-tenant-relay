"""Logging configuration for the application."""

import logging

from eqtr.settings import SETTINGS


def _resolve_console_handlers() -> list[logging.Handler]:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    if uvicorn_error_logger.handlers:
        return list(uvicorn_error_logger.handlers)

    uvicorn_logger = logging.getLogger("uvicorn")
    if uvicorn_logger.handlers:
        return list(uvicorn_logger.handlers)

    return [logging.StreamHandler()]


def get_logger(logger_name: str) -> logging.Logger:
    """Get a logger instance."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(SETTINGS.log_level.upper())

    logger.handlers = []
    for handler in _resolve_console_handlers():
        logger.addHandler(handler)

    logger.propagate = False
    return logger
