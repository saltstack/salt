# tests/pytests/unit/states/test_pem.py

from datetime import datetime

import pytest

import salt.states.pem as pem
from tests.support.mock import MagicMock, mock_open, patch

GOOD_CERT = """
    -----BEGIN CERTIFICATE-----
    MIIG6zCCBdOgAwIBAgIQD5enH9rVhbYSQrtpPBDjsDANBgkqhkiG9w0BAQsFADBZ
    MQswCQYDVQQGEwJVUzEVMBMGA1UEChMMRGlnaUNlcnQgSW5jMTMwMQYDVQQDEypE
    aWdpQ2VydCBHbG9iYWwgRzIgVExTIFJTQSBTSEEyNTYgMjAyMCBDQTEwHhcNMjMx
    MDA2MDAwMDAwWhcNMjQxMTA1MjM1OTU5WjBsMQswCQYDVQQGEwJVUzEVMBMGA1UE
    CBMMUGVubnN5bHZhbmlhMQ4wDAYDVQQHEwVQYW9saTEbMBkGA1UEChMSRHVjayBE
    dWNrIEdvLCBJbmMuMRkwFwYDVQQDDBAqLmR1Y2tkdWNrZ28uY29tMIIBIjANBgkq
    hkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtqZKa5gE0IO5367vb9MGypqNzDdicz3y
    RAF938TbQMUA0ZCyEbAFnngUkJYLR+YmSazWHKt0kW9c2SOsu230E/YQtsdzayYu
    dlHnwOuXVBeFzUCFSICMNhrRW5gw4kIh9Lw3PS8RBxafzvO4gRcTtk+odRxElH+I
    BcXF4DA22mKdkA9p8Nh7HYBpsuRKniyjiUVTDC2u1uNJ3YRcWsug3Dkq/M7tw57o
    dp59JNpIWOybtTfwppTrUyQGOqMzW+zt/uJYRk2ZB1Hd98hIBAqy8Q7EkEGw/V1f
    CRpM+byhYgq/otBMd9XAGP9zpHD3F4qiYCQOyK+RKd1iMNXs1+CtowIDAQABo4ID
    mjCCA5YwHwYDVR0jBBgwFoAUdIWAwGbH3zfez70pN6oDHb7tzRcwHQYDVR0OBBYE
    FIaIVeEXZBu4TesZG6lpf+zmOty9MCsGA1UdEQQkMCKCECouZHVja2R1Y2tnby5j
    b22CDmR1Y2tkdWNrZ28uY29tMD4GA1UdIAQ3MDUwMwYGZ4EMAQICMCkwJwYIKwYB
    BQUHAgEWG2h0dHA6Ly93d3cuZGlnaWNlcnQuY29tL0NQUzAOBgNVHQ8BAf8EBAMC
    BaAwHQYDVR0lBBYwFAYIKwYBBQUHAwEGCCsGAQUFBwMCMIGfBgNVHR8EgZcwgZQw
    SKBGoESGQmh0dHA6Ly9jcmwzLmRpZ2ljZXJ0LmNvbS9EaWdpQ2VydEdsb2JhbEcy
    VExTUlNBU0hBMjU2MjAyMENBMS0xLmNybDBIoEagRIZCaHR0cDovL2NybDQuZGln
    aWNlcnQuY29tL0RpZ2lDZXJ0R2xvYmFsRzJUTFNSU0FTSEEyNTYyMDIwQ0ExLTEu
    Y3JsMIGHBggrBgEFBQcBAQR7MHkwJAYIKwYBBQUHMAGGGGh0dHA6Ly9vY3NwLmRp
    Z2ljZXJ0LmNvbTBRBggrBgEFBQcwAoZFaHR0cDovL2NhY2VydHMuZGlnaWNlcnQu
    Y29tL0RpZ2lDZXJ0R2xvYmFsRzJUTFNSU0FTSEEyNTYyMDIwQ0ExLTEuY3J0MAwG
    A1UdEwEB/wQCMAAwggF8BgorBgEEAdZ5AgQCBIIBbASCAWgBZgB1AO7N0GTV2xrO
    xVy3nbTNE6Iyh0Z8vOzew1FIWUZxH7WbAAABiwRZRLwAAAQDAEYwRAIgQSl6sqy2
    uIt1vG+7EHKLkToASFvYY5NV9Np8runSdAYCIBQ0qDazjm9FwrGunk8C9rEaw3QV
    +hb8juCsd90A+9DXAHUASLDja9qmRzQP5WoC+p0w6xxSActW3SyB2bu/qznYhHMA
    AAGLBFlEbwAABAMARjBEAiANubHLJUmCBphlEmTf4PR5TYBHnNLDTDGTEKsXDF+N
    LQIgNwPp1iM7kwUT8g+nxkrPyNhNh/kQVmrfuMrBaLxwr3UAdgDatr9rP7W2Ip+b
    wrtca+hwkXFsu1GEhTS9pD0wSNf7qwAAAYsEWURZAAAEAwBHMEUCIGE1BSUI8i/1
    apqkN6hdrlvo0le3RYCu36BLbb9qqzn8AiEAkib0gR04diUH4Rta1EY2nyrXoTxZ
    XuaT9SL5tW5aw+YwDQYJKoZIhvcNAQELBQADggEBADLm6XLJ1/uPtSDFB0rtHYVK
    tKjSYqmjP2m/7xUFsc05qxmd7xBuD17wArDRZSMfnfSb4ZL1kyMmGHtUmaPLUEh1
    r9jioPvdHI09afqhLSzbGCaP9bN9hCz++m0vKVT1jyo91NuDfubYjF5IYwFpCanw
    ccNUo9RHaJ78Umd697/4z5lIgNTy/EUoyOMLM77JNoYnRsgZwYuy/OmsZDLagyEy
    YX4VHgyZ0mbjZ3wLhxLaR7bpXm3xaXhkT+aYhxAz41VLnTbrrd8tWndpUBZxZIOo
    QzrWHN1s5ktSh2ThhyA4d3hanaxrohNFFWPqpk0WX1PZwJeNPAL8P8d8B6VPzMs=
    -----END CERTIFICATE-----
"""

