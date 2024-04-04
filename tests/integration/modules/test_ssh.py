"""
Test the ssh module
"""

import os
import shutil

import pytest
import requests

import salt.utils.files
import salt.utils.platform
from tests.support.case import ModuleCase
from tests.support.runtests import RUNTIME_VARS

GITHUB_FINGERPRINT = "b8:d8:95:ce:d9:2c:0a:c0:e1:71:cd:2e:f5:ef:01:ba:34:17:55:4a:4a:64:80:d3:31:cc:c2:be:3d:ed:0f:6b"


def check_status():
    """
    Check the status of Github for remote operations
    """
    try:
        return requests.get("https://github.com", timeout=60).status_code == 200
    except Exception:  # pylint: disable=broad-except
        return False


# @pytest.mark.windows_whitelisted
# De-whitelist windows since it's hanging on the newer windows golden images
@pytest.mark.skip_if_binaries_missing("ssh", "ssh-keygen", check_all=True)
class SSHModuleTest(ModuleCase):
    """
    Test the ssh module
    """

    @classmethod
    def setUpClass(cls):
        cls.subsalt_dir = os.path.join(RUNTIME_VARS.TMP, "subsalt")
        cls.authorized_keys = os.path.join(cls.subsalt_dir, "authorized_keys")
        cls.known_hosts = os.path.join(cls.subsalt_dir, "known_hosts")

    def setUp(self):
        """
        Set up the ssh module tests
        """
        if not check_status():
            self.skipTest("External source, github.com is down")
        super().setUp()
        if not os.path.isdir(self.subsalt_dir):
            os.makedirs(self.subsalt_dir)

        known_hosts_file = os.path.join(RUNTIME_VARS.FILES, "ssh", "known_hosts")
        with salt.utils.files.fopen(known_hosts_file) as fd:
            self.key = fd.read().strip().splitlines()[0].split()[-1]

    def tearDown(self):
        """
        Tear down the ssh module tests
        """
        if os.path.isdir(self.subsalt_dir):
            shutil.rmtree(self.subsalt_dir)
        super().tearDown()
        del self.key

    @pytest.mark.slow_test
    def test_auth_keys(self):
        """
        test ssh.auth_keys
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "authorized_keys"),
            self.authorized_keys,
        )
        user = "root"
        if salt.utils.platform.is_windows():
            user = "Administrator"
        ret = self.run_function("ssh.auth_keys", [user, self.authorized_keys])
        self.assertEqual(len(list(ret.items())), 1)  # exactly one key is found
        key_data = list(ret.items())[0][1]
        try:
            self.assertEqual(key_data["comment"], "github.com")
            self.assertEqual(key_data["enc"], "ssh-rsa")
            self.assertEqual(
                key_data["options"], ['command="/usr/local/lib/ssh-helper"']
            )
            self.assertEqual(key_data["fingerprint"], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")

    @pytest.mark.slow_test
    def test_bad_enctype(self):
        """
        test to make sure that bad key encoding types don't generate an
        invalid key entry in authorized_keys
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "authorized_badkeys"),
            self.authorized_keys,
        )
        ret = self.run_function("ssh.auth_keys", ["root", self.authorized_keys])

        # The authorized_badkeys file contains a key with an invalid ssh key
        # encoding (dsa-sha2-nistp256 instead of ecdsa-sha2-nistp256)
        # auth_keys should skip any keys with invalid encodings.  Internally
        # the minion will throw a CommandExecutionError so the
        # user will get an indicator of what went wrong.
        self.assertEqual(len(list(ret.items())), 0)  # Zero keys found

    @pytest.mark.slow_test
    def test_get_known_host_entries(self):
        """
        Check that known host information is returned from ~/.ssh/config
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "known_hosts"), self.known_hosts
        )
        arg = ["root", "github.com"]
        kwargs = {"config": self.known_hosts}
        ret = self.run_function("ssh.get_known_host_entries", arg, **kwargs)[0]
        try:
            self.assertEqual(ret["enc"], "ssh-rsa")
            self.assertEqual(ret["key"], self.key)
            self.assertEqual(ret["fingerprint"], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")

    @pytest.mark.skip_on_photonos(
        reason="Skip on PhotonOS.  Attempting to receive the SSH key from Github, using RSA keys which are disabled.",
    )
    @pytest.mark.slow_test
    def test_recv_known_host_entries(self):
        """
        Check that known host information is returned from remote host
        """
        ret = self.run_function(
            "ssh.recv_known_host_entries", ["github.com"], enc="ssh-rsa"
        )
        try:
            self.assertNotEqual(ret, None)
            self.assertEqual(ret[0]["enc"], "ssh-rsa")
            self.assertEqual(ret[0]["key"], self.key)
            self.assertEqual(ret[0]["fingerprint"], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")

    @pytest.mark.slow_test
    def test_check_known_host_add(self):
        """
        Check known hosts by its fingerprint. File needs to be updated
        """
        arg = ["root", "github.com"]
        kwargs = {"fingerprint": GITHUB_FINGERPRINT, "config": self.known_hosts}
        ret = self.run_function("ssh.check_known_host", arg, **kwargs)
        self.assertEqual(ret, "add")

    @pytest.mark.slow_test
    def test_check_known_host_update(self):
        """
        ssh.check_known_host update verification
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "known_hosts"), self.known_hosts
        )
        arg = ["root", "github.com"]
        kwargs = {"config": self.known_hosts}
        # wrong fingerprint
        ret = self.run_function(
            "ssh.check_known_host", arg, **dict(kwargs, fingerprint="aa:bb:cc:dd")
        )
        self.assertEqual(ret, "update")
        # wrong keyfile
        ret = self.run_function("ssh.check_known_host", arg, **dict(kwargs, key="YQ=="))
        self.assertEqual(ret, "update")

    @pytest.mark.slow_test
    def test_check_known_host_exists(self):
        """
        Verify check_known_host_exists
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "known_hosts"), self.known_hosts
        )
        arg = ["root", "github.com"]
        kwargs = {"config": self.known_hosts}
        # wrong fingerprint
        ret = self.run_function(
            "ssh.check_known_host", arg, **dict(kwargs, fingerprint=GITHUB_FINGERPRINT)
        )
        self.assertEqual(ret, "exists")
        # wrong keyfile
        ret = self.run_function(
            "ssh.check_known_host", arg, **dict(kwargs, key=self.key)
        )
        self.assertEqual(ret, "exists")

    @pytest.mark.slow_test
    def test_rm_known_host(self):
        """
        ssh.rm_known_host
        """
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, "ssh", "known_hosts"), self.known_hosts
        )
        arg = ["root", "github.com"]
        kwargs = {"config": self.known_hosts, "key": self.key}
        # before removal
        ret = self.run_function("ssh.check_known_host", arg, **kwargs)
        self.assertEqual(ret, "exists")
        # remove
        self.run_function("ssh.rm_known_host", arg, config=self.known_hosts)
        # after removal
        ret = self.run_function("ssh.check_known_host", arg, **kwargs)
        self.assertEqual(ret, "add")

    @pytest.mark.skip_on_photonos(
        reason="Skip on PhotonOS.  Attempting to receive the SSH key from Github, using RSA keys which are disabled.",
    )
    @pytest.mark.slow_test
    def test_set_known_host(self):
        """
        ssh.set_known_host
        """
        # add item
        ret = self.run_function(
            "ssh.set_known_host",
            ["root", "github.com"],
            enc="ssh-rsa",
            config=self.known_hosts,
        )
        try:
            self.assertEqual(ret["status"], "updated")
            self.assertEqual(ret["old"], None)
            self.assertEqual(ret["new"][0]["fingerprint"], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")
        # check that item does exist
        ret = self.run_function(
            "ssh.get_known_host_entries",
            ["root", "github.com"],
            config=self.known_hosts,
        )[0]
        try:
            self.assertEqual(ret["fingerprint"], GITHUB_FINGERPRINT)
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")
        # add the same item once again
        ret = self.run_function(
            "ssh.set_known_host", ["root", "github.com"], config=self.known_hosts
        )
        try:
            self.assertEqual(ret["status"], "exists")
        except AssertionError as exc:
            raise AssertionError(f"AssertionError: {exc}. Function returned: {ret}")
