import pytest

from salt.cli.batch import Batch


class FakeIter:
    """
    Iterator used to simulate cmd_iter_no_block()
    """

    def __init__(self, parts):
        self._iter = iter(parts)

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self._iter)
        if isinstance(item, StopIteration):
            raise StopIteration
        return item


class FakeLocalClient:
    """
    Fake LocalClient to control ping + job return payloads
    """

    def __init__(self, ping_returns, cmd_returns):
        self._ping_returns = ping_returns
        self._cmd_returns = cmd_returns

    def cmd_iter(self, *args, **kwargs):
        return iter(self._ping_returns)

    def cmd_iter_no_block(self, *args, **kwargs):
        return FakeIter(self._cmd_returns)

    def destroy(self):
        pass


@pytest.fixture
def base_opts():
    return {
        "tgt": "*",
        "fun": "test.ping",
        "arg": [],
        "timeout": 5,
        "batch": 1,
        "conf_file": "/dev/null",
        "gather_job_timeout": 5,
    }
    

def test_gather_minions_ignores_error_payload(monkeypatch, base_opts):
    ping_returns = [
        # Transport-level error payload
        {"error": "Authentication failure", "jid": "20260101000000"},
        # Legit discovery payload
        {"minions": ["minion1"], "jid": "20260101000001"},
        {"minion1": {"ret": True}},
    ]

    fake_client = FakeLocalClient(ping_returns, [])

    monkeypatch.setattr(
        "salt.client.get_local_client",
        lambda *a, **k: fake_client,
    )

    batch = Batch(base_opts, quiet=True)
    minions, _, _ = batch.gather_minions()

    assert "error" not in minions
    assert minions == ["minion1"]

def test_batch_run_ignores_error_return(monkeypatch, base_opts):
    ping_returns = [
        {"minions": ["minion1"], "jid": "123"},
        {"minion1": {"ret": True}},
    ]

    cmd_returns = [
        # Error payload emitted by transport/publish
        {"error": "Publish failed", "failed": True},
        # Legit minion return
        {"minion1": {"ret": True}},
    ]

    fake_client = FakeLocalClient(ping_returns, cmd_returns)

    monkeypatch.setattr(
        "salt.client.get_local_client",
        lambda *a, **k: fake_client,
    )

    batch = Batch(base_opts, quiet=True)

    results = list(batch.run())

    returned_minions = []
    for item, _ in results:
        if isinstance(item, dict):
            returned_minions.extend(item.keys())

    assert "error" not in returned_minions
    assert "minion1" in returned_minions


def test_batch_duplicate_returns_are_idempotent(monkeypatch, base_opts):
    ping_returns = [
        {"minions": ["minion1"], "jid": "123"},
        {"minion1": {"ret": True}},
    ]

    cmd_returns = [
        {"minion1": {"ret": True}},
        {"minion1": {"ret": True}},  # duplicate return
        StopIteration(),
    ]

    fake_client = FakeLocalClient(ping_returns, cmd_returns)

    monkeypatch.setattr(
        "salt.client.get_local_client",
        lambda *a, **k: fake_client,
    )

    batch = Batch(base_opts, quiet=True)

    results = list(batch.run())

    assert results
    for item, _ in results:
        if isinstance(item, dict):
            assert "error" not in item
