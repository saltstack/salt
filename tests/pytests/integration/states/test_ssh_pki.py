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
def sshpki_pkidir(tmp_path_factory):
    _sshpki_pkidir = tmp_path_factory.mktemp("pki")
    try:
        yield _sshpki_pkidir
    finally:
        shutil.rmtree(str(_sshpki_pkidir), ignore_errors=True)


@pytest.fixture(scope="module", autouse=True)
def sshpki_data(
    sshpki_pkidir,
    rsa_privkey,
    rsa_privkey_enc,
    rsa_pubkey,
):
    with pytest.helpers.temp_file("key", rsa_privkey, sshpki_pkidir):
        with pytest.helpers.temp_file("key_enc", rsa_privkey_enc, sshpki_pkidir):
            with pytest.helpers.temp_file("key_pub", rsa_pubkey, sshpki_pkidir):
                yield sshpki_pkidir


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
def ca_minion_config(sshpki_minion_id, ca_key_enc, rsa_privkey, ec_privkey):
    return {
        "open_mode": True,
        "ssh_signing_policies": {
            "testpolicy": {
                "cert_type": "user",
                "signing_private_key": ca_key_enc,
                "signing_private_key_passphrase": "correct horse battery staple",
                "key_id": "from_signing_policy",
                "valid_principals": ["from_signing_policy"],
                "critical_options": {
                    "force-command": "echo hi",
                    "no-port-forwarding": True,
                    "verify-required": False,
                },
                "extensions": {
                    "permit-X11-forwarding": True,
                    "permit-agent-forwarding": True,
                    "permit-port-forwarding": True,
                    "permit-pty": True,
                    "permit-user-rc": False,
                },
            },
            "testchangepolicy": {
                "cert_type": "host",
                "signing_private_key": ca_key_enc,
                "signing_private_key_passphrase": "correct horse battery staple",
                "key_id": "from_changed_signing_policy",
                "valid_principals": ["from_signing_policy"],
                "critical_options": {
                    "force-command": "echo there",
                    "no-port-forwarding": False,
                    "verify-required": True,
                },
                "extensions": {
                    "permit-X11-forwarding": True,
                    "permit-agent-forwarding": False,
                    "permit-port-forwarding": True,
                    "permit-pty": True,
                    "permit-user-rc": True,
                },
            },
            "testchangecapolicy": {
                "cert_type": "user",
                "signing_private_key": ec_privkey,
                "key_id": "from_signing_policy",
                "valid_principals": ["from_user_signing_policy"],
                "critical_options": {
                    "force-command": "echo hi",
                    "no-port-forwarding": True,
                    "verify-required": False,
                },
                "extensions": {
                    "permit-X11-forwarding": True,
                    "permit-agent-forwarding": True,
                    "permit-port-forwarding": True,
                    "permit-pty": True,
                    "permit-user-rc": False,
                },
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
            ca_minion_id: [
                "match.compound",
            ],
        },
    }


@pytest.fixture
def privkey_new(sshpki_salt_master, tmp_path, ca_minion_id, ssh_salt_call_cli):
    state = f"""\
Private key:
  ssh_pki.private_key_managed:
    - name: {tmp_path}/my.key
    - algo: ec
    - backup: true
    - new: true
    {{% if salt["file.file_exists"]("{tmp_path}/my.key") -%}}
    - prereq:
      - ssh_pki: {tmp_path}/my.crt
    {{%- endif %}}

Certificate:
  ssh_pki.certificate_managed:
    - name: {tmp_path}/my.crt
    - ca_server: {ca_minion_id}
    - signing_policy: testpolicy
    - private_key: {tmp_path}/my.key
    - ttl_remaining: 999d
    - backup: true
    """
    with sshpki_salt_master.state_tree.base.temp_file("manage_cert.sls", state):
        ret = ssh_salt_call_cli.run("state.apply", "manage_cert")
        assert ret.returncode == 0
        assert ret.data[next(iter(ret.data))]["changes"]
        assert (tmp_path / "my.key").exists()
        assert (tmp_path / "my.crt").exists()
        yield


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


@pytest.fixture(scope="module")
def ca_pub():
    return (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCZGKLRlP0qgvdoL1fsjy5CZxUZrg"
        "buo6XIic3EaAo8Lezn6SyEhVMxB+6B3WKsVPtysXopqaKCrRLe40HOmr8jFAEhGryf"
        "ucccXGJOCL5IrrVdcwN2Vsux1dnGHtORMxg+nfaeYpQUN13EBVAIbAW/ORXa1u3GmJ"
        "E7oT/rRvbYum3epLQl1KBJin2rQgW/aI1H5in4qi/H8jz5HJJ2GB5ylGvXpC6X4Oq8"
        "So21e80m/i4DWeHfgYIoG81rwl6QJiEZamJcq8NolEQQV9W24vRiuAMJLomZuoyt5i"
        "rOyXz5A32ASS3gmMNNCQQZQjtrhlj6br3DZ43l5PQN5to1YbOR"
    )


@pytest.fixture(scope="module")
def ec_privkey():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAaAAAABNlY2RzYS1zaGEy
LW5pc3RwMjU2AAAACG5pc3RwMjU2AAAAQQScOqN2HTar84e+l3Er4Ti0ZsY3nbR9RkRsgZb0Flie
lc8SN/zIHSLroaJ21ofSqfu+mazGpGFWkNo34zSbBW5+AAAAoEaJqOBGiajgAAAAE2VjZHNhLXNo
YTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBJw6o3YdNqvzh76XcSvhOLRmxjedtH1GRGyBlvQW
WJ6VzxI3/MgdIuuhonbWh9Kp+76ZrMakYVaQ2jfjNJsFbn4AAAAhAL7DzNqGQYRNLOeXUt/t+DFz
R4+26CwTk8SDLHiIt2dpAAAAAAECAwQFBgc=
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture(scope="module")
def cert_exts():
    return (
        "ssh-rsa-cert-v01@openssh.com AAAAHHNzaC1yc2EtY2VydC12MDFAb3BlbnNzaC"
        "5jb20AAAAgkLBn5P+v6IYplxKHlGOX1MmcDeRkwFNKUumq9NqVSLIAAAADAQABAAABA"
        "QC3XUySGj4KFeUcLfenkj4rSvbCV2sdXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/"
        "+JsUQ2sWCj/KDYweH9KV2ALp9AWpmvz24n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHY"
        "OO489rpQLyERnCcTmWD79Q3kGOKK9kJs7T8uXz8xeU+9KTe10hqje3AcnhbApg+i1fB"
        "notQzscWWgL/I8t+P8BCHPoY7V9PnAuhsN58HxamDZtY87TIu8qUMZtlbOfbHLt14/Z"
        "auOpSyBMz09pQoshUESAH8CnDYVSQ2QzqUcYzVsECyJjkvchKoEiS7W6zZO/BFlEYoN"
        "BhgibeZvA2htsw1e8lQAAAABAAAADXNhbHRzdGFja3Rlc3QAAAARAAAABHNhbHQAAAA"
        "Fc3RhY2sAAAAAZJvNIgAAAABknR6iAAAANgAAAA1mb3JjZS1jb21tYW5kAAAAB2VjaG"
        "8gaGkAAAASbm8tcG9ydC1mb3J3YXJkaW5nAAAAAAAAADwAAAAVcGVybWl0LVgxMS1mb"
        "3J3YXJkaW5nAAAAAAAAABdwZXJtaXQtYWdlbnQtZm9yd2FyZGluZwAAAAAAAAAAAAAB"
        "FwAAAAdzc2gtcnNhAAAAAwEAAQAAAQEAmRii0ZT9KoL3aC9X7I8uQmcVGa4G7qOlyIn"
        "NxGgKPC3s5+kshIVTMQfugd1irFT7crF6Kamigq0S3uNBzpq/IxQBIRq8n7nHHFxiTg"
        "i+SK61XXMDdlbLsdXZxh7TkTMYPp32nmKUFDddxAVQCGwFvzkV2tbtxpiRO6E/60b22"
        "Lpt3qS0JdSgSYp9q0IFv2iNR+Yp+Kovx/I8+RySdhgecpRr16Qul+DqvEqNtXvNJv4u"
        "A1nh34GCKBvNa8JekCYhGWpiXKvDaJREEFfVtuL0YrgDCS6JmbqMreYqzsl8+QN9gEk"
        "t4JjDTQkEGUI7a4ZY+m69w2eN5eT0DebaNWGzkQAAARQAAAAMcnNhLXNoYTItNTEyAA"
        "ABAEQr+2fI7WweYEdQwq1y1y9PlnO1/HtndLnz2yb42b1OW1NSdTrk0zqgB5MUlXut9"
        "DjSF7u60ghZu2WVIInzbdBAgfimqZgYB0C30AL5MjWpcROeudHm0r3AAyA6cAbjd/hf"
        "cFvj2NZwXY7VWofrf4WLILULtseTPKdqivDkNzU4A4MsykqdQZfrc7TaL7Kk9G2U4mZ"
        "Trcm/H5O5uSJLhfe6tAZuaTnPcwIh4kZ+SGNjr9zslaenZpRH4ms6cbo7E3Pcq5iEdq"
        "xsuAIVF/4Viq0hnjs69WjDJIt9X1X5ZN+bb6TX9ndwPSdoNHxb6JLlWytRdCzhESeZd"
        "xJyPG8BRrI="
    )


@pytest.fixture
def cert_args(ca_minion_id, sshpki_data, tmp_path):
    return {
        "name": f"{tmp_path}/cert",
        "ca_server": ca_minion_id,
        "signing_policy": "testpolicy",
        "private_key": str(sshpki_data / "key"),
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


@pytest.fixture(params=[{}])
def existing_cert(ssh_salt_call_cli, cert_args, ca_key, rsa_privkey, request):
    cert_args.update(request.param)
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)
    yield cert_args["name"]


@pytest.fixture(scope="module")
def ssh_salt_call_cli(sshpki_salt_minion):
    return sshpki_salt_minion.salt_call_cli()


@pytest.fixture(scope="module")
def other_backend(cert_exts, ssh_salt_call_cli, sshpki_salt_master, ca_pub):
    module = f"""\
__virtualname__ = "other_backend"


def get_signing_policy(signing_policy, ca_server=None, donotfail=False):
    if donotfail is False:
        raise ValueError("Was not instructed to not fail :|")
    return {{
        "signing_public_key": "{ca_pub.strip()}",
        "cert_type": "user",
        "key_id": "saltstacktest",
        "serial_number": "03:68:6D:B3:0D:5E:F2:54",
        "not_before": "2023-06-28 08:03:14",
        "not_after": "2023-06-29 08:03:14",
        "critical_options": {{"force-command": "echo hi", "no-port-forwarding": True}},
        "extensions": {{"permit-X11-forwarding": True, "permit-agent-forwarding": True}},
        "valid_principals": ["salt", "stack"],
    }}

def create_certificate(
    ca_server=None,
    signing_policy=None,
    path=None,
    overwrite=False,
    raw=False,
    **kwargs,
):
    if not kwargs.get("donotfail"):
        raise ValueError("Was not instructed to not fail :|")
    return '''\
{cert_exts}'''
"""
    module_dir = Path(sshpki_salt_master.config["file_roots"]["base"][0]) / "_modules"
    module_tempfile = pytest.helpers.temp_file("other_backend.py", module, module_dir)
    try:
        with module_tempfile:
            ret = sshpki_salt_master.salt_run_cli().run("fileserver.update")
            assert ret.returncode == 0
            ret = ssh_salt_call_cli.run("saltutil.sync_modules")
            assert ret.returncode == 0
            assert "modules.other_backend" in ret.data
            yield
    finally:
        ret = ssh_salt_call_cli.run("saltutil.sync_modules")
        assert ret.returncode == 0


def test_certificate_managed_remote(ssh_salt_call_cli, cert_args, ca_key, rsa_privkey):
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_signing_policy"
    assert _signed_by(cert, ca_key)
    assert _belongs_to(cert, rsa_privkey)


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_policy_change(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangepolicy"
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert "key_id" in ret.data[next(iter(ret.data))]["changes"]
    cert = _get_cert(cert_args["name"])
    assert cert.key_id == b"from_changed_signing_policy"


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_signing_key_change(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["signing_policy"] = "testchangecapolicy"
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert "signing_private_key" in changes


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_no_changes_signing_policy_override(
    ssh_salt_call_cli, cert_args, ca_key, rsa_privkey
):
    cert_args["extensions"] = {"permit-user-rc": True}
    cert_args["critical_options"] = {"force-command": "rm -rf /"}
    cert_args["cert_type"] = "host"
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"] == {}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_remote_renew(ssh_salt_call_cli, cert_args):
    cert_cur = _get_cert(cert_args["name"])
    cert_args["ttl_remaining"] = "999d"
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial != cert_cur.serial


@pytest.mark.usefixtures("other_backend")
def test_certificate_managed_different_backend(
    ssh_salt_call_cli, cert_args, rsa_privkey, ca_key, cert_exts
):
    cert_args["backend"] = "other_backend"
    cert_args["backend_args"] = {"donotfail": True}
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert changes.get("created") == cert_args["name"]
    cert = _get_cert(cert_args["name"])
    assert cert.public_bytes().decode().strip() == cert_exts


@pytest.mark.usefixtures("other_backend")
@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_existing_different_backend(
    ssh_salt_call_cli, cert_args, rsa_privkey, ca_key, cert_exts
):
    cert_args["backend"] = "other_backend"
    cert_args["backend_args"] = {"donotfail": True}
    ret = ssh_salt_call_cli.run(
        "state.single", "ssh_pki.certificate_managed", **cert_args
    )
    assert ret.returncode == 0
    changes = ret.data[next(iter(ret.data))]["changes"]
    assert changes
    assert not changes["extensions"]["added"]
    assert not changes["extensions"]["changed"]
    assert set(changes["extensions"]["removed"]) == {
        "permit-port-forwarding",
        "permit-pty",
    }
    assert set(changes["principals"]["added"]) == {"salt", "stack"}
    assert set(changes["principals"]["removed"]) == {"from_signing_policy"}
    assert changes["key_id"] == {"old": "from_signing_policy", "new": "saltstacktest"}
    assert "critical_options" not in changes
    cert = _get_cert(cert_args["name"])
    assert cert.public_bytes().decode().strip() == cert_exts


@pytest.mark.usefixtures("privkey_new")
def test_privkey_new_with_prereq(ssh_salt_call_cli, tmp_path):
    cert_cur = _get_cert(tmp_path / "my.crt")
    pk_cur = _get_privkey(tmp_path / "my.key")
    assert _belongs_to(cert_cur, pk_cur)

    ret = ssh_salt_call_cli.run("state.apply", "manage_cert")
    assert ret.returncode == 0
    assert ret.data[next(iter(ret.data))]["changes"]
    cert_new = _get_cert(tmp_path / "my.crt")
    pk_new = _get_privkey(tmp_path / "my.key")
    assert _belongs_to(cert_new, pk_new)
    assert not _belongs_to(cert_new, pk_cur)


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
    if hasattr(pk, "private_bytes"):
        return pk
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
