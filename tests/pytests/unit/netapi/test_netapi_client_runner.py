"""
Regression tests for NetapiClient.runner timeout coercion (issue #68653).

The salt-api HTTP form encodes all values as strings, so a request like
``-d timeout=600`` arrives at ``NetapiClient.runner`` as ``timeout="600"``.
The downstream ``salt.utils.event._get_event`` does ``timeout_at = start +
wait`` which raises ``TypeError`` when ``wait`` is a string. ``runner`` now
coerces the value to ``float`` at the boundary so HTTP-form callers can
specify a timeout without crashing the runner.
"""

import pytest

import salt.netapi
from tests.support.mock import patch


@pytest.fixture
def netapi_client(master_opts):
    return salt.netapi.NetapiClient(master_opts)


def test_runner_coerces_string_timeout_to_float(netapi_client):
    """
    NetapiClient.runner must not raise TypeError when given a string
    timeout from the HTTP form, and must forward a numeric value to
    RunnerClient.cmd_sync (issue #68653).
    """
    captured = {}

    class FakeRunner:
        def __init__(self, opts):
            self.opts = opts

        def cmd_sync(self, low, timeout=None, full_return=False):
            captured["timeout"] = timeout
            captured["low"] = low
            captured["full_return"] = full_return
            return {"return": "ok"}

    with patch("salt.runner.RunnerClient", FakeRunner):
        ret = netapi_client.runner("test.arg", timeout="600")

    assert ret == {"return": "ok"}
    assert captured["timeout"] == 600.0
    assert isinstance(captured["timeout"], float)
    assert captured["low"]["fun"] == "test.arg"


def test_runner_coerces_fractional_string_timeout(netapi_client):
    """
    Fractional string timeouts must be preserved as float (the v1 of
    the fix used ``int()`` which truncated ``"0.5"`` to ``0``; v2
    corrected to ``float()``).
    """
    captured = {}

    class FakeRunner:
        def __init__(self, opts):
            pass

        def cmd_sync(self, low, timeout=None, full_return=False):
            captured["timeout"] = timeout
            return {"return": "ok"}

    with patch("salt.runner.RunnerClient", FakeRunner):
        netapi_client.runner("test.arg", timeout="0.5")

    assert captured["timeout"] == 0.5


def test_runner_preserves_none_timeout(netapi_client):
    """
    ``timeout=None`` must pass through unchanged so the downstream
    default (``opts["rest_timeout"]``) still applies.
    """
    captured = {}

    class FakeRunner:
        def __init__(self, opts):
            pass

        def cmd_sync(self, low, timeout=None, full_return=False):
            captured["timeout"] = timeout
            return {"return": "ok"}

    with patch("salt.runner.RunnerClient", FakeRunner):
        netapi_client.runner("test.arg")

    assert captured["timeout"] is None


def test_runner_passes_numeric_timeout_unchanged_value(netapi_client):
    """
    A numeric (int/float) timeout still ends up as a float with the
    same value — the coercion is idempotent.
    """
    captured = {}

    class FakeRunner:
        def __init__(self, opts):
            pass

        def cmd_sync(self, low, timeout=None, full_return=False):
            captured["timeout"] = timeout
            return {"return": "ok"}

    with patch("salt.runner.RunnerClient", FakeRunner):
        netapi_client.runner("test.arg", timeout=42)

    assert captured["timeout"] == 42.0
    assert isinstance(captured["timeout"], float)
