"""
Tests for the x509_v2 module
"""

import base64
import logging
import shutil
from pathlib import Path

import pytest
from saltfactories.utils import random_string

import salt.utils.x509 as x509util

try:
    import cryptography
    import cryptography.x509 as cx509
    from cryptography.hazmat.primitives.serialization import (
        load_der_private_key,
        load_pem_private_key,
        pkcs7,
        pkcs12,
    )

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


@pytest.fixture(scope="module")
def x509_pkidir(tmp_path_factory):
    _x509_pkidir = tmp_path_factory.mktemp("pki")
    try:
        yield _x509_pkidir
    finally:
        shutil.rmtree(str(_x509_pkidir), ignore_errors=True)


@pytest.fixture(scope="module", autouse=True)
def x509_data(
    x509_pkidir,
    rsa_privkey,
    rsa_privkey_enc,
    rsa_pubkey,
    csr,
):
    with pytest.helpers.temp_file("key", rsa_privkey, x509_pkidir):
        with pytest.helpers.temp_file("key_enc", rsa_privkey_enc, x509_pkidir):
            with pytest.helpers.temp_file("key_pub", rsa_pubkey, x509_pkidir):
                with pytest.helpers.temp_file("csr", csr, x509_pkidir):
                    yield x509_pkidir


@pytest.fixture(scope="module")
def x509_salt_master(salt_factories, ca_minion_id, x509_master_config):
    factory = salt_factories.salt_master_daemon(
        "x509-master", defaults=x509_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def ca_minion_id():
    return random_string("x509ca-minion", uppercase=False)


@pytest.fixture(scope="module")
def x509_minion_id():
    return random_string("x509-minion", uppercase=False)


@pytest.fixture(scope="module")
def ca_minion_config(x509_minion_id, ca_cert, ca_key_enc, rsa_privkey, ca_new_cert):
    return {
        "open_mode": True,
        "x509_signing_policies": {
            "testpolicy": {
                "signing_cert": ca_cert,
                "signing_private_key": ca_key_enc,
                "signing_private_key_passphrase": "correct horse battery staple",
                "CN": "from_signing_policy",
                "basicConstraints": "critical, CA:FALSE",
                "keyUsage": "critical, cRLSign, keyCertSign",
                "authorityKeyIdentifier": "keyid:always",
                "subjectKeyIdentifier": "hash",
            },
            "testchangepolicy": {
                "signing_cert": ca_cert,
                "signing_private_key": ca_key_enc,
                "signing_private_key_passphrase": "correct horse battery staple",
                "CN": "from_changed_signing_policy",
                "basicConstraints": "critical, CA:FALSE",
                "keyUsage": "critical, cRLSign, keyCertSign",
                "authorityKeyIdentifier": "keyid:always",
                "subjectKeyIdentifier": "hash",
            },
            "testchangecapolicy": {
                "signing_cert": ca_new_cert,
                "signing_private_key": rsa_privkey,
                "CN": "from_signing_policy",
                "basicConstraints": "critical, CA:FALSE",
                "keyUsage": "critical, cRLSign, keyCertSign",
                "authorityKeyIdentifier": "keyid:always",
                "subjectKeyIdentifier": "hash",
            },
        },
        "features": {
            "x509_v2": True,
        },
    }


@pytest.fixture(scope="module", autouse=True)
def x509ca_salt_minion(x509_salt_master, ca_minion_id, ca_minion_config):
    assert x509_salt_master.is_running()
    factory = x509_salt_master.salt_minion_daemon(
        ca_minion_id,
        defaults=ca_minion_config,
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="module")
def x509_salt_minion(x509_salt_master, x509_minion_id):
    assert x509_salt_master.is_running()
    factory = x509_salt_master.salt_minion_daemon(
        x509_minion_id,
        defaults={
            "open_mode": True,
            "features": {"x509_v2": True},
            "grains": {"testgrain": "foo"},
        },
    )
    with factory.started():
        # Sync All
        salt_call_cli = factory.salt_call_cli()
        ret = salt_call_cli.run("saltutil.sync_all", _timeout=120)
        assert ret.returncode == 0, ret
        yield factory


@pytest.fixture(scope="module")
def x509_master_config(ca_minion_id):
    return {
        "open_mode": True,
        "peer": {
            ".*": [
                "x509.sign_remote_certificate",
            ],
            ca_minion_id: [
                "match.compound",
            ],
        },
    }


@pytest.fixture
def privkey_new(x509_salt_master, tmp_path, ca_minion_id, x509_salt_call_cli):
    state = f"""\
Private key:
  x509.private_key_managed:
    - name: {tmp_path}/priv.key
    - algo: ec
    - backup: true
    - new: true
    {{% if salt['file.file_exists']('{tmp_path}/priv.key') -%}}
    - prereq:
      - x509: {tmp_path}/cert.pem
    {{%- endif %}}

Certificate:
  x509.certificate_managed:
    - name: {tmp_path}/cert.pem
    - ca_server: {ca_minion_id}
    - signing_policy: testpolicy
    - private_key: {tmp_path}/priv.key
    - days_remaining: 999
    - backup: true
    """
    with x509_salt_master.state_tree.base.temp_file("manage_cert.sls", state):
        ret = x509_salt_call_cli.run("state.apply", "manage_cert")
        assert ret.returncode == 0
        assert ret.data[next(iter(ret.data))]["changes"]
        assert (tmp_path / "priv.key").exists()
        assert (tmp_path / "cert.pem").exists()
        yield


@pytest.fixture
def privkey_new_pkcs12(x509_salt_master, tmp_path, ca_minion_id, x509_salt_call_cli):
    state = f"""\
Private key:
  x509.private_key_managed:
    - name: {tmp_path}/cert
    - algo: ec
    - backup: true
    - new: true
    - encoding: pkcs12
    {{% if salt['file.file_exists']('{tmp_path}/priv.key') -%}}
    - prereq:
      - x509: {tmp_path}/cert.pem
    {{%- endif %}}

Certificate:
  x509.certificate_managed:
    - name: {tmp_path}/cert
    - ca_server: {ca_minion_id}
    - signing_policy: testpolicy
    - private_key: {tmp_path}/cert
    - days_remaining: 999
    - backup: true
    - encoding: pkcs12
    """
    with x509_salt_master.state_tree.base.temp_file("manage_cert.sls", state):
        ret = x509_salt_call_cli.run("state.apply", "manage_cert")
        assert ret.returncode == 0
        assert ret.data[next(iter(ret.data))]["changes"]
        assert (tmp_path / "cert").exists()
        yield


@pytest.fixture(scope="module")
def rsa_privkey():
    return """\
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAzIdEbSkbPIc5F/aewNoqWPsF/YP+DByMwvYs+0K+lehc39P8
2fL8K2GIaGMBBzqlsX6CplAzGcoEQEBLTouLm+JYC5e1zRjaml4M+Bid8A7qwdjl
Wd0enCAxVB9BMNnj/mokWzh3hAQMBXfmddGRhH0P9KXfjBNh2V09vfHdtS9XMEEQ
jN6vCxaezXqsOMN3bjRTIcUatH7dVUgUpt9cye1mdbD5KVBgJ9MArc2tJ3rmB0lx
jEbAhTEHrNnIkDOJCKE8TaQOW4RyVWlIvSEL+Ov0TPeXXaef8HJlkyIpKrCZ+c4i
0N7qOlyrJEWTXmKNCj87xgTpY5I7ARISeOQD8QIDAQABAoIBABYNN4l1dyRNiBBX
XMJ6QzqYxgqRYqC3q02R8UOd7KKJDQps9sQg+KNMvsJSelfnMNo0Q63e08OiDldH
F1d+oCzMeKW3U7irR1aBcXCGZvDtCs6frgrEVnqK1ga13/d+ZqCVnRngurIXJZyp
UsW9NK1ONpwwDiwyIsimzvNd0oOoR6ROIN2Fk+AhKQ6bPdgqLM1Swx6BA0J/aaqO
jAqSkYkGOEL970W8ZhnyyDDRcbgPbacUDo7AJnrBeqHoAqrJ1PzJ3jhcWDJl8Xcy
uVDP1hBeK9yg4nuMcArsqrRQvqL2GuafGYygfzrU1aW96hlXciOv32ov36h2qIJU
r4JfJGECgYEA7UPD4iRsHV6eMkD98Ev74ygdnFL2TMknqOUEboPNiQzSzr5oVrKa
KFDhzenUNlMSoeiAaLLI7xaD4xptXuN8xx7sQZVSiEniBfJ7F+9sPNjCXwYbUuWp
qpp6KfCrjLxDxgSKH9FUIlTvL7M4lmAD2yHn4zXjFz3BOs261JUn6l0CgYEA3K2/
S2eP3VUL6K4+HNMzXTj9Q8S7LSYnTZVIjfek6pQHMwaMKE8EC7L4XeS9TZ49BKCS
Mh9RI2yBCX6L1uo2zURAI0oDrowDhjaUCD4xxTD27OyMcvjdSzk/+0E+DtsWdgYm
FGX/l0zTRUsZBbc7ItTG0ksIB+aMM4njBbHubqUCgYAq9llS6pt1Gfv1R5Vz3J5o
vIvYEaGtt8Lpr0aFKHKgPWUysIG+KSsG39ZzbcLSb2pxTONrkewWdvI8vj1NsE2Y
1L2dBofiS9aUkxq888qanflcMYPjF9kIHl6+l2jI3BI9mfbU2hes+8ovzfkSKaKp
HFOb7dcID1Oc7UHGWpfWtQKBgQDC3Y4xOKbaLDJS6iIg9ALETAGgqQUbzjggkzU5
X7e6CLL+xMZZBcUty4Dz8HuVIakCAAR4zByq6jJbvuofAj0YLy9vufjcVfj6uBEp
4jmyxhUVi6BOGiHXPhuYc7koByCjYbSYiKUU5psc8j6LRIysqjVTFzxlNZkSHa1h
pwhDnQKBgATpQou7MeAOMHjMPaNx8OCq7QNhocp8Q+goxPb0ND2jF9xSI+gjzRRt
Kpz+xO6tri6wCgWrmE5cJbEe3/EYf3bmbNA9wOQ72kfoy9uO0cCi+5gSJigwaIKM
DYRTDIS9eg2LF4B64hZvkCLTmP4rLJWdRnWrLosIC4rD1uWgGayC
-----END RSA PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def rsa_privkey_enc():
    return """\
-----BEGIN ENCRYPTED PRIVATE KEY-----
MIIFLTBXBgkqhkiG9w0BBQ0wSjApBgkqhkiG9w0BBQwwHAQIHU2H6hhL0gYCAggA
MAwGCCqGSIb3DQIJBQAwHQYJYIZIAWUDBAEqBBD64PydhZIJPW9amw7M8yGvBIIE
0LHXvvQleCJMlH/Rtml1Vx2nygReVl+1Ag+FjtsNQHtsXYkzVWSDI0zI7nFyDpb9
Kr2+9UOsOhQA5/swka9ude4oJng0YZcV4qgar8yFncWTrMTk/mrvFSNZPz9LMGsq
in7hzYGAP6XdprHgJfw+wDQfwbwcTQp5DUOPYbhxfnggVQBL84gp/2urCcNnFX+T
OKGm9C3NfLycrCbaQxaV/2oTo7+UHUaXKwZwY6zKxCqbwGBy7dNcZD16nJyOBmbj
ytOi/OqBcoj03yK4ETIm7EWwem6CRAbPH1GnUAxmb5tG6jzKphbMJur8n72Vv+VK
9+Gkz5vOq1O1wlK+DfB+Xrgfx3lHHQllxi7FtlQegSFlIbHAacG/muwMRQ5PoMEp
RaGQkxOhiU7VSaZ3Gdx3TrQMaF5nBqvs90Xw40uWdD9+Kd3Oqkj9OgiqHZwgWPfW
txB+jXYGj1ERUvb36T7P8IH/QDa8jwVf3+f1pOpoMe4+6i3rr9bAkDhIjpNDo2a0
YXvVns18UisnLXHxdAZb9R2V/VoTxhs3IqK3nEb5qnb1RAtJfV4p1ENVsoPiHl5C
pq7xcRO+25hy18CjMWqj8t3PH5MdBL8UMFZyDnIH9z9N019U0ZIaD3NqiiRgGD+U
CSLkoXq5oni5RkDQCnzJRFo/Vzmx2P5OJyZvHYLtVOUwsp1dW8JFtdKJoGBxNc1M
kc7eevfwUZEDc2dHxcwxDj0Tas05DaMBib3Oi0D/ipxDdzW+uENQHdCwy7XZf+T+
ig03Ega0/w+c/rdnUevdXK/L1sIO7F8hyDlVG1q0PeoJ8jXnZk+UfNYy820sPWIE
IwtT1aODvnYgio8vgrDXpB0qVDNi2Ml83gYxznIQuxWg6dCrifvCa8TwCTe9tAhv
gTkEkYdyBTpvT585z/1x+dra3uOGiMCN0rP3n3JaICDqCwImznvIP8kqNEnalWQj
pUVI3nKZunTtrL9vAegW9jF0Ipvyf+VSQmw+yN5B35Qfy95CwAwtJ/HPjy1sZmJZ
carKrlqoD4xdSyrIun3fraGTbM+u4S+USRjikce+pu1cHi70Y3xm4JBAZsRJgPwB
G/Orf5yC+E2pCK+7rX3rWINgwmX/kk94EtnYbMeES+lhlKOu/mR09K00atuBEDnJ
o0MCM0BWYy5XQ2RAJLKCdcuJ2aWs/+slKRzlTCWnCUgISng6KFpcyA0aS/8r3ZyH
SKdoSSgOtAieE/TGll0wjvONMIMfoEgR40OBV8BCSF8zWASZBXASTTSlUcu2wQ0q
/wPFS2KkBdBc+qr+TxDNoeFDX+Rh9Nai25O/xoRtCC7afHsd5aQ4yen5C34/jsR1
2kuayvZJ2pgYfIobFdgq9qHi637dVeW8n09XRq6HWhZu1ODO5bGX2oLr64MJAmgi
fA+zu5Dfoe2Q4N1Ja3y0M7Xpfws14jyFxnJ8dR/T6rIJOy1QtHGo3UTai8nSBqCP
RJ766EKBW7j83/53aYyChHvTXEPf4C29iOur72iMAlT2S06K/SH4fFM3brBzz0Fq
EykXIgConLXDwj9+87XKYmOQX/0UP2sxAno6gJakdzExIod+u5koXP1o9vL5zMlH
ahZPgPpP2p2uAz1+9MHpVPo2EIrvibm5T89DznwuaEfe
-----END ENCRYPTED PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def rsa_pubkey():
    return """\
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzIdEbSkbPIc5F/aewNoq
WPsF/YP+DByMwvYs+0K+lehc39P82fL8K2GIaGMBBzqlsX6CplAzGcoEQEBLTouL
m+JYC5e1zRjaml4M+Bid8A7qwdjlWd0enCAxVB9BMNnj/mokWzh3hAQMBXfmddGR
hH0P9KXfjBNh2V09vfHdtS9XMEEQjN6vCxaezXqsOMN3bjRTIcUatH7dVUgUpt9c
ye1mdbD5KVBgJ9MArc2tJ3rmB0lxjEbAhTEHrNnIkDOJCKE8TaQOW4RyVWlIvSEL
+Ov0TPeXXaef8HJlkyIpKrCZ+c4i0N7qOlyrJEWTXmKNCj87xgTpY5I7ARISeOQD
8QIDAQAB
-----END PUBLIC KEY-----"""


@pytest.fixture(scope="module")
def csr():
    return """\
-----BEGIN CERTIFICATE REQUEST-----
MIICRTCCAS0CAQAwADCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMyH
RG0pGzyHORf2nsDaKlj7Bf2D/gwcjML2LPtCvpXoXN/T/Nny/CthiGhjAQc6pbF+
gqZQMxnKBEBAS06Li5viWAuXtc0Y2ppeDPgYnfAO6sHY5VndHpwgMVQfQTDZ4/5q
JFs4d4QEDAV35nXRkYR9D/Sl34wTYdldPb3x3bUvVzBBEIzerwsWns16rDjDd240
UyHFGrR+3VVIFKbfXMntZnWw+SlQYCfTAK3NrSd65gdJcYxGwIUxB6zZyJAziQih
PE2kDluEclVpSL0hC/jr9Ez3l12nn/ByZZMiKSqwmfnOItDe6jpcqyRFk15ijQo/
O8YE6WOSOwESEnjkA/ECAwEAAaAAMA0GCSqGSIb3DQEBCwUAA4IBAQB9PbGDorNt
Tl4xYObUsQwUkMVRPI59MLLYKEJRu/DGSA4sKf/vLK1ypyLIvxNp4gNFgm28nDV2
t2gQ+DpBvwC1+XZQDZjgL7pPtLvErGCs6O6Y5fW8Lywxx5GqiVTIic/XLKTijKJv
EecvwPjWv1VgtBKLZxN18KgIIs2Sq/t+GYe+Lu30c92Lc5INbrwTIEDYNTHywKet
8FTSaYEMU6sGgsrIC5VxNT00EgJHjyjdCVIqQr/LqKyBMqJICWUSPq2ufjwqFsFi
q1HXd62bA8k27ukX7w8qWsk6fOTwPh5F3883L5jVqcRsL9pqb4RUugTh/aReVlKW
0WMDRBksXs1E
-----END CERTIFICATE REQUEST-----"""


@pytest.fixture(scope="module")
def ca_cert():
    # the final newline here is important since it is compared
    # with the ca_server return, which is parsed to contain one
    return """\
-----BEGIN CERTIFICATE-----
MIIDODCCAiCgAwIBAgIIbfpgqP0VGPgwDQYJKoZIhvcNAQELBQAwKzELMAkGA1UE
BhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQwHhcNMjIxMTE1MTQw
NDMzWhcNMzIxMTEyMTQwNDMzWjArMQswCQYDVQQGEwJVUzENMAsGA1UEAwwEVGVz
dDENMAsGA1UECgwEU2FsdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEB
AOGTScvrjcEt6vsJcG9RUp6fKaDNDWZnJET0omanK9ZwaoGpJPp8UDYe/8ADeI7N
10wdyB4oDM9gRDjInBtdQO/PsrmKZF6LzqVFgLMxu2up+PHMi9z6B2P4esIAzMu9
PYxc9zH4HzLImHqscVD2HCabsjp9X134Af7hVY5NN/W/4qTP7uOM20wSG2TPI6+B
tA9VyPbEPMPRzXzrqc45rVYe6kb2bT84GE93Vcu/e5JZ/k2AKD8Hoa2cxLPsTLq5
igl+D+k+dfUtiABiKPvVQiYBsD1fyHDn2m7B6pCgvrGqHjsoAKufgFnXy6PJRg7n
vQfaxSiusM5s+VS+fjlvgwsCAwEAAaNgMF4wDwYDVR0TBAgwBgEB/wIBATALBgNV
HQ8EBAMCAQYwHQYDVR0OBBYEFFzy8fRTKSOe7kBakqO0Ki71potnMB8GA1UdIwQY
MBaAFFzy8fRTKSOe7kBakqO0Ki71potnMA0GCSqGSIb3DQEBCwUAA4IBAQBZS4MP
fXYPoGZ66seM+0eikScZHirbRe8vHxHkujnTBUjQITKm86WeQgeBCD2pobgBGZtt
5YFozM4cERqY7/1BdemUxFvPmMFFznt0TM5w+DfGWVK8un6SYwHnmBbnkWgX4Srm
GsL0HHWxVXkGnFGFk6Sbo3vnN7CpkpQTWFqeQQ5rHOw91pt7KnNZwc6I3ZjrCUHJ
+UmKKrga16a4Q+8FBpYdphQU609npo/0zuaE6FyiJYlW3tG+mlbbNgzY/+eUaxt2
9Bp9mtA+Hkox551Mfpq45Oi+ehwMt0xjZCjuFCM78oiUdHCGO+EmcT7ogiYALiOF
LN1w5sybsYwIw6QN
-----END CERTIFICATE-----
"""


@pytest.fixture(scope="module")
def ca_new_cert():
    return """\
-----BEGIN CERTIFICATE-----
MIIDNDCCAhygAwIBAgIUd9vWUmDYMY7l3hSOwMV4UO36zfMwDQYJKoZIhvcNAQEL
BQAwKzELMAkGA1UEBhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQw
HhcNMjIxMTIxMTUyOTE1WhcNMjIxMjIxMTUyOTE1WjAbMRkwFwYDVQQDDBBTYWx0
IG5ldyB0ZXN0IENBMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzIdE
bSkbPIc5F/aewNoqWPsF/YP+DByMwvYs+0K+lehc39P82fL8K2GIaGMBBzqlsX6C
plAzGcoEQEBLTouLm+JYC5e1zRjaml4M+Bid8A7qwdjlWd0enCAxVB9BMNnj/mok
Wzh3hAQMBXfmddGRhH0P9KXfjBNh2V09vfHdtS9XMEEQjN6vCxaezXqsOMN3bjRT
IcUatH7dVUgUpt9cye1mdbD5KVBgJ9MArc2tJ3rmB0lxjEbAhTEHrNnIkDOJCKE8
TaQOW4RyVWlIvSEL+Ov0TPeXXaef8HJlkyIpKrCZ+c4i0N7qOlyrJEWTXmKNCj87
xgTpY5I7ARISeOQD8QIDAQABo2AwXjAMBgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQE
AwIBBjAdBgNVHQ4EFgQUkLZONoQf6p8T2tLmMuWJG3iSmeQwHwYDVR0jBBgwFoAU
XPLx9FMpI57uQFqSo7QqLvWmi2cwDQYJKoZIhvcNAQELBQADggEBAI3P5XQAWV79
7/8ARx8IW4zhn7MTwBSO7wlViQ9bNF0DFrMspajyUrtLVX1gg4UAhVon3dmHf/eq
wt+oT6YjmDAhR3mWUl1kp/LvE6EQgAnpmoOWe3PjZOiyE11651zO9pMF68FHdsin
TjKXsggEXTllc03VomuXDUvxz2nMh1TIUVdAFH+eDykp5EFqGmXvPEJ7eVUv6v/m
rXM0cUNy6MAjQM49slAxU03yRBD+oBauaVewrg+HKmY9FuzYga46rcQciOxRbPyl
FokHBycPfCXe7QyPLZe9Kqth5BWXdhyyqvKSErUV6glxiShVxX0ciDNziBfU9UCY
TMwH/TREa3g=
-----END CERTIFICATE-----"""


@pytest.fixture(scope="module")
def ca_key():
    return """\
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA4ZNJy+uNwS3q+wlwb1FSnp8poM0NZmckRPSiZqcr1nBqgakk
+nxQNh7/wAN4js3XTB3IHigMz2BEOMicG11A78+yuYpkXovOpUWAszG7a6n48cyL
3PoHY/h6wgDMy709jFz3MfgfMsiYeqxxUPYcJpuyOn1fXfgB/uFVjk039b/ipM/u
44zbTBIbZM8jr4G0D1XI9sQ8w9HNfOupzjmtVh7qRvZtPzgYT3dVy797kln+TYAo
PwehrZzEs+xMurmKCX4P6T519S2IAGIo+9VCJgGwPV/IcOfabsHqkKC+saoeOygA
q5+AWdfLo8lGDue9B9rFKK6wzmz5VL5+OW+DCwIDAQABAoIBAFfImc9hu6iR1gAb
jEXFwAE6r1iEc9KGEPdEvG52X/jzhn8u89UGy7BEIAL5VtE8Caz1agtSSqnpLKNs
blO31q18hnDuCmFAxwpKIeuaTvV3EAoJL+Su6HFfIWaeKRSgcHNPOmOXy4xXw/75
XJ/FJu9fZ9ybLaHEAgLObh0Sr9RSPQbZ72ZawPP8+5WCbR+2w90RApHXQL0piSbW
lIx1NE6o5wQb3vik8z/k5FqLCY2a8++WNyfvS+WWFY5WXGI7ZiDDQk46gnslquH2
Lon5CEn3JlTGQFhxaaa2ivssscf2lA2Rvm2E8o1rdZJS2OpSE0ai4TXY9XnyjZj1
5usWIwECgYEA+3Mwu03A7PyLEBksS/u3MSo/176S9lF/uXcecQNdhAIalUZ8AgV3
7HP2yI9ZC0ekA809ZzFjGFostXm9VfUOEZ549jLOMzvBtCdaI0aBUE8icu52fX4r
fT2NY6hYgz5/fxD8sq1XH/fqNNexABwtViH6YAly/9A1/8M3BOWt72UCgYEA5ag8
sIfiBUoWd1sS6qHDuugWlpx4ZWYC/59XEJyCN2wioP8qFji/aNZxF1wLfyQe/zaa
YBFusjsBnSfBU1p4UKCRHWQ9/CnC0DzqTkyKC4Fv8GuxgywNm5W9gPKk7idHP7mw
e+7Uvf1pOQccqEPh7yltpW+Xw27gfsC2DMAIGa8CgYByv/q5P56PiCCeVB6W/mR3
l2RTPLEsn7y+EtJdmL+QgrVG8kedVImJ6tHwbRqhvyvmYD9pXGxwrJZCqy/wjkjB
WaSyFjVrxBV99Yd5Ga/hyntaH+ELHA0UtoZTuHvMSTU9866ei+R6vlSvkM9B0ZoO
+KqeMTG99HLwKVJudbKO0QKBgQCd33U49XBOqoufKSBr4yAmUH2Ws6GgMuxExUiY
xr5NUyzK+B36gLA0ZZYAtOnCURZt4x9kgxdRtnZ5jma74ilrY7XeOpbRzfN6KyX3
BW6wUh6da6rvvUztc5Z+Gk9+18mG6SOFTr04jgfTiCwPD/s06YnSfFAbrRDukZOU
WD45SQKBgBvjSwl3AbPoJnRjZjGuCUMKQKrLm30xCeorxasu+di/4YV5Yd8VUjaO
mYyqXW6bQndKLuXT+AXtCd/Xt2sI96z8mc0G5fImDUxQjMUuS3RyQK357cEOu8Zy
HdI7Pfaf/l0HozAw/Al+LXbpmSBdfmz0U/EGAKRqXMW5+vQ7XHXD
-----END RSA PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def ca_key_enc():
    return """\
-----BEGIN ENCRYPTED PRIVATE KEY-----
MIIFLTBXBgkqhkiG9w0BBQ0wSjApBgkqhkiG9w0BBQwwHAQIy/O+FhcKBKUCAggA
MAwGCCqGSIb3DQIJBQAwHQYJYIZIAWUDBAEqBBDtSfZzKh7brkHFw/s6bcbVBIIE
0JcLyycDhdSPzL7Zm1+ZLavjxiuaGEaHU8hu8ZScqyjcdWbdOfOuqZgu7OzxwfIc
8Q1bfqMGUfxPcs/JQh13CVOaDYmafeMZYN3rqsNoci11iaHDhTAqgYCM2iVXaFUt
6ZdfW+/hEk+yHwK5K2R1/ks8buAe0OgjkV0N3DqAif93BPyFP6XT7btVMrorGJjh
1OJjuw3q0xJ02rn7O5imaZ5NnCIDShkKwWO6sUew3QHhW61/nuCBPyJTsAO0L4+t
9zjb2jOIIuvTpZUhAty6I+bKgaYLhsii7z5jVYpt+NbYpzIe+9RvAD1psGk9+bGD
rN70Bnhx29mPEKdmozXVQ8GTqDOSQSYMr9aax+BhSJoTnCtVtGGX0LXE5Dvd/HHy
+Yw2HFrVglptsPYo4EBKccC3FJlS0mL6yBW5NCpU7MOhDV/iOMbzM4bqwKG+jqaw
sjIScCg+ljBxGhNrcMa0AEBWukTRe4gERpb8AyGKYOSVN6iZyP5qhN/Abu1asKrj
c4NRUu3yILleZuxjkDd4w0CwhjlCaKFLsp1XeFE5ZHM5Iezi1/I4QMXFTydB1KnX
xOSofZ7b7pnvOiBQG2nQzYSjSnBO7E7NQOhjvkRgcxNsdAQWADIqdE3bKZ8qcEZ6
q1TE0XtcDgwFGwQF/cyuEEXyMAkQV687e8IdCjc+MbyyqUtQA9382JyjOuzavvMD
nO5s80lB5aa0WHdE+Rg7KiBIwL1CjBSGSiggKvkG01ObeQL4DCQG6gHgz+nvdiNe
du2u6hW2/PUuUIOM2ApE98T2TAzCnyu02iMIN5aH4za5y1w5YzaU4Lsl4nzAEA3c
8EuVIWMutZnqT4ZSCLCq1AtDYkSXxIjGQPwhRslyCJuwtuiaDXLIZIpMRGqMKdGS
c3q0k5ba92jXppIOVYN/kViNjYeHVZ3KRAi2MqUByqiMBkZo11NsgaU/uPsKsK16
D0XueVs9EobU55tgBV71Q8g/5BiGG19W5UZVzjiiuGuj44msOfYV4027KqqFf302
U5RXAwBko9S+v3SuTZrRXK4uuYceR9Uyco8aP/tNAhHEGa8Z73vLngZICp57qD1h
8smjOrm1volZpu31HP9CWVh47GyuzSZ8BUFrR/uXfa+uqyLqeBKglz5SC6Ak3nL8
eAHu3EK2dVp4vqwYB2oO9DQqs4CN7DKyArNeUzKSf6ZKEYBZCdF5V5HgbSpY5f+e
xj5cpuMVc7s+Nxv/0bqxNzt8ghe2sDELxK8lo7Q6E+aUNBWt++nHI2b8y5ynaANU
kQjeoorrPHUScXN8TVrgrIYIfXOqkI14UmroRH5/oyORHXN25JekV1DisKZOtSdV
Vqt3o/hlGFYhaeznIgquBm27trLkLHOfCGx6M2xlKszlWBP03zFLp0PiXE+y07zC
IwzaiVlj/O+QIsiMmrtc8WXYiNWVN5XDe1elFPs1K2cw0cIeyLgC1Bibxa7dH01G
Z0Nr+hZN+/EqI3Tu+lWeWtj/lIhjJrKQvUOMM4W1MFZZdK09ZsCdW0Y1fFYn/3Xz
g1KvGcFoszp0uMptlJUhsxtFooG4xKtgEITmtraRU+hTGU3NZgtk7Qff4tFa0O0h
A62orBDc+8x+AehfwYSm11dz5/P6aL3QZf+tzr05vbVn
-----END ENCRYPTED PRIVATE KEY-----"""


@pytest.fixture
def cert_args(ca_minion_id, tmp_path, x509_data):
    return {
        "name": str(tmp_path / "cert_managed"),
        "ca_server": ca_minion_id,
        "signing_policy": "testpolicy",
        "private_key": str(x509_data / "key"),
        "CA": "from_args",
    }


@pytest.fixture
def cert_args_exts():
    return {
        "basicConstraints": "critical, CA:TRUE, pathlen:1",
        "keyUsage": "critical, cRLSign, keyCertSign, digitalSignature",
        "extendedKeyUsage": "OCSPSigning",
        "subjectKeyIdentifier": "hash",
        "authorityKeyIdentifier": "keyid:always",
        "issuerAltName": "DNS:mysalt.ca",
        "authorityInfoAccess": "OCSP;URI:http://ocsp.salt.ca/",
        "subjectAltName": "DNS:me.salt.ca",
        "crlDistributionPoints": None,
        "certificatePolicies": "1.2.4.5",
        "policyConstraints": "requireExplicitPolicy:3",
        "inhibitAnyPolicy": 2,
        "nameConstraints": "permitted;IP:192.168.0.0/255.255.0.0,excluded;email:.com",
        "noCheck": True,
        "tlsfeature": "status_request",
    }


@pytest.fixture(params=[{}])
def existing_cert(x509_salt_call_cli, cert_args, ca_key, rsa_privkey, request):
    cert_args.update(request.param)
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)
    yield cert_args["name"]


@pytest.fixture(scope="module")
def x509_salt_run_cli(x509_salt_master):
    return x509_salt_master.salt_run_cli()


@pytest.fixture(scope="module")
def x509_salt_call_cli(x509_salt_minion):
    return x509_salt_minion.salt_call_cli()


def test_certificate_managed_remote(
    x509_salt_call_cli, cert_args, ca_key, rsa_privkey, x509_data
):
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes(
    x509_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_policy_change(
    x509_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangepolicy"
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert "subject_name" in ret.data[next(iter(ret.data))]["changes"]
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_changed_signing_policy"


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_ca_cert_change(
    x509_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangecapolicy"
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert "signing_private_key" in changes
    assert "issuer_name" in changes
    assert "extensions" in changes
    assert "authorityKeyIdentifier" in changes["extensions"]["changed"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes_signing_policy_override(
    x509_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["basicConstraints"] = "critical, CA:TRUE, pathlen:3"
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_renew(x509_salt_call_cli, cert_args):
    cert_cur = _get_cert(cert_args["name"])
    cert_args["days_remaining"] = 999
    ret = x509_salt_call_cli.run(
        "state.single", "x509.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial_number != cert_cur.serial_number


@pytest.mark.usefixtures("privkey_new")
def test_privkey_new_with_prereq(x509_salt_call_cli, tmp_path):
    cert_cur = _get_cert(tmp_path / "cert.pem")
    pk_cur = _get_privkey(tmp_path / "priv.key")
    assert _belongs_to(cert_cur, pk_cur)

    ret = x509_salt_call_cli.run("state.apply", "manage_cert")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]
    cert_new = _get_cert(tmp_path / "cert.pem")
    pk_new = _get_privkey(tmp_path / "priv.key")
    assert _belongs_to(cert_new, pk_new)
    assert not _belongs_to(cert_new, pk_cur)


@pytest.mark.usefixtures("privkey_new_pkcs12")
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 36,
    reason="Complete PKCS12 deserialization requires cryptography v36+",
)
def test_privkey_new_with_prereq_pkcs12(x509_salt_call_cli, tmp_path):
    cert_cur = _get_cert(tmp_path / "cert", encoding="pkcs12").cert.certificate
    pk_cur = _get_privkey(tmp_path / "cert", encoding="pkcs12")
    assert _belongs_to(cert_cur, pk_cur)

    ret = x509_salt_call_cli.run("state.apply", "manage_cert")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]
    cert_new = _get_cert(tmp_path / "cert", encoding="pkcs12").cert.certificate
    pk_new = _get_privkey(tmp_path / "cert", encoding="pkcs12")
    assert _belongs_to(cert_new, pk_new)
    assert not _belongs_to(cert_new, pk_cur)


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, cx509.Certificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, x509util.load_privkey(privkey))


def _signed_by(cert, privkey):
    return x509util.verify_signature(cert, x509util.load_privkey(privkey).public_key())


def _get_cert(cert, encoding="pem", passphrase=None):
    try:
        p = Path(cert)
        if p.exists():
            cert = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass

    if encoding == "pem":
        if not isinstance(cert, bytes):
            cert = cert.encode()
        return cx509.load_pem_x509_certificate(cert)
    if encoding == "der":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        return cx509.load_der_x509_certificate(cert)
    if encoding == "pkcs7_pem":
        if not isinstance(cert, bytes):
            cert = cert.encode()
        return pkcs7.load_pem_pkcs7_certificates(cert)
    if encoding == "pkcs7_der":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        return pkcs7.load_der_pkcs7_certificates(cert)
    if encoding == "pkcs12":
        if not isinstance(cert, bytes):
            cert = base64.b64decode(cert)
        if passphrase is not None and not isinstance(passphrase, bytes):
            passphrase = passphrase.encode()
        return pkcs12.load_pkcs12(cert, passphrase)


def _get_privkey(pk, encoding="pem", passphrase=None):
    try:
        p = Path(pk)
        if p.exists():
            pk = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass
    if passphrase is not None:
        passphrase = passphrase.encode()

    if encoding == "pem":
        if not isinstance(pk, bytes):
            pk = pk.encode()
        return load_pem_private_key(pk, passphrase)
    if encoding == "der":
        if not isinstance(pk, bytes):
            pk = base64.b64decode(pk)
        return load_der_private_key(pk, passphrase)
    if encoding == "pkcs12":
        if not isinstance(pk, bytes):
            pk = base64.b64decode(pk)
        return pkcs12.load_pkcs12(pk, passphrase).key
    raise ValueError("Need correct encoding")
