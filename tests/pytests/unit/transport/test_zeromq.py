"""
    :codeauthor: Thomas Jackson <jacksontj.89@gmail.com>
"""

import ctypes
import hashlib
import logging
import multiprocessing
import os
import threading
import time
import uuid

import msgpack
import pytest
import zmq.eventloop.future

import salt.channel.client
import salt.channel.server
import salt.config
import salt.crypt
import salt.exceptions
import salt.ext.tornado.concurrent
import salt.ext.tornado.gen
import salt.ext.tornado.ioloop
import salt.transport.zeromq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from salt.master import SMaster
from tests.conftest import FIPS_TESTRUN
from tests.support.mock import AsyncMock, MagicMock, patch

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.core_test,
]


MASTER_PRIV_KEY = """
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


MASTER_PUB_KEY = """
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

MASTER2_PRIV_KEY = """
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


MASTER2_PUB_KEY = """
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


MASTER_SIGNING_PRIV = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAtieqrBMTM0MSIbhPKkDcozHqyXKyL/+bXYYw+iVPsns7c7bJ
zBqenLQlWoRVyrVyBFrrwQSrKu/0Mqn3l639iOGPlUoR3I7aZKIpyEdDkqd3xGIC
e+BtNNDqhUai67L63hEdG+iYAchi8UZw3LZGtcGpJ3FkBH4cYFX9EOam2QjbD7WY
EO7m1+j6XEYIOTCmAP9dGAvBbU0Jblc+wYxG3qNr+2dBWsK76QXWEqib2VSOGP+z
gjJa8tqY7PXXdOJpalQXNphmD/4o4pHKR4Euy0yL/1oMkpacmrV61LWB8Trnx9nS
9gdVrUteQF/cL1KAGwOsdVmiLpHfvqLLRqSAAQIDAQABAoIBABjB+HEN4Kixf4fk
wKHKEhL+SF6b/7sFX00NXZ/KLXRhSnnWSMQ8g/1hgMg2P2DfW4FbCDsCUu9xkLvI
HTZY+CJAIh9U42uaYPWXkt09TmJi76TZ+2Nx4/XvRUjbCm7Fs1I2ekHeUbbAUS5g
+BsPjTnL+h05zLHNoDa5yT0gVGIgFsQcX/w38arZCe8Rjp9le7PXUB5IIqASsDiw
t8zJvdyWToeXd0WswCHTQu5coHvKo5MCjIZZ1Ink1yJcCCc3rKDc+q3jB2z9T9oW
cUsKzJ4VuleiYj1eRxFITBmXbjKrb/GPRRUkeqCQbs68Hyj2d3UtOFDPeF4vng/3
jGsHPq8CgYEA0AHAbwykVC6NMa37BTvEqcKoxbjTtErxR+yczlmVDfma9vkwtZvx
FJdbS/+WGA/ucDby5x5b2T5k1J9ueMR86xukb+HnyS0WKsZ94Ie8WnJAcbp+38M6
7LD0u74Cgk93oagDAzUHqdLq9cXxv/ppBpxVB1Uvu8DfVMHj+wt6ie8CgYEA4C7u
u+6b8EmbGqEdtlPpScKG0WFstJEDGXRARDCRiVP2w6wm25v8UssCPvWcwf8U1Hoq
lhMY+H6a5dnRRiNYql1MGQAsqMi7VeJNYb0B1uxi7X8MPM+SvXoAglX7wm1z0cVy
O4CE5sEKbBg6aQabx1x9tzdrm80SKuSsLc5HRQ8CgYEAp/mCKSuQWNru8ruJBwTp
IB4upN1JOUN77ZVKW+lD0XFMjz1U9JPl77b65ziTQQM8jioRpkqB6cHVM088qxIh
vssn06Iex/s893YrmPKETJYPLMhqRNEn+JQ+To53ADykY0uGg0SD18SYMbmULHBP
+CKvF6jXT0vGDnA1ZzoxzskCgYEA2nQhYrRS9EVlhP93KpJ+A8gxA5tCCHo+YPFt
JoWFbCKLlYUNoHZR3IPCPoOsK0Zbj+kz0mXtsUf9vPkR+py669haLQqEejyQgFIz
QYiiYEKc6/0feapzvXtDP751w7JQaBtVAzJrT0jQ1SCO2oT8C7rPLlgs3fdpOq72
MPSPcnUCgYBWHm6bn4HvaoUSr0v2hyD9fHZS/wDTnlXVe5c1XXgyKlJemo5dvycf
HUCmN/xIuO6AsiMdqIzv+arNJdboz+O+bNtS43LkTJfEH3xj2/DdUogdvOgG/iPM
u9KBT1h+euws7PqC5qt4vqLwCTTCZXmUS8Riv+62RCC3kZ5AbpT3ZA==
-----END RSA PRIVATE KEY-----
"""

MASTER_SIGNING_PUB = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtieqrBMTM0MSIbhPKkDc
ozHqyXKyL/+bXYYw+iVPsns7c7bJzBqenLQlWoRVyrVyBFrrwQSrKu/0Mqn3l639
iOGPlUoR3I7aZKIpyEdDkqd3xGICe+BtNNDqhUai67L63hEdG+iYAchi8UZw3LZG
tcGpJ3FkBH4cYFX9EOam2QjbD7WYEO7m1+j6XEYIOTCmAP9dGAvBbU0Jblc+wYxG
3qNr+2dBWsK76QXWEqib2VSOGP+zgjJa8tqY7PXXdOJpalQXNphmD/4o4pHKR4Eu
y0yL/1oMkpacmrV61LWB8Trnx9nS9gdVrUteQF/cL1KAGwOsdVmiLpHfvqLLRqSA
AQIDAQAB
-----END PUBLIC KEY-----
"""

