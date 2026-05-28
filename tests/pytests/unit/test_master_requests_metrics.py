"""
Verify the per-command master dispatcher metrics:

* ``salt.master.requests.handled{cmd}`` counter
* ``salt.master.requests.duration{cmd}`` histogram

These are recorded by ``MWorker._handle_clear`` and ``MWorker._handle_aes``
and give OTel parity with the legacy ``master_stats`` per-command runs +
mean surface.
"""

import asyncio

import pytest

import salt.master
import salt.utils.metrics as metrics


@pytest.fixture(autouse=True)
def _reset_metrics(monkeypatch):
    metrics.shutdown()
    monkeypatch.setattr(metrics, "_cached_opts", None)
    yield
    metrics.shutdown()


@pytest.fixture
def in_memory_reader(monkeypatch):
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader

    reader = InMemoryMetricReader()
    monkeypatch.setattr(metrics, "_build_readers", lambda _opts: [reader])
    return reader


class _FakeClearFuncs:
    """Stand-in for ``salt.master.ClearFuncs`` exposing only what
    ``_handle_clear`` touches."""

    async_methods = ("publish",)

    def __init__(self):
        self.calls = []

    def get_method(self, cmd):
        async def _async_handler(load):
            self.calls.append((cmd, load))
            return {"ok": True}

        def _sync_handler(load):
            self.calls.append((cmd, load))
            return {"ok": True}

        return _async_handler if cmd in self.async_methods else _sync_handler


class _FakeAesFuncs:
    """Stand-in for ``salt.master.AESFuncs.get_method`` + ``run_func``."""

    def __init__(self):
        self.calls = []

    def get_method(self, cmd):
        return self._method

    def _method(self, data):
        # ``get_method`` just needs to be truthy; the real dispatch goes
        # through ``run_func`` below.
        return None

    def run_func(self, cmd, data):
        self.calls.append((cmd, data))
        return {"ok": True}


def _make_worker():
    """Construct an MWorker without running ``__init__`` (we only need
    the two ``_handle_*`` methods)."""
    worker = salt.master.MWorker.__new__(salt.master.MWorker)
    worker.opts = {"master_stats": False}
    worker.clear_funcs = _FakeClearFuncs()
    worker.aes_funcs = _FakeAesFuncs()
    # ``self.stats`` is touched only when ``master_stats`` is enabled, but
    # leave it defined for safety.
    worker.stats = {}
    return worker


def _by_cmd(reader, name):
    out = {}
    data = reader.get_metrics_data()
    if data is None:
        return out
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name != name:
                    continue
                for dp in m.data.data_points:
                    cmd = dict(dp.attributes).get("cmd", "")
                    value = getattr(dp, "value", None)
                    if value is None:
                        value = getattr(dp, "sum", None)
                    out.setdefault(cmd, []).append(value)
    return out


def test_handle_clear_records_request_metrics(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    worker = _make_worker()
    # Async path: ``publish`` is on ``async_methods``.
    asyncio.run(worker._handle_clear({"cmd": "publish", "fun": "test.ping"}))
    asyncio.run(worker._handle_clear({"cmd": "publish", "fun": "test.ping"}))
    # Sync path: anything not on async_methods.
    asyncio.run(worker._handle_clear({"cmd": "ping"}))

    counts = _by_cmd(in_memory_reader, "salt.master.requests.handled")
    assert sum(counts.get("publish", [])) == 2
    assert sum(counts.get("ping", [])) == 1

    durations = _by_cmd(in_memory_reader, "salt.master.requests.duration")
    assert "publish" in durations
    assert "ping" in durations


def test_handle_aes_records_request_metrics(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    worker = _make_worker()
    # Use a lock-free shim for ``salt.utils.ctx.request_context``: the
    # real one wraps ``contextvars`` and needs no opts validation.
    worker._handle_aes({"cmd": "_return", "fun": "test.ping", "success": True})
    worker._handle_aes({"cmd": "_return", "fun": "test.ping", "success": False})
    worker._handle_aes({"cmd": "_serve_file"})

    counts = _by_cmd(in_memory_reader, "salt.master.requests.handled")
    assert sum(counts.get("_return", [])) == 2
    assert sum(counts.get("_serve_file", [])) == 1

    durations = _by_cmd(in_memory_reader, "salt.master.requests.duration")
    assert "_return" in durations
    assert "_serve_file" in durations


def test_metrics_disabled_remains_noop(in_memory_reader):
    metrics.configure({"metrics": {"enabled": False}, "__role": "master"})
    worker = _make_worker()
    asyncio.run(worker._handle_clear({"cmd": "publish", "fun": "test.ping"}))
    worker._handle_aes({"cmd": "_return", "fun": "test.ping"})

    assert _by_cmd(in_memory_reader, "salt.master.requests.handled") == {}
    assert _by_cmd(in_memory_reader, "salt.master.requests.duration") == {}


def test_handle_clear_records_even_when_handler_raises(in_memory_reader):
    """The histogram is in a ``try/finally`` so failures still record latency."""
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    worker = _make_worker()

    boom = RuntimeError("simulated handler failure")

    def _failing_method(load):
        raise boom

    # Replace the clear-funcs dispatcher with one that always raises.
    worker.clear_funcs = _FakeClearFuncs()
    worker.clear_funcs.get_method = lambda cmd: _failing_method

    with pytest.raises(RuntimeError):
        asyncio.run(worker._handle_clear({"cmd": "ping"}))

    counts = _by_cmd(in_memory_reader, "salt.master.requests.handled")
    durations = _by_cmd(in_memory_reader, "salt.master.requests.duration")
    assert counts.get("ping") == [1]
    assert "ping" in durations
