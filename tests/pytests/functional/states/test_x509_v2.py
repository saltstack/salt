import base64
from pathlib import Path

import pytest

try:
    import cryptography
    import cryptography.x509 as cx509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa
    from cryptography.hazmat.primitives.serialization import (
        load_der_private_key,
        load_pem_private_key,
        pkcs7,
        pkcs12,
    )

    import salt.utils.x509 as x509util

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {
        "x509_signing_policies": {
            "testpolicy": {
                "CN": "from_signing_policy",
                "basicConstraints": "critical, CA:FALSE",
                "keyUsage": "critical, cRLSign, keyCertSign",
                "authorityKeyIdentifier": "keyid:always",
                "subjectKeyIdentifier": "hash",
            },
            "testsubjectstrpolicy": {
                "subject": "CN=from_signing_policy",
            },
            "testnosubjectpolicy": {
                "CN": "from_signing_policy",
            },
        },
        "features": {
            "x509_v2": True,
        },
    }


@pytest.fixture
def x509(loaders, states, tmp_path):
    yield states.x509


@pytest.fixture
def ca_cert():
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


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
def csr_invalid_version():
    return """\
-----BEGIN CERTIFICATE REQUEST-----
MIICVjCCAT4CAQIwADCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAM5+
0OS8+xIy2I475qlgxEqqSP28BncqlRG1d1VjB4Xc22K+QHS2ipeFM6NRlO2OytYy
qMMgqU1lKU7sJXxw/uXfNMP40G3t5hrI8O/KtVbIYwujVkswgEMg4bZvmOSjyqte
BbOH4baQK+7P8LN8Ceaja6d5QAWKBvKSD8f8X1khZP8Lw0rUJjOFWi+XIrEsyd8d
gern7Qw6ATdFvLs7aY5p2AliUhp1zlqkBJqNcqpLQZubVlg8w1ABfzwFRvTslGio
SCoCA0MJ0QyThgHjJIqpvZGVdrD4ZQP4rXZHMv8Qzquolpou0n984oCk8t3qyaR+
WmJIdcPtmMYr8Y6YGKcCAwEAAaARMA8GCSqGSIb3DQEJDjECMAAwDQYJKoZIhvcN
AQELBQADggEBAEwUc47pXGCNLmZSKAhDu4FbrVyW+PrdWGYKBI+onycy7wCqDP9c
vQ4lGeuG3t074drgKvm9fIDUdTZLqDDXD2kOAW+7AYbRYxUvTxMiDyrsqyH+N590
S+SucVJzEZTVNqrWLMn4JwOuXf4onuAxtFLOY+dSGbpU6CiFbaXk6qDDsankqn0Y
TsAWx3PqeU2w9CT3a68rW214Avn1aMP+aCMHZ7QQpnTnRKXVZscOjiY6MT9Yb8Nv
BldjvVnQN7bCjM2TQTMSbd00lD+071hLm6ceDQdoewbipNKyhBnQd4hFYJgDPQR7
1OVnGCilmno3MkKW4yztBX2gI2ifXSaunmY=
-----END CERTIFICATE REQUEST-----"""


@pytest.fixture
def ec_privkey():
    return """\
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg1lRdFUUOd7WZsydR
eMzFLD5u1Bjxg+NPia6Vznhb4EehRANCAAS+5meGSwViKrRQ3Ni1cfa08WG5dK/u
ldlNqU8U1Lz3ckCGI3TdGZ6nPaL3IT/UNH6C+J86RWSLY18hFHXoeKBD
-----END PRIVATE KEY-----"""


@pytest.fixture
def ec_pubkey():
    return """\
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvuZnhksFYiq0UNzYtXH2tPFhuXSv
7pXZTalPFNS893JAhiN03Rmepz2i9yE/1DR+gvifOkVki2NfIRR16HigQw==
-----END PUBLIC KEY-----"""


@pytest.fixture
def ed25519_privkey():
    return """\
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIFKFjPIOBze2eo9x/EiCL0ni5GacaKIRZdfREBfuEdE9
-----END PRIVATE KEY-----"""


@pytest.fixture
def ed25519_pubkey():
    return """\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAK+1yspaj/3Mb2K7H6y2d0Y+udSF+7sBozMY4aKUBR0I=
-----END PUBLIC KEY-----"""


@pytest.fixture
def ed448_privkey():
    return """\
-----BEGIN PRIVATE KEY-----
MEcCAQAwBQYDK2VxBDsEObnZH0tXF86wbuvvz9Blg9MjUIkyW+Cpz6n4WmaFHIT4
Y2QKHSRG0M1ZUFr/EYH9F9mTgnAwmyp7oA==
-----END PRIVATE KEY-----"""


@pytest.fixture
def ed448_pubkey():
    return """\
-----BEGIN PUBLIC KEY-----
MEMwBQYDK2VxAzoAiIWDcsK9mSaXUL+67ZIdyik8T5Zf0sLEwq3aUf6eysYxjEoZ
vHv0+Ke3LRlEzGbwroKtP66opn4A
-----END PUBLIC KEY-----"""


@pytest.fixture
def cert_exts():
    return """
-----BEGIN CERTIFICATE-----
MIIEQDCCAyigAwIBAgIUDPVBmE6XZ0e15hwi1lQrVrO0/W8wDQYJKoZIhvcNAQEL
BQAwKzELMAkGA1UEBhMCVVMxDTALBgNVBAMMBFRlc3QxDTALBgNVBAoMBFNhbHQw
HhcNMjIxMTE1MTc1MzQwWhcNMjIxMjE1MTc1MzQwWjAAMIIBIjANBgkqhkiG9w0B
AQEFAAOCAQ8AMIIBCgKCAQEAzIdEbSkbPIc5F/aewNoqWPsF/YP+DByMwvYs+0K+
lehc39P82fL8K2GIaGMBBzqlsX6CplAzGcoEQEBLTouLm+JYC5e1zRjaml4M+Bid
8A7qwdjlWd0enCAxVB9BMNnj/mokWzh3hAQMBXfmddGRhH0P9KXfjBNh2V09vfHd
tS9XMEEQjN6vCxaezXqsOMN3bjRTIcUatH7dVUgUpt9cye1mdbD5KVBgJ9MArc2t
J3rmB0lxjEbAhTEHrNnIkDOJCKE8TaQOW4RyVWlIvSEL+Ov0TPeXXaef8HJlkyIp
KrCZ+c4i0N7qOlyrJEWTXmKNCj87xgTpY5I7ARISeOQD8QIDAQABo4IBhTCCAYEw
EgYDVR0TAQH/BAgwBgEB/wIBATAOBgNVHQ8BAf8EBAMCAQYwEwYDVR0lBAwwCgYI
KwYBBQUHAwkwHQYDVR0OBBYEFJC2TjaEH+qfE9rS5jLliRt4kpnkMB8GA1UdIwQY
MBaAFFzy8fRTKSOe7kBakqO0Ki71potnMBIGA1UdEgQLMAmCB3NhbHQuY2EwMAYI
KwYBBQUHAQEEJDAiMCAGCCsGAQUFBzABhhRodHRwOi8vb2NzcC5zYWx0LmNhLzAj
BgNVHREEHDAaggtzdWIuc2FsdC5jYYELc3ViQHNhbHQuY2EwKAYDVR0fBCEwHzAd
oBugGYYXaHR0cDovL3NhbHQuY2EvbXljYS5jcmwwEAYDVR0gBAkwBzAFBgMqBAUw
DAYDVR0kBAUwA4ABAzAKBgNVHTYEAwIBAjAhBgNVHR4EGjAYoAwwCocIwKgAAP//
AAChCDAGgQQuY29tMA8GCSsGAQUFBzABBQQCBQAwEQYIKwYBBQUHARgEBTADAgEF
MA0GCSqGSIb3DQEBCwUAA4IBAQDAw8RirQU2WcDCKGPHHu7yZsrA08Fw/6P0OwLT
hapKKXEdFcB8jflwEAQiZVge84xEYgdo/LgepRjOnkIc82Vlr3cy+F3A2c2JOwDU
qf+A7rqJpwLZDHK1v4x9Boh3/JOiwOcyw2LugyQQhvKRqFhVjMAnX+cM3mSm2xn5
paiBCooGdTl4l66JsTET56oXSsJ5FJ6XKPy86f/MY2n1LRSIQcvKGCP6vF5z7PDr
sM09tkOYmSGN0coP6Y6PFS92zBnW6wXrzfNe0jvJMfVXJUbne5U0SQCY3mwkIuzB
IiC+2Um3mhImnIoeRxH/cXTABsOrSE+QzIv7Z3orIUxyMqtm
-----END CERTIFICATE-----"""


