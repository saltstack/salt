import salt.executors.sudo
from tests.support.mock import MagicMock, patch


def test_sudo_execute_adds_priv_arg():
    # Setup inputs
    opts = {"sudo_user": "saltdev", "config_dir": "/etc/salt"}
    data = {"fun": "test.ping"}
    func = MagicMock()
    args = []
    kwargs = {}

    # Mock __salt__ and cmd.run_all
    mock_run_all = MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '{"local": {"return": true, "retcode": 0}}',
        }
    )

    # Mock __context__
    context_dict = {}

    # Initialize dunder dictionaries if they don't exist
    if not hasattr(salt.executors.sudo, "__salt__"):
        salt.executors.sudo.__salt__ = {}
    if not hasattr(salt.executors.sudo, "__context__"):
        salt.executors.sudo.__context__ = {}

    with patch.dict(
        salt.executors.sudo.__salt__, {"cmd.run_all": mock_run_all}
    ), patch.dict(salt.executors.sudo.__context__, context_dict):

        salt.executors.sudo.execute(opts, data, func, args, kwargs)

        # Verify the command called includes --priv saltdev
        call_args = mock_run_all.call_args[0][0]

        # Check expected parts of command
        assert "sudo" in call_args
        assert "-u" in call_args
        assert "saltdev" in call_args
        assert "salt-call" in call_args
        assert "--priv" in call_args

        # Verify --priv follows salt-call and precedes saltdev
        salt_call_idx = call_args.index("salt-call")
        priv_idx = call_args.index("--priv")
        user_idx = priv_idx + 1

        assert priv_idx > salt_call_idx
        assert call_args[user_idx] == "saltdev"
