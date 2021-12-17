import datetime
import hashlib
import logging
import os
import pprint
import textwrap

import pytest
import salt.utils.files
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

log = logging.getLogger(__name__)


@pytest.mark.usefixtures("salt_sub_minion")
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
        self.run_function(
            "grains.set", ["x509_test_grain", "correct_value"], minion_tgt="sub_minion"
        )
        self.run_function(
            "grains.set", ["x509_test_grain", "not_correct_value"], minion_tgt="minion"
        )

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
        ret = super().run_function(*args, **kwargs)
        return ret

    @staticmethod
    def file_checksum(path):
        hash = hashlib.sha1()
        with salt.utils.files.fopen(path, "rb") as f:
            for block in iter(lambda: f.read(4096), b""):
                hash.update(block)
        return hash.hexdigest()

    @with_tempfile(suffix=".pem", create=False)
    @pytest.mark.slow_test
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
    @pytest.mark.slow_test
    def test_issue_49008(self, keyfile, crtfile):
        ret = self.run_function(
            "state.apply",
            ["issue-49008"],
            pillar={"keyfile": keyfile, "crtfile": crtfile},
        )
        assert isinstance(ret, dict), ret
        for state_result in ret.values():
            assert state_result["result"] is True, state_result
        assert os.path.exists(keyfile)
        assert os.path.exists(crtfile)

    @pytest.mark.slow_test
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

    @pytest.mark.slow_test
    def test_cert_signing_based_on_csr(self):
        ret = self.run_function(
            "state.apply",
            ["x509.cert_signing_based_on_csr"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]

    @pytest.mark.slow_test
    def test_proper_cert_comparison(self):
        # In this SLS we define two certs which have identical content.
        # The first one is expected to be created.
        # The second one is expected to be recognized as already present.
        ret = self.run_function(
            "state.apply",
            ["x509.proper_cert_comparison"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )
        # check the first generated cert
        first_key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert first_key in ret
        assert "changes" in ret[first_key]
        assert "Certificate" in ret[first_key]["changes"]
        assert "New" in ret[first_key]["changes"]["Certificate"]
        # check whether the second defined cert is considered to match the first one
        second_key = (
            "x509_|-second_test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
                RUNTIME_VARS.TMP
            )
        )
        assert second_key in ret
        assert "changes" in ret[second_key]
        assert ret[second_key]["changes"] == {}

    @pytest.mark.slow_test
    def test_crl_managed(self):
        ret = self.run_function(
            "state.apply", ["x509.crl_managed"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-{}/pki/ca.crl_|-{}/pki/ca.crl_|-crl_managed".format(
            RUNTIME_VARS.TMP, RUNTIME_VARS.TMP
        )

        # hints for easier debugging
        # import json
        # print(json.dumps(ret[key], indent=4, sort_keys=True))
        # print(ret[key]['comment'])

        assert key in ret
        assert "changes" in ret[key]
        self.assertEqual(ret[key]["result"], True)
        assert "New" in ret[key]["changes"]
        assert "Revoked Certificates" in ret[key]["changes"]["New"]
        self.assertEqual(
            ret[key]["changes"]["Old"],
            "{}/pki/ca.crl does not exist.".format(RUNTIME_VARS.TMP),
        )

    @pytest.mark.slow_test
    def test_crl_managed_replacing_existing_crl(self):
        os.mkdir(os.path.join(RUNTIME_VARS.TMP, "pki"))
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP, "pki/ca.crl"), "wb"
        ) as crl_file:
            crl_file.write(
                b"""-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCjdjbgL4kQ8Lu73xeRRM1q3C3K3ptfCLpyfw38LRnymxaoJ6ls
pNSx2dU1uJ89YKFlYLo1QcEk4rJ2fdIjarV0kuNCY3rC8jYUp9BpAU5Z6p9HKeT1
2rTPH81JyjbQDR5PyfCyzYOQtpwpB4zIUUK/Go7tTm409xGKbbUFugJNgQIDAQAB
AoGAF24we34U1ZrMLifSRv5nu3OIFNZHyx2DLDpOFOGaII5edwgIXwxZeIzS5Ppr
yO568/8jcdLVDqZ4EkgCwRTgoXRq3a1GLHGFmBdDNvWjSTTMLoozuM0t2zjRmIsH
hUd7tnai9Lf1Bp5HlBEhBU2gZWk+SXqLvxXe74/+BDAj7gECQQDRw1OPsrgTvs3R
3MNwX6W8+iBYMTGjn6f/6rvEzUs/k6rwJluV7n8ISNUIAxoPy5g5vEYK6Ln/Ttc7
u0K1KNlRAkEAx34qcxjuswavL3biNGE+8LpDJnJx1jaNWoH+ObuzYCCVMusdT2gy
kKuq9ytTDgXd2qwZpIDNmscvReFy10glMQJAXebMz3U4Bk7SIHJtYy7OKQzn0dMj
35WnRV81c2Jbnzhhu2PQeAvt/i1sgEuzLQL9QEtSJ6wLJ4mJvImV0TdaIQJAAYyk
TcKK0A8kOy0kMp3yvDHmJZ1L7wr7bBGIZPBlQ0Ddh8i1sJExm1gJ+uN2QKyg/XrK
tDFf52zWnCdVGgDwcQJALW/WcbSEK+JVV6KDJYpwCzWpKIKpBI0F6fdCr1G7Xcwj
c9bcgp7D7xD+TxWWNj4CSXEccJgGr91StV+gFg4ARQ==
-----END RSA PRIVATE KEY-----
"""
            )

        ret = self.run_function(
            "state.apply", ["x509.crl_managed"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-{}/pki/ca.crl_|-{}/pki/ca.crl_|-crl_managed".format(
            RUNTIME_VARS.TMP, RUNTIME_VARS.TMP
        )

        # hints for easier debugging
        # import json
        # print(json.dumps(ret[key], indent=4, sort_keys=True))
        # print(ret[key]['comment'])

        assert key in ret
        assert "changes" in ret[key]
        self.assertEqual(ret[key]["result"], True)
        assert "New" in ret[key]["changes"]
        assert "Revoked Certificates" in ret[key]["changes"]["New"]
        self.assertEqual(
            ret[key]["changes"]["Old"],
            "{}/pki/ca.crl is not a valid CRL.".format(RUNTIME_VARS.TMP),
        )

    def test_cert_issue_not_before_not_after(self):
        ret = self.run_function(
            "state.apply",
            ["test_cert_not_before_not_after"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]
        assert "Not Before" in ret[key]["changes"]["Certificate"]["New"]
        assert "Not After" in ret[key]["changes"]["Certificate"]["New"]
        not_before = ret[key]["changes"]["Certificate"]["New"]["Not Before"]
        not_after = ret[key]["changes"]["Certificate"]["New"]["Not After"]
        assert not_before == "2019-05-05 00:00:00"
        assert not_after == "2020-05-05 14:30:00"

    def test_cert_issue_not_before(self):
        ret = self.run_function(
            "state.apply",
            ["test_cert_not_before"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]
        assert "Not Before" in ret[key]["changes"]["Certificate"]["New"]
        assert "Not After" in ret[key]["changes"]["Certificate"]["New"]
        not_before = ret[key]["changes"]["Certificate"]["New"]["Not Before"]
        assert not_before == "2019-05-05 00:00:00"

    def test_cert_issue_not_after(self):
        ret = self.run_function(
            "state.apply", ["test_cert_not_after"], pillar={"tmp_dir": RUNTIME_VARS.TMP}
        )
        key = "x509_|-test_crt_|-{}/pki/test.crt_|-certificate_managed".format(
            RUNTIME_VARS.TMP
        )
        assert key in ret
        assert "changes" in ret[key]
        assert "Certificate" in ret[key]["changes"]
        assert "New" in ret[key]["changes"]["Certificate"]
        assert "Not Before" in ret[key]["changes"]["Certificate"]["New"]
        assert "Not After" in ret[key]["changes"]["Certificate"]["New"]
        not_after = ret[key]["changes"]["Certificate"]["New"]["Not After"]
        assert not_after == "2020-05-05 14:30:00"

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_issue_41858(self, keyfile, crtfile):
        ret_key = "x509_|-test_crt_|-{}_|-certificate_managed".format(crtfile)
        signing_policy = "no_such_policy"
        ret = self.run_function(
            "state.apply",
            ["issue-41858.gen_cert"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "tmp_dir": RUNTIME_VARS.TMP,
            },
        )
        self.assertTrue(ret[ret_key]["result"])
        cert_sum = self.file_checksum(crtfile)

        ret = self.run_function(
            "state.apply",
            ["issue-41858.check"],
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "signing_policy": signing_policy,
            },
        )
        self.assertFalse(ret[ret_key]["result"])
        # self.assertSaltCommentRegexpMatches(ret[ret_key], "Signing policy {0} does not exist".format(signing_policy))
        self.assertEqual(self.file_checksum(crtfile), cert_sum)

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_compound_match_minion_have_correct_grain_value(self, keyfile, crtfile):
        ret_key = "x509_|-test_crt_|-{}_|-certificate_managed".format(crtfile)
        signing_policy = "compound_match"
        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.gen_ca"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )

        # sub_minion have grain set and CA is on other minion
        # CA minion have same grain with incorrect value
        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.check"],
            minion_tgt="sub_minion",
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "signing_policy": signing_policy,
            },
        )
        self.assertTrue(ret[ret_key]["result"])

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_compound_match_ca_have_correct_grain_value(self, keyfile, crtfile):
        self.run_function(
            "grains.set", ["x509_test_grain", "correct_value"], minion_tgt="minion"
        )
        self.run_function(
            "grains.set",
            ["x509_test_grain", "not_correct_value"],
            minion_tgt="sub_minion",
        )

        ret_key = "x509_|-test_crt_|-{}_|-certificate_managed".format(crtfile)
        signing_policy = "compound_match"
        self.run_function(
            "state.apply",
            ["x509_compound_match.gen_ca"],
            pillar={"tmp_dir": RUNTIME_VARS.TMP},
        )

        ret = self.run_function(
            "state.apply",
            ["x509_compound_match.check"],
            minion_tgt="sub_minion",
            pillar={
                "keyfile": keyfile,
                "crtfile": crtfile,
                "signing_policy": signing_policy,
            },
        )
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
        key = "x509_|-self_signed_cert_|-{}_|-certificate_managed".format(crtfile)
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
            "Certificate needs renewal: 29 days remaining but it needs to be at"
            " least 90",
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
        key = "x509_|-self_signed_cert_|-{}_|-certificate_managed".format(crtfile)
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

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_file_properties_are_updated(self, keyfile, crtfile):
        """
        Self-signed certificate, no CA.
        First create a cert, then run the state again with different
        file mode. The cert should not be recreated, but the file
        should be updated.
        Finally, run once more with the same file mode as the second
        run. Nothing should change.
        """
        first_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar={"keyfile": keyfile, "crtfile": crtfile, "fileMode": "0755"},
        )
        key = "x509_|-self_signed_cert_|-{}_|-certificate_managed".format(crtfile)
        self.assertEqual(
            "Certificate is valid and up to date",
            first_run[key]["changes"]["Status"]["New"],
        )
        self.assertTrue(os.path.exists(crtfile), "Certificate was not created.")
        self.assertEqual("0755", oct(os.stat(crtfile).st_mode)[-4:])

        second_run_pillar = {
            "keyfile": keyfile,
            "crtfile": crtfile,
            "mode": "0600",
        }
        second_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar=second_run_pillar,
        )
        self.assertEqual("0600", oct(os.stat(crtfile).st_mode)[-4:])

        third_run = self.run_function(
            "state.apply",
            ["x509.self_signed_different_properties"],
            pillar=second_run_pillar,
        )
        self.assertEqual({}, third_run[key]["changes"])
        self.assertEqual("0600", oct(os.stat(crtfile).st_mode)[-4:])

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_file_managed_failure(self, keyfile, crtfile):
        """
        Test that a failure in the file.managed call marks the state
        call as failed.
        """
        crtfile_pieces = os.path.split(crtfile)
        bad_crtfile = os.path.join(
            crtfile_pieces[0], "deeply/nested", crtfile_pieces[1]
        )
        ret = self.run_function(
            "state.apply",
            ["x509.self_signed_file_error"],
            pillar={"keyfile": keyfile, "crtfile": bad_crtfile},
        )

        key = "x509_|-self_signed_cert_|-{}_|-certificate_managed".format(bad_crtfile)
        self.assertFalse(ret[key]["result"], "State should have failed.")
        self.assertEqual({}, ret[key]["changes"])
        self.assertFalse(
            os.path.exists(crtfile), "Certificate should not have been created."
        )

    @with_tempfile(suffix=".crt", create=False)
    @with_tempfile(suffix=".key", create=False)
    def test_py2_generated_cert_is_not_recreated(self, keyfile, crtfile):
        keyfile_contents = textwrap.dedent(
            """\
        -----BEGIN RSA PRIVATE KEY-----
        MIIEpAIBAAKCAQEAp5PQyx5NlYrfzd7vU/Xb2YR5qbWWtpWWoKmJC1gML5v5DBI7
        +p/kAHNNmK8uqHXTaI4N/zgarfjrg4zceq2Du7pP0xiCAYolhFqF78ibxNrN4OkT
        UPm2kM88iJ8Z14Yph8ueSxLIlujCGaEFhr6wRzTj4T9b+0Bb/PZHI2t5YwtIooVM
        EFCBFkt4bb004tO0D9q0CPPVT2AsGmxnY43Aj3Epy++kqmaWj1hIucSprkDrAXFS
        WacBQPFQ8XctnL2Z1Q6CJ5WUNrW8ohAJ9RJkwjiqbZTwYIPSSrl+FO3XqDY70SxU
        3xDeqhU4zvyjxJ8w9SPqTUu/C3BZtRBT9dCBEQIDAQABAoIBAQCZvS23u1RYVrEe
        sWGF+LA67aOkg9kCJ1iqiv8UrjF32DNy1KO8OcY2d5H/+u/mUzqh2HmU5QbtBsoi
        xS9dSSTrLHGhbAGRogjrVRU9uCDYSBjLN2mmR4IrdkTF3pkZtpcRY0gU/eWTNXUl
        iCmGxhj5KtfJxZQAfLon6FW5dBdIOgxSCJhvRq0zFpWJZFGWWkBExDfeNg//0fCU
        UbjRjGacP/+R6FSJa6tevzgR7tIIapm1dY/ofPXIXsZGo1R87fRgLI1D+e84Jdds
        /U0bKzPOgAjcC1b262lJ8058pjG/nqWC0YUfpIJUVv2ciJpH3Ha+90526InLAUXA
        RWe1Z2YxAoGBANqACEKvUbxENu+XxQj0SI1co4SRTOvgbrSQGL61rDY6PvY/bOqC
        JeR0KC3MN6e7fx52tsl/eqP9iyExUpO9b0BCnGg967MivJXWUxhUdOL/r2ceQBqD
        DiPVZCFsjeNdSNihnNctAig9Po3GEUWE0ikHr3NcD+wXTnhnIEjJ/fltAoGBAMRW
        dIcOiuDLm/oDLNCpwEO4m63ymbUgeOj2cZhKMTqFmspnKnuCU1U/A8cuQcs1gydL
        7MzxVP7MZDIEqT5gGj3eyuVMAmKbvLFR2NctDIDjaUs6oz0J9NGByPNjXaYr4uMd
        EZrxD8gLZ/G+/7eKsCgBA9ksSydDo00Vf/qAsmO1AoGBANWqc+l59eyrrCj5egU6
        lKQf3gsp51WV/8v0SS5dC41vwdgdx80+/fz8FbpLRHVypWlN34sFbRFmQ6Juz/iH
        O35UZQyO2KkxI8dGcbWOCUtditHExBzo4W/rIWKJ++pFc5Hb4DqO2dgto7kR4hvg
        OX9D869UbIGLfQHCntBvLju1AoGAHpcl0sEmTD4NEFgcTGqWZTbHMsQAxOLJU+rJ
        6iNtJiQY6P5H9TRqDXci/I6te57bz2yZ+ZiEWKq51b06LVjF3evviuhb2sdPEAWj
        lmsTbqWAC1OYiXMarOXezGUn+zMNR7uIua5jehSk3lqW9x7psWHvGpA3KWf1cpYt
        +XbB1J0CgYBCSjALTv4dcn+CtS3kqb806z8H9MSZznUwSmcgvwCR5sqwLAUk1xRn
        hEqXbC1RGee3Xqv9mXPDK2LirpdRYi9Jr9ApZkrSkeaXSd2d4cy2ujUT0c7P8JrD
        i6QXb+HaFeBuS5ulYDmo4mIbCysuTsgrLzplViUy3xUQv23M/Eh1gw==
        -----END RSA PRIVATE KEY-----
        """
        )
        crtfile_contents = textwrap.dedent(
            """\
        -----BEGIN CERTIFICATE-----
        MIIEhTCCA22gAwIBAgIIUijHgif6VJUwDQYJKoZIhvcNAQELBQAwgYIxCzAJBgNV
        BAYTAkJFMRgwFgYDVQQDDA9FeGFtcGxlIFJvb3QgQ0ExETAPBgNVBAcMCEthcGVs
        bGVuMRAwDgYDVQQIDAdBbnR3ZXJwMRAwDgYDVQQKDAdFeGFtcGxlMSIwIAYJKoZI
        hvcNAQkBFhNjZXJ0YWRtQGV4YW1wbGUub3JnMB4XDTIwMDYxNjA3Mzk1OVoXDTMw
        MDYxNDA3Mzk1OVowgYIxCzAJBgNVBAYTAkJFMRgwFgYDVQQDDA9FeGFtcGxlIFJv
        b3QgQ0ExETAPBgNVBAcMCEthcGVsbGVuMRAwDgYDVQQIDAdBbnR3ZXJwMRAwDgYD
        VQQKDAdFeGFtcGxlMSIwIAYJKoZIhvcNAQkBFhNjZXJ0YWRtQGV4YW1wbGUub3Jn
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp5PQyx5NlYrfzd7vU/Xb
        2YR5qbWWtpWWoKmJC1gML5v5DBI7+p/kAHNNmK8uqHXTaI4N/zgarfjrg4zceq2D
        u7pP0xiCAYolhFqF78ibxNrN4OkTUPm2kM88iJ8Z14Yph8ueSxLIlujCGaEFhr6w
        RzTj4T9b+0Bb/PZHI2t5YwtIooVMEFCBFkt4bb004tO0D9q0CPPVT2AsGmxnY43A
        j3Epy++kqmaWj1hIucSprkDrAXFSWacBQPFQ8XctnL2Z1Q6CJ5WUNrW8ohAJ9RJk
        wjiqbZTwYIPSSrl+FO3XqDY70SxU3xDeqhU4zvyjxJ8w9SPqTUu/C3BZtRBT9dCB
        EQIDAQABo4H8MIH5MA8GA1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMB0G
        A1UdDgQWBBTmNsYLuQTxpANgTuw7LRn1qHJsjzCBtgYDVR0jBIGuMIGrgBTmNsYL
        uQTxpANgTuw7LRn1qHJsj6GBiKSBhTCBgjELMAkGA1UEBhMCQkUxGDAWBgNVBAMM
        D0V4YW1wbGUgUm9vdCBDQTERMA8GA1UEBwwIS2FwZWxsZW4xEDAOBgNVBAgMB0Fu
        dHdlcnAxEDAOBgNVBAoMB0V4YW1wbGUxIjAgBgkqhkiG9w0BCQEWE2NlcnRhZG1A
        ZXhhbXBsZS5vcmeCCFIox4In+lSVMA0GCSqGSIb3DQEBCwUAA4IBAQBnC1/kK+xr
        Vjr5Y2YRjyjm4e8I/nTU+RX2p5K+Yth3CqWO3JuDiV/31UMtPl832n2GWSgXG2pP
        B52oeuCP4Re76jqhOmJWY3CKPji+Rs16wj199i9AAcwhSF0rpi5+Fi84HtP3q6pH
        cuzZfIPW44aJ5l4k+QvTLoWzr0XujMFcYzI45i3SJqTMs8xdIP5YLN8JXtQSPw9Z
        8/nBKbPj7WTUC9cj9Cw2bz+wTpdRF4XCsUF3Vpl9fP7SK8yvv0I85LZnWQx1eQlv
        COAM5HWxUT9bWgv18zXdYkc6VLw6ufQSxxuhLMjJxuK27Ny/F18/xYLRTVnse36d
        tPJrseUPmvIK
        -----END CERTIFICATE-----
        """
        )
        slsfile = textwrap.dedent(
            """\
        {%- set ca_key_path = '"""
            + keyfile
            + """' %}
        {%- set ca_crt_path = '"""
            + crtfile
            + """' %}

        certificate.authority::private-key:
          x509.private_key_managed:
            - name: {{ ca_key_path }}
            - backup: True

        certificate.authority::certificate:
          x509.certificate_managed:
            - name: {{ ca_crt_path }}
            - signing_private_key: {{ ca_key_path }}
            - CN: Example Root CA
            - O: Example
            - C: BE
            - ST: Antwerp
            - L: Kapellen
            - Email: certadm@example.org
            - basicConstraints: "critical CA:true"
            - keyUsage: "critical cRLSign, keyCertSign"
            - subjectKeyIdentifier: hash
            - authorityKeyIdentifier: keyid,issuer:always
            - days_valid: 3650
            - days_remaining: 0
            - backup: True
            - require:
              - x509: certificate.authority::private-key
        """
        )
        with salt.utils.files.fopen(
            os.path.join(RUNTIME_VARS.TMP_STATE_TREE, "cert.sls"), "w"
        ) as wfh:
            wfh.write(slsfile)

        # Generate the certificate twice.
        # On the first run, no key nor cert exist.
        ret = self.run_function("state.sls", ["cert"])
        log.debug(
            "First state run ret dictionary:\n%s", pprint.pformat(list(ret.values()))
        )
        for state_run_id, state_run_details in ret.items():
            if state_run_id.endswith("private_key_managed"):
                assert state_run_details["result"]
                assert "new" in state_run_details["changes"]
            if state_run_id.endswith("certificate_managed"):
                assert state_run_details["result"]
                assert "Certificate" in state_run_details["changes"]
                assert "New" in state_run_details["changes"]["Certificate"]
                assert "Status" in state_run_details["changes"]
                assert "New" in state_run_details["changes"]["Status"]
        # On the second run, they exist and should not trigger any modification
        ret = self.run_function("state.sls", ["cert"])
        log.debug(
            "Second state run ret dictionary:\n%s", pprint.pformat(list(ret.values()))
        )
        for state_run_id, state_run_details in ret.items():
            if state_run_id.endswith("private_key_managed"):
                assert state_run_details["result"]
                assert state_run_details["changes"] == {}
            if state_run_id.endswith("certificate_managed"):
                assert state_run_details["result"]
                assert state_run_details["changes"] == {}
        # Now we repleace they key and cert contents with the contents of the above
        # call, but under Py2
        with salt.utils.files.fopen(keyfile, "w") as wfh:
            wfh.write(keyfile_contents)
        with salt.utils.files.fopen(keyfile) as rfh:
            log.debug("Written keyfile, %r, contents:\n%s", keyfile, rfh.read())
        with salt.utils.files.fopen(crtfile, "w") as wfh:
            wfh.write(crtfile_contents)
        with salt.utils.files.fopen(crtfile) as rfh:
            log.debug("Written crtfile, %r, contents:\n%s", crtfile, rfh.read())
        # We should not trigger any modification
        ret = self.run_function("state.sls", ["cert"])
        log.debug(
            "Third state run ret dictionary:\n%s", pprint.pformat(list(ret.values()))
        )
        for state_run_id, state_run_details in ret.items():
            if state_run_id.endswith("private_key_managed"):
                assert state_run_details["result"]
                assert state_run_details["changes"] == {}
            if state_run_id.endswith("certificate_managed"):
                assert state_run_details["result"]
                assert state_run_details["changes"] == {}