MINION_PRIV_KEY = """
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAsT6TwnlI0L7urjXu6D5E11tFJ/NglQ45jW/WN9tAUNvphq6Q
cjJCd/aWmdqlqe7ix8y9M/8rgwghRQsnPXblVBvPwFcUEXhMRnOGzqbq/0zyQX01
KecT0plBhlDt2lTyCLU6E4XCqyLbPfOxgXzsVqM0/TnzRtpVvGNy+5N4eFGylrjb
cJhPxKt2G9TDOCM/hYacDs5RVIYQQmcYb8LJq7G3++FfWpYRDaxdKoHNFDspEynd
jzr67hgThnwzc388OKNJx/7B2atwPTunPb3YBjgwDyRO/01OKK4gUHdw5KoctFgp
kDCDjwjemlyXV+MYODRTIdtOlAP83ZkntEuLoQIDAQABAoIBAAJOKNtvFGfF2l9H
S4CXZSUGU0a+JaCkR+wmnjsPwPn/dXDpAe8nGpidpNicPWqRm6WABjeQHaxda+fB
lpSrRtEdo3zoi2957xQJ5wddDtI1pmXJQrdbm0H/K39oIg/Xtv/IZT769TM6OtVg
paUxG/aftmeGXDtGfIL8w1jkuPABRBLOakWQA9uVdeG19KTU0Ag8ilpJdEX64uFJ
W75bpVjT+KO/6aV1inuCntQSP097aYvUWajRwuiYVJOxoBZHme3IObcE6mdnYXeQ
wblyWBpJUHrOS4MP4HCODV2pHKZ2rr7Nwhh8lMNw/eY9OP0ifz2AcAqe3sUMQOKP
T0qRC6ECgYEAyeU5JvUPOpxXvvChYh6gJ8pYTIh1ueDP0O5e4t3vhz6lfy9DKtRN
ROJLUorHvw/yVXMR72nT07a0z2VswcrUSw8ov3sI53F0NkLGEafQ35lVhTGs4vTl
CFoQCuAKPsxeUl4AIbfbpkDsLGQqzW1diFArK7YeQkpGuGaGodXl480CgYEA4L40
x5cUXnAhTPsybo7sbcpiwFHoGblmdkvpYvHA2QxtNSi2iHHdqGo8qP1YsZjKQn58
371NhtqidrJ6i/8EBFP1dy+y/jr9qYlZNNGcQeBi+lshrEOIf1ct56KePG79s8lm
DmD1OY8tO2R37+Py46Nq1n6viT/ST4NjLQI3GyUCgYEAiOswSDA3ZLs0cqRD/gPg
/zsliLmehTFmHj4aEWcLkz+0Ar3tojUaNdX12QOPFQ7efH6uMhwl8NVeZ6xUBlTk
hgbAzqLE1hjGBCpiowSZDZqyOcMHiV8ll/VkHcv0hsQYT2m6UyOaDXTH9g70TB6Y
KOKddGZsvO4cad/1+/jQkB0CgYAzDEEkzLY9tS57M9uCrUgasAu6L2CO50PUvu1m
Ig9xvZbYqkS7vVFhva/FmrYYsOHQNLbcgz0m0mZwm52mSuh4qzFoPxdjE7cmWSJA
ExRxCiyxPR3q6PQKKJ0urgtPIs7RlX9u6KsKxfC6OtnbTWWQO0A7NE9e13ZHxUoz
oPsvWQKBgCa0+Fb2lzUeiQz9bV1CBkWneDZUXuZHmabAZomokX+h/bq+GcJFzZjW
3kAHwYkIy9IAy3SyO/6CP0V3vAye1p+XbotiwsQ/XZnr0pflSQL3J1l1CyN3aopg
Niv7k/zBn15B72aK73R/CpUSk9W/eJGqk1NcNwf8hJHsboRYx6BR
-----END RSA PRIVATE KEY-----
"""


