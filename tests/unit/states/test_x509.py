import tempfile

import pytest

import salt.utils.files
from salt.modules import x509 as x509_mod
from salt.states import x509
from tests.support.helpers import dedent
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock
from tests.support.unit import TestCase

try:
    import M2Crypto  # pylint: disable=unused-import

    HAS_M2CRYPTO = True
except ImportError:
    HAS_M2CRYPTO = False


class X509TestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        return {x509: {"__opts__": {"fips_mode": False}}}

    def test_certificate_info_matches(self):
        cert_info = {"MD5 Finger Print": ""}
        required_info = {"MD5 Finger Print": ""}
        ret = x509._certificate_info_matches(cert_info, required_info)
        assert ret == (True, [])


class X509FipsTestCase(TestCase, LoaderModuleMockMixin):
    def setup_loader_modules(self):
        self.file_managed_mock = MagicMock()
        self.file_managed_mock.return_value = {"changes": True}

        return {
            x509: {
                "__opts__": {"fips_mode": True},
                "__salt__": {
                    "x509.get_pem_entry": x509_mod.get_pem_entry,
                    "x509.get_private_key_size": x509_mod.get_private_key_size,
                },
                "__states__": {"file.managed": self.file_managed_mock},
            }
        }

    @pytest.mark.skipif(
        not HAS_M2CRYPTO, reason="Skipping, reason=M2Crypto is unavailable"
    )
    def test_private_key_fips_mode(self):
        """
        :return:
        """
        test_key = dedent(
            """
        -----BEGIN PRIVATE KEY-----
        MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDx7UUt0cPi5G51
        FmRBhAZtZb5x6P0PFn7GwnLmSvLNhCsOcD/vq/yBUU62pknzmOjM5pgWTACZj66O
        GOFmWBg06v8+sqUbaF9PZ/CxQD5MogmQhYNgfyuopHWWgLXMub2hlP+15qGohkzg
        Tr/mXp2ohVAb6ihjqb7XV9MiZaLNVX+XWauM8SlhqXMiJyDUopEGbg2pLsHhIMcX
        1twLlyDja+uDbCMZ4jDNB+wsWxTaPRH8KizfEabB1Cl+fdyD10pSAYcodOAnlkW+
        G/DX2hwb/ZAM9B1SXTfZ3gzaIIbqXBEHcZQNXxHL7szBTVcOmfx/RPfOeRncytb9
        Mit7RIBxAgMBAAECggEAD4Pi+uRIBsYVm2a7OURpURzEUPPbPtt3d/HCgqht1+ZR
        CJUEVK+X+wcm4Cnb9kZpL7LeMBfhtfdz/2LzGagurT4g7nlwg0h3TFVjJ0ryc+G0
        cVNOsKKXPzKE5AkPH7kNw04V9Cl9Vpx+U6hZQEHzJHqgP5oNyw540cCtJriT700b
        fG1q3PYKWSkDwTiUnJTnVLybFIKQC6urxTeT2UWeiBadfDY7DjI4USfrQsqCfGMO
        uWPpOOJk5RIvw5r0Of2xvxV76xCgzVTkgtWjBRMTEkfeYx3019xKlQtAKoGbZd1T
        tF8DH0cDlnri4nG7YT8yYvx/LWVDg12E6IZij1X60QKBgQD7062JuQGEmTd99a7o
        5TcgWYqDrmE9AEgJZjN+gnEPcsxc50HJaTQgrkV0oKrS8CMbStIymbzMKWifOj7o
        gvQBVecydq1AaXePt3gRe8vBFiP4cHjFcSegs9FDvdfJR36iHOBIgEp4DWvV1vgs
        +z82LT6Qy5kxUQvnlQ4dEaGdrQKBgQD175f0H4enRJ3BoWTrqt2mTAwtJcPsKmGD
        9YfFB3H4+O2rEKP4FpBO5PFXZ0dqm54hDtxqyC/lSXorFCUjVUBero1ECGt6Gnn2
        TSnhgk0VMxvhnc0GReIt4K9WrXGd0CMUDwIhFHj8kbb1X1yqt2hwyw7b10xFVStl
        sGv8CQB+VQKBgAF9q1VZZwzl61Ivli2CzeS/IvbMnX7C9ao4lK13EDxLLbKPG/CZ
        UtmurnKWUOyWx15t/viVuGxtAlWO/rhZriAj5g6CbVwoQ7DyIR/ZX8dw3h2mbNCe
        buGgruh7wz9J0RIcoadMOySiz7SgZS++/QzRD8HDstB77loco8zAQfixAoGBALDO
        FbTocfKbjrpkmBQg24YxR9OxQb/n3AEtI/VO2+38r4h6xxaUyhwd1S9bzWjkBXOI
        poeR8XTqNQ0BR422PTeUT3SohPPcUu/yG3jG3zmta47wjjPDS85lqEgtGvA0cPN7
        srErcatJ6nlOnGUSw9/K65y6lFeH2lIZ2hfwNM2dAoGBAMVCc7i3AIhLp6UrGzjP
        0ioCHCakpxfl8s1VQp55lhHlP6Y4RfqT72Zq7ScteTrisIAQyI9ot0gsuct2miQM
        nyDdyKGki/MPduGTzzWlBA7GZEHnxbAILH8kWJ7eE/Nh7zdF1CRts8utEO9L9S+0
        lVz1j/xGOseQk4cVos681Wpw
        -----END PRIVATE KEY-----"""
        )
        test_cert = dedent(
            """
        -----BEGIN CERTIFICATE-----
        MIIDazCCAlOgAwIBAgIUAfATs1aodKw11Varh55msmU0LoowDQYJKoZIhvcNAQEL
        BQAwRTELMAkGA1UEBhMCQVUxEzARBgNVBAgMClNvbWUtU3RhdGUxITAfBgNVBAoM
        GEludGVybmV0IFdpZGdpdHMgUHR5IEx0ZDAeFw0yMTAzMjMwMTM4MzdaFw0yMjAz
        MjMwMTM4MzdaMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEw
        HwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwggEiMA0GCSqGSIb3DQEB
        AQUAA4IBDwAwggEKAoIBAQDx7UUt0cPi5G51FmRBhAZtZb5x6P0PFn7GwnLmSvLN
        hCsOcD/vq/yBUU62pknzmOjM5pgWTACZj66OGOFmWBg06v8+sqUbaF9PZ/CxQD5M
        ogmQhYNgfyuopHWWgLXMub2hlP+15qGohkzgTr/mXp2ohVAb6ihjqb7XV9MiZaLN
        VX+XWauM8SlhqXMiJyDUopEGbg2pLsHhIMcX1twLlyDja+uDbCMZ4jDNB+wsWxTa
        PRH8KizfEabB1Cl+fdyD10pSAYcodOAnlkW+G/DX2hwb/ZAM9B1SXTfZ3gzaIIbq
        XBEHcZQNXxHL7szBTVcOmfx/RPfOeRncytb9Mit7RIBxAgMBAAGjUzBRMB0GA1Ud
        DgQWBBT0qx4KLhozvuWAI9peT/utYV9FITAfBgNVHSMEGDAWgBT0qx4KLhozvuWA
        I9peT/utYV9FITAPBgNVHRMBAf8EBTADAQH/MA0GCSqGSIb3DQEBCwUAA4IBAQDx
        tWvUyGfEwJJg1ViBa10nVhg5sEc6KfqcPzc2GvatIGJlAbc3b1AYu6677X04SQNA
        dYRA2jcZcKudy6eolPJow6SDpkt66IqciZYdbQE5h9elnwpZxmXlJTQTB9cEwyIk
        2em5DKpdIwa9rRDlbAjAVJb3015MtpKRu2gsQ7gl5X2U3K+DFsWtBPf+0xiJqUiq
        rd7tiHF/zylubSyH/LVONJZ6+/oT/qzJfxfpvygtQWcu4b2zzME/FPenMA8W6Rau
        ZYycQfpMVc7KwqF5/wfjnkmfxoFKnkD7WQ3qFCJ/xULk/Yn1hrvNeIr+khX3qKQi
        Y3BMA5m+J+PZrNy7EQSa
        -----END CERTIFICATE-----
        """
        )
        fp, name = tempfile.mkstemp()
        with salt.utils.files.fopen(name, "w") as fd:
            fd.write(test_key)
            fd.write(test_cert)
        ret = x509.private_key_managed(name)
        self.file_managed_mock.assert_called_once()
        assert (
            self.file_managed_mock.call_args.kwargs["contents"].strip()
            == test_key.strip()
        )

    def test_certificate_info_matches(self):
        cert_info = {"MD5 Finger Print": ""}
        required_info = {"MD5 Finger Print": ""}
        ret = x509._certificate_info_matches(cert_info, required_info)
        assert ret == (False, ["MD5 Finger Print"])
