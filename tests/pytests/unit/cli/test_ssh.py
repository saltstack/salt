from salt.cli.ssh import SaltSSH
from tests.support.mock import MagicMock, call, patch


def test_fsclient_destroy_called(minion_opts):
    """
    Test that `salt.client.ssh.SSH.fsclient.destroy()` is called.
    """
    ssh_mock = MagicMock()
    with patch(
        "salt.utils.parsers.SaltSSHOptionParser.parse_args", return_value=MagicMock()
    ), patch("salt.client.ssh.SSH", return_value=ssh_mock):
        parser = SaltSSH()
        parser.config = minion_opts
        parser.run()
    assert ssh_mock.fsclient.mock_calls == [call.destroy()]