BAD_CERT = """
    -----BEGIN CERTIFICATE-----
    MIICEjCCAXsCAg36MA0GCSqGSIb3DQEBBQUAMIGbMQswCQYDVQQGEwJKUDEOMAwG
    A1UECBMFVG9reW8xEDAOBgNVBAcTB0NodW8ta3UxETAPBgNVBAoTCEZyYW5rNERE
    MRgwFgYDVQQLEw9XZWJDZXJ0IFN1cHBvcnQxGDAWBgNVBAMTD0ZyYW5rNEREIFdl
    YiBDQTEjMCEGCSqGSIb3DQEJARYUc3VwcG9ydEBmcmFuazRkZC5jb20wHhcNMTIw
    ODIyMDUyNjU0WhcNMTcwODIxMDUyNjU0WjBKMQswCQYDVQQGEwJKUDEOMAwGA1UE
    CAwFVG9reW8xETAPBgNVBAoMCEZyYW5rNEREMRgwFgYDVQQDDA93d3cuZXhhbXBs
    ZS5jb20wXDANBgkqhkiG9w0BAQEFAANLADBIAkEAm/xmkHmEQrurE/0re/jeFRLl
    8ZPjBop7uLHhnia7lQG/5zDtZIUC3RVpqDSwBuw/NTweGyuP+o8AG98HxqxTBwID
    AQABMA0GCSqGSIb3DQEBBQUAA4GBABS2TLuBeTPmcaTaUW/LCB2NYOy8GMdzR1mx
    8iBIu2H6/E2tiY3RIevV2OW61qY2/XRQg7YPxx3ffeUugX9F4J/iPnnu1zAxxyBy
    2VguKv4SWjRFoRkIfIlHX0qVviMhSlNy2ioFLy7JcPZb+v3ftDGywUqcBiVDoea0
    Hn+GmxZA
    -----END CERTIFICATE-----
"""


@pytest.fixture
def configure_loader_modules():
    return {
        pem: {
            "__opts__": {"test": False},
            "__salt__": {},
            "__states__": {
                "file.managed": MagicMock(
                    return_value={"result": True, "changes": {}, "comment": ""}
                )
            },
        }
    }


