# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os
import subprocess

import salt.client.ssh.shell as shell
from tests.support.helpers import skip_if_binaries_missing
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase


@skip_if_binaries_missing("ssh")
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
        ret = subprocess.check_output(
            ["ssh-keygen", "-f", self.priv_key, "-y"]
        )
        self.assertTrue(ret.decode().startswith("ssh-rsa"))