MINION_PUB_KEY = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsT6TwnlI0L7urjXu6D5E
11tFJ/NglQ45jW/WN9tAUNvphq6QcjJCd/aWmdqlqe7ix8y9M/8rgwghRQsnPXbl
VBvPwFcUEXhMRnOGzqbq/0zyQX01KecT0plBhlDt2lTyCLU6E4XCqyLbPfOxgXzs
VqM0/TnzRtpVvGNy+5N4eFGylrjbcJhPxKt2G9TDOCM/hYacDs5RVIYQQmcYb8LJ
q7G3++FfWpYRDaxdKoHNFDspEyndjzr67hgThnwzc388OKNJx/7B2atwPTunPb3Y
BjgwDyRO/01OKK4gUHdw5KoctFgpkDCDjwjemlyXV+MYODRTIdtOlAP83ZkntEuL
oQIDAQAB
-----END PUBLIC KEY-----
"""

AES_KEY = "8wxWlOaMMQ4d3yT74LL4+hGrGTf65w8VgrcNjLJeLRQ2Q6zMa8ItY2EQUgMKKDb7JY+RnPUxbB0="


@pytest.fixture
def signing_algorithm():
    if FIPS_TESTRUN:
        return salt.crypt.PKCS1v15_SHA224
    return salt.crypt.PKCS1v15_SHA1


@pytest.fixture
def encryption_algorithm():
    if FIPS_TESTRUN:
        return salt.crypt.OAEP_SHA224
    return salt.crypt.OAEP_SHA1


@pytest.fixture
def pki_dir(tmp_path):
    _pki_dir = tmp_path / "pki"
    _pki_dir.mkdir()
    madir = _pki_dir / "master"
    madir.mkdir()

    mapriv = madir / "master.pem"
    mapriv.write_text(MASTER_PRIV_KEY.strip())
    mapub = madir / "master.pub"
    mapub.write_text(MASTER_PUB_KEY.strip())

    maspriv = madir / "master_sign.pem"
    maspriv.write_text(MASTER_SIGNING_PRIV.strip())
    maspub = madir / "master_sign.pub"
    maspub.write_text(MASTER_SIGNING_PUB.strip())

    misdir = madir / "minions"
    misdir.mkdir()
    misdir.joinpath("minion").write_text(MINION_PUB_KEY.strip())
    for sdir in [
        "minions_autosign",
        "minions_denied",
        "minions_pre",
        "minions_rejected",
    ]:
        madir.joinpath(sdir).mkdir()

    midir = _pki_dir / "minion"
    midir.mkdir()
    mipub = midir / "minion.pub"
    mipub.write_text(MINION_PUB_KEY.strip())
    mipriv = midir / "minion.pem"
    mipriv.write_text(MINION_PRIV_KEY.strip())
    mimapriv = midir / "minion_master.pub"
    mimapriv.write_text(MASTER_PUB_KEY.strip())
    mimaspriv = midir / "master_sign.pub"
    mimaspriv.write_text(MASTER_SIGNING_PUB.strip())
    yield _pki_dir


def test_master_uri():
    """
    test _get_master_uri method
    """

    m_ip = "127.0.0.1"
    m_port = 4505
    s_ip = "111.1.0.1"
    s_port = 4058

    m_ip6 = "1234:5678::9abc"
    s_ip6 = "1234:5678::1:9abc"

    with patch("salt.transport.zeromq.LIBZMQ_VERSION_INFO", (4, 1, 6)), patch(
        "salt.transport.zeromq.ZMQ_VERSION_INFO", (16, 0, 1)
    ):
        # pass in both source_ip and source_port
        assert (
            salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_ip=s_ip, source_port=s_port
            )
            == f"tcp://{s_ip}:{s_port};{m_ip}:{m_port}"
        )

        assert (
            salt.transport.zeromq._get_master_uri(
                master_ip=m_ip6, master_port=m_port, source_ip=s_ip6, source_port=s_port
            )
            == f"tcp://[{s_ip6}]:{s_port};[{m_ip6}]:{m_port}"
        )

        # source ip and source_port empty
        assert (
            salt.transport.zeromq._get_master_uri(master_ip=m_ip, master_port=m_port)
            == f"tcp://{m_ip}:{m_port}"
        )

        assert (
            salt.transport.zeromq._get_master_uri(master_ip=m_ip6, master_port=m_port)
            == f"tcp://[{m_ip6}]:{m_port}"
        )

        # pass in only source_ip
        assert (
            salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_ip=s_ip
            )
            == f"tcp://{s_ip}:0;{m_ip}:{m_port}"
        )

        assert (
            salt.transport.zeromq._get_master_uri(
                master_ip=m_ip6, master_port=m_port, source_ip=s_ip6
            )
            == f"tcp://[{s_ip6}]:0;[{m_ip6}]:{m_port}"
        )

        # pass in only source_port
        assert (
            salt.transport.zeromq._get_master_uri(
                master_ip=m_ip, master_port=m_port, source_port=s_port
            )
            == f"tcp://0.0.0.0:{s_port};{m_ip}:{m_port}"
        )


def test_clear_req_channel_master_uri_override(temp_salt_minion, temp_salt_master):
    """
    ensure master_uri kwarg is respected
    """
    opts = temp_salt_minion.config.copy()
    # minion_config should be 127.0.0.1, we want a different uri that still connects
    opts.update(
        {
            "id": "root",
            "transport": "zeromq",
            "auth_tries": 1,
            "auth_timeout": 5,
            "master_ip": "127.0.0.1",
            "master_port": temp_salt_master.config["ret_port"],
            "master_uri": "tcp://127.0.0.1:{}".format(
                temp_salt_master.config["ret_port"]
            ),
        }
    )
    master_uri = "tcp://{master_ip}:{master_port}".format(
        master_ip="localhost", master_port=opts["master_port"]
    )
    with salt.channel.client.ReqChannel.factory(opts, master_uri=master_uri) as channel:
        assert "127.0.0.1" in channel.transport.message_client.addr


def run_loop_in_thread(loop, evt):
    """
    Run the provided loop until an event is set
    """
    loop.make_current()

    @salt.ext.tornado.gen.coroutine
    def stopper():
        yield salt.ext.tornado.gen.sleep(0.1)
        while True:
            if not evt.is_set():
                loop.stop()
                break
            yield salt.ext.tornado.gen.sleep(0.3)

    loop.add_callback(evt.set)
    loop.add_callback(stopper)
    try:
        loop.start()
    finally:
        loop.close()


class MockSaltMinionMaster:
    mock = MagicMock()

    def __init__(self, temp_salt_minion, temp_salt_master):
        SMaster.secrets["aes"] = {
            "secret": multiprocessing.Array(
                ctypes.c_char,
                salt.utils.stringutils.to_bytes(
                    salt.crypt.Crypticle.generate_key_string()
                ),
            ),
            "reload": salt.crypt.Crypticle.generate_key_string,
        }
        self.process_manager = salt.utils.process.ProcessManager(
            name="ReqServer_ProcessManager"
        )

        master_opts = temp_salt_master.config.copy()
        master_opts.update({"transport": "zeromq"})
        self.server_channel = salt.channel.server.ReqServerChannel.factory(master_opts)
        self.server_channel.pre_fork(self.process_manager)

        self.io_loop = salt.ext.tornado.ioloop.IOLoop()
        self.evt = threading.Event()
        self.server_channel.post_fork(self._handle_payload, io_loop=self.io_loop)
        self.server_thread = threading.Thread(
            target=run_loop_in_thread, args=(self.io_loop, self.evt)
        )
        self.server_thread.start()
        minion_opts = temp_salt_minion.config.copy()
        minion_opts.update(
            {
                "master_ip": "127.0.0.1",
                "transport": "zeromq",
            }
        )
        self.channel = salt.channel.client.ReqChannel.factory(
            minion_opts, crypt="clear"
        )

    def __enter__(self):
        self.channel.__enter__()
        self.evt.wait()
        return self

    def __exit__(self, *args, **kwargs):
        self.channel.__exit__(*args, **kwargs)
        del self.channel
        # Attempting to kill the children hangs the test suite.
        # Let the test suite handle this instead.
        self.process_manager.stop_restarting()
        self.process_manager.kill_children()
        self.evt.clear()
        self.server_thread.join()
        # Give the procs a chance to fully close before we stop the io_loop
        time.sleep(2)
        self.server_channel.close()
        SMaster.secrets.pop("aes")
        del self.server_channel
        del self.io_loop
        del self.process_manager
        del self.server_thread

    # pylint: enable=W1701
    @classmethod
    @salt.ext.tornado.gen.coroutine
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        cls.mock._handle_payload_hook()
        raise salt.ext.tornado.gen.Return((payload, {"fun": "send_clear"}))


@pytest.mark.parametrize("message", ["", [], ()])
def test_badload(temp_salt_minion, temp_salt_master, message):
    """
    Test a variety of bad requests, make sure that we get some sort of error
    """
    with MockSaltMinionMaster(temp_salt_minion, temp_salt_master) as minion_master:
        ret = minion_master.channel.send(message, timeout=5, tries=1)
        assert ret == "payload and load must be a dict"


def test_payload_handling_exception(temp_salt_minion, temp_salt_master):
    """
    test of getting exception on payload handling
    """
    with MockSaltMinionMaster(temp_salt_minion, temp_salt_master) as minion_master:
        with patch.object(minion_master.mock, "_handle_payload_hook") as _mock:
            _mock.side_effect = Exception()
            ret = minion_master.channel.send({}, timeout=5, tries=1)
            assert ret == "Some exception handling minion payload"


def test_serverside_exception(temp_salt_minion, temp_salt_master):
    """
    test of getting server side exception on payload handling
    """
    with MockSaltMinionMaster(temp_salt_minion, temp_salt_master) as minion_master:
        with patch.object(minion_master.mock, "_handle_payload_hook") as _mock:
            _mock.side_effect = salt.ext.tornado.gen.Return(({}, {"fun": "madeup-fun"}))
            ret = minion_master.channel.send({}, timeout=5, tries=1)
            assert ret == "Server-side exception handling payload"


def test_zeromq_async_pub_channel_publish_port(temp_salt_master):
    """
    test when connecting that we use the publish_port set in opts when its not 4506
    """
    opts = dict(
        temp_salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        recon_randomize=False,
        publish_port=455505,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)
    ioloop = salt.ext.tornado.ioloop.IOLoop()
    transport = salt.transport.zeromq.PublishClient(opts, ioloop)
    with transport:
        patch_socket = MagicMock(return_value=True)
        patch_auth = MagicMock(return_value=True)
        with patch.object(transport, "_socket", patch_socket):
            transport.connect(455505)
    assert str(opts["publish_port"]) in patch_socket.mock_calls[0][1][0]


def test_zeromq_async_pub_channel_filtering_decode_message_no_match(
    temp_salt_master,
):
    """
    test zeromq PublishClient _decode_messages when
    zmq_filtering enabled and minion does not match
    """
    message = [
        b"4f26aeafdb2367620a393c973eddbe8f8b846eb",
        b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
        b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
        b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
        b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
        b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
        b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
    ]

    opts = dict(
        temp_salt_master.config.copy(),
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        recon_randomize=False,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

    ioloop = salt.ext.tornado.ioloop.IOLoop()
    channel = salt.transport.zeromq.PublishClient(opts, ioloop)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ):
            res = channel._decode_messages(message)
    assert res.result() is None


def test_zeromq_async_pub_channel_filtering_decode_message(
    temp_salt_master, temp_salt_minion
):
    """
    test AsyncZeroMQPublishClient _decode_messages when zmq_filtered enabled
    """
    minion_hexid = salt.utils.stringutils.to_bytes(
        hashlib.sha1(salt.utils.stringutils.to_bytes(temp_salt_minion.id)).hexdigest()
    )

    message = [
        minion_hexid,
        b"\x82\xa3enc\xa3aes\xa4load\xda\x00`\xeeR\xcf"
        b"\x0eaI#V\x17if\xcf\xae\x05\xa7\xb3bN\xf7\xb2\xe2"
        b'\xd0sF\xd1\xd4\xecB\xe8\xaf"/*ml\x80Q3\xdb\xaexg'
        b"\x8e\x8a\x8c\xd3l\x03\\,J\xa7\x01i\xd1:]\xe3\x8d"
        b"\xf4\x03\x88K\x84\n`\xe8\x9a\xad\xad\xc6\x8ea\x15>"
        b"\x92m\x9e\xc7aM\x11?\x18;\xbd\x04c\x07\x85\x99\xa3\xea[\x00D",
    ]

    opts = dict(
        temp_salt_master.config.copy(),
        id=temp_salt_minion.id,
        ipc_mode="ipc",
        pub_hwm=0,
        zmq_filtering=True,
        recon_randomize=False,
        recon_default=1,
        recon_max=2,
        master_ip="127.0.0.1",
        acceptance_wait_time=5,
        acceptance_wait_time_max=5,
        sign_pub_messages=False,
    )
    opts["master_uri"] = "tcp://{interface}:{publish_port}".format(**opts)

    ioloop = salt.ext.tornado.ioloop.IOLoop()
    channel = salt.transport.zeromq.PublishClient(opts, ioloop)
    with channel:
        with patch(
            "salt.crypt.AsyncAuth.crypticle",
            MagicMock(return_value={"tgt_type": "glob", "tgt": "*", "jid": 1}),
        ) as mock_test:
            res = channel._decode_messages(message)

    assert res.result()["enc"] == "aes"


def test_req_server_chan_encrypt_v2(
    pki_dir, encryption_algorithm, signing_algorithm, master_opts
):
    loop = salt.ext.tornado.ioloop.IOLoop.current()
    master_opts.update(
        {
            "worker_threads": 1,
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "zmq_monitor": False,
            "mworker_queue_niceness": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("master")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
        }
    )
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    dictkey = "pillar"
    nonce = "abcdefg"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(
        pillar_data,
        dictkey,
        "minion",
        nonce,
        encryption_algorithm=encryption_algorithm,
        signing_algorithm=signing_algorithm,
    )
    assert "key" in ret
    assert dictkey in ret

    key = salt.crypt.PrivateKey(str(pki_dir.joinpath("minion", "minion.pem")))
    aes = key.decrypt(ret["key"], encryption_algorithm)
    pcrypt = salt.crypt.Crypticle(master_opts, aes)
    signed_msg = pcrypt.loads(ret[dictkey])

    assert "sig" in signed_msg
    assert "data" in signed_msg
    data = salt.payload.loads(signed_msg["data"])
    assert "key" in data
    assert data["key"] == ret["key"]
    assert "key" in data
    assert data["nonce"] == nonce
    assert "pillar" in data
    assert data["pillar"] == pillar_data


def test_req_server_chan_encrypt_v1(pki_dir, encryption_algorithm, master_opts):
    loop = salt.ext.tornado.ioloop.IOLoop.current()
    master_opts.update(
        {
            "worker_threads": 1,
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "zmq_monitor": False,
            "mworker_queue_niceness": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("master")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
        }
    )
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    dictkey = "pillar"
    nonce = "abcdefg"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(
        pillar_data,
        dictkey,
        "minion",
        sign_messages=False,
        encryption_algorithm=encryption_algorithm,
    )

    assert "key" in ret
    assert dictkey in ret

    key = salt.crypt.PrivateKey(str(pki_dir.joinpath("minion", "minion.pem")))
    aes = key.decrypt(ret["key"], encryption_algorithm)
    pcrypt = salt.crypt.Crypticle(master_opts, aes)
    data = pcrypt.loads(ret[dictkey])
    assert data == pillar_data


def test_req_chan_decode_data_dict_entry_v1(
    pki_dir, encryption_algorithm, minion_opts, master_opts
):
    mockloop = MagicMock()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    master_opts = dict(master_opts, pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    client = salt.channel.client.ReqChannel.factory(minion_opts, io_loop=mockloop)
    dictkey = "pillar"
    target = "minion"
    pillar_data = {"pillar1": "meh"}
    ret = server._encrypt_private(
        pillar_data,
        dictkey,
        target,
        sign_messages=False,
        encryption_algorithm=encryption_algorithm,
    )
    key = client.auth.get_keys()
    aes = key.decrypt(ret["key"], encryption_algorithm)
    pcrypt = salt.crypt.Crypticle(client.opts, aes)
    ret_pillar_data = pcrypt.loads(ret[dictkey])
    assert ret_pillar_data == pillar_data


async def test_req_chan_decode_data_dict_entry_v2(minion_opts, master_opts, pki_dir):
    mockloop = MagicMock()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=mockloop)

    dictkey = "pillar"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(minion_opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.mpub = auth.mpub
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.transport = MagicMock()

    print(minion_opts["encryption_algorithm"])

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.transport.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data,
            dictkey,
            target,
            nonce=load["nonce"],
            sign_messages=True,
            encryption_algorithm=minion_opts["encryption_algorithm"],
            signing_algorithm=minion_opts["signing_algorithm"],
        )
        raise salt.ext.tornado.gen.Return(ret)

    client.transport.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }
    ret = await client.crypted_transfer_decode_dictentry(  # pylint: disable=E1121,E1123
        load,
        dictkey="pillar",
    )
    assert "version" in client.transport.msg
    assert client.transport.msg["version"] == 2
    assert ret == {"pillar1": "meh"}


async def test_req_chan_decode_data_dict_entry_v2_bad_nonce(
    pki_dir, minion_opts, master_opts
):
    mockloop = MagicMock()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(minion_opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.mpub = auth.mpub
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.transport = MagicMock()
    ret = server._encrypt_private(
        pillar_data,
        dictkey,
        target,
        nonce=badnonce,
        sign_messages=True,
        encryption_algorithm=minion_opts["encryption_algorithm"],
        signing_algorithm=minion_opts["signing_algorithm"],
    )

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.transport.msg = msg
        raise salt.ext.tornado.gen.Return(ret)

    client.transport.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
        ret = await client.crypted_transfer_decode_dictentry(  # pylint: disable=E1121,E1123
            load,
            dictkey="pillar",
        )
    assert "Pillar nonce verification failed." == excinfo.value.message


async def test_req_chan_decode_data_dict_entry_v2_bad_signature(
    pki_dir, minion_opts, master_opts
):
    mockloop = MagicMock()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(minion_opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.mpub = auth.mpub
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.transport = MagicMock()

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.transport.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data,
            dictkey,
            target,
            nonce=load["nonce"],
            sign_messages=True,
            encryption_algorithm=minion_opts["encryption_algorithm"],
            signing_algorithm=minion_opts["signing_algorithm"],
        )

        key = client.auth.get_keys()
        aes = key.decrypt(ret["key"], minion_opts["encryption_algorithm"])
        pcrypt = salt.crypt.Crypticle(client.opts, aes)
        signed_msg = pcrypt.loads(ret[dictkey])
        # Changing the pillar data will cause the signature verification to
        # fail.
        data = salt.payload.loads(signed_msg["data"])
        data["pillar"] = {"pillar1": "bar"}
        signed_msg["data"] = salt.payload.dumps(data)
        ret[dictkey] = pcrypt.dumps(signed_msg)
        raise salt.ext.tornado.gen.Return(ret)

    client.transport.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }

    with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
        ret = await client.crypted_transfer_decode_dictentry(  # pylint: disable=E1121,E1123
            load,
            dictkey="pillar",
        )
    assert "Pillar payload signature failed to validate." == excinfo.value.message


async def test_req_chan_decode_data_dict_entry_v2_bad_key(
    pki_dir, minion_opts, master_opts
):
    mockloop = MagicMock()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=mockloop)

    dictkey = "pillar"
    badnonce = "abcdefg"
    target = "minion"
    pillar_data = {"pillar1": "meh"}

    # Mock auth and message client.
    auth = client.auth
    auth._crypticle = salt.crypt.Crypticle(master_opts, AES_KEY)
    client.auth = MagicMock()
    client.auth.mpub = auth.mpub
    client.auth.authenticated = True
    client.auth.get_keys = auth.get_keys
    client.auth.crypticle.dumps = auth.crypticle.dumps
    client.auth.crypticle.loads = auth.crypticle.loads
    client.transport = MagicMock()

    @salt.ext.tornado.gen.coroutine
    def mocksend(msg, timeout=60, tries=3):
        client.transport.msg = msg
        load = client.auth.crypticle.loads(msg["load"])
        ret = server._encrypt_private(
            pillar_data,
            dictkey,
            target,
            nonce=load["nonce"],
            sign_messages=True,
            encryption_algorithm=minion_opts["encryption_algorithm"],
            signing_algorithm=minion_opts["signing_algorithm"],
        )

        mkey = client.auth.get_keys()
        aes = mkey.decrypt(ret["key"], minion_opts["encryption_algorithm"])
        pcrypt = salt.crypt.Crypticle(client.opts, aes)
        signed_msg = pcrypt.loads(ret[dictkey])

        # Now encrypt with a different key
        key = salt.crypt.Crypticle.generate_key_string()
        pcrypt = salt.crypt.Crypticle(master_opts, key)
        pubfn = os.path.join(master_opts["pki_dir"], "minions", "minion")
        pub = salt.crypt.PublicKey(pubfn)
        ret[dictkey] = pcrypt.dumps(signed_msg)
        key = salt.utils.stringutils.to_bytes(key)
        ret["key"] = pub.encrypt(key, minion_opts["encryption_algorithm"])
        raise salt.ext.tornado.gen.Return(ret)

    client.transport.send = mocksend

    # Note the 'ver' value in 'load' does not represent the the 'version' sent
    # in the top level of the transport's message.
    load = {
        "id": target,
        "grains": {},
        "saltenv": "base",
        "pillarenv": "base",
        "pillar_override": True,
        "extra_minion_data": {},
        "ver": "2",
        "cmd": "_pillar",
    }
    try:
        with pytest.raises(salt.crypt.AuthenticationError) as excinfo:
            await client.crypted_transfer_decode_dictentry(  # pylint: disable=E1121,E1123
                load,
                dictkey="pillar",
            )
        assert "Key verification failed." == excinfo.value.message
    finally:
        client.close()
        server.close()


async def test_req_serv_auth_v1(pki_dir, minion_opts, master_opts):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)

    pub = salt.crypt.get_rsa_pub_key(str(pki_dir.joinpath("minion", "minion.pub")))
    token = salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = salt.crypt.clean_key(fp.read())

    load = {
        "cmd": "_auth",
        "id": "minion",
        "token": token,
        "pub": pub_key,
        "enc_algo": minion_opts["encryption_algorithm"],
        "sig_algo": minion_opts["signing_algorithm"],
    }
    ret = server._auth(load, sign_messages=False)
    assert "load" not in ret


async def test_req_serv_auth_v2(pki_dir, minion_opts, master_opts):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)

    pub = salt.crypt.get_rsa_pub_key(str(pki_dir.joinpath("minion", "minion.pub")))
    token = salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string())
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = fp.read()

    load = {
        "cmd": "_auth",
        "id": "minion",
        "nonce": nonce,
        "token": token,
        "pub": pub_key,
        "enc_algo": minion_opts["encryption_algorithm"],
        "sig_algo": minion_opts["signing_algorithm"],
    }
    ret = server._auth(load, sign_messages=True)
    assert "sig" in ret
    assert "load" in ret


async def test_req_chan_auth_v2(pki_dir, io_loop, minion_opts, master_opts):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 4505,
            "auth_mode": 1,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = False
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    minion_opts["verify_master_pubkey_sign"] = False
    minion_opts["always_verify_signature"] = False
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=io_loop)
    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    assert "version" in pload
    assert pload["version"] == 2

    ret = server._auth(pload["load"], sign_messages=True)
    assert "sig" in ret
    ret = client.auth.handle_signin_response(signin_payload, ret)
    assert "aes" in ret
    assert "master_uri" in ret
    assert "publish_port" in ret


async def test_req_chan_auth_v2_with_master_signing(
    pki_dir, io_loop, minion_opts, master_opts
):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 4505,
            "auth_mode": 1,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts = dict(master_opts, pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = True
    master_opts["master_use_pubkey_signature"] = False
    master_opts["signing_key_pass"] = ""
    master_opts["master_sign_key_name"] = "master_sign"
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    minion_opts["verify_master_pubkey_sign"] = True
    minion_opts["always_verify_signature"] = True
    minion_opts["master_sign_key_name"] = "master_sign"
    minion_opts["master"] = "master"

    assert (
        pki_dir.joinpath("minion", "minion_master.pub").read_text()
        == pki_dir.joinpath("master", "master.pub").read_text()
    )

    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=io_loop)
    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    assert "version" in pload
    assert pload["version"] == 2

    server_reply = server._auth(pload["load"], sign_messages=True)
    # With version 2 we always get a clear signed response
    assert "enc" in server_reply
    assert server_reply["enc"] == "clear"
    assert "sig" in server_reply
    assert "load" in server_reply
    ret = client.auth.handle_signin_response(signin_payload, server_reply)
    assert "aes" in ret
    assert "master_uri" in ret
    assert "publish_port" in ret

    # Now create a new master key pair and try auth with it.
    mapriv = pki_dir.joinpath("master", "master.pem")
    mapriv.unlink()
    mapriv.write_text(MASTER2_PRIV_KEY.strip())
    mapub = pki_dir.joinpath("master", "master.pub")
    mapub.unlink()
    mapub.write_text(MASTER2_PUB_KEY.strip())

    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)

    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    server_reply = server._auth(pload["load"], sign_messages=True)
    ret = client.auth.handle_signin_response(signin_payload, server_reply)

    assert "aes" in ret
    assert "master_uri" in ret
    assert "publish_port" in ret

    assert (
        pki_dir.joinpath("minion", "minion_master.pub").read_text()
        == pki_dir.joinpath("master", "master.pub").read_text()
    )


async def test_req_chan_auth_v2_new_minion_with_master_pub(
    pki_dir, io_loop, minion_opts, master_opts
):

    pki_dir.joinpath("master", "minions", "minion").unlink()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 4505,
            "auth_mode": 1,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = False
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    minion_opts["verify_master_pubkey_sign"] = False
    minion_opts["always_verify_signature"] = False
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=io_loop)
    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    assert "version" in pload
    assert pload["version"] == 2

    ret = server._auth(pload["load"], sign_messages=True)
    assert "sig" in ret
    ret = client.auth.handle_signin_response(signin_payload, ret)
    assert ret == "retry"


async def test_req_chan_auth_v2_new_minion_with_master_pub_bad_sig(
    pki_dir, io_loop, minion_opts, master_opts
):

    pki_dir.joinpath("master", "minions", "minion").unlink()

    # Give the master a different key than the minion has.
    mapriv = pki_dir.joinpath("master", "master.pem")
    mapriv.unlink()
    mapriv.write_text(MASTER2_PRIV_KEY.strip())
    mapub = pki_dir.joinpath("master", "master.pub")
    mapub.unlink()
    mapub.write_text(MASTER2_PUB_KEY.strip())

    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 4505,
            "auth_mode": 1,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(
        pki_dir=str(pki_dir.joinpath("master")), master_sign_pubkey=False
    )
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    minion_opts["verify_master_pubkey_sign"] = False
    minion_opts["always_verify_signature"] = False
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=io_loop)
    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    assert "version" in pload
    assert pload["version"] == 2

    ret = server._auth(pload["load"], sign_messages=True)
    assert "sig" in ret
    with pytest.raises(salt.crypt.SaltClientError, match="Invalid signature"):
        ret = client.auth.handle_signin_response(signin_payload, ret)


async def test_req_chan_auth_v2_new_minion_without_master_pub(
    minion_opts,
    master_opts,
    pki_dir,
    io_loop,
):

    pki_dir.joinpath("master", "minions", "minion").unlink()
    pki_dir.joinpath("minion", "minion_master.pub").unlink()
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "publish_port": 4505,
            "auth_mode": 1,
            "acceptance_wait_time": 3,
            "acceptance_wait_time_max": 3,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = False
    server = salt.channel.server.ReqServerChannel.factory(master_opts)
    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    minion_opts["verify_master_pubkey_sign"] = False
    minion_opts["always_verify_signature"] = False
    client = salt.channel.client.AsyncReqChannel.factory(minion_opts, io_loop=io_loop)
    signin_payload = client.auth.minion_sign_in_payload()
    pload = client._package_load(signin_payload)
    try:
        assert "version" in pload
        assert pload["version"] == 2

        ret = server._auth(pload["load"], sign_messages=True)
        assert "sig" in ret
        ret = client.auth.handle_signin_response(signin_payload, ret)
        assert ret == "retry"
    finally:
        client.close()
        server.close()


async def test_req_server_garbage_request(io_loop):
    """
    Validate invalid msgpack messages will not raise exceptions in the
    RequestServers's message handler.
    """
    opts = salt.config.master_config("")
    opts["zmq_monitor"] = True
    request_server = salt.transport.zeromq.RequestServer(opts)

    def message_handler(payload):
        return payload

    request_server.post_fork(message_handler, io_loop)

    byts = msgpack.dumps({"foo": "bar"})
    badbyts = byts[:3] + b"^M" + byts[3:]

    valid_response = msgpack.dumps({"msg": "bad load"})

    stream = MagicMock()
    request_server.stream = stream

    try:
        await request_server.handle_message(stream, badbyts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(f"Exception was raised {exc}")

    request_server.stream.send.assert_called_once_with(valid_response)


async def test_req_chan_bad_payload_to_decode(pki_dir, io_loop):
    opts = {
        "master_uri": "tcp://127.0.0.1:4506",
        "interface": "127.0.0.1",
        "ret_port": 4506,
        "ipv6": False,
        "sock_dir": ".",
        "pki_dir": str(pki_dir.joinpath("minion")),
        "id": "minion",
        "__role": "minion",
        "keysize": 4096,
        "max_minions": 0,
        "auto_accept": False,
        "open_mode": False,
        "key_pass": None,
        "publish_port": 4505,
        "auth_mode": 1,
        "acceptance_wait_time": 3,
        "acceptance_wait_time_max": 3,
    }
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts = dict(opts, pki_dir=str(pki_dir.joinpath("master")))
    master_opts["master_sign_pubkey"] = False
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload(None)
    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload({})
    with pytest.raises(salt.exceptions.SaltDeserializationError):
        server._decode_payload(12345)


async def test_client_timeout_msg(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )
    client.connect()
    try:
        with pytest.raises(salt.exceptions.SaltReqTimeoutError):
            await client.send({"meh": "bah"}, 1)
    finally:
        client.close()


async def test_client_send_recv_on_cancelled_error(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )

    mock_future = MagicMock(**{"done.return_value": True})

    try:
        client.socket = AsyncMock()
        client.socket.recv.side_effect = zmq.eventloop.future.CancelledError
        await client._send_recv({"meh": "bah"}, mock_future)

        mock_future.set_exception.assert_not_called()
    finally:
        client.close()


async def test_client_send_recv_on_exception(minion_opts):
    client = salt.transport.zeromq.AsyncReqMessageClient(
        minion_opts, "tcp://127.0.0.1:4506"
    )

    mock_future = MagicMock(**{"done.return_value": True})

    try:
        client.socket = None
        await client._send_recv({"meh": "bah"}, mock_future)

        mock_future.set_exception.assert_not_called()
    finally:
        client.close()


def test_pub_client_init(minion_opts, io_loop):
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "syndic"
    minion_opts["master_ip"] = "127.0.0.1"
    minion_opts["zmq_filtering"] = True
    minion_opts["zmq_monitor"] = True
    client = salt.transport.zeromq.PublishClient(minion_opts, io_loop)
    client.send(b"asf")
    client.close()


async def test_unclosed_request_client(minion_opts, io_loop):
    minion_opts["master_uri"] = "tcp://127.0.0.1:4506"
    client = salt.transport.zeromq.RequestClient(minion_opts, io_loop)
    await client.connect()
    try:
        assert client._closing is False
        with pytest.warns(salt.transport.base.TransportWarning):
            client.__del__()  # pylint: disable=unnecessary-dunder-call
    finally:
        client.close()


async def test_unclosed_publish_client(minion_opts, io_loop):
    minion_opts["id"] = "minion"
    minion_opts["__role"] = "minion"
    minion_opts["master_ip"] = "127.0.0.1"
    minion_opts["zmq_filtering"] = True
    minion_opts["zmq_monitor"] = True
    client = salt.transport.zeromq.PublishClient(minion_opts, io_loop)
    await client.connect(2121)
    try:
        assert client._closing is False
        with pytest.warns(salt.transport.base.TransportWarning):
            client.__del__()  # pylint: disable=unnecessary-dunder-call
    finally:
        client.close()


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only run on fips enabled platforms")
def test_req_server_auth_unsupported_sig_algo(
    pki_dir, minion_opts, master_opts, caplog
):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    pub = salt.crypt.PublicKey(str(pki_dir.joinpath("master", "master.pub")))
    token = pub.encrypt(
        salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        algorithm=minion_opts["encryption_algorithm"],
    )
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = salt.crypt.clean_key(fp.read())

    load = {
        "version": 2,
        "cmd": "_auth",
        "id": "minion",
        "token": token,
        "pub": pub_key,
        "nonce": "asdfse",
        "enc_algo": minion_opts["encryption_algorithm"],
        "sig_algo": salt.crypt.PKCS1v15_SHA1,
    }
    with caplog.at_level(logging.INFO):
        ret = server._auth(load, sign_messages=True)
        assert (
            "Minion tried to authenticate with unsupported signing algorithm: PKCS1v15-SHA1"
            in caplog.text
        )
        assert "load" in ret
        assert "ret" in ret["load"]
        assert ret["load"]["ret"] == "bad sig algo"


def test_req_server_auth_garbage_sig_algo(pki_dir, minion_opts, master_opts, caplog):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    pub = salt.crypt.PublicKey(str(pki_dir.joinpath("master", "master.pub")))
    token = pub.encrypt(
        salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        algorithm=minion_opts["encryption_algorithm"],
    )
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = salt.crypt.clean_key(fp.read())

    load = {
        "version": 2,
        "cmd": "_auth",
        "id": "minion",
        "token": token,
        "pub": pub_key,
        "nonce": "asdfse",
        "enc_algo": minion_opts["encryption_algorithm"],
        "sig_algo": "IAMNOTANALGO",
    }
    with caplog.at_level(logging.INFO):
        ret = server._auth(load, sign_messages=True)
        assert (
            "Minion tried to authenticate with unsupported signing algorithm: IAMNOTANALGO"
            in caplog.text
        )
        assert "load" in ret
        assert "ret" in ret["load"]
        assert ret["load"]["ret"] == "bad sig algo"


@pytest.mark.skipif(not FIPS_TESTRUN, reason="Only run on fips enabled platforms")
def test_req_server_auth_unsupported_enc_algo(
    pki_dir, minion_opts, master_opts, caplog
):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    import tests.pytests.unit.crypt

    pub = tests.pytests.unit.crypt.LegacyPublicKey(
        str(pki_dir.joinpath("master", "master.pub"))
    )
    token = pub.encrypt(
        salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
    )
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = salt.crypt.clean_key(fp.read())

    load = {
        "version": 2,
        "cmd": "_auth",
        "id": "minion",
        "token": token,
        "pub": pub_key,
        "nonce": "asdfse",
        "enc_algo": "OAEP-SHA1",
        "sig_algo": minion_opts["signing_algorithm"],
    }
    with caplog.at_level(logging.INFO):
        ret = server._auth(load, sign_messages=True)
        assert (
            "Minion minion tried to authenticate with unsupported encryption algorithm: OAEP-SHA1"
            in caplog.text
        )
        assert "load" in ret
        assert "ret" in ret["load"]
        assert ret["load"]["ret"] == "bad enc algo"


def test_req_server_auth_garbage_enc_algo(pki_dir, minion_opts, master_opts, caplog):
    minion_opts.update(
        {
            "master_uri": "tcp://127.0.0.1:4506",
            "interface": "127.0.0.1",
            "ret_port": 4506,
            "ipv6": False,
            "sock_dir": ".",
            "pki_dir": str(pki_dir.joinpath("minion")),
            "id": "minion",
            "__role": "minion",
            "keysize": 4096,
            "max_minions": 0,
            "auto_accept": False,
            "open_mode": False,
            "key_pass": None,
            "master_sign_pubkey": False,
            "publish_port": 4505,
            "auth_mode": 1,
        }
    )
    SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    master_opts.update(pki_dir=str(pki_dir.joinpath("master")))
    server = salt.channel.server.ReqServerChannel.factory(master_opts)

    server.auto_key = salt.daemons.masterapi.AutoKey(server.opts)
    server.cache_cli = False
    server.event = salt.utils.event.get_master_event(
        master_opts, master_opts["sock_dir"], listen=False
    )
    server.master_key = salt.crypt.MasterKeys(server.opts)
    import tests.pytests.unit.crypt

    pub = tests.pytests.unit.crypt.LegacyPublicKey(
        str(pki_dir.joinpath("master", "master.pub"))
    )
    token = pub.encrypt(
        salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
    )
    nonce = uuid.uuid4().hex

    # We need to read the public key with fopen otherwise the newlines might
    # not match on windows.
    with salt.utils.files.fopen(
        str(pki_dir.joinpath("minion", "minion.pub")), "r"
    ) as fp:
        pub_key = salt.crypt.clean_key(fp.read())

    load = {
        "version": 2,
        "cmd": "_auth",
        "id": "minion",
        "token": token,
        "pub": pub_key,
        "nonce": "asdfse",
        "enc_algo": "IAMNOTAENCALGO",
        "sig_algo": minion_opts["signing_algorithm"],
    }
    with caplog.at_level(logging.INFO):
        ret = server._auth(load, sign_messages=True)
        assert (
            "Minion minion tried to authenticate with unsupported encryption algorithm: IAMNOTAENCALGO"
            in caplog.text
        )
        assert "load" in ret
        assert "ret" in ret["load"]
        assert ret["load"]["ret"] == "bad enc algo"
