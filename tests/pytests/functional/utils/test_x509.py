from base64 import b64decode
from textwrap import dedent

import pytest

import salt.utils.x509 as x509

cx509 = pytest.importorskip("cryptography.x509")

from cryptography.hazmat.primitives.asymmetric import rsa


@pytest.fixture
def b64cert_with_prefix():
    return (
        "b64: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"
    )


@pytest.fixture
def b64cert(b64cert_with_prefix):
    return b64cert_with_prefix[4:]


@pytest.fixture
def cert_pem():
    return dedent(
        """
        -----BEGIN CERTIFICATE-----
        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
        -----END CERTIFICATE-----
        """
    )


def test_load_file_or_bytes_base64_der_with_b64_prefix(b64cert_with_prefix):
    der = x509.load_file_or_bytes(b64cert_with_prefix)
    cert = cx509.load_der_x509_certificate(der)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )


def test_load_file_or_bytes_base64_der(b64cert):
    der = x509.load_file_or_bytes(b64cert)
    cert = cx509.load_der_x509_certificate(der)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )


def test_load_file_or_bytes_pem(cert_pem):
    pem = x509.load_file_or_bytes(cert_pem)
    cert = cx509.load_pem_x509_certificate(pem)
    assert (
        cert.subject.rfc4514_string() == "CN=nifi.cdx.eitr.dev,L=Sykesville,ST=MD,C=US"
    )


@pytest.fixture
def privkey_pem():
    return """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDLAxOPz/iWNFHZ
8XMH2X7jlWHqDSG8/ZGK1Plf9KPakUgMvSAWYFH7G0H/nSP7EUMeUMwrdMxW0aqV
6J/VoXQ2uUIDND0A1JA4T7kliot0ObQV/8BhNI4Pp9heOwn9vonAxde58X81lPE1
gA41XWimVae66J+gBVLk4eJ/RFGgHKNa2y2ih9lT+sWqUEUPJVBwcbPmPS+tvmu3
JTPuIPXj9jwc+v3RAuWW9rgIoh1zS1WZRZBBT18bWchZBJctX5LxUwGGGcnRJbJz
JOJCA3pJ889UAlk4CiuZ4By6GMllJEnCdcpXq98hzF9xA1jJBQEV5w1luh4LYAtF
B34qaR3tAgMBAAECggEAAOUZRuCEhYQvui8f/sn2ju7fjB/iGEp73XaCSB1ORAF9
vx46tntW0S114h6uUNLq9O0np6di2tBSZeL57v/aGpjaRPGL6H8g/AaQV+CFxdp9
RApcR3FrKn/m0Pkf2nNmrKfF0C2G2u5QDX7St5yBgH41kfoPJHrxhxqRz4k2Q023
zYRYiPnt2ujuc5Yol/Jk0XCNskTcuFTtnMzVyPxQQ7wsyZ6vO4/eJWG5DRhx2MUe
HZQgNg8o8P1LRb2hchgV6ukrvkzy/vXqW5kr0fJuephMNpH0JNhcefyp9qG8/XKO
Bji/QXJ+/IHeEgouJ6WfgDcp95mSd2KDV1yjgJBaZwKBgQDvAGtHZgRK2TIO3xvX
RXEdu03Iv0JKTXN+ZBAxvo3GSZt3kBLcHg/I1cidoddiSw2hlSbcl2Arxt2pfada
W5z7XFyVKcnpDIRMLuXXR0rt3s5LA+03QBzD6JpBe4WggwkH3Np5d4quWNdkT/6G
on2gsoHSNTUf3d+lqVbr2mZxbwKBgQDZc2Hw8FbeSNGcBFnAi/PaPj+ImIdbDud3
F1C+/+clR+kO/TPv259HPpf3HiI+Bigu7Jnhqqs8DxH/R7vjH0STVOgFJybD3zQ2
lMTUpOYSdwqSV44qCH5ENHis0Mh8Gj8rlmm2m2jZDmGM46eEaeS7Lm/KmIPe75R9
HNCuT8jAYwKBgQDGfEebzRqFeql69kkt16rgcTxhGo2YHYhsD/fvB/zAD0NA4XL4
QTMErJ7mYpD4PbJ9XdwfWMvyrz5JU2RXwzu0+PienEzl8ZIxnsUcq0WMFPyoCgPI
XcNF4/evqEDKk+g9EmqSc/fFYVzIHzMXZv0EJxtvkuaip2XkM6VPTFrFmwKBgFbo
b5+NXxquPeA+OOTkyoxSTrA4TfjNxyLo1aPQwUA8MmCEQErAGzOtR61DhOoHKe4/
L+1qec+iMk42DFjk+VJtH+JXWH32anbaFKTsVuvQWhBNIAuao2R9GDHxq/81ukOg
dRW/nTMLNV/K6PvaGsnY8GMne6URWeZ7KshQKOsDAoGBAItYYYARi1w8voL4AMVM
wu5YeqbKANKP7h1735smASm8wgNnTnn9LNqf8daG71TN+0oVD5TtQwQ0rentbxk0
mDGfXMF1zixUpa7AYSISFXjaqVPCkIxzG+V/J/HUGS4V9LQ+XnRPVyNPxCPOUYWg
xIwrJAEMrmQmgyPKRGywNjlE
-----END PRIVATE KEY-----
    """