@pytest.fixture
def csr_exts():
    return """\
-----BEGIN CERTIFICATE REQUEST-----
MIIDvjCCAqYCAQAwADCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMyH
RG0pGzyHORf2nsDaKlj7Bf2D/gwcjML2LPtCvpXoXN/T/Nny/CthiGhjAQc6pbF+
gqZQMxnKBEBAS06Li5viWAuXtc0Y2ppeDPgYnfAO6sHY5VndHpwgMVQfQTDZ4/5q
JFs4d4QEDAV35nXRkYR9D/Sl34wTYdldPb3x3bUvVzBBEIzerwsWns16rDjDd240
UyHFGrR+3VVIFKbfXMntZnWw+SlQYCfTAK3NrSd65gdJcYxGwIUxB6zZyJAziQih
PE2kDluEclVpSL0hC/jr9Ez3l12nn/ByZZMiKSqwmfnOItDe6jpcqyRFk15ijQo/
O8YE6WOSOwESEnjkA/ECAwEAAaCCAXcwggFzBgkqhkiG9w0BCQ4xggFkMIIBYDAS
BgNVHRMBAf8ECDAGAQH/AgEBMA4GA1UdDwEB/wQEAwIBBjATBgNVHSUEDDAKBggr
BgEFBQcDCTAdBgNVHQ4EFgQUkLZONoQf6p8T2tLmMuWJG3iSmeQwEgYDVR0SBAsw
CYIHc2FsdC5jYTAwBggrBgEFBQcBAQQkMCIwIAYIKwYBBQUHMAGGFGh0dHA6Ly9v
Y3NwLnNhbHQuY2EvMCMGA1UdEQQcMBqCC3N1Yi5zYWx0LmNhgQtzdWJAc2FsdC5j
YTAoBgNVHR8EITAfMB2gG6AZhhdodHRwOi8vc2FsdC5jYS9teWNhLmNybDAQBgNV
HSAECTAHMAUGAyoEBTAMBgNVHSQEBTADgAEDMAoGA1UdNgQDAgECMCEGA1UdHgQa
MBigDDAKhwjAqAAA//8AAKEIMAaBBC5jb20wDwYJKwYBBQUHMAEFBAIFADARBggr
BgEFBQcBGAQFMAMCAQUwDQYJKoZIhvcNAQELBQADggEBAINICpHFaJaxDfABkbwV
b3Ji/djatf5dc2jB/A/qP18+M97xIpvJPi/xGTR+sMqffsXLGuZgrhmmkhrbYqIf
CHi9VPpZ7l0sB/mESJ5+//50J5tRN6I+7UCc3MWTs45HM8/alJQQAKX8Fdx6cZnI
2lz6raNyT4DUo/eympAtSjJRNnhT62YEiIR+9+Vu4aMjsnRLgLbtOGUraOoyC9do
eY6fyUlpNgz8ny7Ow6nV/J5FNaZfEt/79X+kjHdPkqz7r2A1PEI/Uu+Gksoyizvs
qFrpUgv3nrP7olcq8rKYbwI9bXj3LMQpWtUZ300Sy2+dzwjoBneJ9VmkaD2U6Njd
O68=
-----END CERTIFICATE REQUEST-----"""


@pytest.fixture
def cert_args(tmp_path, ca_cert, ca_key):
    return {
        "name": f"{tmp_path}/cert",
        "signing_private_key": ca_key,
        "signing_cert": ca_cert,
        "CN": "success",
    }


@pytest.fixture
def cert_args_exts():
    return {
        "basicConstraints": "critical, CA:TRUE, pathlen:1",
        "keyUsage": "critical, cRLSign, keyCertSign",
        "extendedKeyUsage": "OCSPSigning",
        "subjectKeyIdentifier": "hash",
        "authorityKeyIdentifier": "keyid:always",
        "issuerAltName": "DNS:salt.ca",
        "authorityInfoAccess": "OCSP;URI:http://ocsp.salt.ca/",
        "subjectAltName": "DNS:sub.salt.ca,email:sub@salt.ca",
        "crlDistributionPoints": "URI:http://salt.ca/myca.crl",
        "certificatePolicies": "1.2.4.5",
        "policyConstraints": "requireExplicitPolicy:3",
        "inhibitAnyPolicy": 2,
        "nameConstraints": "permitted;IP:192.168.0.0/255.255.0.0,excluded;email:.com",
        "noCheck": True,
        "tlsfeature": "status_request",
    }


@pytest.fixture
def crl_args(tmp_path, ca_cert, ca_key):
    return {
        "name": f"{tmp_path}/crl",
        "signing_private_key": ca_key,
        "signing_cert": ca_cert,
        "revoked": [],
    }


@pytest.fixture
def crl_args_exts():
    return {
        "authorityKeyIdentifier": "keyid:always",
        "issuerAltName": "DNS:salt.ca",
        "issuingDistributionPoint": {
            "critical": True,
            "fullname": [
                "URI:http://salt.ca/myca.crl",
            ],
        },
        "cRLNumber": 1,
    }


@pytest.fixture
def crl_revoked():
    return [
        {
            "serial_number": "01337A",
            "extensions": {
                "CRLReason": "unspecified",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "01337B",
            "extensions": {
                "CRLReason": "keyCompromise",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "01337C",
            "extensions": {
                "CRLReason": "cACompromise",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "01337D",
            "extensions": {
                "CRLReason": "affiliationChanged",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "01337E",
            "extensions": {
                "CRLReason": "superseded",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "01337F",
            "extensions": {
                "CRLReason": "cessationOfOperation",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "013380",
            "extensions": {
                "CRLReason": "certificateHold",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "013381",
            "extensions": {
                "CRLReason": "privilegeWithdrawn",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "013382",
            "extensions": {
                "CRLReason": "aACompromise",
                "invalidityDate": "2022-11-18 13:37:00",
            },
        },
        {
            "serial_number": "013383",
            "extensions": {
                "CRLReason": "removeFromCRL",
            },
        },
    ]


@pytest.fixture
def csr_args(tmp_path, rsa_privkey):
    return {
        "name": f"{tmp_path}/csr",
        "private_key": rsa_privkey,
        "CN": "success",
    }


@pytest.fixture
def csr_args_exts():
    return {
        "basicConstraints": "critical, CA:TRUE, pathlen:1",
        "keyUsage": "critical, cRLSign, keyCertSign",
        "extendedKeyUsage": "OCSPSigning",
        "subjectKeyIdentifier": "hash",
        "subjectAltName": "DNS:sub.salt.ca,email:sub@salt.ca",
        "certificatePolicies": "1.2.4.5",
        "policyConstraints": "requireExplicitPolicy:3",
        "inhibitAnyPolicy": 2,
        "nameConstraints": "permitted;IP:192.168.0.0/255.255.0.0,excluded;email:.com",
        "noCheck": True,
        "tlsfeature": "status_request",
    }


@pytest.fixture
def pk_args(tmp_path):
    return {
        "name": f"{tmp_path}/private_key",
    }


@pytest.fixture(params=["1234"])
def existing_file(tmp_path, request):
    text = request.param
    if callable(text):
        text = request.getfixturevalue(text.__name__)
    test_file = tmp_path / "cert"
    test_file.write_text(text)
    yield test_file
    # cleanup is done by tmp_path


@pytest.fixture(params=[{}])
def existing_cert(x509, cert_args, ca_key, rsa_privkey, request):
    cert_args["private_key"] = rsa_privkey
    cert_args.update(request.param)
    ret = x509.certificate_managed(**cert_args)
    subject = cert_args.get("subject", "CN={}".format(cert_args.get("CN")))
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        encoding=cert_args.get("encoding", "pem"),
        passphrase=cert_args.get("pkcs12_passphrase"),
        subject=subject
        if "signing_policy" not in cert_args
        else "CN=from_signing_policy",
    )
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_cert_chain(x509, cert_args, ca_key, rsa_privkey, ca_cert, request):
    cert_args["private_key"] = rsa_privkey
    cert_args.update(request.param)
    cert_args["append_certs"] = ca_cert
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        encoding=cert_args.get("encoding", "pem"),
        passphrase=cert_args.get("pkcs12_passphrase"),
    )
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_cert_exts(x509, cert_args, cert_args_exts, ca_key, rsa_privkey, request):
    cert_args["private_key"] = rsa_privkey
    cert_args.update(cert_args_exts)
    cert_args.update(request.param)
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        encoding=cert_args.get("encoding", "pem"),
        passphrase=cert_args.get("pkcs12_passphrase"),
    )
    assert len(cert.extensions) == len(cert_args_exts)
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_cert_csr_exts(x509, cert_args, rsa_privkey, ca_key, csr_exts, request):
    cert_args["csr"] = csr_exts
    cert_args.update(request.param)
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        encoding=cert_args.get("encoding", "pem"),
        passphrase=cert_args.get("pkcs12_passphrase"),
    )
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_crl(x509, crl_args, ca_key, request):
    crl_args.update(request.param)
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key, encoding=crl_args.get("encoding", "pem"))
    assert len(crl) == len(crl_args["revoked"])
    yield crl_args["name"]


@pytest.fixture(params=[{}])
def existing_crl_exts(x509, crl_args, crl_args_exts, ca_key, request):
    crl_args["extensions"] = crl_args_exts
    crl_args.update(request.param)
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key, encoding=crl_args.get("encoding", "pem"))
    assert len(crl) == len(crl_args["revoked"])
    assert len(crl.extensions) == len(crl_args_exts)
    yield crl_args["name"]


@pytest.fixture(params=[{}])
def existing_crl_rev(x509, crl_args, crl_revoked, ca_key, request):
    crl_args["revoked"] = crl_revoked
    crl_args.update(request.param)
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key, encoding=crl_args.get("encoding", "pem"))
    assert len(crl) == len(crl_args["revoked"])
    yield crl_args["name"]


@pytest.fixture(params=[{}])
def existing_csr(x509, csr_args, rsa_privkey, request):
    csr_args.update(request.param)
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(
        ret,
        rsa_privkey,
        encoding=csr_args.get("encoding", "pem"),
        passphrase=csr_args.get("private_key_passphrase"),
    )
    yield csr_args["name"]


@pytest.fixture(params=[{}])
def existing_csr_exts(x509, csr_args, csr_args_exts, ca_key, rsa_privkey, request):
    csr_args.update(csr_args_exts)
    csr_args.update(request.param)
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(
        ret,
        rsa_privkey,
        encoding=csr_args.get("encoding", "pem"),
        passphrase=csr_args.get("private_key_passphrase"),
    )
    assert len(csr.extensions) == len(csr_args_exts)
    yield csr_args["name"]


@pytest.fixture(params=[{}])
def existing_pk(x509, pk_args, request):
    pk_args.update(request.param)
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(
        ret,
        pk_args.get("algo", "rsa"),
        encoding=pk_args.get("encoding", "pem"),
        passphrase=pk_args.get("passphrase"),
    )
    yield pk_args["name"]


@pytest.fixture(params=["existing_cert"])
def existing_symlink(request):
    existing = request.getfixturevalue(request.param)
    test_file = Path(existing).with_name("symlink")
    test_file.symlink_to(existing)
    yield test_file
    # cleanup is done by tmp_path


def test_certificate_managed_self_signed(x509, cert_args, ca_key):
    cert_args.pop("signing_cert")
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], ca_key, ca_key)


