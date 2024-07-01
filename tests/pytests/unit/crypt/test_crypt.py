"""
tests.pytests.unit.test_crypt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unit tests for salt's crypt module
"""

import uuid

import pytest

import salt.crypt
import salt.master
import salt.utils.files
from tests.conftest import FIPS_TESTRUN

PRIV_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAoAsMPt+4kuIG6vKyw9r3+OuZrVBee/2vDdVetW+Js5dTlgrJ
aghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLnyHNJ/HpVhMG0M07MF6FMfILtDrrt8
ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+fu6HYwu96HggmG2pqkOrn3iGfqBvV
YVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpef8vRUrNicRLc7dAcvfhtgt2DXEZ2
d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvTIIPQIjR8htFxGTz02STVXfnhnJ0Z
k8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cYOwIDAQABAoIBABZUJEO7Y91+UnfC
H6XKrZEZkcnH7j6/UIaOD9YhdyVKxhsnax1zh1S9vceNIgv5NltzIsfV6vrb6v2K
Dx/F7Z0O0zR5o+MlO8ZncjoNKskex10gBEWG00Uqz/WPlddiQ/TSMJTv3uCBAzp+
S2Zjdb4wYPUlgzSgb2ygxrhsRahMcSMG9PoX6klxMXFKMD1JxiY8QfAHahPzQXy9
F7COZ0fCVo6BE+MqNuQ8tZeIxu8mOULQCCkLFwXmkz1FpfK/kNRmhIyhxwvCS+z4
JuErW3uXfE64RLERiLp1bSxlDdpvRO2R41HAoNELTsKXJOEt4JANRHm/CeyA5wsh
NpscufUCgYEAxhgPfcMDy2v3nL6KtkgYjdcOyRvsAF50QRbEa8ldO+87IoMDD/Oe
osFERJ5hhyyEO78QnaLVegnykiw5DWEF02RKMhD/4XU+1UYVhY0wJjKQIBadsufB
2dnaKjvwzUhPh5BrBqNHl/FXwNCRDiYqXa79eWCPC9OFbZcUWWq70s8CgYEAztOI
61zRfmXJ7f70GgYbHg+GA7IrsAcsGRITsFR82Ho0lqdFFCxz7oK8QfL6bwMCGKyk
nzk+twh6hhj5UNp18KN8wktlo02zTgzgemHwaLa2cd6xKgmAyuPiTgcgnzt5LVNG
FOjIWkLwSlpkDTl7ZzY2QSy7t+mq5d750fpIrtUCgYBWXZUbcpPL88WgDB7z/Bjg
dlvW6JqLSqMK4b8/cyp4AARbNp12LfQC55o5BIhm48y/M70tzRmfvIiKnEc/gwaE
NJx4mZrGFFURrR2i/Xx5mt/lbZbRsmN89JM+iKWjCpzJ8PgIi9Wh9DIbOZOUhKVB
9RJEAgo70LvCnPTdS0CaVwKBgDJW3BllAvw/rBFIH4OB/vGnF5gosmdqp3oGo1Ik
jipmPAx6895AH4tquIVYrUl9svHsezjhxvjnkGK5C115foEuWXw0u60uiTiy+6Pt
2IS0C93VNMulenpnUrppE7CN2iWFAiaura0CY9fE/lsVpYpucHAWgi32Kok+ZxGL
WEttAoGAN9Ehsz4LeQxEj3x8wVeEMHF6OsznpwYsI2oVh6VxpS4AjgKYqeLVcnNi
TlZFsuQcqgod8OgzA91tdB+Rp86NygmWD5WzeKXpCOg9uA+y/YL+0sgZZHsuvbK6
PllUgXdYxqClk/hdBFB7v9AQoaj7K9Ga22v32msftYDQRJ94xOI=
-----END RSA PRIVATE KEY-----
"""


PUB_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoAsMPt+4kuIG6vKyw9r3
+OuZrVBee/2vDdVetW+Js5dTlgrJaghWWn3doGmKlEjqh7E4UTa+t2Jd6w8RSLny
HNJ/HpVhMG0M07MF6FMfILtDrrt8ZX7eDVt8sx5gCEpYI+XG8Y07Ga9i3Hiczt+f
u6HYwu96HggmG2pqkOrn3iGfqBvVYVFJzSZYe7e4c1PeEs0xYcrA4k+apyGsMtpe
f8vRUrNicRLc7dAcvfhtgt2DXEZ2d72t/CR4ygtUvPXzisaTPW0G7OWAheCloqvT
IIPQIjR8htFxGTz02STVXfnhnJ0Zk8KhqKF2v1SQvIYxsZU7jaDgl5i3zpeh58cY
OwIDAQAB
-----END PUBLIC KEY-----
"""