@pytest.fixture
def privkey_pem_enc():
    return """
-----BEGIN ENCRYPTED PRIVATE KEY-----
MIIFNTBfBgkqhkiG9w0BBQ0wUjAxBgkqhkiG9w0BBQwwJAQQoTiecHhzRQ1NxMMY
IavW1QICCAAwDAYIKoZIhvcNAgkFADAdBglghkgBZQMEASoEEKJtUTOLHfU16vLs
gz78++oEggTQiHyOUjqxwauGLGtJFzJlMAdmJot5UraVwxPfWBDgauPUYr3Zc/oG
d0dcSecFJW6UVJRw5I6Ds3R4LbC5yj0QkqzupE/GC3t/n2NZeaDppTTB9qsfmJsv
K9CZY14vpaPiYI79N9pSZ9XD9t+bWkyD69QxAeyEuxHhzxF+daP+lCiqJSb0C06/
kC31fSQUgspvw7a/l52Se5NrafrbZFzCcafl02XsX0ztvJFgGhcSyo0YNKPHTXMQ
/ing7l6Uo0OXczV+9WcxofHG6UPw1udMishH2Zp8YutaV2QBC0m6ZZEllJBz0QqZ
TSWx7G9znrcY0kLZ7x8YRRgsNDSR52HQqI+/5rcUNBUKX9WcXFdcbFuOURY9PTCN
lYGtu4CsH6KpuHi7ej48l2vwokbWDN6L7CQk8jDcYlDiUU4NmLXgSIhjK+Jg6CPi
LX6PlBLJ452EJZjj/qDK5miULqqeb5HpMkb5hv88f7E3BucGps6gCRayUsUqskTO
qs/+8InH59eAHJgS+pm+a8fDeiIbNn5TaacAY8HrKXWdJMdQlh0UKJpVmS5qSbTl
jJF2gIXNdUH+/mFj84FHz8Vc4R/ZuZR21twc+uXBsWzNG2RXCNud/6hTAVBQhh2N
N87BJ3S46EXn9c3y6q5mRyU2S0Got9nK1RrzqBO2DVsCG3b9Xku+y30k6Gj0esJf
yCCLn8vsFLzaw8/eJF/F1qJ/Mjodo4mg0JojvBXlxtgti7p8gkDBX5A+a/DATNl3
ABZ//B/Bb0x9/cj/hpHw8iIDVhVsjrUl0gAYGXq0B5cUslSvqIJ7Yxo7t2DCsPZk
l0uUWYKrgqA6xkdjaWmYmjcXfRdPo48Pmwh/KwoyLdO/dPy6y6YD9lzmxprRBQsu
jN655zF9rKVoC7wTbFkUALMwOqokMn9/Aci0IIET+t8sZofz9RVyEAQcJ1N13Lst
6tALrv2AHia147Ll9AFPd+2OEYTX8pcuUml8uqZMHBMx3FBA9hd6ie9YHNGNAQl6
UYHKnSlOQ2Tu7YRw3hJ9VJ9+mxVV4EFe6DNcUeJaa/w6aYOZmbgJrAie65ot0zf6
2X2Mkol+6K0+tH3dJTLDQhlOvE7wzt/DRN+jILyJrqsD8K8nMccC7D4p70IgwWYV
DApP+ckbOGjv+pLTPLV3eAYHmi8b0JGoMaOlOBxis9YBOTA8mjLQHPWXe2y+O2VM
W20eru6khvWgriqezvfYhEe4h15Ou8wm+QWI8IMPGSsa7f+M5twCMWo+OwujOrt2
3vaxafu5VXYat/BIWCO8locXqEzlYxiJM9TzSxtBvb1UDGK3gwfAeQCe17C1ELj+
ICJZ/BLdtIIlc/e4D01IFnMz6gPQ+I9Z6/P4z0rtjzoarfJp05qN0qHdXl8Q7GKW
Qj3LvsjE3Xscvw95i5bewYxa+ENNpS0j3izHU4HuWVaj8p5Ht4ltM+XAKSMlU6oR
6c1vi29VwkWgUfHCRX7EvTMXXGdGUky92Kr0VU39lKTOQfVEexNAaqK9SkqD1QdQ
mRyNrxtSHjn8tGgALYxoxVfkoqF92fRb0fuJ8N1IvaG2plc63yul4Max0V7caJCo
S6fexDgOdgtxSgQrM6cAlEnO+3Inog56hZhSt51Zsa5JC7m+WbWpO4A=
-----END ENCRYPTED PRIVATE KEY-----
    """


