import logging
import shutil

import pytest
from saltfactories.utils import random_string

log = logging.getLogger(__name__)


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
def sshpki_salt_master(salt_factories, ca_minion_id, sshpki_master_config):
    factory = salt_factories.salt_master_daemon(
        "sshpki-master", defaults=sshpki_master_config
    )
    with factory.started():
        yield factory


@pytest.fixture(scope="module")
def ssh_salt_ssh_cli(sshpki_salt_master, salt_ssh_roster_file, sshd_config_dir):
    return sshpki_salt_master.salt_ssh_cli(
        timeout=180,
        roster_file=salt_ssh_roster_file,
        target_host="localhost",
        client_key=str(sshd_config_dir / "client_key"),
        base_script_args=["--ignore-host-keys"],
    )


@pytest.fixture(scope="module")
def ca_minion_id():
    return random_string("sshpkica-minion", uppercase=False)


@pytest.fixture(scope="module")
def sshpki_minion_id():
    return "localhost"


@pytest.fixture(scope="module")
def ca_minion_config(sshpki_minion_id, ca_key, ca_key_enc, ec_privkey):
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
        "ssh-rsa-cert-v01@openssh.com AAAAHHNzaC1yc2EtY2VydC12MDFAb3BlbnNzaC5"
        "jb20AAAAgAutZE2GohcxGXD1rmPbhaLcN5uLcWjBk0KQIXOcDr5oAAAADAQABAAABAQC"
        "3XUySGj4KFeUcLfenkj4rSvbCV2sdXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/+Js"
        "UQ2sWCj/KDYweH9KV2ALp9AWpmvz24n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHYOO48"
        "9rpQLyERnCcTmWD79Q3kGOKK9kJs7T8uXz8xeU+9KTe10hqje3AcnhbApg+i1fBnotQz"
        "scWWgL/I8t+P8BCHPoY7V9PnAuhsN58HxamDZtY87TIu8qUMZtlbOfbHLt14/ZauOpSy"
        "BMz09pQoshUESAH8CnDYVSQ2QzqUcYzVsECyJjkvchKoEiS7W6zZO/BFlEYoNBhgibeZ"
        "vA2htsw1e8lQAAAABAAAADXNhbHRzdGFja3Rlc3QAAAARAAAABHNhbHQAAAAFc3RhY2s"
        "AAAAAZJvNIgAAAABknR6iAAAAOgAAAA1mb3JjZS1jb21tYW5kAAAACwAAAAdlY2hvIGh"
        "pAAAAEm5vLXBvcnQtZm9yd2FyZGluZwAAAAAAAAA8AAAAFXBlcm1pdC1YMTEtZm9yd2F"
        "yZGluZwAAAAAAAAAXcGVybWl0LWFnZW50LWZvcndhcmRpbmcAAAAAAAAAAAAAARcAAAA"
        "Hc3NoLXJzYQAAAAMBAAEAAAEBAJkYotGU/SqC92gvV+yPLkJnFRmuBu6jpciJzcRoCjw"
        "t7OfpLISFUzEH7oHdYqxU+3KxeimpooKtEt7jQc6avyMUASEavJ+5xxxcYk4IvkiutV1"
        "zA3ZWy7HV2cYe05EzGD6d9p5ilBQ3XcQFUAhsBb85FdrW7caYkTuhP+tG9ti6bd6ktCX"
        "UoEmKfatCBb9ojUfmKfiqL8fyPPkcknYYHnKUa9ekLpfg6rxKjbV7zSb+LgNZ4d+Bgig"
        "bzWvCXpAmIRlqYlyrw2iURBBX1bbi9GK4AwkuiZm6jK3mKs7JfPkDfYBJLeCYw00JBBl"
        "CO2uGWPpuvcNnjeXk9A3m2jVhs5EAAAEUAAAADHJzYS1zaGEyLTUxMgAAAQAUJpzjwKC"
        "Ib2oHLo4q6v6qN37ssRmprwtAVJaV9FmAgczroMyWiL3P5O7U4TLPzluODVRSzpI1K5j"
        "oeIheQQ24npcErmxVj3xkk4uFsaTgyAamQfnudlseltmNfzqYX6LStFco27bBM6x1V3p"
        "TPbOfd8m1g1JZEH8yGCt8J4zpVNs6NWTJ862PqdlQKYaZcfEdDyuW0AemSug7YXBe6XU"
        "6F5v55T8W4sGy3yLn9HWMFyvdtnH91Y8NzsC3JgQfuImPDmdH0hjg0Fr/9579EUEIiq3"
        "IHN7S4e2vrj7lIreSxPeKnkQNvrjmrPojLD9atastKTalIriT7mtfqzOTih7V"
    )
