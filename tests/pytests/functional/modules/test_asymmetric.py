import base64
import logging
from pathlib import Path
from textwrap import dedent

import pytest

from salt.exceptions import CommandExecutionError, SaltInvocationError

util = pytest.importorskip("salt.utils.asymmetric")


@pytest.fixture(params=(False,))
def signed_data(request, tmp_path):
    data = "I am an important message"
    if request.param:
        with pytest.helpers.temp_file("signed_data", data, tmp_path) as f:
            yield str(f)
    else:
        yield data


@pytest.fixture
def priv_rsa():
    return dedent(
        """
        -----BEGIN PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5f9OHbgZcXzqx
        ZfH5DSicaYCTreYBGt+gQAClufIdrl+Tu147o2/tXJQNFWjvyl+FJXaDYTj2PdZp
        fdPNWw4k7v5ndqwVdevZGD/nrjzd9eX0WXN/OPPKmnLe7pVYOO179jKEGWIgbewv
        B9VhNodvYLbGmgHSDA9ijytzhTV7gJEswN89vhi0ovVR3uyEOYDXvWCkkG5UIdJz
        cKa8DHRLd+JoaZ5E5i3VtUgqn8wVQzW8CK8FcM/GdYMmcbHf5YNaWCZ5DZlM+83h
        ggUNrnsIao0x5LjFQ9uKgbLUvJnQBRmI+nKd5xhyMtwMidTxMj5Qlr0E3jlRBI1k
        JlT+BDCbAgMBAAECggEAAR8sn74++RJxiFVH7vG4kwDeF+wugJLL8TseFtNrXhYN
        uI9e8/S6gjoMXK9OFBA1nud6l/dyk6YrM5+zu7JzW3nhOa3VP3WBbEvgKDwTTb5S
        cPGy1THrW4DrEzY7JfmjVVCMGQLwhUw2wpQMwUMga8frROz1UoHUk0gnt7snOuje
        sIZCUlXi9yyRu00upFjKpPCONO5lp6ipTCxMZeD6cLw4SNE893kmmJXv0wVIKvhA
        PSqxPGas74h/+7x4/jrVNnuai8YYIMHtQd60YVoWOLV4l3s8m12HARaOUzyMTG/m
        vBAYx+4vCyNCGb+m7S+fDzaQdlsY+qsnE3RL9q6kAQKBgQDueHZLc1JgoahxWM26
        9ZhHZKAFclOQOVMgHPAfFEpmetrIgIZk9qiHaCIyo8sGSN2PLBwwS/Gc1/FikldS
        ACcsOC8w7Zfha4n1tyWvxY1btnbim1YPUDg1ciJuVTOh8vc949pLmyjKUZBvhZTZ
        qah416upxCv7I2hdsKRE1IicmwKBgQDHIo0/CTBr3xJ535bc8I0XlB5Oed6jXUSD
        Z83rpFx+IILotu8MFiOxH4wElr1vZz8VJYWH6paYm6F82hoEdQeFMKQf4DIq1tPO
        6WSC/icipM+y3TBuXTEtqtjRFeRr7siEj8kb11r7EaPYyw3Z2jEjcvfJHdV++tte
        QOrfN6n8AQKBgACfSde6jk14PoNFMww41dPh3FUHTlaC/8eGq8249NS9n1KEm1Uq
        G5h22hf9u2rhx8o22D/8Ar5hBd02+olZPMDtyJm9FPdem3aLqsqBnnPNzxOaSigy
        EmN5T8Ov7zmN870ymgA2gG2+trzDwXar7aebEHSZ8W9vUTdlXZhcYZrfAoGBAIzM
        b1Y8pxH+fc/SOZcqNniPcAZIwRR9I65NvRl58zPyxNzKS6ceGEpqZdPwySx1sfK/
        vvRk9+obUEk45OB15sVTqRgoqxADKWvJNhownXcvVPPA1TeTiOwjOn5LnmB6Syj/
        iVC4KkoPJOxqVfbNAaVw6qY3A/duY6D3AZqmfvgBAoGAQ6OyxYh6kAkGDZi8ITkc
        8i7Eqjb9C+DMURmaycXGm/9Ft11PQDjNIkJA1tiYKacs4v7ELk/dv5swvgOHthZi
        GqcVceAozUEluAj/crlD+IuwD4ohlW0HMqtoHtgsEg02n5q52e3ubmEqJzoeFTJf
        ofJwPHKSkcvnRSH9ZQFbhqo=
        -----END PRIVATE KEY-----
        """
    ).strip()