@pytest.fixture
def privkey_der():
    return """
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCdKFxJ7Z+lDXv9xpfO8J2wiyOk
HnSoKpC6IlwqIK67JGrhFCITbfPHJumuAdFHPBPGmBr3jaJMutyzCF6Dwrn/46X7YiwK0bpNZQEC
3L2H2aE76LQ8C0U7HZmBrStXUFR4YT8+n88LCSOeuTj2Iyp0a24jQWEY3W6LL1/wGH6H4xeTmn51
/ztyH4LX66ZhcmIhEyL/UQHjFm3jKrTB2MxhlQV8SRLAV08f4hqM26ULPyT8j1meXWP1NhwfTeqA
1GeS2WBNy7XT/ms8w3eN1eIltELBgeAK+yhWrLY59Amxk32ypp5zH8EtmPthArSfszsHpAiUKiaP
8x2/onqJcmrtAgMBAAECggEAJIq6bswsVz376yWurcT//YlUx7f3KxT+ovETWg5QYp5UpbI/PCJQ
USnIoxe0GCqtdHtwpcgOiWXXpF9ZTqzL/+ZodTu9/uQGPDG0mvxFq51cYqg4pE+AkP7QbzkbP0mj
4nvGL2MMSsYcvK7Xwk+p8vj52oO8toHiTsW8uoCPhzvWrEVzgqczb35L+IiMqI21dbTG+BW9zOPJ
x5skXduwDew2KfszPZsR9h9cehkD+dm0H3AXKzWDZ/F5MbFs+9KqtUXmCG3lC7OhdP7rFMCHa0iL
/ZPCZZP5Ohh0bVVFAo9EvGlBNkt0+J/YvhVsWeBpKxSB3wcDFuvkKs26WfmBAQKBgQDP9VFlg+bV
yv+Ev47wvb7koIP584lqquVdlVj0n0WtjB0zGHyLUwUvAI78970jivLLr9OC4342rBJYCzDBWtTB
iwnWIjqHY4x6U+neGiit5At7W+w5MThviEZh7FuVb1/36VLvpXvff7mbXAIeQ6GBL2cSLBuZYmEQ
gsyzhdnvgQKBgQDBdq/Y4Ps9bnKhUo4yooK2Z1j2R7M7SB/iH7BnZDOEAd+Kc27mwD8fwggFFuVV
81jSrJR76joG5kJysLnJ1P0YMWEgv1qgEd54zrQeSp3a2BD3EmW7QaSR6gPgCXYtYlev5Dke45pN
JQJ4uXXXRseheiHqgwWndkeAkDRhqK/xbQKBgQC4U+/EFXhERFzcY5blmKpdqFGS+eTx4WzQ2JIy
sgJm4+z131x1ei78DHixjT3fBUhUdxL5z3+OIlNYKwMaP9KZgw5C+a/7Vaesvjhrn7AzAhGTVFU8
FH67jYUlQwWinUfpTK0wsfPslSAFrzZJcRT0lvm7R9Fm0abLpcSf06LrAQKBgQCcsl830PJuDXl3
RQC77njk+MxLnkODrqV0Z6pf8/7t2v6Oi3S2HdyDAouwY50ZguLcsMALpemeEP6dGptA6OyendBH
z/W9VPvW6cVmC5XT3dHP7OzNQRvku6Cr473+gHr5kmbZqAwgk+tukPjrhv7Gwb+azMjVnK3JagOj
Xhgz+QKBgQCDor0HZuyt0TJtloOd5/BXU0Liod/SXQV8g6sLkCelHdRK90fhYqytsl7pjFIUSKhE
mki24NW2pzHg3aUTmtoinxeZvQ+p50zSLMY03BwZkRSpfa7GxuBJO8oXYYSWzjkTYZYwUAqvKInC
zVF4iAM8gruwBsG9rz4qbERWS129bA==
    """


