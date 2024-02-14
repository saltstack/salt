"""
Unit tests for salt.fileclient
"""
import salt.config
import salt.fileclient as fileclient
from tests.support.mock import MagicMock, patch


def test_fsclient_master_no_fs_update(master_opts):
    """
    Test that an FSClient spawned from the master does not cause fileserver
    backends to be refreshed on instantiation. The master already has the
    maintenance thread for that.
    """
    overrides = {"file_client": "local"}
    opts = salt.config.apply_master_config(overrides, master_opts)
    fileserver = MagicMock()
    with patch("salt.fileserver.Fileserver", fileserver):
        client = fileclient.FSClient(opts)
        assert client.channel.fs.update.call_count == 0


def test_fsclient_masterless_fs_update(minion_opts):
    """
    Test that an FSClient spawned from a masterless run refreshes the
    fileserver backends. This is necessary to ensure that a masterless run
    can access any configured gitfs remotes.
    """
    overrides = {"file_client": "local"}
    opts = salt.config.apply_minion_config(overrides, minion_opts)
    fileserver = MagicMock()
    with patch("salt.fileserver.Fileserver", fileserver):
        client = fileclient.FSClient(opts)
        assert client.channel.fs.update.call_count == 1
