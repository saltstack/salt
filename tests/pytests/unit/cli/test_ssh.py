import salt.utils.parsers
from salt.cli.ssh import SaltSSH
from tests.support.mock import MagicMock, call, patch


def test_salt_ssh_parser_accepts_executor_options():
    """
    Verify that SaltSSHOptionParser includes ExecutorsMixIn so that
    --module-executors and --executor-opts are valid CLI options.
    """
    assert issubclass(
        salt.utils.parsers.SaltSSHOptionParser,
        salt.utils.parsers.ExecutorsMixIn,
    )
    # Verify that the option is registered without invoking parse_args
    # (which has filesystem side-effects requiring root or existing /var/log/salt).
    parser = salt.utils.parsers.SaltSSHOptionParser()
    assert parser.has_option("--module-executors")
    assert parser.has_option("--executor-opts")


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