@pytest.fixture
def privkey_der_enc():
    return """
MIIFNTBfBgkqhkiG9w0BBQ0wUjAxBgkqhkiG9w0BBQwwJAQQG4NHfFk7vuQZgdHMlWsYsgICCAAw
DAYIKoZIhvcNAgkFADAdBglghkgBZQMEASoEEJDjwMJPYfA+bbZZ9DzOnw4EggTQN/6SSSaan+Eg
uXX9i0IXDHTg/23yHMuuelMnbausCt1GbCxAL+yKtVcK0gG/k2kgDvEkKjIc04GP54XVu2OUUHS1
keNEnNfLW1tEJzEeke3l+jTjJKIyCVKy1QMfTYnIfKvTdidPl+bWQnlphrgNb/RtF5bp46jkzBdE
UKpzUYvXd8U0m4bhS8H452y0+aKlnb5IZB6P1gBExMafdp6Bw0lOE+boWZiBviAJF7FYBNz0KDcV
ubkNyX/FuSs9Gcnq6Es+o3kEH5RQAfFgNPCo4D5b28ELBEQgB9ZSTbJQbbMkC5xdY0sz5OldMAF0
tz2j1pFg32l1/cyBpwZn08isbJV7bTv8BCc8o+Uvmqldqo2mqaTDh+PrzbsZlOL/cTjYUHYGvtMW
CznuOJQDepsOB+qZ1bp7eN3AQ1Y2odWADo6ZPaZ3WA1CwQxgxB8loFy22/wXk0SauGH/TegL+4AE
jeqRxKTy+Y324kZyBsBkDKxe/M5K44Ye+RHi/Nh2Yybd5WTYfQ766nWWo2pgj3m3/LArq0kCdV+B
evTGQ+L8MSKZ7aA+xbPxi0Idi3j1CaJGQNsvgaENxcMnQVE2WX/g43QUWFC2Jzq5QoIwXWYMIe/f
JyavmDebMX38aRPFXHSftAP3gjtRsCHS4k+D4+wbe67oL04sj4l3+fCMF8bErvo+FTRKhT7SKbJ9
ojCMNKYj0rrKaDHGXNepAcHENrCPA3I1nOwuLgRaY3/KXcTumypgs/k1uvIDieKRxExVrEn7s6IP
HWJfLdmHDS6XbalRkVVOmRYvfc/FIwQ+CAf9c5U1BYcyTlmAWgfu6mJr7h7rodLe3SMXm1STXJZu
h+kfO92GbM6CAVB7IjN117ZhW2vxq70LW9wVu1JUCBXswDsbmAu5y03AgN9YQANT0eJS5mWH4C6h
TGvDkR3YxN0PYsBfzz2d7HSz8MWiPzpKyrCpoF9PFoho2De5J8WFu3WfHYt4A+06yxUeBGhm9Mmk
IhKA+x75gJUu6vDMyNCI1OAelfotUg7PleJT1PTpvPgS+51WpWgKbI9RnOEyjnU3DB9WId70/zwa
7uq0EXNoasJwWkw1dfVjWXXWZEmWIHCWJuvoa07vl59cvYOV2oxdFDQB3W00qmiLJLrq6BIVpp7o
cFzT7U/9nEMfYjVMD7KeAmAyOlVDLmV/+wYYts9LmN4w9mkA2C3CJtQn7pxV0gvagjmPXgGdwHiY
Vb4xrGPCbFOy/Zki6WJG1SGRPJmV6DNsUfVQmbduKPPCBu4h7Efg7zrqCeZMwnB3MKcG9dYugpN8
Y9MYyXA6gBuSDJ9fhVpa1bSfHaXecRNKRDNUlHHRUlfkhZfi2sdchk5gTYeyFrVAyQ3dq/aUkSNC
G/LzmjSuvrb4J58J7uQwaf4wC472Q0PKSldUnw3kRXe2eaL0QJUfwLS3qLA5i9QPhtg3MrX9Lld+
JKsQxpbwe0x5yK4qhUr/k0/7J4Ga+jKiW5cnUFxcDGKoZYcGbhLq3uPi/jLEY/QvJBbPWVMRKFaE
eInHqOhHA2DK0o8b7aAmYMBTTlj6F/eTUSpJhPauSP9bNLwKEvJS2A0nmrJ35UnhgrWnVSOmlkhU
J4lAMe5oYoiw/Phjxphs3zigkK3u0L01Wv0=
    """


