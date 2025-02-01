import copy
import logging
import shutil
from pathlib import Path

import pytest
from saltfactories.utils import random_string

try:
    import cryptography
    from cryptography.hazmat.primitives import serialization

    import salt.utils.x509 as x509util

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
def ssh_pkidir(tmp_path_factory):
    _ssh_pkidir = tmp_path_factory.mktemp("pki")
    try:
        yield _ssh_pkidir
    finally:
        shutil.rmtree(str(_ssh_pkidir), ignore_errors=True)


@pytest.fixture(scope="module", autouse=True)
def sshpki_data(
    ssh_pkidir,
    rsa_privkey,
    rsa_privkey_enc,
    rsa_pubkey,
):
    with pytest.helpers.temp_file("key", rsa_privkey, ssh_pkidir) as privkey_file:
        with pytest.helpers.temp_file("key_enc", rsa_privkey_enc, ssh_pkidir):
            with pytest.helpers.temp_file("key_pub", rsa_pubkey, ssh_pkidir):
                yield privkey_file


@pytest.fixture(scope="module")
def sshpki_salt_master(salt_factories, ca_minion_id, sshpki_master_config):
    factory = salt_factories.salt_master_daemon(
        "sshpki-master", defaults=sshpki_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def ca_minion_id():
    return random_string("sshpkica-minion", uppercase=False)


@pytest.fixture(scope="module")
def sshpki_minion_id():
    return random_string("sshpki-minion", uppercase=False)


@pytest.fixture(scope="module")
def ca_minion_config(sshpki_minion_id, ca_key, ca_key_enc):
    return {
        "open_mode": True,
        "ssh_signing_policies": {
            "testhostpolicy": {
                "cert_type": "host",
                "signing_private_key": ca_key,
                "key_id": "from_signing_policy",
                "valid_principals": ["from_host_signing_policy"],
                "extensions": False,
                "critical_options": False,
            },
            "testuserpolicy": {
                "cert_type": "user",
                "signing_private_key": ca_key,
                "key_id": "from_signing_policy",
                "valid_principals": ["from_user_signing_policy"],
                "critical_options": {
                    "force-command": "echo hi",
                    "source-address": False,
                },
                "extensions": {
                    "permit-X11-forwarding": True,
                    "permit-agent-forwarding": True,
                    "permit-port-forwarding": True,
                    "permit-pty": True,
                    "permit-user-rc": False,
                },
            },
            "testencpolicy": {
                "cert_type": "host",
                "key_id": "from_signing_policy",
                "signing_private_key": ca_key_enc,
                "signing_private_key_passphrase": "correct horse battery staple",
                "valid_principals": ["from_host_signing_policy"],
            },
            "testmatchpolicy": {
                "minions": sshpki_minion_id,
                "key_id": "from_matching_policy",
                "cert_type": "host",
                "signing_private_key": ca_key,
                "valid_principals": ["from_host_signing_policy"],
            },
            "testmatchfailpolicy": {
                "minions": "notallowed",
                "key_id": "from_matchfail_policy",
            },
            "testcompoundmatchpolicy": {
                "minions": "G@testgrain:foo",
                "cert_type": "user",
                "signing_private_key": ca_key,
                "key_id": "from_compound_match_policy",
                "valid_principals": ["from_compound_matching_policy"],
            },
            "testprincipalspolicy": {
                "cert_type": "host",
                "valid_principals": ["a", "b", "c"],
                "signing_private_key": ca_key,
            },
            "testallprincipalspolicy": {
                "cert_type": "host",
                "all_principals": True,
                "signing_private_key": ca_key,
            },
        },
    }


@pytest.fixture(scope="module", autouse=True)
def sshpkica_salt_minion(sshpki_salt_master, ca_minion_id, ca_minion_config):
    assert sshpki_salt_master.is_running()
    factory = sshpki_salt_master.salt_minion_daemon(
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
def sshpki_salt_minion(sshpki_salt_master, sshpki_minion_id):
    assert sshpki_salt_master.is_running()
    factory = sshpki_salt_master.salt_minion_daemon(
        sshpki_minion_id,
        defaults={
            "open_mode": True,
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
def sshpki_master_config(ca_minion_id):
    return {
        "open_mode": True,
        "peer": {
            ".*": [
                "ssh_pki.sign_remote_certificate",
            ],
        },
        "peer_run": {
            ca_minion_id: [
                "match.compound_matches",
            ],
        },
    }


@pytest.fixture(scope="module")
def rsa_privkey():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcnNhAAAA
AwEAAQAAAQEAt11Mkho+ChXlHC33p5I+K0r2wldrHV48T+5fHtuOrHNsaR01perekmDFQMvnhgDh
P/ibFENrFgo/yg2MHh/SldgC6fQFqZr89uJ+/E63oZ3+EIvUdQWiN8jiPkgKTTOlMXh2DjuPPa6U
C8hEZwnE5lg+/UN5BjiivZCbO0/Ll8/MXlPvSk3tdIao3twHJ4WwKYPotXwZ6LUM7HFloC/yPLfj
/AQhz6GO1fT5wLobDefB8Wpg2bWPO0yLvKlDGbZWzn2xy7deP2WrjqUsgTM9PaUKLIVBEgB/Apw2
FUkNkM6lHGM1bBAsiY5L3ISqBIku1us2TvwRZRGKDQYYIm3mbwAAA7gckLhOHJC4TgAAAAdzc2gt
cnNhAAABAQC3XUySGj4KFeUcLfenkj4rSvbCV2sdXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/
+JsUQ2sWCj/KDYweH9KV2ALp9AWpmvz24n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHYOO489rpQL
yERnCcTmWD79Q3kGOKK9kJs7T8uXz8xeU+9KTe10hqje3AcnhbApg+i1fBnotQzscWWgL/I8t+P8
BCHPoY7V9PnAuhsN58HxamDZtY87TIu8qUMZtlbOfbHLt14/ZauOpSyBMz09pQoshUESAH8CnDYV
SQ2QzqUcYzVsECyJjkvchKoEiS7W6zZO/BFlEYoNBhgibeZvAAAAAwEAAQAAAQA6mf3Lv8lODdtQ
GzzH+EwYJ/ge+jNIioJ6BTOvN/osESN3oJcxtJN3cqf34nLW99cFS928JyPFQndKivPZ+M+jhgrA
XHWm09q+yHpPBpVXeJfnD9lRoQBMFc6AmyN3sua7ncUVHWHVE8NK1LFPwOaFu3Q+Gt9F5rnUHbAO
z5zAomT10HfQd9yeDCdywAFsPklwbzmzv72ps3+CSG+ppRm+oh1GYYe7zWmX4SBPuTJbx9BTcuWd
yQTvSUIamP/22gxoNMzNBkYu/WeXNpB5iHGazNMAIEdyJ9x8VimnUIyZeW/hIPXt5MUW/WfFOE8Z
zzQ/+MTPF+uSfBC54tJQUvrxAAAAgD4wQaNkRY5jNZ3c4SUsrzwDDdbWH0SbTGLcnCWpd809apTN
adIBI+vt74kZCYafOqOOldyeU3Akw/fc9+BoBrR62boAYTSWlWNFqsNcE0AjEJbO0fIm2ngr8Z+o
vFp7fIyWQaIklmV0eyetAOz4InF+xC7SJqH2qm38kQvc0bdWAAAAgQDlg1w1HnyiBmooml3Ql5ln
uq+Fv8XZ/xxfVxRY5MCugVAR9eLQcMUJ/s3o44VEu1N3GAe1Dge3HYSQMPtZHIIe2AG38u1wHR+t
fFAQswoOD1Fn3O69CIG8kjzqdPLo12E+0+gJI5ki6lgAGEkVbQW4GsqVm4jBF0SPjUTfN5FRlwAA
AIEAzIaKrsfUUAPBCLuYeiZGfSCiXtdVZ+Yo8ADMwHA7iMSWG6ushLNwcV3PqRjVbW3xfM+9OghX
/zM6sratQmVpqhTBwQnyXBJp5SFT2n/XFYwkKhERBukBB/uEcI6M4HYhP8Z/N8lE7PNuY0ylnmrT
Cy/i60jGoFHQaROUPbs2/OkAAAAAAQID
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def rsa_privkey_enc():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAABA8ZLxKjCh9dRM4
7AmjoqGqAAAAEAAAAAEAAAEXAAAAB3NzaC1yc2EAAAADAQABAAABAQC3XUySGj4KFeUcLfenkj4r
SvbCV2sdXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/+JsUQ2sWCj/KDYweH9KV2ALp9AWpmvz2
4n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHYOO489rpQLyERnCcTmWD79Q3kGOKK9kJs7T8uXz8xe
U+9KTe10hqje3AcnhbApg+i1fBnotQzscWWgL/I8t+P8BCHPoY7V9PnAuhsN58HxamDZtY87TIu8
qUMZtlbOfbHLt14/ZauOpSyBMz09pQoshUESAH8CnDYVSQ2QzqUcYzVsECyJjkvchKoEiS7W6zZO
/BFlEYoNBhgibeZvAAADwDiKlu/+uo3XsapQBgGxZOSTHY1bqXZG1qh1EaE0DxXl0RQApJkZCutV
2wWN8VaCNbtdcLgDTqC8WMHd/QzseJBWabnIUHZXYsCbU9BmcfjUhCQ0kyN2zSb4YmsM73PqMX6I
5usU0nVAV/UhBSMg7tIzMVBQzYLYl+eypW9usp5HYb8dw/vMhQY+a1AYqIpe9vZlPohso8U2Q9bL
LiMNjMSSWcgh2b3i/LbixzHTGSibF9/izntSem/jxnoZ27R1r97KcuxPF3uKfPlrlpsmzNqhVi0d
4YWMttG3EUrpsGHUG5Ylp8bXnfMfmFkmkiEGjU/Gf30tiKlFznQ4G9luYn7h4Rs8vx9U7Xolhz22
yqJ0FxvvY9HYIhK6WTqOdPKE7O1cy1cn9Rne6RG4ALmETjbVh1dMCIKBFaIYztWIoT87XJrH3piD
xRlMQog7Cim/a2zd1l/G+iyEDBoVUzWx5WNJBiJgt9ZbYEJz1cJiWFDJhzWO1mFXYzNaJdfUdL43
xZjU+sxCxXuV+ps6nBjz9CmnI7hkNAIoa9lBNUo8uWds2DnNm0QU48bliVtxcLcjAdpZev5H1Hfx
bPgHDrja3F0fbtJaoadIn/xh8c0CTtOCKgjS1up9YnB2AL+bFoX0vcl13kRvuxnpUDaxQ2xehETR
SBupMQmGcdSSOUhLIF4/QJFijwMHNhUcIJqgzhT256z/dEKxtofi4Q9TiRjDT4uENO9Uy/FbZWAI
zaW3TLPZAnTLTIishfCOOm0yb9XmuxM4hLgGpqAHSxEvSqMXS4fe+BIdj2i5cOsB/N3//OE1yQ1M
qeMqTyvXEbK+PAH65rdhE6xyeJFeKV+fil7dyZX41R6FUtZ9ls3AXcmqFIq463n7MvUGkl8zqMvz
EzH8oCQRJ1Taly9JsLgCd7UbHpokeQeMYKyd5+muYvBu0qX2HPD0exJ5uJSxSqq+0NrlDKmY1INb
/XcPBjxVtKsXoTRfh/vs+TcLxwYbAWymWCdX3k4maa7oJ3ZOc0L5/ypeVUaecW4PcyXlYzEAfIwK
nFAirfDVSpjBochJfNBbhCgmtdmq3nUh8CI7AExJmVrWvEbJ6klJMVet0m50mfqyhBI5idw2YfKs
qxOoAdt3IZIxmGG+pyDeeFB8X9O5RF1BVnFsqNPHEqdRtVD7qPSYBaZDhtgFVJbstwW3+///nyLP
5B5yBiGVm0aFXpFcVeCHYX817crRC+0h/HA5fECosGRMZFZEAJh5CHivuKNvhseKdnWXLwkfIpuO
Ojnp0x6Zow==
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def rsa_pubkey():
    return (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3XUySGj4KFeUcLfenkj4rSvbCV2s"
        "dXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/+JsUQ2sWCj/KDYweH9KV2ALp9AWpmv"
        "z24n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHYOO489rpQLyERnCcTmWD79Q3kGOKK9k"
        "Js7T8uXz8xeU+9KTe10hqje3AcnhbApg+i1fBnotQzscWWgL/I8t+P8BCHPoY7V9PnA"
        "uhsN58HxamDZtY87TIu8qUMZtlbOfbHLt14/ZauOpSyBMz09pQoshUESAH8CnDYVSQ2"
        "QzqUcYzVsECyJjkvchKoEiS7W6zZO/BFlEYoNBhgibeZv"
    )


@pytest.fixture(scope="module")
def ca_key():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcnNhAAAA
AwEAAQAAAQEAmRii0ZT9KoL3aC9X7I8uQmcVGa4G7qOlyInNxGgKPC3s5+kshIVTMQfugd1irFT7
crF6Kamigq0S3uNBzpq/IxQBIRq8n7nHHFxiTgi+SK61XXMDdlbLsdXZxh7TkTMYPp32nmKUFDdd
xAVQCGwFvzkV2tbtxpiRO6E/60b22Lpt3qS0JdSgSYp9q0IFv2iNR+Yp+Kovx/I8+RySdhgecpRr
16Qul+DqvEqNtXvNJv4uA1nh34GCKBvNa8JekCYhGWpiXKvDaJREEFfVtuL0YrgDCS6JmbqMreYq
zsl8+QN9gEkt4JjDTQkEGUI7a4ZY+m69w2eN5eT0DebaNWGzkQAAA7gCJksAAiZLAAAAAAdzc2gt
cnNhAAABAQCZGKLRlP0qgvdoL1fsjy5CZxUZrgbuo6XIic3EaAo8Lezn6SyEhVMxB+6B3WKsVPty
sXopqaKCrRLe40HOmr8jFAEhGryfucccXGJOCL5IrrVdcwN2Vsux1dnGHtORMxg+nfaeYpQUN13E
BVAIbAW/ORXa1u3GmJE7oT/rRvbYum3epLQl1KBJin2rQgW/aI1H5in4qi/H8jz5HJJ2GB5ylGvX
pC6X4Oq8So21e80m/i4DWeHfgYIoG81rwl6QJiEZamJcq8NolEQQV9W24vRiuAMJLomZuoyt5irO
yXz5A32ASS3gmMNNCQQZQjtrhlj6br3DZ43l5PQN5to1YbORAAAAAwEAAQAAAQAcJGIxonCTMvXl
qeZAruUzAZ3oVYwiq+Rao7I2a2WOQGbvDnbHeXacabfXGWn9AbYjFCq/o9YirUvtutqq7tk5yoCW
pEKOHelS9kx/ya2o0Ky4G99EDpps+0GH4LzFUR4gzIq7/KT5vl+3G77lfW3lA8pXqvCUdBEmY/LK
/gV8OyffLxdQMIYCucpVpJq/wSiIYdd3DVK2TvlmUsR0DnvF5zo8/b7nvkALElXdA5G9NUL+k+XZ
0iDiWB0Ezokg5/VokhhhP8NcgiHeO00XHE6AAQ8rbUq9cwRgn0oqyC4ZYMc68MZOQhn2GKcYTRxG
YbGC6xoIUWrvaQq1/L4NEDIRAAAAgB9FHj/pVd/7HDjkGF9YapBu4kvuv9AxGvOVOWWHIk0pQl/L
vOEFj0gz4xl+BEdIDpX0RVS1p0wPD3h8uBKWQ5q2t4wOIzGidfaL+u/NHo4MPVC+cOCfgsRU7sy2
vN9kOjNpP7C3QTOzojq2vJ0zkJt+nZ3IA6OxyvS1Ebc0j88qAAAAgQDVjG+C+YyrYy9m5KBoj5T4
UEjNzgCr9t6ANSHObQjQxafRfeB4gT7vv65xna7Q4I8ATm2wITty1LETLNWbc2B4W5Mir8CnaUw0
P9Eyxql7VaTrHU1M3ee50Yquz1UEFLat1JXE/jMc2vs7s/W5Vd8uitom3uK8IkY/v3XOC4nk1QAA
AIEAt4fCQs36AcsYngt7oboKBMCnaiFWfupvZTAC86kd7VcuF74r7IrC4U9Oohwl1l6jXU90p0Mm
qJJROD1G3S1IFenRXQ6aIizaO7WkFRBeEuUtHwI0MbBq2cDjVzvRsu9qnLgMCeVMuBmj7pVG+Isf
zgx0+GaEc+f1RlC0qh6eIc0AAAAAAQID
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def ca_key_enc():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAACmFlczI1Ni1jdHIAAAAGYmNyeXB0AAAAGAAAABAo0CeCU7RU21xt
OjRqiR2WAAAAEAAAAAEAAAEXAAAAB3NzaC1yc2EAAAADAQABAAABAQCZGKLRlP0qgvdoL1fsjy5C
ZxUZrgbuo6XIic3EaAo8Lezn6SyEhVMxB+6B3WKsVPtysXopqaKCrRLe40HOmr8jFAEhGryfuccc
XGJOCL5IrrVdcwN2Vsux1dnGHtORMxg+nfaeYpQUN13EBVAIbAW/ORXa1u3GmJE7oT/rRvbYum3e
pLQl1KBJin2rQgW/aI1H5in4qi/H8jz5HJJ2GB5ylGvXpC6X4Oq8So21e80m/i4DWeHfgYIoG81r
wl6QJiEZamJcq8NolEQQV9W24vRiuAMJLomZuoyt5irOyXz5A32ASS3gmMNNCQQZQjtrhlj6br3D
Z43l5PQN5to1YbORAAADwIahmMW2HPaQ+r0WV3eT5lkbQjeTIkOo47PexilFof9ZYoOOk3AjcgYP
1SEhq4BXnMnpTVbRUkmzR7+od7tXrqVC9Eo3NuOwyjZwRJuHB+zPKpYqZ9SPOMRVYxx75yUmXnCu
Hsm8zT9F1izm/KQOyoSlbcWK3uQSSvYHYAWku/5bc6+fCPbgFYlB1Bk+cxjeGOPD+qDWQd4IKXj/
W/KCE8ncjQIZkrX1fgPGJsxCJwNUwYpJUad2+8XaZJIAIur36tlyNw+1JmQHSGMhfLW1P+tDXAIc
JJ+KpK/uVhYX5uOdER3/trwa6YQBHuUjo3sGrfYYTprd+WH0PbN2QJ9Vi2m5gJLY7CjCod7ecjbJ
ntTN9xucis+I7eZZPHhd8MO9wNQkXRwy07ZPawExlv2EVDUsofHQxiuHkvPZHNq4eFDz906xIk0v
n0X9IBrVtjg+bvnhl9XG86Ay5NAD7vCquqEqZAAHet24oi7yJmOkAJVA/0PaPzaALfp1a7noFFud
FuC9PmmdTe0gL1m1pQki1fIFMk2dxB83pQiBJThn9C3KhbrtsCN00kWxb3Ezv2mFPNeEs3Q9W7r5
mHVuJfVDusXAdXlpp+EcQueZW1r0Qtnf0UbH57LiTt6S1MUEYn3jgIE/ynHOPTrv0RgE8udCq8/g
1gUcZwL8BLJVCu+Dllj4/l/s/E3BzaTCzmc48toAdbeoZ1+nzXBCez1i8QQZ57gQK7hVfNCqCUD9
yNw84panB1lkxvBxFmN05dKxeBCGY0Bpxnl5xb2ND+rASXCELSEnHxt+9FVEdjrlpyg+KUnuBort
JmmK/VKmeW2yk+7kHDTefKpRiK7PNF1gUko15gzegq0YEGDewo/RT/c9BaYHZougg5HBjT6bUHaN
6x2Jc75z5ILXaeLrsavIyYuhMwpBrMYSPm/xNZvBxPiM+AyhCq2YAgS0eV3Asd4h7HB90NZHbwjc
nvmCLpiZtn269dM1wZdYUGaPCf6Gmj5OojJVRhgaXD8SHOzvb5HqQnco3e+KiVrFCGvfn/S8CTnv
CsQx2szAQcgkO16xsKZC8p1DAJSH+palgYRY2gMjXDzQN57RBGZPd2wwdSUc/iYXjUnXz782Nb/W
a7MutFQiFnqr0WUXscoenXsxDYjU8D81hbqkxVXzX/uwOmux0ilPwX1RlvjB2TuZ0YjDBtdprOYf
tXpvXY2joVcZBnblNTC+AMZQAza2xRdT5/VdNK7b6cdjQ00lo+OMRNeWLcjEL6JI8siEAywW/h69
Dft9BkNgrA==
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture
def ca_pub():
    return (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCZGKLRlP0qgvdoL1fsjy5CZxUZrg"
        "buo6XIic3EaAo8Lezn6SyEhVMxB+6B3WKsVPtysXopqaKCrRLe40HOmr8jFAEhGryf"
        "ucccXGJOCL5IrrVdcwN2Vsux1dnGHtORMxg+nfaeYpQUN13EBVAIbAW/ORXa1u3GmJ"
        "E7oT/rRvbYum3epLQl1KBJin2rQgW/aI1H5in4qi/H8jz5HJJ2GB5ylGvXpC6X4Oq8"
        "So21e80m/i4DWeHfgYIoG81rwl6QJiEZamJcq8NolEQQV9W24vRiuAMJLomZuoyt5i"
        "rOyXz5A32ASS3gmMNNCQQZQjtrhlj6br3DZ43l5PQN5to1YbOR"
    )


@pytest.fixture
def cert_args(ca_minion_id, sshpki_data):
    return {
        "ca_server": ca_minion_id,
        "signing_policy": "testhostpolicy",
        "private_key": str(sshpki_data),
        "key_id": "from_args",
    }


@pytest.fixture
def cert_arg_exts():
    return {
        "permit-X11-forwarding": True,
        "permit-agent-forwarding": True,
        "permit-port-forwarding": True,
        "permit-pty": True,
        "permit-user-rc": False,
    }


@pytest.fixture
def cert_expected_exts():
    return {
        b"permit-X11-forwarding": b"",
        b"permit-agent-forwarding": b"",
        b"permit-port-forwarding": b"",
        b"permit-pty": b"",
    }


@pytest.fixture
def cert_arg_opts():
    return {
        "force-command": "echo hi",
        "no-port-forwarding": True,
        "verify-required": False,
    }


@pytest.fixture
def cert_expected_opts():
    return {
        b"force-command": b"echo hi",
        b"no-port-forwarding": b"",
    }


@pytest.fixture(scope="module")
def sshpki_salt_run_cli(sshpki_salt_master):
    return sshpki_salt_master.salt_run_cli()


@pytest.fixture(scope="module")
def ssh_salt_call_cli(sshpki_salt_minion):
    return sshpki_salt_minion.salt_call_cli()


def test_sign_remote_certificate(ssh_salt_call_cli, cert_args, ca_key, rsa_privkey):
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_match(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testmatchpolicy"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_matching_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_compound_match(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testcompoundmatchpolicy"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_compound_match_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_enc(ssh_salt_call_cli, cert_args, ca_key, rsa_privkey):
    cert_args["private_key"] += "_enc"
    cert_args["private_key_passphrase"] = "hunter1"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_ca_enc(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testencpolicy"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_pubkey(
    ssh_salt_call_cli, cert_args, sshpki_data, ca_key, rsa_privkey
):
    cert_args.pop("private_key")
    cert_args["public_key"] = str(sshpki_data.parent / "key_pub")
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


def test_sign_remote_certificate_nonexistent_policy(ssh_salt_call_cli, cert_args):
    cert_args["signing_policy"] = "missingpolicy"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert not ret.data
    assert "signing_policy must be specified and defined" in ret.stderr


def test_sign_remote_certificate_disallowed_policy(ssh_salt_call_cli, cert_args):
    cert_args["signing_policy"] = "testmatchfailpolicy"
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert not ret.data
    assert "minion not permitted to use specified signing policy" in ret.stderr


def test_get_signing_policy_remote(
    ssh_salt_call_cli, cert_args, ca_minion_config, ca_pub
):
    testpolicy = copy.deepcopy(
        ca_minion_config["ssh_signing_policies"]["testencpolicy"]
    )
    testpolicy.pop("signing_private_key", None)
    testpolicy.pop("signing_private_key_passphrase", None)
    testpolicy["signing_public_key"] = ca_pub
    ret = ssh_salt_call_cli.run(
        "ssh_pki.get_signing_policy", "testencpolicy", ca_server=cert_args["ca_server"]
    )
    assert ret.data
    assert ret.data == testpolicy


def test_sign_remote_certificate_ext_opt_override(ssh_salt_call_cli, cert_args):
    cert_args["signing_policy"] = "testuserpolicy"
    cert_args["extensions"] = {"permit-user-rc": True, "no-touch-required": True}
    cert_args["critical_options"] = {
        "force-command": "rm -rf /",
        "source-address": "1.3.3.7",
        "verify-required": True,
    }
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert b"permit-user-rc" not in cert.extensions
    assert b"no-touch-required" in cert.extensions
    assert cert.critical_options[b"force-command"] == b"echo hi"
    assert cert.critical_options[b"verify-required"] == b""
    assert b"source-address" not in cert.critical_options


@pytest.mark.parametrize(
    "principals,expected", [(["a", "b"], {b"a", b"b"}), (["a", "d"], {b"a"})]
)
def test_sign_remote_certificate_principals_override(
    ssh_salt_call_cli, cert_args, principals, expected
):
    """
    Ensure valid_principals can only be a subset of the ones dictated
    by the signing policy.
    """
    cert_args["signing_policy"] = "testprincipalspolicy"
    cert_args["valid_principals"] = principals
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == expected


def test_sign_remote_certificate_all_principals_from_local_override(
    ssh_salt_call_cli, cert_args
):
    """
    Ensure requesting all principals to be valid when the policy
    dictates a set results in the set from the signing policy to be valid.
    """
    cert_args["signing_policy"] = "testprincipalspolicy"
    cert_args["all_principals"] = True
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == {b"a", b"b", b"c"}


def test_sign_remote_certificate_all_principals_on_remote_override(
    ssh_salt_call_cli, cert_args
):
    """
    Ensure requesting a set of principals to be valid when the policy
    allows all results in only the set to be valid.
    """
    cert_args["signing_policy"] = "testallprincipalspolicy"
    cert_args["valid_principals"] = ["a"]
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert set(cert.valid_principals) == {b"a"}


def test_sign_remote_certificate_copypath(ssh_salt_call_cli, cert_args, tmp_path):
    cert_args["copypath"] = str(tmp_path)
    ret = ssh_salt_call_cli.run("ssh_pki.create_certificate", **cert_args)
    assert ret.data
    cert = _get_cert(ret.data)
    assert (tmp_path / f"{cert.serial:x}.crt").exists()


def test_create_private_key(ssh_salt_call_cli):
    """
    Ensure calling from the CLI works as expected.
    """
    ret = ssh_salt_call_cli.run("ssh_pki.create_private_key")
    assert ret.returncode == 0
    assert ret.data
    assert ret.data["private_key"].startswith("-----BEGIN OPENSSH PRIVATE KEY-----")


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, serialization.SSHCertificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, _get_privkey(privkey))


def _signed_by(cert, privkey):
    cert.verify_cert_signature()
    return x509util.is_pair(cert.signature_key(), _get_privkey(privkey))


def _get_cert(cert):
    try:
        p = Path(cert)
        if p.exists():
            cert = p.read_bytes()
    except Exception:  # pylint: disable=broad-except
        pass
    if isinstance(cert, str):
        cert = cert.encode()
    ret = serialization.load_ssh_public_identity(cert)
    if not isinstance(ret, serialization.SSHCertificate):
        raise ValueError(f"Expected SSHCertificate, got {ret.__class__.__name__}")
    return ret


def _get_privkey(pk, passphrase=None):
    try:
        p = Path(pk)
        if p.exists():
            pk = p.read_bytes()
        else:
            pk = pk.encode()
    except Exception:  # pylint: disable=broad-except
        pass
    if isinstance(pk, str):
        pk = pk.encode()
    if passphrase is not None:
        passphrase = passphrase.encode()

    return serialization.load_ssh_private_key(pk, password=passphrase)
