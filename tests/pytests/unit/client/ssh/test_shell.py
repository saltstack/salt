import os
import subprocess

import pytest
import salt.client.ssh.shell as shell


@pytest.fixture
def keys(tmp_path):
    pub_key = tmp_path / "ssh" / "testkey.pub"
    priv_key = tmp_path / "ssh" / "testkey"
    yield {"pub_key": str(pub_key), "priv_key": str(priv_key)}


@pytest.mark.skip_on_windows(reason="Windows does not support salt-ssh")
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
class TestSSHShell:
    def test_ssh_shell_key_gen(self, keys):
        """
        Test ssh key_gen
        """
        shell.gen_key(keys["priv_key"])
        for fp in keys.keys():
            assert os.path.exists(keys[fp])

        # verify there is not a passphrase set on key
        ret = subprocess.check_output(
            ["ssh-keygen", "-f", keys["priv_key"], "-y"], timeout=30,
        )
        assert ret.decode().startswith("ssh-rsa")