def test_certificate_managed_self_signed_enc(x509, cert_args, ca_key, ca_key_enc):
    cert_args.pop("signing_cert")
    cert_args["signing_private_key"] = ca_key_enc
    cert_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], ca_key, ca_key)


def test_certificate_managed_with_privkey(x509, cert_args, rsa_privkey, ca_key):
    cert_args["private_key"] = rsa_privkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


@pytest.mark.parametrize(
    "encoding",
    [
        "pem",
        "der",
        pytest.param(
            "pkcs7_pem",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            "pkcs7_der",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            "pkcs12",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
    ],
)
def test_certificate_managed_with_privkey_encodings(
    x509, cert_args, rsa_privkey, ca_key, encoding
):
    cert_args["private_key"] = rsa_privkey
    cert_args["encoding"] = encoding
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret, cert_args["name"], rsa_privkey, ca_key, encoding=encoding
    )


def test_certificate_managed_with_privkey_enc(
    x509, cert_args, rsa_privkey_enc, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey_enc
    cert_args["private_key_passphrase"] = "hunter2"
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


def test_certificate_managed_with_privkey_ca_enc(
    x509, cert_args, rsa_privkey, ca_key, ca_key_enc
):
    cert_args["private_key"] = rsa_privkey
    cert_args["signing_private_key"] = ca_key_enc
    cert_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


def test_certificate_managed_with_privkey_enc_ca_enc(
    x509, cert_args, rsa_privkey, rsa_privkey_enc, ca_key, ca_key_enc
):
    cert_args["private_key"] = rsa_privkey_enc
    cert_args["private_key_passphrase"] = "hunter2"
    cert_args["signing_private_key"] = ca_key_enc
    cert_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


def test_certificate_managed_with_pubkey(
    x509, cert_args, rsa_privkey, rsa_pubkey, ca_key
):
    cert_args["public_key"] = rsa_pubkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


def test_certificate_managed_with_csr(x509, cert_args, csr, rsa_privkey, ca_key):
    cert_args["csr"] = csr
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


def test_certificate_managed_with_extensions(
    x509, cert_args, cert_args_exts, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey
    cert_args.update(cert_args_exts)
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert len(cert.extensions) == len(cert_args_exts)


def test_certificate_managed_with_signing_policy(x509, cert_args, rsa_privkey, ca_key):
    cert_args.pop("subject", None)
    cert_args["CN"] = "from_call"
    cert_args["private_key"] = rsa_privkey
    cert_args["signing_policy"] = "testpolicy"
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("created")
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=from_signing_policy"
    assert _belongs_to(cert, rsa_privkey)
    assert _signed_by(cert, ca_key)


def test_certificate_managed_with_distinguished_name_kwargs(
    x509, cert_args, rsa_privkey, ca_key
):
    cert_args.pop("subject", None)
    cert_args["private_key"] = rsa_privkey
    dn_defs = {
        "C": "US",
        "CN": "salt.test",
        "L": "Some Town",
        "ST": "Some State",
        "O": "SaltStack",
        "OU": "SaltStack Test",
    }
    cert_args.update(dn_defs)
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("created") == cert_args["name"]
    cert = _get_cert(cert_args["name"])
    assert (
        cert.subject.rfc4514_string()
        == "CN=salt.test,OU=SaltStack Test,O=SaltStack,L=Some Town,ST=Some State,C=US"
    )
    assert _belongs_to(cert, rsa_privkey)
    assert _signed_by(cert, ca_key)


def test_certificate_managed_without_subject(x509, cert_args, rsa_privkey, ca_key):
    cert_args.pop("subject", None)
    cert_args.pop("CN", None)
    cert_args["private_key"] = rsa_privkey
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("created") == cert_args["name"]
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == ""
    assert _belongs_to(cert, rsa_privkey)
    assert _signed_by(cert, ca_key)


def test_certificate_managed_test_true(x509, cert_args, rsa_privkey, ca_key):
    cert_args["private_key"] = rsa_privkey
    cert_args["test"] = True
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is None
    assert ret.changes
    assert not Path(cert_args["name"]).exists()


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_existing(x509, cert_args):
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert_exts")
def test_certificate_managed_existing_with_exts(x509, cert_args):
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert_csr_exts")
def test_certificate_managed_existing_from_csr(x509, cert_args):
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"signing_policy": "testpolicy", "CN": "from_call"}],
    indirect=True,
)
def test_certificate_managed_existing_with_signing_policy(x509, cert_args):
    """
    Ensure signing policies are taken into account when checking for changes
    """
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"signing_policy": "testsubjectstrpolicy"}],
    indirect=True,
)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 37,
    reason="Parsing of RFC4514 strings requires cryptography >= 37",
)
def test_certificate_managed_with_signing_policy_override_no_changes(x509, cert_args):
    cert_args["CN"] = "from_call"
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"signing_policy": "testnosubjectpolicy"}],
    indirect=True,
)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 37,
    reason="Parsing of RFC4514 strings requires cryptography >= 37",
)
def test_certificate_managed_with_signing_policy_no_subject_override_no_changes(
    x509, cert_args
):
    cert_args["subject"] = "CN=from_call"
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert_chain")
@pytest.mark.parametrize(
    "existing_cert_chain",
    [
        {"encoding": "pem"},
        pytest.param(
            {"encoding": "pkcs12"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
        pytest.param(
            {"encoding": "pkcs7_pem"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            {"encoding": "pkcs7_der"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
    ],
    indirect=True,
)
def test_certificate_managed_existing_chain(x509, cert_args):
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [
        {"encoding": "pkcs12"},
        {"encoding": "pkcs12", "pkcs12_friendlyname": "littlefinger"},
        {"encoding": "pkcs12", "pkcs12_passphrase": "p4ssw0rd"},
    ],
    indirect=True,
)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 36,
    reason="PKCS12 serialization requires cryptography v36+",
)
def test_certificate_managed_existing_pkcs12(x509, cert_args):
    """
    Ensure PKCS12 encoding does not lead to reissued certificates in other ways.
    pkcs12_compat is not checked currently
    """
    ret = x509.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_file")
def test_certificate_managed_existing_not_a_cert(x509, cert_args, rsa_privkey, ca_key):
    """
    If `name` is not a valid certificate, a new one should be issued at the path
    """
    cert_args["private_key"] = rsa_privkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("days,expected", [(1, False), (9999, True)])
def test_certificate_managed_days_remaining(x509, cert_args, days, expected):
    """
    The certificate should be reissued if days_remaining indicates it
    """
    cert_args["days_remaining"] = days
    ret = x509.certificate_managed(**cert_args)
    assert bool(ret.changes) is expected


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("days", [1, 9999])
def test_certificate_managed_days_valid_does_not_override_days_remaining(
    x509, cert_args, days
):
    """
    The certificate should only be renewed when days_remaining indicates it,
    not when not_before/not_after change
    """
    cert_args["days_valid"] = days
    ret = x509.certificate_managed(**cert_args)
    assert not ret.changes


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_privkey_change(x509, cert_args, ec_privkey, ca_key):
    cert_args["private_key"] = ec_privkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], ec_privkey, ca_key)
    assert ret.changes["private_key"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_pubkey_change(
    x509, cert_args, ec_pubkey, ec_privkey, ca_key
):
    cert_args.pop("private_key")
    cert_args["public_key"] = ec_pubkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], ec_privkey, ca_key)
    assert ret.changes["private_key"]


@pytest.mark.usefixtures("existing_cert_csr_exts")
def test_certificate_managed_csr_change(x509, cert_args, csr, rsa_privkey, ca_key):
    cert_args.pop("private_key", None)
    cert_args.pop("public_key", None)
    cert_args["csr"] = csr
    current = _get_cert(cert_args["name"])
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert len(ret.changes["extensions"]["removed"]) == len(current.extensions)


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_digest_change(x509, cert_args, rsa_privkey, ca_key):
    cert_args["digest"] = "sha512"
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert ret.changes["digest"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_signing_cert_change(
    x509, cert_args, rsa_privkey, cert_exts
):
    cert_args["signing_cert"] = cert_exts
    cert_args["signing_private_key"] = rsa_privkey
    cert_args["private_key"] = rsa_privkey
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, rsa_privkey)
    assert set(ret.changes) == {"signing_private_key", "issuer_name"}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_subject_change(x509, cert_args, rsa_privkey, ca_key):
    cert_args["CN"] = "renewed"
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert list(ret.changes) == ["subject_name"]
    assert cert.subject.rfc4514_string() == "CN=renewed"


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_serial_number_change(x509, cert_args, rsa_privkey, ca_key):
    cert_args["serial_number"] = 42
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert list(ret.changes) == ["serial_number"]
    assert cert.serial_number == 42


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "encoding",
    [
        "der",
        pytest.param(
            "pkcs7_pem",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            "pkcs7_der",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            "pkcs12",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
    ],
)
def test_certificate_managed_encoding_change(
    x509, cert_args, rsa_privkey, ca_key, encoding
):
    """
    Ensure that a change in encoding does not reissue the certificate
    """
    cert_args["encoding"] = encoding
    cert_args.pop("serial_number", None)
    cert = _get_cert(cert_args["name"])
    ret = x509.certificate_managed(**cert_args)
    cert_new = _assert_cert_basic(
        ret, cert_args["name"], rsa_privkey, ca_key, encoding=encoding
    )
    assert cert_new.serial_number == cert.serial_number


