"""
    :codeauthor: Wayne Werner <wwerner@saltstack.com>
"""

# Import the future

import os
import tempfile

# Salt Libs
import salt.modules.cmdmod as cmd
import salt.modules.file as file
import salt.modules.tls as tls
import salt.utils.files as files
import salt.utils.stringutils as stringutils

# Testing libs
from tests.support.case import ModuleCase
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.runtests import RUNTIME_VARS


class TLSModuleTest(ModuleCase, LoaderModuleMockMixin):
    """
    Tests for salt.modules.tls
    """

    def setup_loader_modules(self):
        opts = {
            "cachedir": os.path.join(RUNTIME_VARS.TMP, "cache"),
            "test": True,
        }
        return {
            tls: {
                "__salt__": {
                    "config.option": MagicMock(return_value=self.tempdir),
                    "cmd.retcode": cmd.retcode,
                    "pillar.get": MagicMock(return_value=False),
                    "file.replace": file.replace,
                },
                "__opts__": opts,
            },
            file: {
                "__utils__": {
                    "files.is_text": files.is_text,
                    "stringutils.get_diff": stringutils.get_diff,
                },
                "__opts__": opts,
            },
        }

    @classmethod
    def setUpClass(cls):
        cls.ca_name = "roscivs"
        cls.tempdir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    def test_ca_exists_should_be_False_before_ca_is_created(self):
        self.assertFalse(tls.ca_exists(self.ca_name))

    def test_ca_exists_should_be_True_after_ca_is_created(self):
        tls.create_ca(self.ca_name)
        self.assertTrue(tls.ca_exists(self.ca_name))

    def test_creating_csr_should_fail_with_no_ca(self):
        expected_message = (
            'Certificate for CA named "bad_ca" does not exist, please create it first.'
        )
        self.assertEqual(tls.create_csr(ca_name="bad_ca"), expected_message)

    def test_with_existing_ca_signing_csr_should_produce_valid_cert(self):
        print("Revoked should not be here")
        empty_crl_filename = os.path.join(self.tempdir, "empty.crl")
        tls.create_ca(self.ca_name)
        tls.create_csr(
            ca_name=self.ca_name,
            CN="testing.localhost",
        )
        tls.create_ca_signed_cert(
            ca_name=self.ca_name,
            CN="testing.localhost",
        )
        tls.create_empty_crl(
            ca_name=self.ca_name,
            crl_file=empty_crl_filename,
        )
        ret = tls.validate(
            cert=os.path.join(
                self.tempdir,
                self.ca_name,
                "certs",
                "testing.localhost.crt",
            ),
            ca_name=self.ca_name,
            crl_file=empty_crl_filename,
        )
        print("not there")
        self.assertTrue(ret["valid"], ret.get("error"))

    def test_revoked_cert_should_return_False_from_validate(self):
        revoked_crl_filename = os.path.join(self.tempdir, "revoked.crl")
        tls.create_ca(self.ca_name)
        tls.create_csr(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
        )
        tls.create_ca_signed_cert(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
        )
        tls.create_empty_crl(
            ca_name=self.ca_name,
            crl_file=revoked_crl_filename,
        )
        tls.revoke_cert(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
            crl_file=revoked_crl_filename,
        )
        self.assertFalse(
            tls.validate(
                cert=os.path.join(
                    self.tempdir,
                    self.ca_name,
                    "certs",
                    "testing.bad.localhost.crt",
                ),
                ca_name=self.ca_name,
                crl_file=revoked_crl_filename,
            )["valid"]
        )

    def test_validating_revoked_cert_with_no_crl_file_should_return_False(self):
        revoked_crl_filename = None
        tls.create_ca(self.ca_name)
        tls.create_csr(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
        )
        tls.create_ca_signed_cert(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
        )
        tls.create_empty_crl(
            ca_name=self.ca_name,
            crl_file=revoked_crl_filename,
        )
        tls.revoke_cert(
            ca_name=self.ca_name,
            CN="testing.bad.localhost",
            crl_file=revoked_crl_filename,
        )
        self.assertFalse(
            tls.validate(
                cert=os.path.join(
                    self.tempdir,
                    self.ca_name,
                    "certs",
                    "testing.bad.localhost.crt",
                ),
                ca_name=self.ca_name,
                crl_file=revoked_crl_filename,
            )["valid"]
        )
