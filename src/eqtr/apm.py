"""APM instrumentation helpers with disabled-mode no-op behavior."""

from contextlib import AbstractContextManager, nullcontext

import elasticapm

from eqtr.clients import APM_CLIENT
from eqtr.settings import SETTINGS


def capture_span(name: str, span_type: str = "app") -> AbstractContextManager[object]:
    """Create an APM span context manager or a no-op context when disabled."""
    if not SETTINGS.apm.enabled:
        return nullcontext()
    return elasticapm.capture_span(name=name, span_type=span_type)


def capture_exception() -> None:
    """Capture the current exception in APM when enabled."""
    if SETTINGS.apm.enabled and APM_CLIENT is not None:
        APM_CLIENT.capture_exception()


def set_custom_context(context: dict[str, object]) -> None:
    """Attach custom context to the current APM transaction when enabled."""
    if SETTINGS.apm.enabled:
        elasticapm.set_custom_context(context)
