import pytest
import salt.utils.msgpack
from salt.client import ssh
from tests.support.mock import MagicMock, patch


@pytest.fixture
def ssh_target(tmpdir):
    argv = [
        "ssh.set_auth_key",
        "root",
        "hobn+amNAXSBTiOXEqlBjGB...rsa root@master",
    ]

    opts = {
        "argv": argv,
        "__role": "master",
        "cachedir": tmpdir.strpath,
        "extension_modules": tmpdir.join("extmods").strpath,
    }
    target = {
        "passwd": "abc123",
        "ssh_options": None,
        "sudo": False,
        "identities_only": False,
        "host": "login1",
        "user": "root",
        "timeout": 65,
        "remote_port_forwards": None,
        "sudo_user": "",
        "port": "22",
        "priv": "/etc/salt/pki/master/ssh/salt-ssh.rsa",
    }
    return opts, target


@pytest.mark.skip_on_windows(reason="SSH_PY_SHIM not set on windows")
def test_cmd_block_python_version_error(ssh_target):
    opts = ssh_target[0]
    target = ssh_target[1]

    single = ssh.Single(
        opts,
        opts["argv"],
        "localhost",
        mods={},
        fsclient=None,
        thin=salt.utils.thin.thin_path(opts["cachedir"]),
        mine=False,
        winrm=False,
        **target
    )
    mock_shim = MagicMock(
        return_value=(("", "ERROR: Unable to locate appropriate python command\n", 10))
    )
    patch_shim = patch("salt.client.ssh.Single.shim_cmd", mock_shim)
    with patch_shim:
        ret = single.cmd_block()
        assert "ERROR: Python version error. Recommendation(s) follow:" in ret[0]
