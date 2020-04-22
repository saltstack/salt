# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import datetime
import os
import hashlib
import textwrap

import salt.utils.files
from salt.ext import six
from tests.support.case import ModuleCase
from tests.support.helpers import with_tempfile
from tests.support.mixins import SaltReturnAssertsMixin
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import skipIf

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
                  compound_match:
                    - minions: 'G@x509_test_grain:correct_value'
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
                     """.format(RUNTIME_VARS.TMP)))
        with salt.utils.files.fopen(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"), "w") as fp:
            fp.write(textwrap.dedent("""\
                     base:
                       '*':
                         - signing_policies
                     """))
        self.run_function("saltutil.refresh_pillar")
        self.run_function("grains.set", ["x509_test_grain", "correct_value"], minion_tgt="sub_minion")
        self.run_function("grains.set", ["x509_test_grain", "not_correct_value"], minion_tgt="minion")

    def tearDown(self):
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "signing_policies.sls"))
        os.remove(os.path.join(RUNTIME_VARS.TMP_PILLAR_TREE, "top.sls"))
        certs_path = os.path.join(RUNTIME_VARS.TMP, "pki")
        if os.path.exists(certs_path):
            salt.utils.files.rm_rf(certs_path)
        self.run_function("saltutil.refresh_pillar")
        self.run_function("grains.delkey", ["x509_test_grain"], minion_tgt="sub_minion")
        self.run_function("grains.delkey", ["x509_test_grain"], minion_tgt="minion")

    def run_function(self, *args, **kwargs):  # pylint: disable=arguments-differ
        ret = super(x509Test, self).run_function(*args, **kwargs)
        return ret

    @staticmethod
    def file_checksum(path):
        hash = hashlib.sha1()
        with salt.utils.files.fopen(path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                hash.update(block)
        return hash.hexdigest()

    @with_tempfile(suffix=".pem", create=False)
    @skipIf(True, "SLOWTEST skip")
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
    @skipIf(True, "SLOWTEST skip")
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

    @skipIf(True, "SLOWTEST skip")
    def test_cert_signing(self):
        ret = self.run_function(
            "state.apply", ["x509.cert_signing"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_issue_41858(self, keyfile, crtfile):
        ret_key = "x509_|-test_crt_|-{0}_|-certificate_managed".format(crtfile)
        signing_policy = "no_such_policy"
        ret = self.run_function(
            "state.apply",
            ["issue-41858.gen_cert"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "tmp_dir": RUNTIME_VARS.TMP})
        self.assertTrue(ret[ret_key]["result"])
        cert_sum = self.file_checksum(crtfile)

        ret = self.run_function(
            "state.apply",
            ["issue-41858.check"],
            pillar={"keyfile": keyfile, "crtfile": crtfile, "signing_policy": signing_policy})
        self.assertFalse(ret[ret_key]["result"])
        # self.assertSaltCommentRegexpMatches(ret[ret_key], "Signing policy {0} does not exist".format(signing_policy))
        self.assertEqual(self.file_checksum(crtfile), cert_sum)

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_compound_match_minion_have_correct_grain_value(self, keyfile, crtfile):
        ret_key = "x509_|-test_crt_|-{0}_|-certificate_managed".format(crtfile)
        signing_policy = "compound_match"
        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.gen_ca"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP})

        # sub_minion have grain set and CA is on other minion
        # CA minion have same grain with incorrect value
        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.check"],
            minion_tgt="sub_minion",
            pillar={"keyfile": keyfile, "crtfile": crtfile, "signing_policy": signing_policy})
        self.assertTrue(ret[ret_key]["result"])

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_compound_match_ca_have_correct_grain_value(self, keyfile, crtfile):
        self.run_function("grains.set", ["x509_test_grain", "correct_value"], minion_tgt="minion")
        self.run_function("grains.set", ["x509_test_grain", "not_correct_value"], minion_tgt="sub_minion")

        ret_key = "x509_|-test_crt_|-{0}_|-certificate_managed".format(crtfile)
        signing_policy = "compound_match"
        self.run_function("state.apply",
                          ["x509_compound_match.gen_ca"],
                          pillar={"tmp_dir": RUNTIME_VARS.TMP})

        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.check"],
            minion_tgt="sub_minion",
            pillar={"keyfile": keyfile, "crtfile": crtfile, "signing_policy": signing_policy})
        self.assertFalse(ret[ret_key]["result"])

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_self_signed_cert(self, keyfile, crtfile):
        """
        Self-signed certificate, no CA.
        Run the state twice to confirm the cert is only created once
        and its contents don't change.
        """
        first_run = self.run_function(
            "state.apply",
            ["x509.self_signed"],
            pillar={"keyfile": keyfile, "crtfile": crtfile},
        )
        key = "x509_|-self_signed_cert_|-{}_|-certificate_managed".format(crtfile)
        self.assertIn("New", first_run[key]["changes"]["Certificate"])
        self.assertEqual(
            "Certificate is valid and up to date",
            first_run[key]["changes"]["Status"]["New"],
        )
        self.assertTrue(os.path.exists(crtfile), "Certificate was not created.")

        with salt.utils.files.fopen(crtfile, "r") as first_cert:
            cert_contents = first_cert.read()

        second_run = self.run_function(
            "state.apply",
            ["x509.self_signed"],
            pillar={"keyfile": keyfile, "crtfile": crtfile},
        )
        self.assertEqual({}, second_run[key]["changes"])
        with salt.utils.files.fopen(crtfile, "r") as second_cert:
            self.assertEqual(
                cert_contents,
                second_cert.read(),
                "Certificate contents should not have changed.",
            )

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_old_self_signed_cert_is_recreated(self, keyfile, crtfile):
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

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_mismatched_self_signed_cert_is_recreated(self, keyfile, crtfile):
        """
        Self-signed certificate, no CA.
        First create a cert, then run the state again with a different
        subjectAltName. The cert should be recreated.
        Finally, run once more with the same subjectAltName as the
        second run. Nothing should change.
        """
        first_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "subjectAltName": "DNS:alt.service.local",
            },
        )
        key = "x509_|-self_signed_cert_|-{0}_|-certificate_managed".format(crtfile)
        self.assertEqual(
            "Certificate is valid and up to date",
            first_run[key]["changes"]["Status"]["New"],
        )
        sans = first_run[key]["changes"]["Certificate"]["New"]["X509v3 Extensions"][
            "subjectAltName"
        ]
        self.assertEqual("DNS:alt.service.local", sans)
        self.assertTrue(os.path.exists(crtfile), "Certificate was not created.")

        with salt.utils.files.fopen(crtfile, "r") as first_cert:
            first_cert_contents = first_cert.read()

        second_run_pillar = {
            "keyfile": keyfile,
            "crtfile": crtfile,
            "subjectAltName": "DNS:alt1.service.local, DNS:alt2.service.local",
        }
        second_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar=second_run_pillar,
        )
        self.assertEqual(
            "Certificate properties are different: X509v3 Extensions",
            second_run[key]["changes"]["Status"]["Old"],
        )
        sans = second_run[key]["changes"]["Certificate"]["New"]["X509v3 Extensions"][
            "subjectAltName"
        ]
        self.assertEqual("DNS:alt1.service.local, DNS:alt2.service.local", sans)
        with salt.utils.files.fopen(crtfile, "r") as second_cert:
            second_cert_contents = second_cert.read()
            self.assertNotEqual(
                first_cert_contents,
                second_cert_contents,
                "Certificate contents should have changed.",
            )

        third_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar=second_run_pillar,
        )
        self.assertEqual({}, third_run[key]["changes"])
        with salt.utils.files.fopen(crtfile, "r") as third_cert:
            self.assertEqual(
                second_cert_contents,
                third_cert.read(),
                "Certificate contents should not have changed.",
            )

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_certificate_managed_with_managed_private_key_does_not_error(
        self, keyfile, crtfile
    ):
        """
        Test using the deprecated managed_private_key arg in certificate_managed does not throw an error.

        TODO: Remove this test in Aluminium when the arg is removed.
        """
        self.run_state("x509.private_key_managed", name=keyfile, bits=4096)
        ret = self.run_state(
            "x509.certificate_managed",
            name=crtfile,
            CN="localhost",
            signing_private_key=keyfile,
            managed_private_key={"name": keyfile, "bits": 4096},
        )
        key = "x509_|-{0}_|-{0}_|-certificate_managed".format(crtfile)
        self.assertEqual(True, ret[key]["result"])
