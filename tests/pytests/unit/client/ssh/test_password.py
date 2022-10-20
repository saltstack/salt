import pytest

import salt.client.ssh.client
import salt.config
import salt.roster
import salt.utils.files
import salt.utils.path
import salt.utils.thin
import salt.utils.yaml
from salt.client import ssh
from tests.support.mock import MagicMock, patch

pytestmark = [
    pytest.mark.skipif(
        not salt.utils.path.which("ssh"), reason="No ssh binary found in path"
    ),
    pytest.mark.slow_test,
]


def test_password_failure(temp_salt_master, tmp_path):
    """
    Check password failures when trying to deploy keys
    """
    opts = temp_salt_master.config.copy()
    opts["list_hosts"] = False
    opts["argv"] = ["test.ping"]
    opts["selected_target_option"] = "glob"
    opts["tgt"] = "localhost"
    opts["arg"] = []
    roster = str(tmp_path / "roster")
    handle_ssh_ret = [
        {
            "localhost": {
                "retcode": 255,
                "stderr": "Permission denied (publickey).\r\n",
                "stdout": "",
            }
        },
    ]
    expected = {"localhost": "Permission denied (publickey)"}
    display_output = MagicMock()
    with patch("salt.roster.get_roster_file", MagicMock(return_value=roster)), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
    ), patch("salt.client.ssh.SSH.key_deploy", MagicMock(return_value=expected)), patch(
        "salt.output.display_output", display_output
    ):
        client = ssh.SSH(opts)
        ret = next(client.run_iter())
        with pytest.raises(SystemExit):
            client.run()
    display_output.assert_called_once_with(expected, "nested", opts)
    assert ret is handle_ssh_ret[0]
