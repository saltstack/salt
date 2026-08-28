"""
Unit tests for salt.wheel.WheelClient
"""

import salt.wheel
from tests.support.mock import MagicMock


def test_wheelclient_destroy_cleans_up_mminion():
    """
    WheelClient.destroy() must tear down a lazily-created MasterMinion
    (``self._mminion``), mirroring the same fix applied to
    salt.runner.RunnerClient (GH #70174).
    """
    client = salt.wheel.WheelClient.__new__(salt.wheel.WheelClient)
    client.event = None
    client.functions = None
    mminion = client._mminion = MagicMock()

    client.destroy()

    mminion.destroy.assert_called_once()
    assert client._mminion is None


def test_wheelclient_destroy_without_mminion_is_a_noop():
    """
    WheelClient.destroy() must not raise when ``mminion`` was never
    accessed (``_mminion`` was never set on the instance).
    """
    client = salt.wheel.WheelClient.__new__(salt.wheel.WheelClient)
    client.event = None
    client.functions = None

    client.destroy()  # should not raise
