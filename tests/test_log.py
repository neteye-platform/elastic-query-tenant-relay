import logging

from eqtr import log


def test_get_logger_sets_configured_level_and_non_propagating(monkeypatch) -> None:
    monkeypatch.setattr(log.SETTINGS, "log_level", "debug")

    logger = log.get_logger("eqtr.logger.level")

    assert logger.level == logging.DEBUG
    assert logger.propagate is False


def test_get_logger_reuses_uvicorn_error_handlers_for_stdout(monkeypatch) -> None:
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    original_handlers = list(uvicorn_error_logger.handlers)
    stream_handler = logging.StreamHandler()
    uvicorn_error_logger.handlers = [stream_handler]

    try:
        monkeypatch.setattr(log.SETTINGS, "log_level", "info")
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
        monkeypatch.setattr(log.SETTINGS, "log_level", "info")
        logger = log.get_logger("eqtr.fallback")

        assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
    finally:
        uvicorn_error_logger.handlers = original_error_handlers
        uvicorn_logger.handlers = original_uvicorn_handlers
