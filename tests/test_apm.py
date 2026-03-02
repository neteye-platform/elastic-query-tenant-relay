from contextlib import nullcontext

from eqtr import apm


def test_capture_span_is_noop_when_apm_disabled(monkeypatch) -> None:
    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", False)

    span_context = apm.capture_span("test.span")

    assert isinstance(span_context, type(nullcontext()))


def test_capture_span_delegates_to_elasticapm_when_enabled(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    sentinel_context = nullcontext()

    def _capture_span(*, name: str, span_type: str):
        calls.append((name, span_type))
        return sentinel_context

    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", True)
    monkeypatch.setattr(apm.elasticapm, "capture_span", _capture_span)

    span_context = apm.capture_span("test.span", span_type="db")

    assert calls == [("test.span", "db")]
    assert span_context is sentinel_context


def test_capture_exception_is_noop_when_apm_disabled(monkeypatch) -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.called = False

        def capture_exception(self) -> None:
            self.called = True

    client = DummyClient()

    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", False)
    monkeypatch.setattr(apm, "APM_CLIENT", client)

    apm.capture_exception()

    assert client.called is False


def test_capture_exception_delegates_when_enabled(monkeypatch) -> None:
    class DummyClient:
        def __init__(self) -> None:
            self.called = False

        def capture_exception(self) -> None:
            self.called = True

    client = DummyClient()

    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", True)
    monkeypatch.setattr(apm, "APM_CLIENT", client)

    apm.capture_exception()

    assert client.called is True


def test_set_custom_context_is_noop_when_apm_disabled(monkeypatch) -> None:
    called_with: list[dict[str, object]] = []

    def _set_custom_context(value: dict[str, object]) -> None:
        called_with.append(value)

    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", False)
    monkeypatch.setattr(apm.elasticapm, "set_custom_context", _set_custom_context)

    apm.set_custom_context({"key": "value"})

    assert called_with == []


def test_set_custom_context_delegates_when_enabled(monkeypatch) -> None:
    called_with: list[dict[str, object]] = []

    def _set_custom_context(value: dict[str, object]) -> None:
        called_with.append(value)

    monkeypatch.setattr(apm.SETTINGS.apm, "enabled", True)
    monkeypatch.setattr(apm.elasticapm, "set_custom_context", _set_custom_context)

    apm.set_custom_context({"key": "value"})

    assert called_with == [{"key": "value"}]