@pytest.fixture
def privkey_pkcs12():
    return """
MIIFVAIBAzCCBQoGCSqGSIb3DQEHAaCCBPsEggT3MIIE8zCCBO8GCSqGSIb3DQEHAaCCBOAEggTc
MIIE2DCCBNQGCyqGSIb3DQEMCgEBoIIEwzCCBL8CAQAwDQYJKoZIhvcNAQEBBQAEggSpMIIEpQIB
AAKCAQEApAp8BJgczXoTKTeH3swElA39gCRNzY8KxcK/dMoev/6Ba9ZWksviZvRVKcAHfi60cyK7
LKK4fhe6ttfFtUuCsG3JpDM/rp3MM71hSUvSUiGeJxyqefBavWmPc//dYh1KveAAYhkjy+jEkOKY
x3U76pt8PTcIn4RX2Pad6WDGmOMhDlmeDHVH1RLpoMhABQeFrcAXLVLUFf4ZKXv3poI4rx9bzMRE
6yTBr1Sb6RBPPohiJPYqNfEc14SJjMWecDe7T0ADYMXfLKFDVc7ZTcw/sMBmwMjwcZY6yHDbPkt2
IFwcfChtMO2J8/22KPfJ/62jC+jCkhDRW3PwjZ0VrEeG7QIDAQABAoIBAAgYll9ZrI49mKV/np6R
3iX6fMjuwcJD7YmuH2nhsdvS8UtDtFkhY+al53AckKIbJv/Jtogw7b8XZ7kvdAwLEoOnn3yRpPJ2
ykXBcoQ+ED7KdvZCNW24PZo8k/5rId9+R5qQbCRrTjd5oP3vmQ+7Cv58twiEZ1IMI5PLNCb5BkQ0
WUpSQOVVEINXgNXpJ459qrNqrvSOdAnHgvbI1N07DPYnBfUc5fHZTdfXqkySM28c99zyLExyGeax
ELNoAP9xJS4QRFjze/CMMLPzlRmv3jTA2l4W/lKQKtchK7VpbKZCWE7e9myxnRm2YtNSiMvsfMZD
PkllFfyBXB2wXY+8i/ECgYEAzkgQ4Utt7v/kt8LoTyJpW9+RWFibIh3bcf2mD8IdkmMjPv1XyPwC
octjpRIjXAn4XTGjFlcJUL2AzCMEPNN34/87n2otKSAeOUKG3mQGtLjoXa/1xwJ5BKQhL7A7mzqY
UrsNZytvFYIkTaYNTNKIEfiwykVWaPfZzdI4PFaTGzkCgYEAy5QaBgl9mrrSxC0Z9UQwIlvnZ6HB
Gy0o4udPiuPOafiQvcirC4a4F6XFV9rNxAxxZDXYLtmwkKOnQ/b5+pFNJdlhZRf4XloQu1ApdwiP
7e512ChXqQ25ksyTgvxXouL+v0ATNEU0O0ZmFqg+pu33F4aIshXt3M6Ae4fe89dCZVUCgYEAr9qj
+UzSlVM1aqsQXJYbd6UqRUSUTAtkDtOMBBcaGrfFTmevtLmSjNfVRN4nosklIF22iM7+NAS5jk2z
yR8GMCpga9CaW1r0KSBb1a80QFD6VxQw1M142coKOJtm1Tiorq6kCHXwp0dhJ4kOAZXhRmDaZjWi
Kq5Q0bQLGPU9R5ECgYEAmKtMiNJ9O5h3j18zZFfqsRmzBGit5K+NRfyqDkKg/Z/HDEx82XwCetl6
kVQpk6ixMLGgmiHu48mXGsUQ2vQ0ovnOrH25aSip+482SWpGZey6u4wlkUYVsR1yUnzjS+hnmw12
WXC8puc4kC1ELvOuphniUYtYgorql7lhXgREarECgYEAq9s3JhME74yUZsPyoG59pYRhxeqSeDc2
23b/rmQSBnYpISRwY6yOMv2B1DbEb+Bv0fS+AbRRLEtO6jjEH471gWGpkbCbTwxg+AqX2U7wLxLF
SZoT1rGGgZW9n9NQtUniWaoYwCN4UAOJl37Z5XkX0toSrKDjuqA52zrLdIGbBHQwQTAxMA0GCWCG
SAFlAwQCAQUABCCB/CJRUI4ZVdHQqbynRnzzOCJCgTBYtxE9q7S310FSywQI/FISZYD6R5UCAggA
    """