@pytest.mark.usefixtures("existing_cert_chain")
@pytest.mark.parametrize(
    "existing_cert_chain",
    [
        {"encoding": "pem"},
        pytest.param(
            {"encoding": "pkcs12"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
        pytest.param(
            {"encoding": "pkcs7_pem"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
        pytest.param(
            {"encoding": "pkcs7_der"},
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 37,
                reason="PKCS7 serialization requires cryptography v37+",
            ),
        ),
    ],
    indirect=True,
)
def test_certificate_managed_chain_change(
    x509, cert_args, ca_cert, ca_key, cert_exts, rsa_privkey
):
    """
    Ensure that a change in embedded extra certificates is picked up and
    does not reissue the certificate
    """
    cert = _get_cert(cert_args["name"], encoding=cert_args["encoding"])
    cert_args["append_certs"] = [cert_exts]
    ret = x509.certificate_managed(**cert_args)
    assert ret.result
    assert ret.changes
    assert list(ret.changes) == ["additional_certs"]
    cert_new = _assert_cert_basic(
        ret, cert_args["name"], rsa_privkey, ca_key, cert_args["encoding"]
    )
    if cert_args["encoding"].startswith("pkcs7"):
        cert = cert[0]
    elif cert_args["encoding"] == "pkcs12":
        if CRYPTOGRAPHY_VERSION[0] == 36:
            # it seems (serial number) parsing of pkcs12 certificates is broken (?) in that release
            return
        cert = cert.cert.certificate
    assert cert_new.serial_number == cert.serial_number


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_additional_certs_change(
    x509, cert_args, rsa_privkey, ca_key, ca_cert
):
    """
    Ensure that appending a certificate is picked up and does not reissue the certificate
    """
    cert_args["append_certs"] = ca_cert
    cert = _get_cert(cert_args["name"])
    ret = x509.certificate_managed(**cert_args)
    cert_new = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert cert_new.serial_number == cert.serial_number


def test_certificate_managed_wrong_ca_key(
    x509, cert_args, ca_cert, ec_privkey, rsa_privkey
):
    cert_args["private_key"] = ec_privkey
    cert_args["signing_private_key"] = rsa_privkey
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is False
    assert not ret.changes
    assert "Signing private key does not match the certificate" in ret.comment


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    ({"encoding": "pkcs12", "pkcs12_friendlyname": "foo"},),
    indirect=True,
)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 36,
    reason="PKCS12 serialization requires cryptography v36+",
)
def test_pkcs12_friendlyname_change(x509, cert_args, ca_cert, ca_key, rsa_privkey):
    cert_args["pkcs12_friendlyname"] = "bar"
    cert = _get_cert(cert_args["name"], encoding="pkcs12")
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key, encoding="pkcs12")
    cert_new = _get_cert(cert_args["name"], encoding="pkcs12")
    assert (
        cert_new.cert.certificate.serial_number == cert.cert.certificate.serial_number
    )
    assert cert_new.cert.friendly_name == b"bar"


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_extension_added(x509, cert_args, rsa_privkey, ca_key):
    cert_args["basicConstraints"] = "critical, CA:TRUE, pathlen:1"
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "extensions" in ret.changes
    assert ret.changes["extensions"]["added"] == ["basicConstraints"]
    assert cert.extensions[0].critical
    assert cert.extensions[0].value.ca
    assert cert.extensions[0].value.path_length


@pytest.mark.usefixtures("existing_cert_exts")
def test_certificate_managed_extension_changed(x509, cert_args, rsa_privkey, ca_key):
    cert_args["basicConstraints"] = "critical, CA:TRUE, pathlen:2"
    cert_args["subjectAltName"] = "DNS:sub.salt.ca,email:subnew@salt.ca"
    ret = x509.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "extensions" in ret.changes
    assert set(ret.changes["extensions"]["changed"]) == {
        "basicConstraints",
        "subjectAltName",
    }
    bc = cert.extensions.get_extension_for_class(cx509.BasicConstraints)
    assert bc.critical
    assert bc.value.ca
    assert bc.value.path_length == 2


@pytest.mark.usefixtures("existing_cert_exts")
def test_certificate_managed_extension_removed(x509, cert_args, rsa_privkey, ca_key):
    cert_args.pop("tlsfeature")
    cert_args.pop("nameConstraints")
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "extensions" in ret.changes
    assert set(ret.changes["extensions"]["removed"]) == {
        "nameConstraints",
        "TLSFeature",
    }


@pytest.mark.parametrize("mode", ["0400", "0640", "0644"])
def test_certificate_managed_mode(x509, cert_args, rsa_privkey, ca_key, mode, modules):
    """
    This serves as a proxy for all file.managed args
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["mode"] = mode
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert modules.file.get_mode(cert_args["name"]) == mode


def test_certificate_managed_file_managed_create_false(
    x509, cert_args, rsa_privkey, ca_key
):
    """
    Ensure create=False is detected and respected
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["create"] = False
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(cert_args["name"]).exists()


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", [{"mode": "0644"}], indirect=True)
def test_certificate_managed_mode_change_only(
    x509, cert_args, rsa_privkey, ca_key, modules
):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(cert_args["name"]) == "0644"
    cert_args["mode"] = "0640"
    cert_args.pop("serial_number", None)
    cert = _get_cert(cert_args["name"])
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(cert_args["name"]) == "0640"
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial_number == cert.serial_number


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_mode_test_true(x509, cert_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    cert_args["test"] = True
    cert_args["mode"] = "0666"
    ret = x509.certificate_managed(**cert_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert "0666" != modules.file.get_mode(cert_args["name"])


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("encoding", ["pem", "der"])
@pytest.mark.parametrize("backup", ["minion", False])
def test_certificate_managed_backup(
    x509, cert_args, rsa_privkey, ca_key, modules, backup, encoding
):
    """
    file.managed backup arg needs special attention since file.managed
    does not support writing binary data
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["encoding"] = encoding
    cert_args["backup"] = backup
    assert not modules.file.list_backups(cert_args["name"])
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_created_basic(ret, cert_args["name"], rsa_privkey, ca_key, encoding)
    assert bool(modules.file.list_backups(cert_args["name"])) == bool(backup)


@pytest.mark.parametrize(
    "existing_symlink,existing_cert,encoding",
    [("existing_cert", {}, "pem"), ("existing_cert", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_cert"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_certificate_managed_follow_symlinks(
    x509, cert_args, existing_symlink, follow, existing_cert, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    cert_args["name"] = str(existing_symlink)
    cert_args["encoding"] = encoding
    assert Path(cert_args["name"]).is_symlink()
    cert_args["follow_symlinks"] = follow
    ret = x509.certificate_managed(**cert_args)
    assert bool(ret.changes) == (not follow)


@pytest.mark.parametrize(
    "existing_symlink,existing_cert,encoding",
    [("existing_cert", {}, "pem"), ("existing_cert", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_cert"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_certificate_managed_follow_symlinks_changes(
    x509, cert_args, existing_symlink, follow, existing_cert, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    cert_args["name"] = str(existing_symlink)
    assert Path(cert_args["name"]).is_symlink()
    cert_args["follow_symlinks"] = follow
    cert_args["encoding"] = encoding
    cert_args["CN"] = "new"
    ret = x509.certificate_managed(**cert_args)
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.parametrize("encoding", ["pem", "der"])
def test_certificate_managed_file_managed_error(
    x509, cert_args, rsa_privkey, ca_key, encoding
):
    """
    This serves as a proxy for all file.managed args
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["makedirs"] = False
    cert_args["encoding"] = encoding
    cert_args["name"] = str(Path(cert_args["name"]).parent / "missing" / "cert")
    ret = x509.certificate_managed(**cert_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", [{"encoding": "pkcs12"}], indirect=True)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 36,
    reason="PKCS12 serialization requires cryptography v36+",
)
def test_certificate_managed_pkcs12_embedded_pk_kept(
    x509, cert_args, rsa_privkey, ca_key
):
    cur_pk = _get_cert(cert_args["name"], encoding="pkcs12").key
    cert_args["days_remaining"] = 9999
    ret = x509.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key, encoding="pkcs12")
    assert list(ret.changes) == ["expiration"]
    new_pk = _get_cert(cert_args["name"], encoding="pkcs12").key
    assert new_pk.public_key().public_numbers() == cur_pk.public_key().public_numbers()


def test_crl_managed_empty(x509, crl_args, ca_key):
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key)
    assert len(crl) == len(crl_args["revoked"])


def test_crl_managed_ca_enc(x509, crl_args, ca_key, ca_key_enc):
    crl_args["signing_private_key"] = ca_key_enc
    crl_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key)
    assert len(crl) == len(crl_args["revoked"])


def test_crl_managed_with_revocations(x509, crl_args, crl_revoked, ca_key):
    crl_args["revoked"] = crl_revoked
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key)
    assert len(crl) == len(crl_args["revoked"])
    assert len((next(iter(crl))).extensions) == 2


