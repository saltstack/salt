"""
Verify the counter co-located with ``PubServerChannel.publish`` increments
once per publish call with the ``fun`` label.
"""

import asyncio

import pytest

import salt.channel.server
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


class _FakeTransport:
    """Stand-in for the PublishServer transport — captures payloads."""

    def __init__(self):
        self.payloads = []

    async def publish(self, payload):
        self.payloads.append(payload)


def _make_channel():
    """Build a ``PubServerChannel`` stub that only needs publish()."""
    channel = salt.channel.server.PubServerChannel.__new__(
        salt.channel.server.PubServerChannel
    )
    channel.transport = _FakeTransport()
    return channel


def _published_counts(reader):
    counts = {}
    data = reader.get_metrics_data()
    if data is None:
        return counts
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name != "salt.jobs.published":
                    continue
                for dp in m.data.data_points:
                    fun = dict(dp.attributes).get("fun", "")
                    counts[fun] = counts.get(fun, 0) + dp.value
    return counts


def test_publish_increments_jobs_published(in_memory_reader):
    metrics.configure(
        {"metrics": {"enabled": True, "exporter": "console"}, "__role": "master"}
    )
    channel = _make_channel()
    asyncio.run(channel.publish({"jid": "1", "fun": "test.ping", "tgt": "*"}))
    asyncio.run(channel.publish({"jid": "2", "fun": "test.ping", "tgt": "*"}))
    asyncio.run(channel.publish({"jid": "3", "fun": "test.echo", "tgt": "*"}))

    counts = _published_counts(in_memory_reader)
    assert counts.get("test.ping") == 2
    assert counts.get("test.echo") == 1


def test_publish_is_noop_when_metrics_disabled(in_memory_reader):
    # Configure with disabled — counter is a no-op so the reader stays empty.
    metrics.configure({"metrics": {"enabled": False}, "__role": "master"})
    channel = _make_channel()
    asyncio.run(channel.publish({"jid": "1", "fun": "test.ping", "tgt": "*"}))
    assert _published_counts(in_memory_reader) == {}
