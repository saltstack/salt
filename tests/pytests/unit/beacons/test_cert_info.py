# Python libs

import logging

import pytest

# Salt libs
import salt.beacons.cert_info as cert_info
from tests.support.mock import mock_open, patch

log = logging.getLogger(__name__)


_TEST_CERT = """
-----BEGIN CERTIFICATE-----
MIIC/jCCAeagAwIBAgIJAIQMfu6ShHvfMA0GCSqGSIb3DQEBCwUAMCQxIjAgBgNV
BAMMGXNhbHR0ZXN0LTAxLmV4YW1wbGUubG9jYWwwHhcNMTkwNjAzMjA1OTIyWhcN
MjkwNTMxMjA1OTIyWjAkMSIwIAYDVQQDDBlzYWx0dGVzdC0wMS5leGFtcGxlLmxv
Y2FsMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAv5UxxKGsOO8n2hUk
KjL8r2Rjt0om4wwdXUu0R1fQUlaSO0g+vk0wHHaovoVcEU6uZlhDPw1qZ4C+cp9Z
rDzSfwI2Njg813I5jzTBgox+3pJ+82vgXZ14xpqZ+f0ACMo4uRPjBkyQpHqYiDJ3
VockZSxm5s7RT05xDnedDfPgu1WAvzQovWO6slCs+Hlp8sh6QAy/hIwOZ0hT8y3J
NV6PSPqK7BEypOPak36+ogtiuPxxat4da74SUVS8Ffupnr40BjqVqEXBvfIIHiQt
3r5gpjoBjrWX2ccgQlHQP8gFaToFxWLSSYVT6E8Oj5UEywpmvPDRjJsJ5epscblT
oFyVXQIDAQABozMwMTAJBgNVHRMEAjAAMCQGA1UdEQQdMBuCGXNhbHR0ZXN0LTAx
LmV4YW1wbGUubG9jYWwwDQYJKoZIhvcNAQELBQADggEBABPqQlkaZDV5dPwNO/s2
PBT/19LroOwQ+fBJgZpbGha5/ZaSr+jcYZf2jAicPajWGlY/rXAdBSuxpmUYCC12
23tI4stwGyB8Quuoyg2Z+5LQJSDA1LxNJ1kxQfDUnS3tVQa0wJVtq8W9wNryNONL
noaQaDcdbGx3V15W+Bx0as5NfIWqz1uVi4MGGxI6hMBuDD7E7M+k1db8EaS+tI4u
seZBENjwjJA6zZmTXvYyzV5OBP4JyOhYuG9aqr7e6/yjPBEtZv0TJ9KMMbcywvE9
9FF+l4Y+wgKR/icrpDEpPlC4wYn64sy5vk7EGVagnVyhkjLJ52rn4trzyPox8FmO
2Zw=
-----END CERTIFICATE-----
"""


@pytest.fixture
def configure_loader_modules():
    return {cert_info: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = cert_info.validate(config)

    assert ret == (False, "Configuration for cert_info beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = cert_info.validate(config)

    assert ret == (
        False,
        "Configuration for cert_info beacon must contain files option.",
    )


def test_cert_information():
    with patch("salt.utils.files.fopen", mock_open(read_data=_TEST_CERT)):
        config = [{"files": ["/etc/pki/tls/certs/mycert.pem"], "notify_days": -1}]

        ret = cert_info.validate(config)

        assert ret == (True, "Valid beacon configuration")

        _expected_return = [
            {
                "certificates": [
                    {
                        "cert_path": "/etc/pki/tls/certs/mycert.pem",
                        "extensions": [
                            {
                                "ext_data": "CA:FALSE",
                                "ext_name": "basicConstraints",
                            },
                            {
                                "ext_data": "DNS:salttest-01.example.local",
                                "ext_name": "subjectAltName",
                            },
                        ],
                        "has_expired": False,
                        "issuer": 'CN="salttest-01.example.local"',
                        "issuer_dict": {"CN": "salttest-01.example.local"},
                        "notAfter": "2029-05-31 20:59:22Z",
                        "notAfter_raw": "20290531205922Z",
                        "notBefore": "2019-06-03 20:59:22Z",
                        "notBefore_raw": "20190603205922Z",
                        "serial_number": 9515119675852487647,
                        "signature_algorithm": "sha256WithRSAEncryption",
                        "subject": 'CN="salttest-01.example.local"',
                        "subject_dict": {"CN": "salttest-01.example.local"},
                        "version": 2,
                    }
                ]
            }
        ]
        ret = cert_info.beacon(config)
        assert ret == _expected_return