@pytest.fixture
def pub_rsa():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuX/Th24GXF86sWXx+Q0o
        nGmAk63mARrfoEAApbnyHa5fk7teO6Nv7VyUDRVo78pfhSV2g2E49j3WaX3TzVsO
        JO7+Z3asFXXr2Rg/56483fXl9Flzfzjzyppy3u6VWDjte/YyhBliIG3sLwfVYTaH
        b2C2xpoB0gwPYo8rc4U1e4CRLMDfPb4YtKL1Ud7shDmA171gpJBuVCHSc3CmvAx0
        S3fiaGmeROYt1bVIKp/MFUM1vAivBXDPxnWDJnGx3+WDWlgmeQ2ZTPvN4YIFDa57
        CGqNMeS4xUPbioGy1LyZ0AUZiPpynecYcjLcDInU8TI+UJa9BN45UQSNZCZU/gQw
        mwIDAQAB
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_rsa():
    return dedent(
        """
        JQcgQPkK4ys7Nfipn/lZvVvXd4xSRKhgd+Z/zmwB25z9uAXLFB0nVUgIUUk+r2eP8H7LX9lWqNO3
        hNRwkEaEijnnCILW8YezgBXpmKccG7Or50Us3okp52aTvxrCb0BK7CA0h/Tg+aRxNYmM+3RAgttk
        QGSKEkEHHZ2X0DEr8BDPb2bm27ghy5HPYB7DeFb+vJBWn2gCHbIaXy3nNCahApU+UnstdB6Cbe78
        A3TmOoPSVsdekV31FYztb3RBsjnlx76/t2zZ7B9BH1HsbFkz4fSblWJR+W36vg9gpKH4Ife82NlM
        YOhJapxsaXtAfxDlwMGk7NUacj66d0EJ+NJpUg==
        """
    ).strip()


@pytest.fixture
def priv_ec():
    return dedent(
        """
        -----BEGIN PRIVATE KEY-----
        MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgv25d59EOFqxFC07k
        Vzlc+7wOwBjTRYxuvMrcVqEeG3WhRANCAAQAJcGq7ad0wtRL9nRf98pQYCBFR96d
        gGJ7d6vD9A05h9CmAMiM277rFXEwtFG9JgatDYlETBRVdHRJHmkRECeh
        -----END PRIVATE KEY-----
        """
    ).strip()


@pytest.fixture
def priv_ec_enc():
    return dedent(
        """
    -----BEGIN ENCRYPTED PRIVATE KEY-----
    MIHsMFcGCSqGSIb3DQEFDTBKMCkGCSqGSIb3DQEFDDAcBAg2tWHDgK+VvQICCAAw
    DAYIKoZIhvcNAgkFADAdBglghkgBZQMEASoEEP1nD6+tv5dFqdeEPh+FYPcEgZAq
    K7gUEvPm68aprE0jLURTIzB8VlJBpwZMYtWdBH2XBOIVjUms/rOaQvw7JDy3DaOq
    w7lpslo2twZj5rkyueXQkULyhMdg9nA2kIjZckApMPvKClRZtVmt9erMrhlstKYw
    IY2Nc2sYZeohwoifb+n2vMTg/rCVCCce40KDX5jdxQR7AwAHeL8shosqM4xpvtQ=
    -----END ENCRYPTED PRIVATE KEY-----
        """
    ).strip()


@pytest.fixture
def pub_ec():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEACXBqu2ndMLUS/Z0X/fKUGAgRUfe
        nYBie3erw/QNOYfQpgDIjNu+6xVxMLRRvSYGrQ2JREwUVXR0SR5pERAnoQ==
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ec():
    return dedent(
        """
        MEYCIQDwWw2fvPO/ZtE+ezTS4voFoEHmg73ehTXwOfPwIygSJAIhAKnWM9PrXxVLTKE0JTogjz8HVXKn2cTD9ozlnnHWQzbS
        """
    ).strip()


@pytest.fixture
def sig_ec_sha512():
    return dedent(
        """
        MEUCIQDu+3SngDQQhxnYGUyFhiiqYfVFKSWnNWfXXW8dmFe0FgIgXo5KByO0h6q8cyz6reQ4GTseWhn6Df+1UpACCCFiGIQ=
        """
    ).strip()


