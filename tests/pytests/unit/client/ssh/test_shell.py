import subprocess
import types

import pytest

import salt.client.ssh.shell as shell
from tests.support.mock import patch


@pytest.fixture
def keys(tmp_path):
    pub_key = tmp_path / "ssh" / "testkey.pub"
    priv_key = tmp_path / "ssh" / "testkey"
    return types.SimpleNamespace(pub_key=pub_key, priv_key=priv_key)


@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
def test_ssh_shell_key_gen(keys):
    """
    Test ssh key_gen
    """
    shell.gen_key(str(keys.priv_key))
    assert keys.priv_key.exists()
    assert keys.pub_key.exists()
    # verify there is not a passphrase set on key
    ret = subprocess.check_output(
        ["ssh-keygen", "-f", str(keys.priv_key), "-y"],
        timeout=30,
    )
    assert ret.decode().startswith("ssh-rsa")


@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
def test_ssh_shell_exec_cmd(caplog):
    """
    Test executing a command and ensuring the password
    is not in the stdout/stderr logs.
    """
    passwd = "12345"
    opts = {"_ssh_version": (4, 9)}
    host = ""
    _shell = shell.Shell(opts=opts, host=host)
    _shell.passwd = passwd
    with patch.object(_shell, "_split_cmd", return_value=["echo", passwd]):
        ret = _shell.exec_cmd("echo {}".format(passwd))
        assert not any([x for x in ret if passwd in str(x)])
        assert passwd not in caplog.text

    with patch.object(_shell, "_split_cmd", return_value=["ls", passwd]):
        ret = _shell.exec_cmd("ls {}".format(passwd))
        assert not any([x for x in ret if passwd in str(x)])
        assert passwd not in caplog.text
