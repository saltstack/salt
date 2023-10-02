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


def test_not_missing_fun_calling_wfuncs(temp_salt_master, tmp_path):
    opts = temp_salt_master.config.copy()
    opts["list_hosts"] = False
    opts["argv"] = ["state.show_highstate"]
    opts["selected_target_option"] = "glob"
    opts["tgt"] = "localhost"
    opts["arg"] = []
    roster = str(tmp_path / "roster")
    handle_ssh_ret = [({"localhost": {}}, 0)]

    expected = {"localhost": {}}
    display_output = MagicMock()
    with patch("salt.roster.get_roster_file", MagicMock(return_value=roster)), patch(
        "salt.client.ssh.SSH.handle_ssh", MagicMock(return_value=handle_ssh_ret)
    ), patch("salt.client.ssh.SSH.key_deploy", MagicMock(return_value=expected)), patch(
        "salt.output.display_output", display_output
    ):
        client = ssh.SSH(opts)
        client.event = MagicMock()
        ret = next(client.run_iter())
        assert "localhost" in ret
        assert "fun" in ret["localhost"]
        client.run()
    display_output.assert_called_once_with(expected, "nested", opts)
    assert ret is handle_ssh_ret[0][0]
    assert len(client.event.fire_event.call_args_list) == 2
    assert "fun" in client.event.fire_event.call_args_list[0][0][0]
    assert "fun" in client.event.fire_event.call_args_list[1][0][0]