def test_crl_managed_der(x509, crl_args, ca_key):
    crl_args["encoding"] = "der"
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key, encoding="der")
    assert len(crl) == len(crl_args["revoked"])


def test_crl_managed_exts(x509, crl_args, crl_args_exts, ca_key):
    crl_args.update({"extensions": crl_args_exts})
    ret = x509.crl_managed(**crl_args)
    crl = _assert_crl_basic(ret, ca_key)
    assert len(crl) == len(crl_args["revoked"])
    assert len(crl.extensions) == len(crl_args_exts)


def test_crl_managed_test_true(x509, crl_args, crl_revoked):
    crl_args["revoked"] = crl_revoked
    crl_args["test"] = True
    ret = x509.crl_managed(**crl_args)
    assert ret.result is None
    assert ret.changes
    assert ret.result is None
    assert not Path(crl_args["name"]).exists()


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_existing(x509, crl_args):
    ret = x509.crl_managed(**crl_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize("existing_crl", ({"encoding": "der"},), indirect=True)
def test_crl_managed_existing_der(x509, crl_args):
    ret = x509.crl_managed(**crl_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_crl_exts")
def test_crl_managed_existing_exts(x509, crl_args):
    ret = x509.crl_managed(**crl_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_file")
def test_crl_managed_existing_not_a_crl(x509, crl_args, ca_key):
    """
    If `name` is not a valid CRL, a new one should be written to the path
    """
    # existing_file could be parametrized, but is hardcoded to cert atm
    crl_args["name"] = crl_args["name"][:-3] + "cert"
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_existing_renew(x509, crl_args, ca_key):
    crl_args["days_remaining"] = 300
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert set(ret.changes) == {"expiration"}


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_existing_revocations_added(x509, crl_args, crl_revoked, ca_key):
    crl_args["revoked"] = crl_revoked
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "revocations" in ret.changes
    assert len(ret.changes["revocations"]["added"]) == len(crl_revoked)


@pytest.mark.usefixtures("existing_crl_rev")
def test_crl_managed_existing_revocations_changed(x509, crl_args, crl_revoked, ca_key):
    crl_args["revoked"][0]["extensions"]["invalidityDate"] = "2022-08-13 13:37:00"
    crl_args["revoked"][1]["extensions"].pop("invalidityDate")
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "revocations" in ret.changes
    assert len(ret.changes["revocations"]["changed"]) == 2


@pytest.mark.usefixtures("existing_crl_rev")
def test_crl_managed_existing_revocations_removed(x509, crl_args, crl_revoked, ca_key):
    crl_args["revoked"].pop(0)
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "revocations" in ret.changes
    assert len(ret.changes["revocations"]["removed"]) == 1


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_existing_signing_key_change(
    x509, crl_args, rsa_privkey, cert_exts
):
    crl_args["signing_private_key"] = rsa_privkey
    crl_args["signing_cert"] = cert_exts
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, rsa_privkey)
    assert set(ret.changes) == {"issuer_name", "public_key"}


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_existing_digest_change(x509, crl_args, ca_key):
    crl_args["digest"] = "sha512"
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert set(ret.changes) == {"digest"}


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_private_key_mismatch(x509, crl_args, rsa_privkey):
    crl_args["signing_private_key"] = rsa_privkey
    ret = x509.crl_managed(**crl_args)
    assert ret.result is False
    assert not ret.changes
    assert "Signing private key does not match" in ret.comment


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize("include_expired", [False, True])
def test_crl_managed_existing_revocations_include_expired(
    x509, crl_args, ca_key, include_expired
):
    crl_args["revoked"] = [
        {"serial_number": "DEADBEEF", "not_after": "2009-01-03 13:37:42"}
    ]
    crl_args["include_expired"] = include_expired
    ret = x509.crl_managed(**crl_args)
    assert ret.result
    assert bool(ret.changes) == include_expired


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_exts_added(x509, crl_args, crl_args_exts, ca_key):
    crl_args["extensions"] = crl_args_exts
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "extensions" in ret.changes
    assert len(ret.changes["extensions"]["added"]) == len(crl_args_exts)


@pytest.mark.usefixtures("existing_crl_exts")
def test_crl_managed_existing_exts_changed(x509, crl_args, ca_key):
    crl_args["extensions"]["issuerAltName"] = ["DNS:ca.salt.com"]
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "extensions" in ret.changes
    assert len(ret.changes["extensions"]["changed"]) == 1


@pytest.mark.usefixtures("existing_crl_exts")
def test_crl_managed_existing_exts_removed(x509, crl_args, ca_key):
    crl_args["extensions"].pop("issuingDistributionPoint")
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert "extensions" in ret.changes
    assert len(ret.changes["extensions"]["removed"]) == 1


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize(
    "existing_crl", ({"extensions": {"cRLNumber": "auto"}},), indirect=True
)
def test_crl_managed_existing_crl_crlnumber_auto(x509, crl_args, crl_revoked, ca_key):
    # the dict is manipulated by the state function, it contains 1 now
    crl_args["extensions"]["cRLNumber"] = "auto"
    cur = _get_crl(crl_args["name"])
    assert cur.extensions[0].value.crl_number == 1
    crl_args["revoked"] = crl_revoked
    ret = x509.crl_managed(**crl_args)
    new = _assert_crl_basic(ret, ca_key)
    assert new.extensions[0].value.crl_number == 2


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize(
    "existing_crl", ({"extensions": {"cRLNumber": "auto"}},), indirect=True
)
def test_crl_managed_existing_crl_crlnumber_auto_no_change(x509, crl_args):
    # the dict is manipulated by the state function, it contains 1 now
    crl_args["extensions"]["cRLNumber"] = "auto"
    cur = _get_crl(crl_args["name"])
    assert cur.extensions[0].value.crl_number == 1
    ret = x509.crl_managed(**crl_args)
    _assert_not_changed(ret)
    new = _get_crl(crl_args["name"])
    assert new.extensions[0].value.crl_number == cur.extensions[0].value.crl_number


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize(
    "existing_crl", ({"extensions": {"cRLNumber": "auto"}},), indirect=True
)
def test_crl_managed_existing_encoding_change_only(x509, crl_args, ca_key):
    # the dict is manipulated by the state function, it contains 1 now
    crl_args["extensions"]["cRLNumber"] = "auto"
    crl_args["encoding"] = "der"
    cur = _get_crl(crl_args["name"])
    assert cur.extensions[0].value.crl_number == 1
    ret = x509.crl_managed(**crl_args)
    assert ret.result
    assert ret.changes
    new = _get_crl(crl_args["name"], encoding="der")
    assert new.extensions[0].value.crl_number == 1


@pytest.mark.parametrize("mode", ["0400", "0640", "0644"])
def test_crl_managed_mode(x509, crl_args, ca_key, mode, modules):
    """
    This serves as a proxy for all file.managed args
    """
    crl_args["mode"] = mode
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key)
    assert modules.file.get_mode(crl_args["name"]) == mode


def test_crl_managed_file_managed_create_false(x509, crl_args):
    """
    Ensure create=False is detected and respected
    """
    crl_args["create"] = False
    ret = x509.crl_managed(**crl_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(crl_args["name"]).exists()


@pytest.mark.usefixtures("existing_crl")
@pytest.mark.parametrize(
    "existing_crl",
    [{"mode": "0644", "extensions": {"cRLNumber": "auto"}}],
    indirect=True,
)
def test_crl_managed_mode_change_only(x509, crl_args, ca_key, modules):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(crl_args["name"]) == "0644"
    crl_args["mode"] = "0640"
    crl = _get_crl(crl_args["name"])
    ret = x509.crl_managed(**crl_args)
    assert ret.result is True
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(crl_args["name"]) == "0640"
    crl_new = _get_crl(crl_args["name"])
    assert (
        crl_new.extensions.get_extension_for_class(cx509.CRLNumber).value
        == crl.extensions.get_extension_for_class(cx509.CRLNumber).value
    )


@pytest.mark.usefixtures("existing_crl")
def test_crl_managed_mode_test_true(x509, crl_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    crl_args["test"] = True
    crl_args["mode"] = "0666"
    ret = x509.crl_managed(**crl_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert "0666" != modules.file.get_mode(crl_args["name"])


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("encoding", ["pem", "der"])
@pytest.mark.parametrize("backup", ["minion", False])
def test_crl_managed_backup(x509, crl_args, ca_key, modules, backup, encoding):
    """
    file.managed backup arg needs special attention since file.managed
    does not support writing binary data
    """
    crl_args["encoding"] = encoding
    crl_args["backup"] = backup
    assert not modules.file.list_backups(crl_args["name"])
    ret = x509.crl_managed(**crl_args)
    _assert_crl_basic(ret, ca_key, encoding=encoding)
    assert bool(modules.file.list_backups(crl_args["name"])) == bool(backup)


@pytest.mark.parametrize(
    "existing_symlink,existing_crl,encoding",
    [("existing_crl", {}, "pem"), ("existing_crl", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_crl"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_crl_managed_follow_symlinks(
    x509, crl_args, existing_symlink, follow, existing_crl, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    crl_args["name"] = str(existing_symlink)
    crl_args["encoding"] = encoding
    assert Path(crl_args["name"]).is_symlink()
    crl_args["follow_symlinks"] = follow
    ret = x509.crl_managed(**crl_args)
    assert bool(ret.changes) == (not follow)


@pytest.mark.parametrize(
    "existing_symlink,existing_crl,encoding",
    [("existing_crl", {}, "pem"), ("existing_crl", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_crl"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_crl_managed_follow_symlinks_changes(
    x509, crl_args, existing_symlink, follow, crl_revoked, existing_crl, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    crl_args["name"] = str(existing_symlink)
    assert Path(crl_args["name"]).is_symlink()
    crl_args["follow_symlinks"] = follow
    crl_args["encoding"] = encoding
    crl_args["revoked"] = crl_revoked
    ret = x509.crl_managed(**crl_args)
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.parametrize("encoding", ["pem", "der"])
def test_crl_managed_file_managed_error(x509, crl_args, encoding):
    """
    This serves as a proxy for all file.managed args
    """
    crl_args["makedirs"] = False
    crl_args["encoding"] = encoding
    crl_args["name"] = str(Path(crl_args["name"]).parent / "missing" / "crl")
    ret = x509.crl_managed(**crl_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


def test_csr_managed_with_privkey(x509, csr_args, rsa_privkey):
    csr_args["private_key"] = rsa_privkey
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)


@pytest.mark.parametrize("encoding", ["pem", "der"])
def test_csr_managed_with_privkey_encodings(x509, csr_args, rsa_privkey, encoding):
    csr_args["private_key"] = rsa_privkey
    csr_args["encoding"] = encoding
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey, encoding=encoding)


def test_csr_managed_with_privkey_enc(x509, csr_args, rsa_privkey_enc, rsa_privkey):
    csr_args["private_key"] = rsa_privkey_enc
    csr_args["private_key_passphrase"] = "hunter2"
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)


def test_csr_managed_with_extensions(x509, csr_args, csr_args_exts, rsa_privkey):
    csr_args["private_key"] = rsa_privkey
    csr_args.update(csr_args_exts)
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(ret, rsa_privkey)
    assert len(csr.extensions) == len(csr_args_exts)


def test_csr_managed_with_subject(x509, csr_args, rsa_privkey):
    csr_args["CN"] = "success"
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(ret, rsa_privkey)
    assert csr.subject.rfc4514_string() == "CN=success"


def test_csr_managed_test_true(x509, csr_args, rsa_privkey):
    csr_args["private_key"] = rsa_privkey
    csr_args["test"] = True
    ret = x509.csr_managed(**csr_args)
    assert ret.result is None
    assert ret.changes
    assert not Path(csr_args["name"]).exists()


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_existing(x509, csr_args):
    ret = x509.csr_managed(**csr_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_csr_exts")
def test_csr_managed_existing_with_exts(x509, csr_args, rsa_privkey):
    ret = x509.csr_managed(**csr_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_file")
def test_csr_managed_existing_not_a_csr(x509, csr_args, rsa_privkey):
    """
    If `name` is not a valid csr, a new one should be written to the path
    """
    csr_args["name"] = csr_args["name"][:-3] + "cert"
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("existing_file", [csr_invalid_version], indirect=True)
@pytest.mark.skipif(
    CRYPTOGRAPHY_VERSION[0] < 38,
    reason="Cryptography < v38 does not enforce correct version fields",
)
def test_csr_managed_existing_invalid_version(x509, csr_args, rsa_privkey):
    """
    The previous x509 modules created CSR with invalid version
    fields by default. Since cryptography v38, this leads to an
    exception.
    """
    csr_args["name"] = csr_args["name"][:-3] + "cert"
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_privkey_change(x509, csr_args, ec_privkey):
    csr_args["private_key"] = ec_privkey
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, ec_privkey)
    assert ret.changes["private_key"]


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_digest_change(x509, csr_args, rsa_privkey):
    csr_args["digest"] = "sha512"
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)
    assert ret.changes["digest"]


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_encoding_change(x509, csr_args, rsa_privkey):
    csr_args["encoding"] = "der"
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey, encoding="der")
    assert ret.changes


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_subject_change(x509, csr_args, rsa_privkey):
    csr_args["CN"] = "renewed"
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(ret, rsa_privkey)
    assert list(ret.changes) == ["subject_name"]
    assert csr.subject.rfc4514_string() == "CN=renewed"


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_extension_added(x509, csr_args, rsa_privkey):
    csr_args["basicConstraints"] = "critical, CA:TRUE, pathlen:1"
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(ret, rsa_privkey)
    assert "extensions" in ret.changes
    assert ret.changes["extensions"]["added"] == ["basicConstraints"]
    assert csr.extensions[0].critical
    assert csr.extensions[0].value.ca
    assert csr.extensions[0].value.path_length


@pytest.mark.usefixtures("existing_csr_exts")
def test_csr_managed_extension_changed(x509, csr_args, csr_args_exts, rsa_privkey):
    csr_args["basicConstraints"] = "critical, CA:TRUE, pathlen:2"
    csr_args["subjectAltName"] = "DNS:sub.salt.ca,email:subnew@salt.ca"
    ret = x509.csr_managed(**csr_args)
    csr = _assert_csr_basic(ret, rsa_privkey)
    assert "extensions" in ret.changes
    assert set(ret.changes["extensions"]["changed"]) == {
        "basicConstraints",
        "subjectAltName",
    }
    bc = csr.extensions.get_extension_for_class(cx509.BasicConstraints)
    assert bc.critical
    assert bc.value.ca
    assert bc.value.path_length == 2


@pytest.mark.usefixtures("existing_csr_exts")
def test_csr_managed_extension_removed(x509, csr_args, csr_args_exts, rsa_privkey):
    csr_args.pop("tlsfeature")
    csr_args.pop("nameConstraints")
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)
    assert "extensions" in ret.changes
    assert set(ret.changes["extensions"]["removed"]) == {
        "nameConstraints",
        "TLSFeature",
    }


@pytest.mark.parametrize("mode", ["0400", "0640", "0644"])
def test_csr_managed_mode(x509, csr_args, rsa_privkey, mode, modules):
    """
    This serves as a proxy for all file.managed args
    """
    csr_args["mode"] = mode
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey)
    assert modules.file.get_mode(csr_args["name"]) == mode


def test_csr_managed_file_managed_create_false(x509, csr_args):
    """
    Ensure create=False is detected and respected
    """
    csr_args["create"] = False
    ret = x509.csr_managed(**csr_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(csr_args["name"]).exists()


@pytest.mark.usefixtures("existing_csr")
@pytest.mark.parametrize("existing_csr", [{"mode": "0644"}], indirect=True)
def test_csr_managed_mode_change_only(x509, csr_args, ca_key, modules):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(csr_args["name"]) == "0644"
    csr_args["mode"] = "0640"
    ret = x509.csr_managed(**csr_args)
    assert ret.result is True
    assert not ret.changes
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(csr_args["name"]) == "0640"


@pytest.mark.usefixtures("existing_csr")
def test_csr_managed_mode_test_true(x509, csr_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    csr_args["test"] = True
    csr_args["mode"] = "0666"
    ret = x509.csr_managed(**csr_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert "0666" != modules.file.get_mode(csr_args["name"])


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("encoding", ["pem", "der"])
@pytest.mark.parametrize("backup", ["minion", False])
def test_csr_managed_backup(x509, csr_args, rsa_privkey, modules, backup, encoding):
    """
    file.managed backup arg needs special attention since file.managed
    does not support writing binary data
    """
    csr_args["encoding"] = encoding
    csr_args["backup"] = backup
    assert not modules.file.list_backups(csr_args["name"])
    ret = x509.csr_managed(**csr_args)
    _assert_csr_basic(ret, rsa_privkey, encoding=encoding)
    assert bool(modules.file.list_backups(csr_args["name"])) == bool(backup)


@pytest.mark.parametrize(
    "existing_symlink,existing_csr,encoding",
    [("existing_csr", {}, "pem"), ("existing_csr", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_csr"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_csr_managed_follow_symlinks(
    x509, csr_args, existing_symlink, follow, existing_csr, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    csr_args["name"] = str(existing_symlink)
    assert Path(csr_args["name"]).is_symlink()
    csr_args["follow_symlinks"] = follow
    csr_args["encoding"] = encoding
    ret = x509.csr_managed(**csr_args)
    assert bool(ret.changes) == (not follow)
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.parametrize(
    "existing_symlink,existing_csr,encoding",
    [("existing_csr", {}, "pem"), ("existing_csr", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_csr"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_csr_managed_follow_symlinks_changes(
    x509, csr_args, existing_symlink, follow, existing_csr, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    csr_args["name"] = str(existing_symlink)
    assert Path(csr_args["name"]).is_symlink()
    csr_args["follow_symlinks"] = follow
    csr_args["encoding"] = encoding
    csr_args["CN"] = "new"
    ret = x509.csr_managed(**csr_args)
    assert ret.result
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.parametrize("encoding", ["pem", "der"])
def test_csr_managed_file_managed_error(x509, csr_args, encoding):
    """
    This serves as a proxy for all file.managed args
    """
    csr_args["makedirs"] = False
    csr_args["encoding"] = encoding
    csr_args["name"] = str(Path(csr_args["name"]).parent / "missing" / "csr")
    ret = x509.csr_managed(**csr_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


@pytest.mark.parametrize("algo", ["rsa", "ec", "ed25519", "ed448"])
@pytest.mark.parametrize(
    "encoding",
    [
        "der",
        "pem",
        pytest.param(
            "pkcs12",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
    ],
)
@pytest.mark.parametrize("passphrase", [None, "hunter1"])
def test_private_key_managed(x509, pk_args, algo, encoding, passphrase):
    if (
        algo in ["ed25519", "ed448"]
        and encoding == "pkcs12"
        and CRYPTOGRAPHY_VERSION[0] < 37
    ):
        pytest.skip(
            "PKCS12 serialization of Edwards-curve keys requires cryptography v37"
        )
    pk_args["algo"] = algo
    pk_args["encoding"] = encoding
    pk_args["passphrase"] = passphrase
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, algo, encoding, passphrase)


@pytest.mark.parametrize("algo,keysize", [("rsa", 3072), ("ec", 384)])
def test_private_key_managed_keysize(x509, pk_args, algo, keysize):
    pk_args["algo"] = algo
    pk_args["keysize"] = keysize
    ret = x509.private_key_managed(**pk_args)
    pk = _assert_pk_basic(ret, algo)
    assert pk.key_size == keysize


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize(
    "existing_pk",
    [
        {},
        {"algo": "ec"},
        {"algo": "ed25519"},
        {"algo": "ed448"},
        {"keysize": 3072},
        {"algo": "ec", "keysize": 384},
    ],
    indirect=True,
)
def test_private_key_managed_existing(x509, pk_args):
    ret = x509.private_key_managed(**pk_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_existing_new(x509, pk_args):
    cur = _get_privkey(pk_args["name"])
    pk_args["new"] = True
    ret = x509.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa")
    assert cur.public_key().public_numbers() != new.public_key().public_numbers()


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "hunter2"}], indirect=True)
def test_private_key_managed_existing_new_with_passphrase_change(x509, pk_args):
    cur = _get_privkey(pk_args["name"], passphrase=pk_args["passphrase"])
    pk_args.pop("passphrase")
    pk_args["new"] = True
    ret = x509.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa")
    assert cur.public_key().public_numbers() != new.public_key().public_numbers()


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_algo_change(x509, pk_args):
    pk_args["algo"] = "ed25519"
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "ed25519")


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_keysize_change(x509, pk_args):
    pk_args["keysize"] = 3072
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize(
    "encoding",
    [
        "der",
        pytest.param(
            "pkcs12",
            marks=pytest.mark.skipif(
                CRYPTOGRAPHY_VERSION[0] < 36,
                reason="PKCS12 serialization requires cryptography v36+",
            ),
        ),
    ],
)
def test_private_key_managed_encoding_change(x509, pk_args, encoding):
    cur = _get_privkey(pk_args["name"])
    pk_args["encoding"] = encoding
    ret = x509.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa", encoding=encoding)
    assert new.public_key().public_numbers() == cur.public_key().public_numbers()


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_passphrase_introduced(x509, pk_args):
    pk_args["passphrase"] = "hunter1"
    cur = _get_privkey(pk_args["name"])
    ret = x509.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa", passphrase="hunter1")
    assert new.public_key().public_numbers() == cur.public_key().public_numbers()


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_removed_not_overwrite(x509, pk_args):
    pk_args.pop("passphrase")
    ret = x509.private_key_managed(**pk_args)
    assert ret.result is False
    assert not ret.changes
    assert "The existing file is encrypted. Pass overwrite" in ret.comment


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_removed_overwrite(x509, pk_args):
    pk_args.pop("passphrase")
    pk_args["overwrite"] = True
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_changed_not_overwrite(x509, pk_args):
    pk_args["passphrase"] = "hunter1"
    ret = x509.private_key_managed(**pk_args)
    assert ret.result is False
    assert not ret.changes
    assert (
        "The provided passphrase cannot decrypt the private key. Pass overwrite"
        in ret.comment
    )


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_changed_overwrite(x509, pk_args):
    pk_args["passphrase"] = "hunter1"
    pk_args["overwrite"] = True
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa", passphrase="hunter1")


@pytest.mark.parametrize("encoding", ["pem", "der"])
@pytest.mark.parametrize("mode", [None, "0600", "0644"])
def test_private_key_managed_mode(x509, pk_args, mode, encoding, modules):
    """
    This serves as a proxy for all file.managed args
    """
    pk_args["mode"] = mode
    pk_args["encoding"] = encoding
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa", encoding=encoding)
    assert modules.file.get_mode(pk_args["name"]) == (mode or "0400")


def test_private_key_managed_file_managed_create_false(x509, pk_args):
    """
    Ensure create=False is detected and respected
    """
    pk_args["create"] = False
    ret = x509.private_key_managed(**pk_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(pk_args["name"]).exists()


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_mode_test_true(x509, pk_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    pk_args["test"] = True
    pk_args["mode"] = "0666"
    ret = x509.private_key_managed(**pk_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert "0666" != modules.file.get_mode(pk_args["name"])


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("encoding", ["pem", "der"])
@pytest.mark.parametrize("backup", ["minion", False])
def test_private_key_managed_backup(x509, pk_args, modules, backup, encoding):
    """
    file.managed backup arg needs special attention since file.managed
    does not support writing binary data
    """
    pk_args["encoding"] = encoding
    pk_args["backup"] = backup
    assert not modules.file.list_backups(pk_args["name"])
    ret = x509.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa", encoding=encoding)
    assert bool(modules.file.list_backups(pk_args["name"])) == bool(backup)


@pytest.mark.parametrize(
    "existing_symlink,existing_pk,encoding",
    [("existing_pk", {}, "pem"), ("existing_pk", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_pk"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_private_key_managed_follow_symlinks(
    x509, pk_args, existing_symlink, follow, existing_pk, encoding
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    pk_args["name"] = str(existing_symlink)
    pk_args["encoding"] = encoding
    assert Path(pk_args["name"]).is_symlink()
    pk_args["follow_symlinks"] = follow
    ret = x509.private_key_managed(**pk_args)
    assert bool(ret.changes) == (not follow)


@pytest.mark.parametrize(
    "existing_symlink,existing_pk,encoding",
    [("existing_pk", {}, "pem"), ("existing_pk", {"encoding": "der"}, "der")],
    indirect=["existing_symlink", "existing_pk"],
)
@pytest.mark.parametrize("follow", [True, False])
def test_private_key_managed_follow_symlinks_changes(
    x509, pk_args, existing_symlink, follow, encoding, existing_pk
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the x509 module
    """
    pk_args["name"] = str(existing_symlink)
    assert Path(pk_args["name"]).is_symlink()
    pk_args["follow_symlinks"] = follow
    pk_args["encoding"] = encoding
    pk_args["algo"] = "ec"
    ret = x509.private_key_managed(**pk_args)
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"mode": "0400"}], indirect=True)
def test_private_key_managed_mode_change_only(x509, pk_args, modules):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(pk_args["name"]) == "0400"
    pk_args["mode"] = "0600"
    cur = _get_privkey(pk_args["name"])
    ret = x509.private_key_managed(**pk_args)
    assert ret.result is True
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(pk_args["name"]) == "0600"
    new = _get_privkey(pk_args["name"])
    assert new.public_key().public_numbers() == cur.public_key().public_numbers()


@pytest.mark.parametrize("encoding", ["pem", "der"])
def test_private_key_managed_file_managed_error(x509, pk_args, encoding):
    """
    This serves as a proxy for all file.managed args
    """
    pk_args["makedirs"] = False
    pk_args["encoding"] = encoding
    pk_args["name"] = str(Path(pk_args["name"]).parent / "missing" / "pk")
    ret = x509.private_key_managed(**pk_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("overwrite", [False, True])
def test_private_key_managed_existing_not_a_pk(x509, pk_args, overwrite):
    pk_args["name"] = pk_args["name"][:-11] + "cert"
    pk_args["overwrite"] = overwrite
    ret = x509.private_key_managed(**pk_args)
    assert bool(ret.result) == overwrite
    assert bool(ret.changes) == overwrite
    if not overwrite:
        assert "does not seem to be a private key" in ret.comment
        assert "Pass overwrite" in ret.comment


def test_pem_managed(x509, ca_cert, tmp_path):
    tgt = tmp_path / "ca"
    ret = x509.pem_managed(str(tgt), text=ca_cert)
    assert ret.result
    assert ret.changes
    assert tgt.exists()
    assert tgt.read_text() == ca_cert


def test_pem_managed_newline_fix(x509, ca_cert, tmp_path):
    tgt = tmp_path / "ca"
    ret = x509.pem_managed(str(tgt), text=ca_cert.replace("\n", ""))
    assert ret.result
    assert ret.changes
    assert tgt.exists()
    assert tgt.read_text() == ca_cert


def test_pem_managed_newline_fix_no_changes(x509, ca_cert, tmp_path):
    tgt = tmp_path / "ca"
    tgt.write_text(ca_cert)
    ret = x509.pem_managed(str(tgt), text=ca_cert.replace("\n", ""))
    assert ret.result
    assert not ret.changes
    assert tgt.read_text() == ca_cert


# Deprecated arguments


@pytest.mark.parametrize("arg", [{"version": 3}, {"serial_bits": 64}, {"text": True}])
def test_certificate_managed_should_not_fail_with_removed_args(
    x509, cert_args, rsa_privkey, arg
):
    cert_args["days_valid"] = 30
    cert_args["days_remaining"] = 7
    cert_args["private_key"] = rsa_privkey
    with pytest.deprecated_call():
        ret = x509.certificate_managed(**cert_args, **arg)
    assert ret.result is True
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=success"


def test_certificate_managed_warns_about_algorithm_renaming(
    x509, cert_args, rsa_privkey
):
    cert_args["days_valid"] = 30
    cert_args["days_remaining"] = 7
    cert_args["private_key"] = rsa_privkey
    with pytest.deprecated_call():
        ret = x509.certificate_managed(**cert_args, algorithm="sha512")
    assert ret.result is True
    cert = _get_cert(cert_args["name"])
    assert isinstance(cert.signature_hash_algorithm, hashes.SHA512)


def test_certificate_managed_warns_about_long_name_attributes(
    x509, cert_args, rsa_privkey
):
    cert_args["days_valid"] = 30
    cert_args["days_remaining"] = 7
    cert_args["commonName"] = "success"
    cert_args["private_key"] = rsa_privkey
    with pytest.deprecated_call():
        ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    cert = _get_cert(cert_args["name"])
    assert cert.subject.rfc4514_string() == "CN=success"


def test_certificate_managed_warns_about_long_extensions(x509, cert_args, rsa_privkey):
    cert_args["X509v3 Basic Constraints"] = "critical CA:TRUE, pathlen:1"
    cert_args["days_valid"] = 30
    cert_args["days_remaining"] = 7
    cert_args["private_key"] = rsa_privkey
    with pytest.deprecated_call():
        ret = x509.certificate_managed(**cert_args)
    assert ret.result is True
    cert = _get_cert(cert_args["name"])
    assert len(cert.extensions) == 1
    assert isinstance(cert.extensions[0].value, cx509.BasicConstraints)
    assert cert.extensions[0].critical
    assert cert.extensions[0].value.ca
    assert cert.extensions[0].value.path_length == 1


@pytest.mark.parametrize("arg", [{"version": 1}, {"text": True}])
def test_csr_managed_should_not_fail_with_removed_args(x509, arg, csr_args):
    with pytest.deprecated_call():
        ret = x509.csr_managed(**csr_args, **arg)
    assert ret.result is True
    csr = _get_csr(csr_args["name"])
    assert csr.subject.rfc4514_string() == "CN=success"


def test_csr_managed_warns_about_algorithm_renaming(x509, csr_args):
    with pytest.deprecated_call():
        ret = x509.csr_managed(**csr_args, algorithm="sha512")
    assert ret.result is True
    csr = _get_csr(csr_args["name"])
    assert isinstance(csr.signature_hash_algorithm, hashes.SHA512)


def test_csr_managed_warns_about_long_name_attributes(x509, csr_args):
    csr_args.pop("CN", None)
    with pytest.deprecated_call():
        ret = x509.csr_managed(**csr_args, commonName="deprecated_yo")
    assert ret.result is True
    csr = _get_csr(csr_args["name"])
    assert csr.subject.rfc4514_string() == "CN=deprecated_yo"


def test_csr_managed_warns_about_long_extensions(x509, csr_args):
    csr_args["X509v3 Basic Constraints"] = "critical CA:FALSE"
    with pytest.deprecated_call():
        ret = x509.csr_managed(**csr_args)
    assert ret.result is True
    csr = _get_csr(csr_args["name"])
    assert len(csr.extensions) == 1
    assert isinstance(csr.extensions[0].value, cx509.BasicConstraints)
    assert csr.extensions[0].critical
    assert csr.extensions[0].value.ca is False
    assert csr.extensions[0].value.path_length is None


@pytest.mark.parametrize("arg", [{"text": True}])
def test_crl_managed_should_not_fail_with_removed_args(x509, arg, crl_args):
    crl_args["days_remaining"] = 3
    crl_args["days_valid"] = 7
    with pytest.deprecated_call():
        ret = x509.crl_managed(**crl_args, **arg)
    assert ret.result is True
    crl = _get_crl(crl_args["name"])
    assert len(crl) == 0


def test_crl_managed_should_recognize_old_style_revoked(x509, crl_args, crl_revoked):
    revoked = [
        {f"key_{i}": [{"serial_number": rev["serial_number"]}]}
        for i, rev in enumerate(crl_revoked)
    ]
    crl_args["revoked"] = revoked
    crl_args["days_remaining"] = 3
    crl_args["days_valid"] = 7
    with pytest.deprecated_call():
        ret = x509.crl_managed(**crl_args)
    assert ret.result is True
    crl = _get_crl(crl_args["name"])
    assert len(crl) == len(crl_revoked)


@pytest.mark.usefixtures("existing_crl_rev")
def test_crl_managed_should_recognize_old_style_revoked_for_change_detection(
    x509, crl_args, crl_revoked
):
    revoked = [
        {
            f"key_{i}": [
                {"serial_number": rev["serial_number"]},
                {"extensions": rev["extensions"]},
            ]
        }
        for i, rev in enumerate(crl_revoked)
    ]
    crl_args["revoked"] = revoked
    crl_args["days_remaining"] = 3
    crl_args["days_valid"] = 7
    with pytest.deprecated_call():
        ret = x509.crl_managed(**crl_args)
    assert ret.result is True
    assert not ret.changes


def test_crl_managed_should_recognize_old_style_reason(x509, crl_args):
    revoked = [{"key_1": [{"serial_number": "01337A"}, {"reason": "keyCompromise"}]}]
    crl_args["revoked"] = revoked
    crl_args["days_remaining"] = 3
    crl_args["days_valid"] = 7
    with pytest.deprecated_call():
        ret = x509.crl_managed(**crl_args)
    assert ret.result is True
    crl = _get_crl(crl_args["name"])
    assert len(crl) == 1
    rev = crl.get_revoked_certificate_by_serial_number(78714)
    assert rev
    assert rev.extensions
    assert len(rev.extensions) == 1
    assert isinstance(rev.extensions[0].value, cx509.CRLReason)


@pytest.mark.parametrize(
    "arg", [{"cipher": "aes_256_cbc"}, {"verbose": True}, {"text": True}]
)
def test_private_key_managed_should_not_fail_with_removed_args(x509, arg, pk_args):
    with pytest.deprecated_call():
        ret = x509.private_key_managed(**pk_args, **arg)
    assert ret.result is True
    assert _get_privkey(pk_args["name"])


def test_private_key_managed_warns_about_bits_renaming(x509, pk_args):
    with pytest.deprecated_call():
        ret = x509.private_key_managed(**pk_args, bits=3072)
    assert ret.result is True
    pk = _get_privkey(pk_args["name"])
    assert pk.key_size == 3072


def _assert_cert_created_basic(
    ret,
    name,
    privkey,
    ca_key,
    encoding="pem",
    passphrase=None,
    get_pkcs12=False,
    subject=None,
):
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("created") == name or ret.changes.get("replaced") == name
    cert = _get_cert(name, encoding=encoding, passphrase=passphrase)
    if encoding.startswith("pkcs7"):
        cert = cert[0]
    elif encoding == "pkcs12":
        # pkcs12 embeds the private key inside the container
        assert _belongs_to(cert.key.public_key(), privkey)
        if get_pkcs12:
            return cert
        cert = cert.cert.certificate
    if subject is None:
        subject = "CN=success"
    assert cert.subject.rfc4514_string() == subject
    assert _belongs_to(cert, privkey)
    assert _signed_by(cert, ca_key)
    return cert


def _assert_cert_basic(
    ret, name, privkey, ca_key, encoding="pem", passphrase=None, get_pkcs12=False
):
    assert ret.result is True
    assert ret.changes
    cert = _get_cert(name, encoding=encoding, passphrase=passphrase)
    if encoding.startswith("pkcs7"):
        cert = cert[0]
    elif encoding == "pkcs12":
        assert _belongs_to(cert.key.public_key(), privkey)
        if get_pkcs12:
            return cert
        cert = cert.cert.certificate
    assert _belongs_to(cert, privkey)
    assert _signed_by(cert, ca_key)
    return cert


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


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, cx509.Certificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, x509util.load_privkey(privkey))


def _signed_by(cert, privkey):
    return x509util.verify_signature(cert, x509util.load_privkey(privkey).public_key())


def _assert_crl_basic(ret, ca_key, encoding="pem", passphrase=None):
    assert ret.result is True
    assert ret.changes
    crl = _get_crl(ret.name, encoding=encoding)
    assert crl.is_signature_valid(
        x509util.load_privkey(ca_key, passphrase=passphrase).public_key()
    )
    return crl


def _assert_csr_basic(ret, privkey, encoding="pem", passphrase=None):
    assert ret.result is True
    assert ret.changes
    csr = _get_csr(ret.name, encoding=encoding)
    privkey = x509util.load_privkey(privkey, passphrase=passphrase)
    assert x509util.is_pair(csr.public_key(), privkey)
    return csr


def _assert_pk_basic(ret, algo, encoding="pem", passphrase=None):
    assert ret.result
    assert ret.changes
    pk = _get_privkey(ret.name, encoding=encoding, passphrase=passphrase)
    if algo == "rsa":
        assert isinstance(pk, rsa.RSAPrivateKey)
    if algo == "ec":
        assert isinstance(pk, ec.EllipticCurvePrivateKey)
    if algo == "ed25519":
        assert isinstance(pk, ed25519.Ed25519PrivateKey)
    if algo == "ed448":
        assert isinstance(pk, ed448.Ed448PrivateKey)
    return pk


def _assert_not_changed(ret):
    assert ret.result
    assert not ret.changes
    assert "in the correct state" in ret.comment


def _get_crl(crl, encoding="pem"):
    try:
        p = Path(crl)
        if p.exists():
            crl = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass

    if encoding == "pem":
        if not isinstance(crl, bytes):
            crl = crl.encode()
        return cx509.load_pem_x509_crl(crl)
    if encoding == "der":
        if not isinstance(crl, bytes):
            crl = base64.b64decode(crl)
        return cx509.load_der_x509_crl(crl)


def _get_csr(csr, encoding="pem"):
    try:
        p = Path(csr)
        if p.exists():
            csr = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass

    if encoding == "pem":
        if not isinstance(csr, bytes):
            csr = csr.encode()
        return cx509.load_pem_x509_csr(csr)
    if encoding == "der":
        if not isinstance(csr, bytes):
            csr = base64.b64decode(csr)
        return cx509.load_der_x509_csr(csr)


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