@pytest.fixture
def priv_ed25519():
    return dedent(
        """
        -----BEGIN PRIVATE KEY-----
        MC4CAQAwBQYDK2VwBCIEIO6BM6CnCIbOI4WvxFYys+QYjrFZLyrQYRxTqnYZLuEm
        -----END PRIVATE KEY-----
        """
    ).strip()


@pytest.fixture
def pub_ed25519():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MCowBQYDK2VwAyEAC5+5Ei58lozexyPknspZWwdONLxJFgKEHwmxpFsc+4k=
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ed25519():
    return dedent(
        """
        Lo6RH3psCiop68Ryvb8b/Hf3Hkkr2CwBDBoIvuCU22n2rOz3XMJTfQL7FNqsQBhQparsy8zfq4XFf3K2YhQvBQ==
        """
    ).strip()


@pytest.fixture
def priv_ed448():
    return dedent(
        """
        -----BEGIN PRIVATE KEY-----
        MEcCAQAwBQYDK2VxBDsEOeHr/G4AyIHMuzQRY4rqX2Z52aE7QebFN1TZZUlHpt30
        taTKZ5B3zV+HEXUtBwPXQLl5Zz1+PKfNCQ==
        -----END PRIVATE KEY-----
        """
    ).strip()


@pytest.fixture
def pub_ed448():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MEMwBQYDK2VxAzoAaI9rB2S21l+PWK7KznH4O1G9sjsyzMeIRGolsN4/f9B+gKOh
        E+WnN/+tA0YoN+n8GluwOlss1cOA
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ed448():
    return dedent(
        """
        oQj3viRXHfZdH655AF3Q9j18lHecXdRQf85QKVJo0FHz6ycM/cZ3ptEuMpi3MMYJDHv7MHwcTaQA6/5lRoVMARDaqmaBCHeer+j12KOu/uCK0iuSTvLFN7XmTIC2i0pX6RRE4pVLPo85ELHfE2tovy8A
        """
    ).strip()


@pytest.fixture
def asymm(modules):
    return modules.asymmetric


@pytest.mark.parametrize("signed_data", (False, True), indirect=True)
@pytest.mark.parametrize(
    "algo",
    (
        "rsa",
        "ec",
        pytest.param("ed25519", marks=pytest.mark.skip_on_fips_enabled_platform),
        pytest.param("ed448", marks=pytest.mark.skip_on_fips_enabled_platform),
    ),
)
def test_sign(algo, signed_data, request, asymm):
    privkey = request.getfixturevalue(f"priv_{algo}")
    filename = text = None
    if signed_data.startswith("/"):
        filename = signed_data
        data = Path(filename).read_bytes()
    else:
        text = signed_data
        data = text.encode()
    res = asymm.sign(privkey, filename=filename, text=text)
    pubkey = request.getfixturevalue(f"pub_{algo}")
    util.verify(pubkey, res, data)


def test_sign_encrypted_privkey(priv_ec_enc, pub_ec, signed_data, asymm):
    res = asymm.sign(priv_ec_enc, text=signed_data, passphrase="hunter1")
    util.verify(pub_ec, res, signed_data)


@pytest.mark.parametrize("algo", ("rsa", "ec"))
def test_sign_digest(algo, signed_data, request, asymm):
    privkey = request.getfixturevalue(f"priv_{algo}")
    res = asymm.sign(privkey, text=signed_data, digest="sha512")
    pubkey = request.getfixturevalue(f"pub_{algo}")
    with pytest.raises(util.InvalidSignature):
        util.verify(pubkey, res, signed_data)
    util.verify(pubkey, res, signed_data, digest="sha512")


@pytest.mark.parametrize("raw", (False, True))
def test_sign_raw(raw, priv_ec, signed_data, asymm):
    res = asymm.sign(priv_ec, text=signed_data, raw=raw)
    assert isinstance(res, bytes) is raw
    assert isinstance(res, str) is not raw


@pytest.mark.parametrize("raw", (False, True))
def test_sign_path(raw, priv_ec, signed_data, tmp_path, asymm):
    out = tmp_path / "out"
    res = asymm.sign(priv_ec, text=signed_data, raw=raw, path=str(out))
    assert str(out) in res
    data = out.read_bytes()
    try:
        data.decode()
        unicode = True
    except UnicodeDecodeError:
        unicode = False
    assert raw is not unicode