def test_managed():
    """
    Test pem.managed state
    """
    name = "/tmp/example.crt"
    source = "salt://example.crt"
    user = "root"
    group = "root"
    mode = "0600"

    # Mock cp.get_file_str to return local tmp file
    with patch.dict(
        pem.__salt__,
        {"cp.get_file_str": MagicMock(return_value=GOOD_CERT)},
    ):

        # Local existing cert was not found
        with patch(
            "salt.utils.files.fopen", MagicMock(side_effect=FileNotFoundError())
        ):
            ret = pem.managed(
                name=name, source=source, user=user, group=group, mode=mode
            )
            assert ret["result"] is True
            assert (
                ret["comment"]
                == "New cert info:\n+ Subject: CN=*.duckduckgo.com,O=Duck Duck Go\\, Inc.,L=Paoli,ST=Pennsylvania,C=US\n+ Not valid after: 2024-11-05 23:59:59\n"
            )

        # Test mode
        with patch.dict(pem.__opts__, {"test": True}), patch(
            "salt.utils.files.fopen", mock_open(read_data=BAD_CERT.encode())
        ):
            ret = pem.managed(
                name=name, source=source, user=user, group=group, mode=mode
            )
            assert ret["result"] is False
            assert (
                ret["comment"]
                == "Certificates CN does not match (skip with pillar='{skip_conditions: True}')\n"
            )
            assert ret["changes"] == {}


def test_managed_with_templating_and_cp_get_file_str():
    """
    Test pem.managed state with templating and cp.get_file_str
    """
    name = "/tmp/example.crt"
    source = "salt://example.crt"
    user = "root"
    group = "root"
    mode = "0600"
    template = "jinja"

    # Mock cp.get_file_str to return the good certificate
    with patch.dict(
        pem.__salt__, {"cp.get_file_str": MagicMock(return_value=GOOD_CERT)}
    ), patch.dict(
        pem.__salt__,
        {"file.apply_template_on_contents": MagicMock(return_value=GOOD_CERT)},
    ), patch(
        "salt.utils.files.fopen", mock_open(read_data=GOOD_CERT.encode())
    ):

        # Call the managed function with the template argument
        ret = pem.managed(
            name=name,
            source=source,
            user=user,
            group=group,
            mode=mode,
            template=template,
        )

        # Assertions to ensure the template was applied and cp.get_file_str was called
        pem.__salt__["file.apply_template_on_contents"].assert_called_with(
            GOOD_CERT,
            template=template,
            context=None,
            defaults=None,
            saltenv="base",
        )
        pem.__salt__["cp.get_file_str"].assert_called_with(path=source, saltenv="base")

        # Check the result
        assert ret["result"] is True
        assert "Certificates are the same:" in ret["comment"]
        assert ret["changes"] == {}


def test_managed_failed_conditions():
    """
    Test failure conditions in pem.managed state
    """

    name = "/tmp/example.crt"
    source = "salt://example.crt"
    user = "root"
    group = "root"
    mode = "0600"

    existing_cert = MagicMock()
    existing_cert.subject.rfc4514_string.return_value = "CN=existing.com"
    # existing_cert.not_valid_after.isoformat.return_value = "2023-01-01T00:00:00"
    existing_cert.not_valid_after = datetime(2023, 1, 1)
    new_cert = MagicMock()
    new_cert.subject.rfc4514_string.return_value = "CN=new.com"
    # new_cert.not_valid_after.isoformat.return_value = "2022-01-01T00:00:00"
    new_cert.not_valid_after = datetime(2022, 1, 1)

    with patch.dict(
        pem.__salt__,
        {"cp.get_file_str": MagicMock(return_value=new_cert)},
    ), patch("salt.utils.files.fopen", MagicMock()), patch(
        "cryptography.x509.load_pem_x509_certificate",
        MagicMock(side_effect=[new_cert, existing_cert]),
    ):
        ret = pem.managed(name=name, source=source, user=user, group=group, mode=mode)
        assert ret["result"] is False
        assert "New certificate expires sooner than existing one" in ret["comment"]
        assert "Certificates CN does not match" in ret["comment"]
        assert ret["changes"] == {}

    # Skip coditions
    with patch.dict(
        pem.__salt__,
        {"cp.get_file_str": MagicMock(return_value=new_cert)},
    ), patch("salt.utils.files.fopen", MagicMock()), patch(
        "cryptography.x509.load_pem_x509_certificate",
        MagicMock(side_effect=[new_cert, existing_cert]),
    ):
        ret = pem.managed(
            name=name,
            source=source,
            user=user,
            group=group,
            mode=mode,
            skip_conditions=True,
        )
        assert ret["result"] is True
        assert ret["changes"] == {}
