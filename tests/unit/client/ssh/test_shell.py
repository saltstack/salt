import os
import subprocess

import salt.client.ssh.shell as shell
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


class SSHShellTests(TestCase):
    def setUp(self):
        self.pub_key = os.path.join(RUNTIME_VARS.TMP, "ssh", "testkey.pub")
        self.priv_key = os.path.join(RUNTIME_VARS.TMP, "ssh", "testkey")
        self.keys = [self.pub_key, self.priv_key]

    def tearDown(self):
        for fp in self.keys:
            os.remove(fp)

    def test_ssh_shell_key_gen(self):
        """
        Test ssh key_gen
        """
        shell.gen_key(self.priv_key)
        for fp in self.keys:
            assert os.path.exists(fp)

        # verify there is not a passphrase set on key
        ret = subprocess.run(
            ["ssh-keygen", "-f", self.priv_key, "-y"],
            capture_output=True,
            timeout=30,
            check=True,
        )
        self.assertTrue(ret.stdout.decode().startswith("ssh-rsa"))
        self.assertEqual(ret.returncode, 0)