PRIV_KEY2 = """
-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAp+8cTxguO6Vg+YO92VfHgNld3Zy8aM3JbZvpJcjTnis+YFJ7
Zlkcc647yPRRwY9nYBNywahnt5kIeuT1rTvTsMBZWvmUoEVUj1Xg8XXQkBvb9Ozy
Gqy/G/p8KDDpzMP/U+XCnUeHiXTZrgnqgBIc2cKeCVvWFqDi0GRFGzyaXLaX3PPm
M7DJ0MIPL1qgmcDq6+7Ze0gJ9SrDYFAeLmbuT1OqDfufXWQl/82JXeiwU2cOpqWq
7n5fvPOWim7l1tzQ+dSiMRRm0xa6uNexCJww3oJSwvMbAmgzvOhqqhlqv+K7u0u7
FrFFojESsL36Gq4GBrISnvu2tk7u4GGNTYYQbQIDAQABAoIBAADrqWDQnd5DVZEA
lR+WINiWuHJAy/KaIC7K4kAMBgbxrz2ZbiY9Ok/zBk5fcnxIZDVtXd1sZicmPlro
GuWodIxdPZAnWpZ3UtOXUayZK/vCP1YsH1agmEqXuKsCu6Fc+K8VzReOHxLUkmXn
FYM+tixGahXcjEOi/aNNTWitEB6OemRM1UeLJFzRcfyXiqzHpHCIZwBpTUAsmzcG
QiVDkMTKubwo/m+PVXburX2CGibUydctgbrYIc7EJvyx/cpRiPZXo1PhHQWdu4Y1
SOaC66WLsP/wqvtHo58JQ6EN/gjSsbAgGGVkZ1xMo66nR+pLpR27coS7o03xCks6
DY/0mukCgYEAuLIGgBnqoh7YsOBLd/Bc1UTfDMxJhNseo+hZemtkSXz2Jn51322F
Zw/FVN4ArXgluH+XsOhvG/MFFpojwZSrb0Qq5b1MRdo9qycq8lGqNtlN1WHqosDQ
zW29kpL0tlRrSDpww3wRESsN9rH5XIrJ1b3ZXuO7asR+KBVQMy/+NcUCgYEA6MSC
c+fywltKPgmPl5j0DPoDe5SXE/6JQy7w/vVGrGfWGf/zEJmhzS2R+CcfTTEqaT0T
Yw8+XbFgKAqsxwtE9MUXLTVLI3sSUyE4g7blCYscOqhZ8ItCUKDXWkSpt++rG0Um
1+cEJP/0oCazG6MWqvBC4NpQ1nzh46QpjWqMwokCgYAKDLXJ1p8rvx3vUeUJW6zR
dfPlEGCXuAyMwqHLxXgpf4EtSwhC5gSyPOtx2LqUtcrnpRmt6JfTH4ARYMW9TMef
QEhNQ+WYj213mKP/l235mg1gJPnNbUxvQR9lkFV8bk+AGJ32JRQQqRUTbU+yN2MQ
HEptnVqfTp3GtJIultfwOQKBgG+RyYmu8wBP650izg33BXu21raEeYne5oIqXN+I
R5DZ0JjzwtkBGroTDrVoYyuH1nFNEh7YLqeQHqvyufBKKYo9cid8NQDTu+vWr5UK
tGvHnwdKrJmM1oN5JOAiq0r7+QMAOWchVy449VNSWWV03aeftB685iR5BXkstbIQ
EVopAoGAfcGBTAhmceK/4Q83H/FXBWy0PAa1kZGg/q8+Z0KY76AqyxOVl0/CU/rB
3tO3sKhaMTHPME/MiQjQQGoaK1JgPY6JHYvly2KomrJ8QTugqNGyMzdVJkXAK2AM
GAwC8ivAkHf8CHrHa1W7l8t2IqBjW1aRt7mOW92nfG88Hck0Mbo=
-----END RSA PRIVATE KEY-----
"""