def test_sign_bytes(priv_ec, pub_ec, signed_data, asymm):
    res = asymm.sign(priv_ec, text=signed_data.encode())
    util.verify(pub_ec, res, signed_data.encode())


@pytest.mark.parametrize("signed_data", (False, True), indirect=True)
@pytest.mark.parametrize(
    "algo",
    (
        "rsa",
        "ec",
        pytest.param("ed25519", marks=pytest.mark.skip_on_fips_enabled_platform),
        pytest.param("ed448", marks=pytest.mark.skip_on_fips_enabled_platform),
    ),
)
def test_verify(algo, signed_data, request, asymm):
    pubkey = request.getfixturevalue(f"pub_{algo}")
    sig = request.getfixturevalue(f"sig_{algo}")
    filename = text = None
    if signed_data.startswith("/"):
        filename = signed_data
    else:
        text = signed_data
    res = asymm.verify(pubkey=pubkey, filename=filename, text=text, signature=sig)
    assert isinstance(res, dict)
    assert res["res"] is True
    assert "is valid" in res["message"]


def test_verify_pub_sig_from_url(pub_ec, sig_ec, signed_data, state_tree, asymm):
    with pytest.helpers.temp_file("pub_ec.pem", pub_ec, state_tree):
        with pytest.helpers.temp_file("sig_ec", sig_ec, state_tree):
            res = asymm.verify(
                text=signed_data, pubkey="salt://pub_ec.pem", signature="salt://sig_ec"
            )
    assert res["res"] is True
    assert "is valid" in res["message"]


def test_verify_pub_sig_from_file_url(
    pub_ec, sig_ec, signed_data, state_tree, tmp_path, asymm
):
    sig = tmp_path / "sig"
    pub = tmp_path / "pub"
    sig.write_bytes(sig_ec.encode())
    pub.write_bytes(pub_ec.encode())
    res = asymm.verify(
        text=signed_data, pubkey=f"file://{pub}", signature=f"file://{sig}"
    )
    assert res["res"] is True
    assert "is valid" in res["message"]


def test_verify_pub_from_url_notfound(pub_ec, sig_ec, signed_data, state_tree, asymm):
    with pytest.helpers.temp_file("sig_ec", sig_ec, state_tree):
        res = asymm.verify(
            text=signed_data, pubkey="salt://pub_ec.pem", signature="salt://sig_ec"
        )
    assert res["res"] is False
    assert "Failed fetching" in res["message"]


def test_verify_sig_from_url_notfound(pub_ec, sig_ec, signed_data, state_tree, asymm):
    with pytest.helpers.temp_file("pub_ec.pem", pub_ec, state_tree):
        res = asymm.verify(
            text=signed_data, pubkey="salt://pub_ec.pem", signature="salt://sig_ec"
        )
    assert res["res"] is False
    assert "Failed fetching" in res["message"]


def test_verify_bytes(pub_ec, sig_ec, signed_data, asymm):
    sig = base64.b64decode(sig_ec)
    res = asymm.verify(text=signed_data.encode(), pubkey=pub_ec, signature=sig)
    assert res["res"] is True


def test_verify_fail_wrong_data(pub_ec, sig_ec, signed_data, asymm):
    signed_data += "!"
    res = asymm.verify(pubkey=pub_ec, signature=sig_ec, text=signed_data)
    assert res["res"] is False
    assert "Invalid signature" in res["message"]


@pytest.mark.parametrize(
    "algo",
    (
        "rsa",
        "ec",
        pytest.param("ed25519", marks=pytest.mark.skip_on_fips_enabled_platform),
        pytest.param("ed448", marks=pytest.mark.skip_on_fips_enabled_platform),
    ),
)
def test_verify_fail_wrong_pubkey(algo, signed_data, request, modules, asymm):
    sig = request.getfixturevalue(f"sig_{algo}")
    pub = modules.x509.get_public_key(modules.x509.create_private_key(algo))
    res = asymm.verify(pubkey=pub, signature=sig, text=signed_data)
    assert res["res"] is False
    assert "Invalid signature" in res["message"]


