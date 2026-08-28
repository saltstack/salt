"""
Unit tests for salt.runner
"""

from unittest.mock import MagicMock

import salt.runner


def test_runnerclient_destroy_cleans_up_mminion():
    """
    RunnerClient.destroy() must tear down a lazily-created MasterMinion
    (``self._mminion``) too. Without this, the MasterMinion created by
    ``mixins.SyncClientMixin.mminion`` during ``low()`` is only ever torn
    down by ``__del__``'s GC-time safety net, which now logs a loud
    "unclosed MasterMinion" WARNING (see GH #70174).
    """
    client = salt.runner.RunnerClient.__new__(salt.runner.RunnerClient)
    client.event = None
    client._functions = None
    client.utils = None
    mminion = client._mminion = MagicMock()

    client.destroy()

    mminion.destroy.assert_called_once()
    assert client._mminion is None


def test_runnerclient_destroy_without_mminion_is_a_noop():
    """
    RunnerClient.destroy() must not raise when ``mminion`` was never
    accessed (``_mminion`` was never set on the instance).
    """
    client = salt.runner.RunnerClient.__new__(salt.runner.RunnerClient)
    client.event = None
    client._functions = None
    client.utils = None

    client.destroy()  # should not raise
