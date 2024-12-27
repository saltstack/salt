import ctypes
import logging
import multiprocessing
import threading
import time

import msgpack
import pytest
import tornado.gen
import zmq.eventloop.future

import salt.config
import salt.transport.base
import salt.transport.zeromq
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
from salt.master import SMaster
from tests.conftest import FIPS_TESTRUN
from tests.support.mock import AsyncMock, MagicMock

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


def run_loop_in_thread(loop, evt):
    """
    Run the provided loop until an event is set
    """
    loop.make_current()

    @tornado.gen.coroutine
    def stopper():
        yield tornado.gen.sleep(0.1)
        while True:
            if not evt.is_set():
                loop.stop()
                break
            yield tornado.gen.sleep(0.3)

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

        self.io_loop = tornado.ioloop.IOLoop()
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
    @tornado.gen.coroutine
    def _handle_payload(cls, payload):
        """
        TODO: something besides echo
        """
        cls.mock._handle_payload_hook()
        raise tornado.gen.Return((payload, {"fun": "send_clear"}))


async def test_req_server_garbage_request(io_loop):
    """
    Validate invalid msgpack messages will not raise exceptions in the
    RequestServers's message handler.
    """
    opts = salt.config.master_config("")
    request_server = salt.transport.zeromq.RequestServer(opts)

    def message_handler(payload):
        return payload

    request_server.post_fork(message_handler, io_loop)

    byts = msgpack.dumps({"foo": "bar"})
    badbyts = byts[:3] + b"^M" + byts[3:]

    try:
        ret = await request_server.handle_message(None, badbyts)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(f"Exception was raised {exc}")
    finally:
        request_server.close()

    assert ret == {"msg": "bad load"}


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
    with salt.transport.zeromq.PublishClient(
        minion_opts, io_loop, host=minion_opts["master_ip"], port=121212
    ) as client:
        client.send(b"asf")


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
    client = salt.transport.zeromq.PublishClient(
        minion_opts, io_loop, host=minion_opts["master_ip"], port=121212
    )
    await client.connect()
    try:
        assert client._closing is False
        with pytest.warns(salt.transport.base.TransportWarning):
            client.__del__()  # pylint: disable=unnecessary-dunder-call
    finally:
        client.close()