PUB_KEY2 = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp+8cTxguO6Vg+YO92VfH
gNld3Zy8aM3JbZvpJcjTnis+YFJ7Zlkcc647yPRRwY9nYBNywahnt5kIeuT1rTvT
sMBZWvmUoEVUj1Xg8XXQkBvb9OzyGqy/G/p8KDDpzMP/U+XCnUeHiXTZrgnqgBIc
2cKeCVvWFqDi0GRFGzyaXLaX3PPmM7DJ0MIPL1qgmcDq6+7Ze0gJ9SrDYFAeLmbu
T1OqDfufXWQl/82JXeiwU2cOpqWq7n5fvPOWim7l1tzQ+dSiMRRm0xa6uNexCJww
3oJSwvMbAmgzvOhqqhlqv+K7u0u7FrFFojESsL36Gq4GBrISnvu2tk7u4GGNTYYQ
bQIDAQAB
-----END PUBLIC KEY-----
"""


def test_get_rsa_pub_key_bad_key(tmp_path):
    """
    get_rsa_pub_key raises InvalidKeyError when encoutering a bad key
    """
    key_path = str(tmp_path / "key")
    with salt.utils.files.fopen(key_path, "w") as fp:
        fp.write("")
    with pytest.raises(salt.crypt.InvalidKeyError):
        salt.crypt.get_rsa_pub_key(key_path)


def test_cryptical_dumps_no_nonce():
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data)

    # Validate message structure
    assert isinstance(ret, bytes)
    une = master_crypt.decrypt(ret)
    une.startswith(master_crypt.PICKLE_PAD)
    assert salt.payload.loads(une[len(master_crypt.PICKLE_PAD) :]) == data

    # Validate load back to orig data
    assert master_crypt.loads(ret) == data


def test_cryptical_dumps_valid_nonce():
    nonce = uuid.uuid4().hex
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data, nonce=nonce)

    assert isinstance(ret, bytes)
    une = master_crypt.decrypt(ret)
    une.startswith(master_crypt.PICKLE_PAD)
    nonce_and_data = une[len(master_crypt.PICKLE_PAD) :]
    assert nonce_and_data.startswith(nonce.encode())
    assert salt.payload.loads(nonce_and_data[len(nonce) :]) == data

    assert master_crypt.loads(ret, nonce=nonce) == data


def test_cryptical_dumps_invalid_nonce():
    nonce = uuid.uuid4().hex
    master_crypt = salt.crypt.Crypticle({}, salt.crypt.Crypticle.generate_key_string())
    data = {"foo": "bar"}
    ret = master_crypt.dumps(data, nonce=nonce)
    assert isinstance(ret, bytes)
    with pytest.raises(salt.crypt.SaltClientError, match="Nonce verification error"):
        assert master_crypt.loads(ret, nonce="abcde")


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_verify_signature(tmp_path):
    tmp_path.joinpath("foo.pem").write_text(PRIV_KEY.strip())
    tmp_path.joinpath("foo.pub").write_text(PUB_KEY.strip())
    tmp_path.joinpath("bar.pem").write_text(PRIV_KEY2.strip())
    tmp_path.joinpath("bar.pub").write_text(PUB_KEY2.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert salt.crypt.verify_signature(str(tmp_path.joinpath("foo.pub")), msg, sig)


@pytest.mark.skipif(FIPS_TESTRUN, reason="Legacy key can not be loaded in FIPS mode")
def test_verify_signature_bad_sig(tmp_path):
    tmp_path.joinpath("foo.pem").write_text(PRIV_KEY.strip())
    tmp_path.joinpath("foo.pub").write_text(PUB_KEY.strip())
    tmp_path.joinpath("bar.pem").write_text(PRIV_KEY2.strip())
    tmp_path.joinpath("bar.pub").write_text(PUB_KEY2.strip())
    msg = b"foo bar"
    sig = salt.crypt.sign_message(str(tmp_path.joinpath("foo.pem")), msg)
    assert not salt.crypt.verify_signature(str(tmp_path.joinpath("bar.pub")), msg, sig)