@pytest.mark.parametrize("raw", (False, True))
@pytest.mark.parametrize(
    "algo",
    (
        "rsa",
        "ec",
        pytest.param("ed25519", marks=pytest.mark.skip_on_fips_enabled_platform),
        pytest.param("ed448", marks=pytest.mark.skip_on_fips_enabled_platform),
    ),
)
def test_verify_signature_from_file(raw, algo, signed_data, request, asymm, tmp_path):
    pubkey = request.getfixturevalue(f"pub_{algo}")
    sig = request.getfixturevalue(f"sig_{algo}")
    sig_path = tmp_path / "sig"
    if raw:
        sig_data = base64.b64decode(sig)
    else:
        sig_data = sig.encode()
    sig_path.write_bytes(sig_data)

    res = asymm.verify(pubkey=pubkey, text=signed_data, signature=str(sig_path))
    assert isinstance(res, dict)
    assert res["res"] is True
    assert "is valid" in res["message"]


def test_verify_digest(pub_ec, signed_data, sig_ec_sha512, asymm):
    res = asymm.verify(
        pubkey=pub_ec, text=signed_data, signature=sig_ec_sha512, digest="sha512"
    )
    assert isinstance(res, dict)
    assert res["res"] is True
    assert "is valid" in res["message"]


@pytest.fixture
def pub_ec1():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEsxSmSTxtsNiCKtHru74H7L+62nF6
        qGgyw6gGkTBkh56GCPXfhLk7yR67aypZncncWMcJSTPYSo3jSVNEfxAHhw==
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ec1():
    return dedent(
        """
        MEYCIQCgd+u3FHFrVCFxOgiUtGWeBnB38Vf9U8DkW/A2yqZhoQIhAIFFANHzHqjoTQcCazyCx8imEmchVCPssF9m5FRSnLxD
        """
    ).strip()


@pytest.fixture
def pub_ec2():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAErtBZ3qL5m97SzlSwOoxFzzG/1v5a
        sLzOIrXykh4yO8tDn4h6JMOe+P0HuoUbENxk4+f/1D9hTEI88rj70bi7Ig==
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ec2():
    return dedent(
        """
        MEUCIQDRcivGIrzfFv0bZaLpP7cG3DOucRTIcAObez12H9dpuQIgHt56uSCHJqJK8J0EHLOjeunffAyM2Vllnv6zhZPKFjA=
        """
    ).strip()


@pytest.fixture
def pub_ec3():
    return dedent(
        """
        -----BEGIN PUBLIC KEY-----
        MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE/cuKGCA0Kj8YBEmBxKtj+jg4Hpy5
        OCN5s7cYUVq3Cl/dVObv3ZbBv7ttct4tWd25f4g46cpIjDwoUXP6IRwKYg==
        -----END PUBLIC KEY-----
        """
    ).strip()


@pytest.fixture
def sig_ec3():
    return dedent(
        """
        MEQCIG5IPYRuQSykJYkp3wm9K4dxI12u/raQ1VSGoMP+iEtFAiB0f6NZh7QLlB+OazGUdrgdiQo/YXeQf6zrHOAYNQ0iOg==
        """
    ).strip()


@pytest.fixture
def sig_notasig():
    return "chaos is a ladder"


