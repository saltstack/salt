# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Gareth J. Greenaway <gareth@saltstack.com>`
    :codeauthor: :email:`David Murphy <dmurphy@saltstack.com>`
"""

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import datetime
import os
import shutil
import time

import salt.modules.gpg as gpg
import salt.utils.files

# Import Salt libs
import salt.utils.platform

# Import Salt Testing Libs
from tests.support.helpers import destructiveTest
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

GPG_TEST_KEY_PASSPHRASE = "testkeypassphrase"
GPG_TEST_KEY_ID = "7416F045"
GPG_TEST_PUB_KEY = """-----BEGIN PGP PUBLIC KEY BLOCK-----

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
ylirh0aqUQdSeIuJTg==
=yF8M
-----END PGP PUBLIC KEY BLOCK-----
"""

GPG_TEST_PRIV_KEY = """-----BEGIN PGP PRIVATE KEY BLOCK-----

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
=WRTN
-----END PGP PRIVATE KEY BLOCK-----
"""

try:
    import gnupg  # pylint: disable=import-error,unused-import

    HAS_GPG = True
except ImportError:
    HAS_GPG = False


@destructiveTest
@skipIf(not salt.utils.platform.is_linux(), "These tests can only be run on linux")
class GpgTestCase(TestCase, LoaderModuleMockMixin):
    """
    Validate the gpg module
    """

    def setup_loader_modules(self):
        return {gpg: {"__salt__": {}}}

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def setUp(self):
        super(GpgTestCase, self).setUp()
        self.gpghome = os.path.join(RUNTIME_VARS.TMP, "gpghome")
        if not os.path.isdir(self.gpghome):
            # left behind... Don't fail because of this!
            os.makedirs(self.gpghome)
        self.gpgfile_pub = os.path.join(RUNTIME_VARS.TMP, "gpgfile.pub")
        with salt.utils.files.fopen(self.gpgfile_pub, "wb") as fp:
            fp.write(salt.utils.stringutils.to_bytes(GPG_TEST_PUB_KEY))
        self.gpgfile_priv = os.path.join(RUNTIME_VARS.TMP, "gpgfile.priv")
        with salt.utils.files.fopen(self.gpgfile_priv, "wb") as fp:
            fp.write(salt.utils.stringutils.to_bytes(GPG_TEST_PRIV_KEY))
        self.user = "salt"

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def tearDown(self):
        if os.path.isfile(self.gpgfile_pub):
            os.remove(self.gpgfile_pub)
        shutil.rmtree(self.gpghome, ignore_errors=True)
        super(GpgTestCase, self).tearDown()

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_list_keys(self):
        """
        Test gpg.list_keys
        """

        _user_mock = {
            "shell": "/bin/bash",
            "workphone": "",
            "uid": 0,
            "passwd": "x",
            "roomnumber": "",
            "gid": 0,
            "groups": ["root"],
            "home": "/root",
            "fullname": "root",
            "homephone": "",
            "name": "root",
        }

        _list_result = [
            {
                "dummy": "",
                "keyid": "xxxxxxxxxxxxxxxx",
                "expires": "2011188692",
                "sigs": [],
                "subkeys": [
                    [
                        "xxxxxxxxxxxxxxxx",
                        "e",
                        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    ]
                ],
                "length": "4096",
                "ownertrust": "-",
                "sig": "",
                "algo": "1",
                "fingerprint": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "date": "1506612692",
                "trust": "-",
                "type": "pub",
                "uids": ["GPG Person <person@example.com>"],
            }
        ]

        _expected_result = [
            {
                "keyid": "xxxxxxxxxxxxxxxx",
                "uids": ["GPG Person <person@example.com>"],
                "created": "2017-09-28",
                "expires": "2033-09-24",
                "keyLength": "4096",
                "ownerTrust": "Unknown",
                "fingerprint": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "trust": "Unknown",
            }
        ]

        mock_opt = MagicMock(return_value="root")
        with patch.dict(
            gpg.__salt__, {"user.info": MagicMock(return_value=_user_mock)}
        ):
            with patch.dict(gpg.__salt__, {"config.option": mock_opt}):
                with patch.object(gpg, "_list_keys", return_value=_list_result):
                    self.assertEqual(gpg.list_keys(), _expected_result)

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_get_key(self):
        """
        Test gpg.get_key
        """

        _user_mock = {
            "shell": "/bin/bash",
            "workphone": "",
            "uid": 0,
            "passwd": "x",
            "roomnumber": "",
            "gid": 0,
            "groups": ["root"],
            "home": "/root",
            "fullname": "root",
            "homephone": "",
            "name": "root",
        }

        _list_result = [
            {
                "dummy": "",
                "keyid": "xxxxxxxxxxxxxxxx",
                "expires": "2011188692",
                "sigs": [],
                "subkeys": [
                    [
                        "xxxxxxxxxxxxxxxx",
                        "e",
                        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    ]
                ],
                "length": "4096",
                "ownertrust": "-",
                "sig": "",
                "algo": "1",
                "fingerprint": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "date": "1506612692",
                "trust": "-",
                "type": "pub",
                "uids": ["GPG Person <person@example.com>"],
            }
        ]

        _expected_result = {
            "fingerprint": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "keyid": "xxxxxxxxxxxxxxxx",
            "uids": ["GPG Person <person@example.com>"],
            "created": "2017-09-28",
            "trust": "Unknown",
            "ownerTrust": "Unknown",
            "expires": "2033-09-24",
            "keyLength": "4096",
        }

        mock_opt = MagicMock(return_value="root")
        with patch.dict(
            gpg.__salt__, {"user.info": MagicMock(return_value=_user_mock)}
        ):
            with patch.dict(gpg.__salt__, {"config.option": mock_opt}):
                with patch.object(gpg, "_list_keys", return_value=_list_result):
                    ret = gpg.get_key("xxxxxxxxxxxxxxxx")
                    self.assertEqual(ret, _expected_result)

    @destructiveTest  # Need to run as root!?
    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_delete_key(self):
        """
        Test gpg.delete_key
        """

        _user_mock = {
            "shell": "/bin/bash",
            "workphone": "",
            "uid": 0,
            "passwd": "x",
            "roomnumber": "",
            "gid": 0,
            "groups": ["root"],
            "home": self.gpghome,
            "fullname": "root",
            "homephone": "",
            "name": "root",
        }

        _list_result = [
            {
                "dummy": "",
                "keyid": "xxxxxxxxxxxxxxxx",
                "expires": "2011188692",
                "sigs": [],
                "subkeys": [
                    [
                        "xxxxxxxxxxxxxxxx",
                        "e",
                        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                    ]
                ],
                "length": "4096",
                "ownertrust": "-",
                "sig": "",
                "algo": "1",
                "fingerprint": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "date": "1506612692",
                "trust": "-",
                "type": "pub",
                "uids": ["GPG Person <person@example.com>"],
            }
        ]

        _expected_result = {
            "res": True,
            "message": "Secret key for xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted\nPublic key for xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx deleted",
        }

        mock_opt = MagicMock(return_value="root")
        with patch.dict(
            gpg.__salt__, {"user.info": MagicMock(return_value=_user_mock)}
        ):
            with patch.dict(gpg.__salt__, {"config.option": mock_opt}):
                with patch.object(gpg, "_list_keys", return_value=_list_result):
                    with patch(
                        "salt.modules.gpg.gnupg.GPG.delete_keys",
                        MagicMock(return_value="ok"),
                    ):
                        ret = gpg.delete_key("xxxxxxxxxxxxxxxx", delete_secret=True)
                        self.assertEqual(ret, _expected_result)

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_search_keys(self):
        """
        Test gpg.search_keys
        """

        _user_mock = {
            "shell": "/bin/bash",
            "workphone": "",
            "uid": 0,
            "passwd": "x",
            "roomnumber": "",
            "gid": 0,
            "groups": ["root"],
            "home": self.gpghome,
            "fullname": "root",
            "homephone": "",
            "name": "root",
        }

        _search_result = [
            {
                "keyid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "uids": ["GPG Person <person@example.com>"],
                "expires": "",
                "sigs": [],
                "length": "1024",
                "algo": "17",
                "date": int(time.mktime(datetime.datetime(2004, 11, 13).timetuple())),
                "type": "pub",
            }
        ]

        _expected_result = [
            {
                "uids": ["GPG Person <person@example.com>"],
                "created": "2004-11-13",
                "keyLength": "1024",
                "keyid": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            }
        ]

        mock_opt = MagicMock(return_value="root")
        with patch.dict(
            gpg.__salt__, {"user.info": MagicMock(return_value=_user_mock)}
        ):
            with patch.dict(gpg.__salt__, {"config.option": mock_opt}):
                with patch.object(gpg, "_search_keys", return_value=_search_result):
                    ret = gpg.search_keys("person@example.com")
                    self.assertEqual(ret, _expected_result)

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_gpg_import_pub_key(self):
        config_user = MagicMock(return_value="salt")
        user_info = MagicMock(
            return_value={"name": "salt", "home": self.gpghome, "uid": 1000}
        )
        with patch.dict(gpg.__salt__, {"config.option": config_user}):
            with patch.dict(gpg.__salt__, {"user.info": user_info}):
                ret = gpg.import_key(None, self.gpgfile_pub, "salt", self.gpghome)
                self.assertEqual(ret["res"], True)

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_gpg_import_priv_key(self):
        config_user = MagicMock(return_value="salt")
        user_info = MagicMock(
            return_value={"name": "salt", "home": self.gpghome, "uid": 1000}
        )
        with patch.dict(gpg.__salt__, {"config.option": config_user}):
            with patch.dict(gpg.__salt__, {"user.info": user_info}):
                ret = gpg.import_key(None, self.gpgfile_priv, "salt", self.gpghome)
                self.assertEqual(ret["res"], True)

    @skipIf(not HAS_GPG, "GPG Module Unavailable")
    def test_gpg_sign(self):
        config_user = MagicMock(return_value="salt")
        user_info = MagicMock(
            return_value={"name": "salt", "home": self.gpghome, "uid": 1000}
        )
        pillar_mock = MagicMock(
            return_value={"gpg_passphrase": GPG_TEST_KEY_PASSPHRASE}
        )
        with patch.dict(gpg.__salt__, {"config.option": config_user}):
            with patch.dict(gpg.__salt__, {"user.info": user_info}):
                with patch.dict(gpg.__salt__, {"pillar.get": pillar_mock}):
                    ret = gpg.import_key(None, self.gpgfile_priv, "salt", self.gpghome)
                    self.assertEqual(ret["res"], True)
                    gpg_text_input = "The quick brown fox jumped over the lazy dog"
                    gpg_sign_output = gpg.sign(
                        config_user,
                        GPG_TEST_KEY_ID,
                        gpg_text_input,
                        None,
                        None,
                        True,
                        self.gpghome,
                    )
                    self.assertIsNotNone(gpg_sign_output)
