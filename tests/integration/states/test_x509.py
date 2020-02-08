# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import datetime
import textwrap

import salt.utils.files
from salt.ext import six

from tests.support.helpers import with_tempfile
from tests.support.case import ModuleCase
from tests.support.unit import skipIf
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS

try:
    import M2Crypto  # pylint: disable=W0611

    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


@skipIf(not HAS_M2CRYPTO, "Skip when no M2Crypto found")
class x509Test(ModuleCase, SaltReturnAssertsMixin):
    @classmethod
    def setUpClass(cls):
        cert_path = os.path.join(RUNTIME_VARS.BASE_FILES, "x509_test.crt")
        with salt.utils.files.fopen(cert_path) as fp:
            cls.x509_cert_text = fp.read()

    def setUp(self):
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "signing_policies.sls"), "w"
        ) as fp:
            fp.write(
                textwrap.dedent(
                    """\
                x509_signing_policies:
                  ca_policy:
                    - minions: '*'
                    - signing_private_key: {0}/pki/ca.key
                    - signing_cert: {0}/pki/ca.crt
                    - O: Test Company
                    - basicConstraints: "CA:false"
                    - keyUsage: "critical digitalSignature, keyEncipherment"
                    - extendedKeyUsage: "critical serverAuth, clientAuth"
                    - subjectKeyIdentifier: hash
                    - authorityKeyIdentifier: keyid
                    - days_valid: 730
                    - copypath: {0}/pki
                     """.format(
                        RUNTIME_VARS.TMP
                    )
                )
            )
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"), "w"
        ) as fp:
            fp.write(
                textwrap.dedent(
                    """\
                     base:
                       '*':
                         - signing_policies
                     """
                )
            )
        self.run_function("saltutil.refresh_pillar")

    def tearDown(self):
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "signing_policies.sls"))
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"))
        certs_path = os.path.join(RUNTIME_VARS.TMP, "pki")
        if os.path.exists(certs_path):
            salt.utils.files.rm_rf(certs_path)
        self.run_function("saltutil.refresh_pillar")

    @with_tempfile(suffix=".pem", create=False)
    def test_issue_49027(self, pemfile):
        ret = self.run_state("x509.pem_managed", name=pemfile, text=self.x509_cert_text)
        assert isinstance(ret, dict), ret
        ret = ret[next(iter(ret))]
        assert ret.get("result") is True, ret
        with salt.utils.files.fopen(pemfile) as fp:
            result = fp.readlines()
        self.assertEqual(self.x509_cert_text.splitlines(True), result)

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_issue_49008(self, keyfile, crtfile):
        ret = self.run_function(
            "state.apply",
            ["issue-49008"],
            pillar={"keyfile": keyfile, "crtfile": crtfile},
        )
        assert isinstance(ret, dict), ret
        for state_result in six.itervalues(ret):
            assert state_result["result"] is True, state_result
        assert os.path.exists(keyfile)
        assert os.path.exists(crtfile)

    def test_cert_signing(self):
        ret = self.run_function(
            "state.apply", ["test_cert"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]

    def test_self_signed_cert(self):
        """
        Self-signed certificate, no CA.
        Run the state twice to confirm the cert is only created once and its contents don't change.
        """
        first_run = self.run_function(
            "state.apply", ["x509.self_signed"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-self_signed_cert_|-{}/self.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        self.assertIn("New", first_run[key]["changes"]["Certificate"])
        self.assertEqual(
            "Certificate is valid and up to date",
            first_run[key]["changes"]["Status"]["New"],
        )
        cert_path = first_run[key]["name"]
        self.assertTrue(os.path.exists(cert_path), "Certificate was not created.")

        with salt.utils.files.fopen(cert_path, "r") as first_cert:
            cert_contents = first_cert.read()

        second_run = self.run_function(
            "state.apply", ["x509.self_signed"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-self_signed_cert_|-{}/self.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        self.assertEqual({}, second_run[key]["changes"])
        with salt.utils.files.fopen(cert_path, "r") as second_cert:
            self.assertEqual(
                cert_contents,
                second_cert.read(),
                "Certificate contents should not have changed.",
            )

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_old_self_signed_cert_is_renewed(self, keyfile, crtfile):
        """
        Self-signed certificate, no CA.
        First create a cert that expires in 30 days, then recreate
        the cert because the second state run requires days_remaining
        to be at least 90.
        """
        first_run = self.run_function(
            "state.apply",
            ["x509.self_signed_expiry"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "days_valid": 30,
                "days_remaining": 10,
            },
        )
        key = "x509_|-self_signed_cert_|-{0}_|-certificate_managed".format(crtfile)
        self.assertEqual(
            "Certificate is valid and up to date",
            first_run[key]["changes"]["Status"]["New"],
        )
        expiry = datetime.datetime.strptime(
            first_run[key]["changes"]["Certificate"]["New"]["Not After"],
            "%Y-%m-%d %H:%M:%S",
        )
        self.assertEqual(29, (expiry - datetime.datetime.now()).days)
        self.assertTrue(os.path.exists(crtfile), "Certificate was not created.")

        with salt.utils.files.fopen(crtfile, "r") as first_cert:
            cert_contents = first_cert.read()

        second_run = self.run_function(
            "state.apply",
            ["x509.self_signed_expiry"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "days_valid": 180,
                "days_remaining": 90,
            },
        )
        self.assertEqual(
            "Certificate needs renewal: 29 days remaining but it needs to be at least 90",
            second_run[key]["changes"]["Status"]["Old"],
        )
        expiry = datetime.datetime.strptime(
            second_run[key]["changes"]["Certificate"]["New"]["Not After"],
            "%Y-%m-%d %H:%M:%S",
        )
        self.assertEqual(179, (expiry - datetime.datetime.now()).days)
        with salt.utils.files.fopen(crtfile, "r") as second_cert:
            self.assertNotEqual(
                cert_contents,
                second_cert.read(),
                "Certificate contents should have changed.",
            )
