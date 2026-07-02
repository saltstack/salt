"""
Regression tests for the ``manage.status`` / ``manage.up`` / ``manage.down``
runner behavior.

The bug fixed by this module: ``manage._ping`` iterates the events yielded by
``LocalClient.get_cli_event_returns`` and adds every minion id it sees to the
``returned`` set. When ``get_cli_event_returns`` is called with
``expect_minions=True`` it also yields synthesized ``no_return`` entries for
minions that did **not** respond. Treating those synthesized entries as
returns made ``manage.status`` report every minion as up and never list any
minion as down (issue #69582).
"""

from contextlib import contextmanager

import pytest

from salt.runners import manage
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {
        manage: {
            "__opts__": {
                "conf_file": "/etc/salt/master",
                "timeout": 5,
                "gather_job_timeout": 10,
            },
        },
    }


class _FakeClient:
    """Stand-in for ``salt.client.LocalClient`` exposing the surface the
    ``manage._ping`` helper uses."""

    def __init__(self, minions, events):
        self._minions = minions
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run_job(self, *args, **kwargs):  # pylint: disable=unused-argument
        return {"jid": "20260627000000000000", "minions": list(self._minions)}

    def _get_timeout(self, timeout):
        return timeout

    def get_cli_event_returns(self, *args, **kwargs):  # pylint: disable=unused-argument
        yield from self._events


@contextmanager
def _patched_client(fake_client):
    @contextmanager
    def _factory(*args, **kwargs):  # pylint: disable=unused-argument
        yield fake_client

    with patch("salt.client.get_local_client", _factory):
        yield


def test_manage_status_reports_unresponsive_minions_as_down():
    """
    ``manage.status`` must distinguish actual returns from the synthetic
    ``no_return`` failure events that ``LocalClient.get_cli_event_returns``
    emits when ``expect_minions`` is True.

    Issue: https://github.com/saltstack/salt/issues/69582
    """
    targeted = ["minion-up", "minion-down"]
    events = [
        # Real return from the responsive minion.
        {"minion-up": {"ret": True, "retcode": 0, "out": "highstate"}},
        # Synthetic ``no_return`` row emitted by ``get_cli_event_returns``
        # for a minion that did not respond in time.
        {
            "minion-down": {
                "out": "no_return",
                "ret": "Minion did not return. [No response]",
                "retcode": 2,
            },
        },
    ]
    fake = _FakeClient(targeted, events)
    with _patched_client(fake):
        result = manage.status(output=False)
    assert result == {"up": ["minion-up"], "down": ["minion-down"]}


def test_manage_down_reports_unresponsive_minions():
    """``manage.down`` should include minions that fail to return."""
    targeted = ["minion-up", "minion-down"]
    events = [
        {"minion-up": {"ret": True, "retcode": 0, "out": "highstate"}},
        {
            "minion-down": {
                "out": "no_return",
                "ret": "Minion did not return. [No response]",
                "retcode": 2,
            },
        },
    ]
    fake = _FakeClient(targeted, events)
    with _patched_client(fake), patch("salt.wheel.Wheel", MagicMock()):
        assert manage.down() == ["minion-down"]


def test_manage_up_excludes_unresponsive_minions():
    """``manage.up`` should not include minions that fail to return."""
    targeted = ["minion-up", "minion-down"]
    events = [
        {"minion-up": {"ret": True, "retcode": 0, "out": "highstate"}},
        {
            "minion-down": {
                "out": "no_return",
                "ret": "Minion did not return. [Not connected]",
                "retcode": 2,
            },
        },
    ]
    fake = _FakeClient(targeted, events)
    with _patched_client(fake):
        assert manage.up() == ["minion-up"]