@pytest.mark.parametrize("signed_data", (False, True), indirect=True)
@pytest.mark.parametrize(
    "sig,by,expected",
    [
        (["ec1"], ["ec1", "ec2"], True),
        (["ec1", "ec3"], ["ec1", "ec2"], True),
        (["ec1", "ec3"], ["ec2", "ec3"], True),
        (["ec1"], ["ec2", "ec3"], False),
        (["notasig"], ["ec1", "ec2", "ec3"], False),
        (["notasig", "ec2"], ["ec1", "ec2"], True),
        pytest.param(
            ["ec2", "rsa", "ed25519", "ed448"],
            ["ec1", "ec2"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ec2", "ed448"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ec2", "rsa"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ec2", "ed25519"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed448"],
            ["ec2", "ed25519"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519"],
            ["ec2", "ed448"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "ed25519", "ed448"],
            ["ec2", "rsa"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec2", "rsa", "ed25519", "ed448"],
            ["ec1"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec", "rsa", "ed25519", "ed448"],
            ["ec1", "ec2", "ec3"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
    ],
)
def test_verify_signed_by_any(signed_data, sig, by, expected, request, asymm):
    sigs = [request.getfixturevalue(f"sig_{key}") for key in sig]
    keys = [request.getfixturevalue(f"pub_{key}") for key in by]
    filename = text = None
    if signed_data.startswith("/"):
        filename = signed_data
    else:
        text = signed_data
    res = asymm.verify(
        filename=filename,
        text=text,
        signature=sigs,
        signed_by_any=keys,
    )
    assert res["res"] is expected


def test_verify_signed_by_any_url(
    state_tree, signed_data, sig_ec, sig_rsa, pub_rsa, pub_ec, asymm
):
    with pytest.helpers.temp_file("pub_rsa.pem", pub_rsa, state_tree):
        with pytest.helpers.temp_file("sig_rsa", sig_rsa, state_tree):
            res = asymm.verify(
                text=signed_data,
                signature=[sig_ec, "salt://sig_rsa"],
                signed_by_any=["salt://pub_rsa.pem", pub_ec],
            )
    assert res["res"] is True
    assert "All required keys have provided a signature" in res["message"]


def test_verify_signed_by_any_sig_url_fail(
    state_tree, signed_data, sig_ec, sig_rsa, pub_rsa, pub_ec, asymm
):
    with pytest.helpers.temp_file("pub_rsa.pem", pub_rsa, state_tree):
        res = asymm.verify(
            text=signed_data,
            signature=[sig_ec, "salt://sig_rsa"],
            signed_by_any=["salt://pub_rsa.pem", pub_ec],
        )
    assert res["res"] is True
    assert "All required keys have provided a signature" in res["message"]


def test_verify_signed_by_any_pub_url_fail(
    state_tree, signed_data, sig_ec, sig_rsa, pub_rsa, pub_ec, asymm
):
    with pytest.helpers.temp_file("sig_rsa", sig_rsa, state_tree):
        res = asymm.verify(
            text=signed_data,
            signature=[sig_ec, "salt://sig_rsa"],
            signed_by_any=["salt://pub_rsa.pem", pub_ec],
        )
    assert res["res"] is True
    assert "All required keys have provided a signature" in res["message"]


def test_verify_sig_url_all_fail(state_tree, signed_data, pub_rsa, pub_ec, asymm):
    with pytest.raises(CommandExecutionError, match="Unable to locate .* signatures"):
        asymm.verify(
            text=signed_data,
            signature=["salt://sig_ec", "salt://sig_rsa"],
            signed_by_any=[pub_rsa, pub_ec],
        )


def test_verify_pub_url_all_fail(
    state_tree, signed_data, sig_rsa, sig_ec, asymm, caplog
):
    with caplog.at_level(logging.ERROR):
        res = asymm.verify(
            text=signed_data,
            signature=[sig_ec, sig_rsa],
            signed_by_any=["salt://pub_ec", "salt://pub_rsa"],
        )
    assert res["res"] is False
    for src in ("pub_ec", "pub_rsa"):
        assert f"Failed fetching 'salt://{src}'" in caplog.text


@pytest.mark.parametrize("signed_data", (False, True), indirect=True)
@pytest.mark.parametrize(
    "sig,by,expected",
    [
        (["ec1"], ["ec1"], True),
        (["ec1", "ec2"], ["ec3"], False),
        (["ec1", "ec2"], ["ec1", "ec2"], True),
        (["ec1", "ec2"], ["ec2", "ec1"], True),
        (["ec1", "ec2"], ["ec2", "ec1", "ec3"], False),
        (["ec1", "ec2", "notasig"], ["ec2", "ec1"], True),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ed448", "ec2"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ed25519", "ec2"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["rsa", "ec2"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ec1", "ec2"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448", "ec"],
            ["rsa", "ed448", "ed25519", "ec1"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448", "ec"],
            ["rsa", "ed448", "ed25519", "ec2"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ed448", "ec1", "rsa", "ed25519"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448"],
            ["ed25519", "rsa", "ec1"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "rsa", "ed25519", "ed448", "notasig"],
            ["ed25519", "rsa", "ec1"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
    ],
)
def test_verify_signed_by_all(signed_data, sig, by, expected, request, asymm):
    sigs = [request.getfixturevalue(f"sig_{key}") for key in sig]
    keys = [request.getfixturevalue(f"pub_{key}") for key in by]
    filename = text = None
    if signed_data.startswith("/"):
        filename = signed_data
    else:
        text = signed_data
    res = asymm.verify(
        filename=filename,
        text=text,
        signature=sigs,
        signed_by_all=keys,
    )
    assert res["res"] is expected


@pytest.mark.parametrize("signed_data", (False, True), indirect=True)
@pytest.mark.parametrize(
    "sig,any_by,all_by,expected",
    [
        (["ec1", "ec2"], ["ec2", "ec3"], ["ec1"], True),
        (["ec1", "ec2"], ["ec", "ec3"], ["ec1", "ec2"], False),
        (["ec1", "ec2"], ["ec1", "ec3"], ["ec2", "ec3"], False),
        (["ec1", "ec2", "ec3"], ["ec1", "ec3"], ["ec2", "ec3"], True),
        pytest.param(
            ["ec1", "ec2", "ec3", "rsa", "ed25519", "ed448"],
            ["ec", "rsa"],
            ["ed25519", "ed448", "ec2"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "ec2", "ec3", "rsa", "ed25519", "ed448"],
            ["ec"],
            ["ed25519", "ed448", "ec2", "rsa"],
            False,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
        pytest.param(
            ["ec1", "ec2", "ec3", "rsa", "ed25519", "ed448"],
            ["ec", "ec2"],
            ["ed25519", "ed448", "ec2", "rsa"],
            True,
            marks=pytest.mark.skip_on_fips_enabled_platform,
        ),
    ],
)
def test_verify_signed_by_any_and_all(
    signed_data, sig, any_by, all_by, expected, request, asymm
):
    sigs = [request.getfixturevalue(f"sig_{key}") for key in sig]
    any_keys = [request.getfixturevalue(f"pub_{key}") for key in any_by]
    all_keys = [request.getfixturevalue(f"pub_{key}") for key in all_by]
    filename = text = None
    if signed_data.startswith("/"):
        filename = signed_data
    else:
        text = signed_data
    res = asymm.verify(
        filename=filename,
        text=text,
        signature=sigs,
        signed_by_any=any_keys,
        signed_by_all=all_keys,
    )
    assert res["res"] is expected


def test_signed_by_any_notalist(pub_ec, sig_ec, signed_data, asymm):
    res = asymm.verify(text=signed_data, signature=sig_ec, signed_by_any=pub_ec)
    assert res["res"] is True


def test_signed_by_all_notalist(pub_ec, sig_ec, signed_data, asymm):
    res = asymm.verify(text=signed_data, signature=sig_ec, signed_by_all=pub_ec)
    assert res["res"] is True


@pytest.mark.parametrize(
    "params,err",
    [
        (
            ("text", "filename", "pubkey", "signature"),
            "`text` and `filename` arguments are mutually exclusive",
        ),
        (
            ("text", "pubkey"),
            "Missing `signature` parameter",
        ),
        (
            ("text", "signature"),
            r"Missing pubkey\(s\) to check against",
        ),
        (
            ("signature", "pubkey"),
            "Missing data to verify.*",
        ),
        (
            ("text", "pubkey", "signed_by_all", "signature"),
            r"Either specify pubkey \+ signature or signed_by_\(any\|all\)",
        ),
        (
            ("text", "pubkey", "signed_by_any", "signature"),
            r"Either specify pubkey \+ signature or signed_by_\(any\|all\)",
        ),
    ],
)
def test_verify_parameter_validation(
    params, err, signed_data, pub_ec, sig_ec, tmp_path, asymm
):
    kwargs = {}
    if "text" in params:
        kwargs["text"] = sig_ec
    if "filename" in params:
        data = tmp_path / "data"
        data.write_text(signed_data)
        kwargs["filename"] = str(data)
    if "pubkey" in params:
        kwargs["pubkey"] = pub_ec
    if "signature" in params:
        kwargs["signature"] = sig_ec
    if "signed_by_any" in params:
        kwargs["signed_by_any"] = [pub_ec]
    if "signed_by_all" in params:
        kwargs["signed_by_all"] = [pub_ec]
    with pytest.raises(SaltInvocationError, match=err):
        asymm.verify(**kwargs)


def test_verify_single_pubkey_no_signature_list(pub_ec, sig_ec, signed_data, asymm):
    with pytest.raises(
        SaltInvocationError,
        match=".*must be a string or bytes when verifying a single.*",
    ):
        asymm.verify(text=signed_data, pubkey=pub_ec, signature=[sig_ec])


def test_verify_missing_filename(pub_ec, sig_ec, tmp_path, asymm):
    with pytest.raises(CommandExecutionError, match="Path .*does not exist.*"):
        asymm.verify(
            filename=str(tmp_path / "missing"), pubkey=pub_ec, signature=sig_ec
        )
