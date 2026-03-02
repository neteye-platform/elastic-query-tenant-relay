import logging

from elasticapm.handlers.logging import LoggingFilter

from eqtr import log


def _count_apm_filters(logger: logging.Logger) -> int:
    return sum(1 for current_filter in logger.filters if isinstance(current_filter, LoggingFilter))


def test_get_logger_adds_apm_log_correlation_filter_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(log.SETTINGS.apm, "enabled", True)

    logger = log.get_logger("eqtr.apm.enabled")

    assert _count_apm_filters(logger) == 1
    assert logger.propagate is False


def test_get_logger_does_not_add_apm_filter_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(log.SETTINGS.apm, "enabled", False)

    logger = log.get_logger("eqtr.apm.disabled")

    assert _count_apm_filters(logger) == 0


def test_get_logger_reuses_uvicorn_error_handlers_for_stdout(monkeypatch) -> None:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    original_handlers = list(uvicorn_error_logger.handlers)
    stream_handler = logging.StreamHandler()
    uvicorn_error_logger.handlers = [stream_handler]

    try:
        monkeypatch.setattr(log.SETTINGS.apm, "enabled", False)
        logger = log.get_logger("eqtr.stdout")

        assert logger.handlers == [stream_handler]
    finally:
        uvicorn_error_logger.handlers = original_handlers


def test_get_logger_falls_back_to_stream_handler_without_uvicorn(monkeypatch) -> None:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_logger = logging.getLogger("uvicorn")
    original_error_handlers = list(uvicorn_error_logger.handlers)
    original_uvicorn_handlers = list(uvicorn_logger.handlers)
    uvicorn_error_logger.handlers = []
    uvicorn_logger.handlers = []

    try:
        monkeypatch.setattr(log.SETTINGS.apm, "enabled", False)
        logger = log.get_logger("eqtr.fallback")

        assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
    finally:
        uvicorn_error_logger.handlers = original_error_handlers
        uvicorn_logger.handlers = original_uvicorn_handlers