@pytest.fixture
def privkey_pkcs12_enc():
    return """
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
AgIIAA==
    """


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.parametrize(
    "typ", ("pem", "pem_enc", "der", "der_enc", "pkcs12", "pkcs12_enc")
)
def test_load_privkey_direct(typ, request):
    passphrase = "foobar" if "enc" in typ else None
    data = request.getfixturevalue(f"privkey_{typ}")
    pk = x509.load_privkey(data, passphrase)
    assert isinstance(pk, rsa.RSAPrivateKey)


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.parametrize(
    "typ", ("pem", "pem_enc", "der", "der_enc", "pkcs12", "pkcs12_enc")
)
def test_load_privkey_file(typ, request, tmp_path):
    passphrase = "foobar" if "enc" in typ else None
    data = request.getfixturevalue(f"privkey_{typ}")
    dst = tmp_path / "pk"
    if "pem" in typ:
        dst.write_text(data)
    else:
        data = b64decode(data)
        dst.write_bytes(data)
    pk = x509.load_privkey(str(dst), passphrase)
    assert isinstance(pk, rsa.RSAPrivateKey)


@pytest.mark.parametrize("typ", ("pem", "der", "pkcs12"))
def test_load_privkey_enc_missing_passphrase(typ, request):
    data = request.getfixturevalue(f"privkey_{typ}_enc")
    with pytest.raises(
        x509.MissingPassword if typ != "pkcs12" else x509.InvalidPassword
    ):
        x509.load_privkey(data, passphrase=None)


@pytest.mark.parametrize("typ", ("pem", "der", "pkcs12"))
def test_load_privkey_enc_wrong_passphrase(typ, request):
    data = request.getfixturevalue(f"privkey_{typ}_enc")
    with pytest.raises(x509.InvalidPassword):
        x509.load_privkey(data, passphrase="barbaz")


@pytest.mark.parametrize("typ", ("pem", "der", "pkcs12"))
def test_load_privkey_enc_superfluous_passphrase(typ, request):
    data = request.getfixturevalue(f"privkey_{typ}")
    with pytest.raises(
        x509.SuperfluousPassword if typ != "pkcs12" else x509.InvalidPassword
    ):
        x509.load_privkey(data, passphrase="barbaz")


@pytest.mark.parametrize("pem", (False, True))
def test_load_privkey_unknown_data(pem):
    if pem:
        data = b"hi there" + x509.PEM_BEGIN + b"abcdefg"
    else:
        data = b"cafebabe"
    with pytest.raises(
        x509.PrivDeserializationError,
        match="Could not load PEM-encoded.*" if pem else "Could not deserialize.*",
    ):
        x509.load_privkey(data, passphrase=None)


