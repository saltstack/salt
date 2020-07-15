# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import os
import shutil
import tempfile
import textwrap

import pytest
import salt.utils.files
import salt.utils.platform
import salt.utils.yaml
from tests.support.case import ShellCase
from tests.support.helpers import (
    destructiveTest,
    skip_if_not_root,
    slowTest,
    with_system_user,
)
from tests.support.mixins import ShellCaseCommonTestsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

USERA = "saltdev"
USERA_PWD = "saltdev"
PUB_KEY = textwrap.dedent(
    """\
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoqIZDtcQtqUNs0wC7qQz
        JwFhXAVNT5C8M8zhI+pFtF/63KoN5k1WwAqP2j3LquTG68WpxcBwLtKfd7FVA/Kr
        OF3kXDWFnDi+HDchW2lJObgfzLckWNRFaF8SBvFM2dys3CGSgCV0S/qxnRAjrJQb
        B3uQwtZ64ncJAlkYpArv3GwsfRJ5UUQnYPDEJwGzMskZ0pHd60WwM1gMlfYmNX5O
        RBEjybyNpYDzpda6e6Ypsn6ePGLkP/tuwUf+q9wpbRE3ZwqERC2XRPux+HX2rGP+
        mkzpmuHkyi2wV33A9pDfMgRHdln2CLX0KgfRGixUQhW1o+Kmfv2rq4sGwpCgLbTh
        NwIDAQAB
        -----END PUBLIC KEY-----
        """
)
MIN_NAME = "minibar"


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("salt_sub_minion")
class KeyTest(ShellCase, ShellCaseCommonTestsMixin):
    """
    Test salt-key script
    """

    _call_binary_ = "salt-key"

    @slowTest
    def test_remove_key(self):
        """
        test salt-key -d usage
        """
        pki_dir = self.master_opts["pki_dir"]
        key = os.path.join(pki_dir, "minions", MIN_NAME)

        with salt.utils.files.fopen(key, "w") as fp:
            fp.write(PUB_KEY)

        check_key = self.run_key("-p {0}".format(MIN_NAME))
        self.assertIn("Accepted Keys:", check_key)
        self.assertIn("{0}:  -----BEGIN PUBLIC KEY-----".format(MIN_NAME), check_key)

        remove_key = self.run_key("-d {0} -y".format(MIN_NAME))

        check_key = self.run_key("-p {0}".format(MIN_NAME))
        self.assertEqual([], check_key)

    @skip_if_not_root
    @destructiveTest
    @skipIf(salt.utils.platform.is_windows(), "PAM eauth not available on Windows")
    @with_system_user(USERA, password=USERA_PWD)
    @slowTest
    def test_remove_key_eauth(self, username):
        """
        test salt-key -d usage
        """
        pki_dir = self.master_opts["pki_dir"]
        key = os.path.join(pki_dir, "minions", MIN_NAME)

        with salt.utils.files.fopen(key, "w") as fp:
            fp.write(PUB_KEY)

        check_key = self.run_key("-p {0}".format(MIN_NAME))
        self.assertIn("Accepted Keys:", check_key)
        self.assertIn("{0}:  -----BEGIN PUBLIC KEY-----".format(MIN_NAME), check_key)

        remove_key = self.run_key(
            "-d {0} -y --eauth pam --username {1} --password {2}".format(
                MIN_NAME, username, USERA_PWD
            )
        )

        check_key = self.run_key("-p {0}".format(MIN_NAME))
        self.assertEqual([], check_key)

    @slowTest
    def test_list_accepted_args(self):
        """
        test salt-key -l for accepted arguments
        """
        for key in ("acc", "pre", "den", "un", "rej"):
            # These should not trigger any error
            data = self.run_key("-l {0}".format(key), catch_stderr=True)
            self.assertNotIn("error:", "\n".join(data[1]))
            data = self.run_key("-l foo-{0}".format(key), catch_stderr=True)
            self.assertIn("error:", "\n".join(data[1]))

    @slowTest
    def test_list_all(self):
        """
        test salt-key -L
        """
        data = self.run_key("-L")
        expect = None
        if self.master_opts["transport"] in ("zeromq", "tcp"):
            expect = [
                "Accepted Keys:",
                "minion",
                "sub_minion",
                "Denied Keys:",
                "Unaccepted Keys:",
                "Rejected Keys:",
            ]
        self.assertEqual(data, expect)

    @slowTest
    def test_list_json_out(self):
        """
        test salt-key -L --json-out
        """
        data = self.run_key("-L --out json")
        ret = {}
        try:
            import salt.utils.json

            ret = salt.utils.json.loads("\n".join(data))
        except ValueError:
            pass

        expect = None
        if self.master_opts["transport"] in ("zeromq", "tcp"):
            expect = {
                "minions_rejected": [],
                "minions_denied": [],
                "minions_pre": [],
                "minions": ["minion", "sub_minion"],
            }
        self.assertEqual(ret, expect)

    @slowTest
    def test_list_yaml_out(self):
        """
        test salt-key -L --yaml-out
        """
        data = self.run_key("-L --out yaml")
        ret = {}
        try:
            import salt.utils.yaml

            ret = salt.utils.yaml.safe_load("\n".join(data))
        except Exception:  # pylint: disable=broad-except
            pass

        expect = []
        if self.master_opts["transport"] in ("zeromq", "tcp"):
            expect = {
                "minions_rejected": [],
                "minions_denied": [],
                "minions_pre": [],
                "minions": ["minion", "sub_minion"],
            }
        self.assertEqual(ret, expect)

    @slowTest
    def test_list_raw_out(self):
        """
        test salt-key -L --raw-out
        """
        data = self.run_key("-L --out raw")
        self.assertEqual(len(data), 1)

        ret = {}
        try:
            import ast

            ret = ast.literal_eval(data[0])
        except ValueError:
            pass

        expect = None
        if self.master_opts["transport"] in ("zeromq", "tcp"):
            expect = {
                "minions_rejected": [],
                "minions_denied": [],
                "minions_pre": [],
                "minions": ["minion", "sub_minion"],
            }
        self.assertEqual(ret, expect)

    @slowTest
    def test_list_acc(self):
        """
        test salt-key -l
        """
        data = self.run_key("-l acc")
        expect = ["Accepted Keys:", "minion", "sub_minion"]
        self.assertEqual(data, expect)

    @skip_if_not_root
    @destructiveTest
    @skipIf(salt.utils.platform.is_windows(), "PAM eauth not available on Windows")
    @with_system_user(USERA, password=USERA_PWD)
    @slowTest
    def test_list_acc_eauth(self, username):
        """
        test salt-key -l with eauth
        """
        data = self.run_key(
            "-l acc --eauth pam --username {0} --password {1}".format(
                username, USERA_PWD
            )
        )
        expect = ["Accepted Keys:", "minion", "sub_minion"]
        self.assertEqual(data, expect)

    @skip_if_not_root
    @destructiveTest
    @skipIf(salt.utils.platform.is_windows(), "PAM eauth not available on Windows")
    @with_system_user(USERA, password=USERA_PWD)
    @slowTest
    def test_list_acc_eauth_bad_creds(self, username):
        """
        test salt-key -l with eauth and bad creds
        """
        data = self.run_key(
            "-l acc --eauth pam --username {0} --password wrongpassword".format(
                username
            )
        )
        expect = [
            'Authentication failure of type "eauth" occurred for user {0}.'.format(
                username
            )
        ]
        self.assertEqual(data, expect)

    @slowTest
    def test_list_acc_wrong_eauth(self):
        """
        test salt-key -l with wrong eauth
        """
        data = self.run_key(
            "-l acc --eauth wrongeauth --username {0} --password {1}".format(
                USERA, USERA_PWD
            )
        )
        expect = r"^The specified external authentication system \"wrongeauth\" is not available\tAvailable eauth types: auto, .*"
        self.assertRegex("\t".join(data), expect)

    @slowTest
    def test_list_un(self):
        """
        test salt-key -l
        """
        data = self.run_key("-l un")
        expect = ["Unaccepted Keys:"]
        self.assertEqual(data, expect)

    @slowTest
    def test_keys_generation(self):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        arg_str = "--gen-keys {0} --gen-keys-dir {1}".format(MIN_NAME, tempdir)
        self.run_key(arg_str)
        try:
            key_names = None
            if self.master_opts["transport"] in ("zeromq", "tcp"):
                key_names = ("{0}.pub".format(MIN_NAME), "{0}.pem".format(MIN_NAME))
            for fname in key_names:
                self.assertTrue(os.path.isfile(os.path.join(tempdir, fname)))
        finally:
            for dirname, dirs, files in os.walk(tempdir):
                for filename in files:
                    os.chmod(os.path.join(dirname, filename), 0o700)
            shutil.rmtree(tempdir)

    @slowTest
    def test_keys_generation_keysize_minmax(self):
        tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)
        arg_str = "--gen-keys minion --gen-keys-dir {0}".format(tempdir)
        try:
            data, error = self.run_key(arg_str + " --keysize=1024", catch_stderr=True)
            self.assertIn(
                "error: The minimum value for keysize is 2048", "\n".join(error)
            )

            data, error = self.run_key(arg_str + " --keysize=32769", catch_stderr=True)
            self.assertIn(
                "error: The maximum value for keysize is 32768", "\n".join(error)
            )
        finally:
            shutil.rmtree(tempdir)