@pytest.fixture
def cert_der():
    return """
MIICsjCCAZqgAwIBAgIUNOj75PQDR6VyFDtZlMT6Kye7PMkwDQYJKoZIhvcNAQELBQAwEzERMA8G
A1UEAwwIc2FsdHRlc3QwHhcNMjYwNjA1MTkyMTM2WhcNMjcwNjA1MTkyMTM2WjATMREwDwYDVQQD
DAhzYWx0dGVzdDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMsDE4/P+JY0UdnxcwfZ
fuOVYeoNIbz9kYrU+V/0o9qRSAy9IBZgUfsbQf+dI/sRQx5QzCt0zFbRqpXon9WhdDa5QgM0PQDU
kDhPuSWKi3Q5tBX/wGE0jg+n2F47Cf2+icDF17nxfzWU8TWADjVdaKZVp7ron6AFUuTh4n9EUaAc
o1rbLaKH2VP6xapQRQ8lUHBxs+Y9L62+a7clM+4g9eP2PBz6/dEC5Zb2uAiiHXNLVZlFkEFPXxtZ
yFkEly1fkvFTAYYZydElsnMk4kIDeknzz1QCWTgKK5ngHLoYyWUkScJ1yler3yHMX3EDWMkFARXn
DWW6HgtgC0UHfippHe0CAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAQzskBUFhJa+h9Ya/RuBYBhBY
N68exttzPChq9RUa0TJVMtVDrH9uylUBVYdDJhgu7Qz/LyH/pAMSPeKr372uCfbE9On3DKP09osN
92TVmxBvdhWyPgBvC0Zc/hMynK91LQi7wCSK815BmbQHh8wDMUS9ugv/2O+DY5g7vG3QuMWUiJ4P
bIXb3P4a0/llpBknRoXYrXNNmKVWyKBQxnD0V8/nlKXAflR0JDoD8eXCjxBryawSL1YGtEwZtYR8
e779DaEgad9mrZ6RCMXptUSHtrSAzkhzXeY17kEBBi8XqQztP6f1TCR+YeRIrFKC/aiLcmAsNUpA
O187t0XJt+NqIw==
    """


@pytest.fixture
def cert_pkcs7_der():
    return """
MIIC4QYJKoZIhvcNAQcCoIIC0jCCAs4CAQExADALBgkqhkiG9w0BBwGgggK2MIICsjCCAZqgAwIB
AgIUQ0FAo70+LAqzTQD9gDxmbsYYOv0wDQYJKoZIhvcNAQELBQAwEzERMA8GA1UEAwwIc2FsdHRl
c3QwHhcNMjYwNjA1MTkyMTU1WhcNMjcwNjA1MTkyMTU1WjATMREwDwYDVQQDDAhzYWx0dGVzdDCC
ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMsDE4/P+JY0UdnxcwfZfuOVYeoNIbz9kYrU
+V/0o9qRSAy9IBZgUfsbQf+dI/sRQx5QzCt0zFbRqpXon9WhdDa5QgM0PQDUkDhPuSWKi3Q5tBX/
wGE0jg+n2F47Cf2+icDF17nxfzWU8TWADjVdaKZVp7ron6AFUuTh4n9EUaAco1rbLaKH2VP6xapQ
RQ8lUHBxs+Y9L62+a7clM+4g9eP2PBz6/dEC5Zb2uAiiHXNLVZlFkEFPXxtZyFkEly1fkvFTAYYZ
ydElsnMk4kIDeknzz1QCWTgKK5ngHLoYyWUkScJ1yler3yHMX3EDWMkFARXnDWW6HgtgC0UHfipp
He0CAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAXAMecqN4g6cg5+YwC7h1cs0dR/Gy79EHLiGBtPsY
LUmWTyLv7uGEac79X3P67eh2OLMVgYNcPt/IUNLvgurAiti10m4XxpTpA+MAIfyGFMzjCzKoDjFm
BR7z70Zq8XfFw9sNSsoLN5kuIsFgTaFWzugvyf13epF/MxSJRZ9iy1imaNTonDSvtGNMhUUTSPke
xr4e9O5js9XcOb57CqAV8Zlw/JABnQWOoXOw6ijVlmPm9+7aM9+TwMo681IWsblOeoOjyGg3pMul
2tZBp9b38z8B8A0D0zAF5WGeCCXcdU/K8h+45EVcjzIKgAoEISSGm74Lw5AZ8NAV6Nv2Pw709jEA
    """


@pytest.fixture
def cert_pkcs7_pem():
    return """
-----BEGIN PKCS7-----
MIIC4QYJKoZIhvcNAQcCoIIC0jCCAs4CAQExADALBgkqhkiG9w0BBwGgggK2MIIC
sjCCAZqgAwIBAgIUdWOmdc1aLMnZEP1+ID0aikww4mswDQYJKoZIhvcNAQELBQAw
EzERMA8GA1UEAwwIc2FsdHRlc3QwHhcNMjYwNjA1MTkyMjEyWhcNMjcwNjA1MTky
MjEyWjATMREwDwYDVQQDDAhzYWx0dGVzdDCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBAMsDE4/P+JY0UdnxcwfZfuOVYeoNIbz9kYrU+V/0o9qRSAy9IBZg
UfsbQf+dI/sRQx5QzCt0zFbRqpXon9WhdDa5QgM0PQDUkDhPuSWKi3Q5tBX/wGE0
jg+n2F47Cf2+icDF17nxfzWU8TWADjVdaKZVp7ron6AFUuTh4n9EUaAco1rbLaKH
2VP6xapQRQ8lUHBxs+Y9L62+a7clM+4g9eP2PBz6/dEC5Zb2uAiiHXNLVZlFkEFP
XxtZyFkEly1fkvFTAYYZydElsnMk4kIDeknzz1QCWTgKK5ngHLoYyWUkScJ1yler
3yHMX3EDWMkFARXnDWW6HgtgC0UHfippHe0CAwEAATANBgkqhkiG9w0BAQsFAAOC
AQEAwtD4MlHfb3kR+sDSaHx6BzlXh4xyZ3OtXwL6oCsJcVng8/Jd3K1Q1Q2FYOvO
guywzNrcfqmQISd3Hvv018MGoTcPe9sqqBlNdQeiykfKsICOUwA4AxvNYOfaxm1s
BlTCOyL0bo0ScagvbWRTHBmtVZmuh3Wv2Mg+Tpbllr2Auer4ZSI8kSA4Jl4Lw2ne
S7ND79VWKqrXDb9dTQ49cDq6hkfkyZlPOgVdYPSv1AudvOWW3+a3yZQbPWxFTSO8
BgcDgFltvGJY/C0lRB4s7xeiZfJIKWope/WJPWWxSQ6HOAa6o/9b3uwzTZj6BT1J
4sB/JCzlaV9VLQdlTXOXJ1aS3DEA
-----END PKCS7-----
    """


@pytest.fixture
def cert_pkcs12():
    return """
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
8mRcM1YECIyxlZOmpDdJAgIIAA==
    """


@pytest.fixture
def cert_pkcs12_enc():
    return """
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
    """


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.parametrize(
    "typ", ("pem", "der", "pkcs7_der", "pkcs7_pem", "pkcs12", "pkcs12_enc")
)
def test_load_cert_direct(typ, request):
    passphrase = "foobar" if "enc" in typ else None
    data = request.getfixturevalue(f"cert_{typ}")
    crt = x509.load_cert(data, passphrase)
    assert isinstance(crt, cx509.Certificate)


@pytest.mark.skip_on_fips_enabled_platform
@pytest.mark.parametrize(
    "typ", ("pem", "der", "pkcs7_der", "pkcs7_pem", "pkcs12", "pkcs12_enc")
)
def test_load_cert_file(typ, request, tmp_path):
    passphrase = "foobar" if "enc" in typ else None
    data = request.getfixturevalue(f"cert_{typ}")
    dst = tmp_path / "pk"
    if "pem" in typ:
        dst.write_text(data)
    else:
        data = b64decode(data)
        dst.write_bytes(data)
    crt = x509.load_cert(data, passphrase)
    assert isinstance(crt, cx509.Certificate)


def test_load_cert_pkcs12_missing_passphrase(cert_pkcs12_enc):
    with pytest.raises(x509.InvalidPassword):
        x509.load_cert(cert_pkcs12_enc, passphrase=None)


def test_load_cert_pkcs12_wrong_passphrase(cert_pkcs12_enc):
    with pytest.raises(x509.InvalidPassword):
        x509.load_cert(cert_pkcs12_enc, passphrase="barbaz")


def test_load_cert_pkcs12_superfluous_passphrase(cert_pkcs12):
    with pytest.raises(x509.InvalidPassword):
        x509.load_cert(cert_pkcs12, passphrase="foobar")


def test_load_cert_unknown_data():
    data = b"cafebabe"
    with pytest.raises(
        x509.CertDeserializationError, match="Could not deserialize binary.*"
    ):
        x509.load_cert(data)


def test_load_cert_broken_pem(cert_pem):
    data = cert_pem[:33] + "#" + cert_pem[34:]
    with pytest.raises(
        x509.CertDeserializationError, match="Could not load PEM-encoded certificate"
    ):
        x509.load_cert(data)


def test_load_cert_broken_pkcs7_pem(cert_pkcs7_pem):
    data = cert_pkcs7_pem[:33] + "#" + cert_pkcs7_pem[34:]
    with pytest.raises(
        x509.CertDeserializationError, match="Could not load PEM-encoded PKCS.*"
    ):
        x509.load_cert(data)
