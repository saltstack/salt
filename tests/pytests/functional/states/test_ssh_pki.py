from pathlib import Path

import pytest

try:
    import cryptography
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

    import salt.utils.x509 as x509util

    HAS_LIBS = True
except ImportError:
    HAS_LIBS = False

try:
    import bcrypt  # pylint: disable=unused-import

    HAS_BCRYPT = True
except ImportError:
    HAS_BCRYPT = False

CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skipif(HAS_LIBS is False, reason="Needs cryptography library"),
]


@pytest.fixture(scope="module")
def minion_config_overrides():
    return {
        "ssh_signing_policies": {
            "testhostpolicy": {
                "cert_type": "host",
                "valid_principals": ["from_host_signing_policy"],
                "allowed_extensions": [],
                "allowed_critical_options": [],
            },
            "testuserpolicy": {
                "cert_type": "user",
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
            "testprincipalspolicy": {
                "cert_type": "host",
                "valid_principals": ["a", "b", "c"],
            },
        },
    }


@pytest.fixture
def ssh(states):
    yield states.ssh_pki


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
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


@pytest.fixture
def rsa_pubkey():
    return (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC3XUySGj4KFeUcLfenkj4rSvbCV2s"
        "dXjxP7l8e246sc2xpHTWl6t6SYMVAy+eGAOE/+JsUQ2sWCj/KDYweH9KV2ALp9AWpmv"
        "z24n78Trehnf4Qi9R1BaI3yOI+SApNM6UxeHYOO489rpQLyERnCcTmWD79Q3kGOKK9k"
        "Js7T8uXz8xeU+9KTe10hqje3AcnhbApg+i1fBnotQzscWWgL/I8t+P8BCHPoY7V9PnA"
        "uhsN58HxamDZtY87TIu8qUMZtlbOfbHLt14/ZauOpSyBMz09pQoshUESAH8CnDYVSQ2"
        "QzqUcYzVsECyJjkvchKoEiS7W6zZO/BFlEYoNBhgibeZv"
    )


@pytest.fixture
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


@pytest.fixture
def ec_pubkey():
    return (
        "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNT"
        "YAAABBBJw6o3YdNqvzh76XcSvhOLRmxjedtH1GRGyBlvQWWJ6VzxI3/MgdIuuhonbW"
        "h9Kp+76ZrMakYVaQ2jfjNJsFbn4="
    )


@pytest.fixture
def ed25519_privkey():
    return """\
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAMwAAAAtzc2gtZWQyNTUx
OQAAACDRCIjV5alJaolYOvZSZMzH8gVgGp7LsKlum8O86Me5EQAAAIidIDmZnSA5mQAAAAtzc2gt
ZWQyNTUxOQAAACDRCIjV5alJaolYOvZSZMzH8gVgGp7LsKlum8O86Me5EQAAAEBc5nqUPbCxESlT
vH72xFJW6XGhm9Sm4CbrmcdfhucVdtEIiNXlqUlqiVg69lJkzMfyBWAansuwqW6bw7zox7kRAAAA
AAECAwQF
-----END OPENSSH PRIVATE KEY-----"""


@pytest.fixture
def ed25519_pubkey():
    return "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINEIiNXlqUlqiVg69lJkzMfyBWAansuwqW6bw7zox7kR"


@pytest.fixture
def cert_args(tmp_path, ca_key):
    return {
        "name": f"{tmp_path}/cert",
        "cert_type": "user",
        "all_principals": True,
        "signing_private_key": ca_key,
        "key_id": "success",
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


@pytest.fixture(params=[{}])
def existing_cert(
    ssh, cert_args, ca_key, rsa_privkey, request, minion_config_overrides
):
    cert_args["private_key"] = rsa_privkey
    cert_args.update(request.param)
    ret = ssh.certificate_managed(**cert_args)
    if "signing_policy" in cert_args:
        signing_policy = minion_config_overrides["ssh_signing_policies"][
            cert_args["signing_policy"]
        ]
        expected_type = signing_policy.get("cert_type", cert_args["cert_type"])
        expected_key_id = signing_policy.get("key_id", cert_args.get("key_id"))
        # This check is hard to do here
        expected_principals = False
    else:
        expected_type = cert_args["cert_type"]
        expected_key_id = cert_args.get("key_id")
        # This check is hard to do here
        expected_principals = [
            x.encode() for x in cert_args.get("valid_principals", [])
        ]
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        expected_type,
        key_id=expected_key_id,
        principals=expected_principals,
    )
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_cert_exts_opts(
    ssh,
    cert_args,
    cert_arg_exts,
    cert_expected_exts,
    cert_arg_opts,
    cert_expected_opts,
    ca_key,
    rsa_privkey,
    request,
):
    cert_args["private_key"] = rsa_privkey
    cert_args["extensions"] = cert_arg_exts
    cert_args["critical_options"] = cert_arg_opts
    cert_args.update(request.param)
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )
    assert cert.extensions == cert_expected_exts
    assert cert.critical_options == cert_expected_opts
    yield cert_args["name"]


@pytest.fixture(params=[{}])
def existing_pk(ssh, pk_args, request):
    pk_args.update(request.param)
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(
        ret,
        pk_args.get("algo", "rsa"),
        passphrase=pk_args.get("passphrase"),
    )
    yield pk_args["name"]


@pytest.fixture(params=["existing_cert"])
def existing_symlink(request):
    existing = request.getfixturevalue(request.param)
    test_file = Path(existing).with_name("symlink")
    test_file.symlink_to(existing)
    try:
        yield test_file
    finally:
        test_file.unlink(missing_ok=True)


@pytest.mark.parametrize("cert_type", ["user", "host"])
@pytest.mark.parametrize("algo", ["rsa", "ec", "ed25519"])
def test_certificate_managed_with_privkey(
    ssh, cert_args, ca_key, algo, request, cert_type
):
    privkey = request.getfixturevalue(f"{algo}_privkey")
    cert_args["private_key"] = privkey
    cert_args["cert_type"] = cert_type
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
def test_certificate_managed_with_privkey_enc(
    ssh, cert_args, rsa_privkey_enc, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey_enc
    cert_args["private_key_passphrase"] = "hunter1"
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
def test_certificate_managed_with_privkey_ca_enc(
    ssh, cert_args, rsa_privkey, ca_key, ca_key_enc
):
    cert_args["private_key"] = rsa_privkey
    cert_args["signing_private_key"] = ca_key_enc
    cert_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
def test_certificate_managed_with_privkey_enc_ca_enc(
    ssh, cert_args, rsa_privkey, rsa_privkey_enc, ca_key, ca_key_enc
):
    cert_args["private_key"] = rsa_privkey_enc
    cert_args["private_key_passphrase"] = "hunter1"
    cert_args["signing_private_key"] = ca_key_enc
    cert_args["signing_private_key_passphrase"] = "correct horse battery staple"
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


@pytest.mark.parametrize("algo", ["rsa", "ec", "ed25519"])
def test_certificate_managed_with_pubkey(ssh, cert_args, ca_key, algo, request):
    privkey = request.getfixturevalue(f"{algo}_privkey")
    pubkey = request.getfixturevalue(f"{algo}_pubkey")
    cert_args["public_key"] = pubkey
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


def test_certificate_managed_with_extensions(
    ssh, cert_args, cert_arg_exts, cert_expected_exts, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey
    cert_args["extensions"] = cert_arg_exts
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )
    assert cert.extensions == cert_expected_exts


def test_certificate_managed_with_signing_policy_host(
    ssh, cert_args, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey
    cert_args["signing_policy"] = "testhostpolicy"
    cert_args["cert_type"] = "user"
    cert_args.pop("all_principals", None)
    cert_args["valid_principals"] = ["from_call"]
    cert_args["extensions"] = {"permit-agent-forwarding": True}
    cert_args["critical_options"] = {"force-command": "rm -rf /"}

    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        "host",
        principals=[b"from_host_signing_policy"],
        key_id=cert_args.get("key_id"),
    )
    assert cert.critical_options == {}
    assert cert.extensions == {}


def test_certificate_managed_with_signing_policy_user(
    ssh, cert_args, rsa_privkey, ca_key
):
    cert_args["private_key"] = rsa_privkey
    cert_args["signing_policy"] = "testuserpolicy"
    cert_args["cert_type"] = "host"
    cert_args.pop("all_principals", None)
    cert_args["valid_principals"] = ["from_call"]
    cert_args["extensions"] = {"permit-user-rc": True, "no-touch-required": True}
    cert_args["critical_options"] = {
        "force-command": "rm -rf /",
        "verify-required": True,
        "source-address": "13.37.13.37",
    }

    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        "user",
        principals=[b"from_user_signing_policy"],
        key_id=cert_args.get("key_id"),
    )
    expected_options = {
        b"force-command": b"echo hi",
        b"no-port-forwarding": b"",
        b"source-address": b"13.37.13.37",
    }
    expected_extensions = {
        b"permit-X11-forwarding": b"",
        b"permit-agent-forwarding": b"",
        b"permit-port-forwarding": b"",
        b"permit-pty": b"",
        b"no-touch-required": b"",
    }
    assert cert.critical_options == expected_options
    assert cert.extensions == expected_extensions


def test_certificate_managed_test_true(ssh, cert_args, rsa_privkey):
    cert_args["private_key"] = rsa_privkey
    cert_args["test"] = True
    ret = ssh.certificate_managed(**cert_args)
    assert ret.result is None
    assert ret.changes
    assert not Path(cert_args["name"]).exists()


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_existing(ssh, cert_args):
    ret = ssh.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert_exts_opts")
def test_certificate_managed_existing_with_exts_opts(ssh, cert_args):
    ret = ssh.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"signing_policy": "testuserpolicy"}],
    indirect=True,
)
def test_certificate_managed_existing_with_signing_policy(ssh, cert_args):
    """
    Ensure signing policies are taken into account when checking for changes
    """
    ret = ssh.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"signing_policy": "testhostpolicy"}],
    indirect=True,
)
def test_certificate_managed_existing_with_signing_policy_override_no_changes(
    ssh, cert_args, cert_arg_exts, cert_arg_opts
):
    cert_args["valid_principals"] = ["from_call"]
    cert_args["extensions"] = cert_arg_exts
    cert_args["critical_options"] = cert_arg_opts
    cert_args["cert_type"] = "user"
    ret = ssh.certificate_managed(**cert_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_file")
def test_certificate_managed_existing_not_a_cert(ssh, cert_args, rsa_privkey, ca_key):
    """
    If `name` is not a valid certificate, a new one should be issued at the path
    """
    cert_args["private_key"] = rsa_privkey
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", [{"ttl": "10d"}], indirect=True)
@pytest.mark.parametrize("ttl,expected", [("1h", False), ("9999d", True)])
def test_certificate_managed_ttl_remaining(ssh, cert_args, ttl, expected):
    """
    The certificate should be reissued if ttl_remaining indicates it
    """
    cert_args["ttl_remaining"] = ttl
    ret = ssh.certificate_managed(**cert_args)
    assert bool(ret.changes) is expected
    if expected:
        assert "expiration" in ret.changes


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("ttl", ["1d", "9999d"])
def test_certificate_managed_ttl_does_not_override_ttl_remaining(ssh, cert_args, ttl):
    """
    The certificate should only be renewed when ttl_remaining indicates it,
    not when not_before/not_after change
    """
    cert_args["ttl"] = ttl
    ret = ssh.certificate_managed(**cert_args)
    assert not ret.changes


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_privkey_change(ssh, cert_args, ec_privkey, ca_key):
    cert_args["private_key"] = ec_privkey
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], ec_privkey, ca_key)
    assert ret.changes["private_key"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_pubkey_change(
    ssh, cert_args, ec_pubkey, ec_privkey, ca_key
):
    cert_args.pop("private_key")
    cert_args["public_key"] = ec_pubkey
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], ec_privkey, ca_key)
    assert ret.changes["private_key"]


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_signing_privkey_change(
    ssh, cert_args, ec_privkey, rsa_privkey
):
    cert_args["signing_private_key"] = ec_privkey
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ec_privkey)
    assert set(ret.changes) == {"signing_private_key"}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_key_id_change(ssh, cert_args, rsa_privkey, ca_key):
    cert_args["key_id"] = "renewed"
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert list(ret.changes) == ["key_id"]
    assert cert.key_id == b"renewed"


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_serial_number_change(ssh, cert_args, rsa_privkey, ca_key):
    cert_args["serial_number"] = 42
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert list(ret.changes) == ["serial_number"]
    assert cert.serial == 42


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_extension_added(
    ssh, cert_args, rsa_privkey, ca_key, cert_arg_exts, cert_expected_exts
):
    cert_args["extensions"] = cert_arg_exts
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "extensions" in ret.changes
    assert set(ret.changes["extensions"]["added"]) == {
        x.decode() for x in cert_expected_exts
    }
    assert ret.changes["extensions"]["changed"] == []
    assert ret.changes["extensions"]["removed"] == []
    assert cert.extensions == cert_expected_exts


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_critical_option_added(
    ssh, cert_args, rsa_privkey, ca_key, cert_arg_opts, cert_expected_opts
):
    cert_args["critical_options"] = cert_arg_opts
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "critical_options" in ret.changes
    assert set(ret.changes["critical_options"]["added"]) == {
        x.decode() for x in cert_expected_opts
    }
    assert ret.changes["critical_options"]["changed"] == []
    assert ret.changes["critical_options"]["removed"] == []
    assert cert.critical_options == cert_expected_opts


@pytest.mark.usefixtures("existing_cert_exts_opts")
def test_certificate_managed_critical_option_changed(
    ssh, cert_args, rsa_privkey, ca_key
):
    cert_args["critical_options"]["force-command"] = "echo there"
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "critical_options" in ret.changes
    assert ret.changes["critical_options"] == {
        "added": [],
        "changed": ["force-command"],
        "removed": [],
    }
    assert cert.critical_options[b"force-command"] == b"echo there"


@pytest.mark.usefixtures("existing_cert_exts_opts")
def test_certificate_managed_extension_removed(
    ssh, cert_args, rsa_privkey, ca_key, cert_expected_exts
):
    cert_args["extensions"].pop("permit-X11-forwarding")
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "extensions" in ret.changes
    assert ret.changes["extensions"] == {
        "added": [],
        "changed": [],
        "removed": ["permit-X11-forwarding"],
    }
    cert_expected_exts.pop(b"permit-X11-forwarding")
    assert cert.extensions == cert_expected_exts


@pytest.mark.usefixtures("existing_cert_exts_opts")
def test_certificate_managed_critical_option_removed(
    ssh, cert_args, rsa_privkey, ca_key, cert_expected_opts
):
    cert_args["critical_options"].pop("force-command")
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert "critical_options" in ret.changes
    assert ret.changes["critical_options"] == {
        "added": [],
        "changed": [],
        "removed": ["force-command"],
    }
    cert_expected_opts.pop(b"force-command")
    assert cert.critical_options == cert_expected_opts


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"all_principals": False, "valid_principals": ["a"]}],
    indirect=True,
)
def test_certificate_managed_principal_added(ssh, cert_args, rsa_privkey, ca_key):
    cert_args["valid_principals"] = ["a", "b"]
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert ret.changes
    assert ret.changes == {"principals": {"added": ["b"], "removed": []}}
    assert set(cert.valid_principals) == {b"a", b"b"}


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"all_principals": False, "valid_principals": ["a", "b"]}],
    indirect=True,
)
def test_certificate_managed_principal_removed(ssh, cert_args, rsa_privkey, ca_key):
    cert_args["valid_principals"] = ["a"]
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert ret.changes
    assert ret.changes == {"principals": {"added": [], "removed": ["b"]}}
    assert set(cert.valid_principals) == {b"a"}


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_all_principals_removed(
    ssh, cert_args, rsa_privkey, ca_key
):
    cert_args["valid_principals"] = ["a"]
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert ret.changes
    assert ret.changes == {"principals": {"added": ["a"], "removed": "*ALL*"}}
    assert set(cert.valid_principals) == {b"a"}


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize(
    "existing_cert",
    [{"all_principals": False, "valid_principals": ["a"]}],
    indirect=True,
)
def test_certificate_managed_all_principals_added(ssh, cert_args, rsa_privkey, ca_key):
    cert_args["valid_principals"] = []
    cert_args["all_principals"] = True
    ret = ssh.certificate_managed(**cert_args)
    cert = _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert ret.changes
    assert ret.changes == {"principals": {"added": "*ALL*", "removed": []}}
    assert cert.valid_principals == []


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_cert_type_change(ssh, cert_args, ca_key, rsa_privkey):
    cert_args["cert_type"] = "host"
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_basic(ret, cert_args["name"], rsa_privkey, ca_key)
    assert set(ret.changes) == {"cert_type"}
    assert ret.changes["cert_type"] == "host"


@pytest.mark.parametrize("mode", ["0400", "0640", "0644"])
def test_certificate_managed_mode(ssh, cert_args, rsa_privkey, ca_key, mode, modules):
    """
    This serves as a proxy for all file.managed args
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["mode"] = mode
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )
    assert modules.file.get_mode(cert_args["name"]) == mode


def test_certificate_managed_file_managed_create_false(ssh, cert_args, rsa_privkey):
    """
    Ensure create=False is detected and respected
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["create"] = False
    ret = ssh.certificate_managed(**cert_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(cert_args["name"]).exists()


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("existing_cert", [{"mode": "0644"}], indirect=True)
def test_certificate_managed_mode_change_only(ssh, cert_args, modules):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(cert_args["name"]) == "0644"
    cert_args["mode"] = "0640"
    cert_args.pop("serial_number", None)
    cert = _get_cert(cert_args["name"])
    ret = ssh.certificate_managed(**cert_args)
    assert ret.result is True
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(cert_args["name"]) == "0640"
    cert_new = _get_cert(cert_args["name"])
    assert cert_new.serial == cert.serial


@pytest.mark.usefixtures("existing_cert")
def test_certificate_managed_mode_test_true(ssh, cert_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    cert_args["test"] = True
    cert_args["mode"] = "0666"
    ret = ssh.certificate_managed(**cert_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(cert_args["name"]) != "0666"


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("backup", ["minion", False])
def test_certificate_managed_backup(
    ssh, cert_args, rsa_privkey, ca_key, modules, backup
):
    cert_args["private_key"] = rsa_privkey
    cert_args["backup"] = backup
    assert not modules.file.list_backups(cert_args["name"])
    ret = ssh.certificate_managed(**cert_args)
    _assert_cert_created_basic(
        ret,
        cert_args["name"],
        rsa_privkey,
        ca_key,
        cert_args["cert_type"],
        key_id=cert_args.get("key_id"),
    )
    assert bool(modules.file.list_backups(cert_args["name"])) == bool(backup)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("follow", [True, False])
def test_certificate_managed_follow_symlinks(ssh, cert_args, existing_symlink, follow):
    """
    file.managed follow_symlinks arg needs special attention since
    the checking of the existing file is performed by the ssh_pki module
    """
    cert_args["name"] = str(existing_symlink)
    assert Path(cert_args["name"]).is_symlink()
    cert_args["follow_symlinks"] = follow
    ret = ssh.certificate_managed(**cert_args)
    assert bool(ret.changes) == (not follow)


@pytest.mark.usefixtures("existing_cert")
@pytest.mark.parametrize("follow", [True, False])
def test_certificate_managed_follow_symlinks_changes(
    ssh, cert_args, existing_symlink, follow
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the ssh_pki module
    """
    cert_args["name"] = str(existing_symlink)
    assert Path(cert_args["name"]).is_symlink()
    cert_args["follow_symlinks"] = follow
    cert_args["key_id"] = "new"
    ret = ssh.certificate_managed(**cert_args)
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


def test_certificate_managed_file_managed_error(ssh, cert_args, rsa_privkey):
    """
    This serves as a proxy for all file.managed args
    """
    cert_args["private_key"] = rsa_privkey
    cert_args["makedirs"] = False
    cert_args["name"] = str(Path(cert_args["name"]).parent / "missing" / "cert")
    ret = ssh.certificate_managed(**cert_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


@pytest.mark.parametrize("algo", ["rsa", "ec", "ed25519"])
@pytest.mark.parametrize(
    "passphrase",
    [
        None,
        pytest.param(
            "hunter1",
            marks=pytest.mark.skipif(
                HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
            ),
        ),
    ],
)
def test_private_key_managed(ssh, pk_args, algo, passphrase):
    pk_args["algo"] = algo
    pk_args["passphrase"] = passphrase
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, algo, passphrase)


@pytest.mark.parametrize("algo,keysize", [("rsa", 4096), ("ec", 384)])
def test_private_key_managed_keysize(ssh, pk_args, algo, keysize):
    pk_args["algo"] = algo
    pk_args["keysize"] = keysize
    ret = ssh.private_key_managed(**pk_args)
    pk = _assert_pk_basic(ret, algo)
    assert pk.key_size == keysize


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize(
    "existing_pk",
    [
        {},
        {"algo": "ec"},
        {"algo": "ed25519"},
        {"keysize": 4096},
        {"algo": "ec", "keysize": 384},
    ],
    indirect=True,
)
def test_private_key_managed_existing(ssh, pk_args):
    ret = ssh.private_key_managed(**pk_args)
    _assert_not_changed(ret)


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_existing_new(ssh, pk_args):
    cur = _get_privkey(pk_args["name"])
    pk_args["new"] = True
    ret = ssh.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa")
    assert ret.changes == {"replaced": pk_args["name"]}
    assert cur.public_key().public_numbers() != new.public_key().public_numbers()


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "hunter2"}], indirect=True)
def test_private_key_managed_existing_new_with_passphrase_change(ssh, pk_args):
    cur = _get_privkey(pk_args["name"], passphrase=pk_args["passphrase"])
    pk_args.pop("passphrase")
    pk_args["new"] = True
    ret = ssh.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa")
    assert ret.changes == {"replaced": pk_args["name"]}
    assert cur.public_key().public_numbers() != new.public_key().public_numbers()


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_algo_change(ssh, pk_args):
    pk_args["algo"] = "ed25519"
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "ed25519")
    assert ret.changes == {"algo": "ed25519"}


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_keysize_change(ssh, pk_args):
    pk_args["keysize"] = 2048
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")
    assert ret.changes == {"keysize": 2048}


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_passphrase_introduced(ssh, pk_args):
    pk_args["passphrase"] = "hunter1"
    cur = _get_privkey(pk_args["name"])
    ret = ssh.private_key_managed(**pk_args)
    new = _assert_pk_basic(ret, "rsa", passphrase="hunter1")
    assert ret.changes == {"passphrase": True}
    assert "has been encrypted" in ret.comment
    assert new.public_key().public_numbers() == cur.public_key().public_numbers()


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_removed_not_overwrite(ssh, pk_args):
    pk_args.pop("passphrase")
    ret = ssh.private_key_managed(**pk_args)
    assert ret.result is False
    assert not ret.changes
    assert "is encrypted with a passphrase. Pass overwrite" in ret.comment


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_removed_overwrite(ssh, pk_args):
    pk_args.pop("passphrase")
    pk_args["overwrite"] = True
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_changed_not_overwrite(ssh, pk_args):
    pk_args["passphrase"] = "hunter1"
    ret = ssh.private_key_managed(**pk_args)
    assert ret.result is False
    assert not ret.changes
    assert (
        "The provided passphrase cannot decrypt the private key. Pass overwrite"
        in ret.comment
    )


@pytest.mark.skipif(
    HAS_BCRYPT is False, reason="Encrypted keys require the bcrypt library"
)
@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"passphrase": "password"}], indirect=True)
def test_private_key_managed_passphrase_changed_overwrite(ssh, pk_args):
    pk_args["passphrase"] = "hunter1"
    pk_args["overwrite"] = True
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa", passphrase="hunter1")


@pytest.mark.parametrize("mode", [None, "0600", "0644"])
def test_private_key_managed_mode(ssh, pk_args, mode, modules):
    """
    This serves as a proxy for all file.managed args
    """
    pk_args["mode"] = mode
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")
    assert modules.file.get_mode(pk_args["name"]) == (mode or "0400")


def test_private_key_managed_file_managed_create_false(ssh, pk_args):
    """
    Ensure create=False is detected and respected
    """
    pk_args["create"] = False
    ret = ssh.private_key_managed(**pk_args)
    assert ret.result is True
    assert not ret.changes
    assert not Path(pk_args["name"]).exists()


@pytest.mark.usefixtures("existing_pk")
def test_private_key_managed_mode_test_true(ssh, pk_args, modules):
    """
    Test mode should not make changes at all.
    The module contains a workaround for
    https://github.com/saltstack/salt/issues/62590
    """
    pk_args["test"] = True
    pk_args["mode"] = "0666"
    ret = ssh.private_key_managed(**pk_args)
    assert ret.filtered["sub_state_run"][0]["result"] is None
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert "0666" != modules.file.get_mode(pk_args["name"])


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("backup", ["minion", False])
def test_private_key_managed_backup(ssh, pk_args, modules, backup):
    pk_args["backup"] = backup
    assert not modules.file.list_backups(pk_args["name"])
    ret = ssh.private_key_managed(**pk_args)
    _assert_pk_basic(ret, "rsa")
    assert bool(modules.file.list_backups(pk_args["name"])) == bool(backup)


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_symlink", ["existing_pk"], indirect=True)
@pytest.mark.parametrize("follow", [True, False])
def test_private_key_managed_follow_symlinks(ssh, pk_args, existing_symlink, follow):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the ssh_pki module
    """
    pk_args["name"] = str(existing_symlink)
    assert Path(pk_args["name"]).is_symlink()
    pk_args["follow_symlinks"] = follow
    ret = ssh.private_key_managed(**pk_args)
    assert bool(ret.changes) == (not follow)


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_symlink", ["existing_pk"], indirect=True)
@pytest.mark.parametrize("follow", [True, False])
def test_private_key_managed_follow_symlinks_changes(
    ssh, pk_args, existing_symlink, follow
):
    """
    file.managed follow_symlinks arg needs special attention as well since
    the checking of the existing file is performed by the ssh_pki module
    """
    pk_args["name"] = str(existing_symlink)
    assert Path(pk_args["name"]).is_symlink()
    pk_args["follow_symlinks"] = follow
    pk_args["algo"] = "ec"
    ret = ssh.private_key_managed(**pk_args)
    assert ret.changes
    assert Path(ret.name).is_symlink() == follow


@pytest.mark.usefixtures("existing_pk")
@pytest.mark.parametrize("existing_pk", [{"mode": "0400"}], indirect=True)
def test_private_key_managed_mode_change_only(ssh, pk_args, modules):
    """
    This serves as a proxy for all file.managed args
    """
    assert modules.file.get_mode(pk_args["name"]) == "0400"
    pk_args["mode"] = "0600"
    cur = _get_privkey(pk_args["name"])
    ret = ssh.private_key_managed(**pk_args)
    assert ret.result is True
    assert ret.filtered["sub_state_run"][0]["changes"]
    assert "mode" in ret.filtered["sub_state_run"][0]["changes"]
    assert modules.file.get_mode(pk_args["name"]) == "0600"
    new = _get_privkey(pk_args["name"])
    assert new.public_key().public_numbers() == cur.public_key().public_numbers()


def test_private_key_managed_file_managed_error(ssh, pk_args):
    """
    This serves as a proxy for all file.managed args
    """
    pk_args["makedirs"] = False
    pk_args["name"] = str(Path(pk_args["name"]).parent / "missing" / "pk")
    ret = ssh.private_key_managed(**pk_args)
    assert ret.result is False
    assert "Could not create file, see file.managed output" in ret.comment


@pytest.mark.usefixtures("existing_file")
@pytest.mark.parametrize("overwrite", [False, True])
def test_private_key_managed_existing_not_a_pk(ssh, pk_args, overwrite):
    pk_args["name"] = pk_args["name"][:-11] + "cert"
    pk_args["overwrite"] = overwrite
    ret = ssh.private_key_managed(**pk_args)
    assert bool(ret.result) == overwrite
    assert bool(ret.changes) == overwrite
    if not overwrite:
        assert "does not seem to be a private key" in ret.comment
        assert "Pass overwrite" in ret.comment


def _assert_cert_created_basic(
    ret,
    name,
    privkey,
    ca_key,
    cert_type,
    principals=None,
    key_id=None,
):
    assert ret.result is True
    assert ret.changes
    assert ret.changes.get("created") == name or ret.changes.get("replaced") == name
    cert = _get_cert(name)
    if isinstance(key_id, str):
        key_id = key_id.encode()
    assert cert.key_id == key_id
    if isinstance(cert_type, str):
        cert_type = getattr(serialization.SSHCertificateType, cert_type.upper())
    assert cert.type is cert_type
    if principals is not False:
        assert cert.valid_principals == (principals or [])
    assert _belongs_to(cert, privkey)
    assert _signed_by(cert, ca_key)
    return cert


def _assert_cert_basic(ret, name, privkey, ca_key):
    assert ret.result is True
    assert ret.changes
    cert = _get_cert(name)
    assert _belongs_to(cert, privkey)
    assert _signed_by(cert, ca_key)
    return cert


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


def _encode_pubkey(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    ).decode()


def _belongs_to(cert_or_pubkey, privkey):
    if isinstance(cert_or_pubkey, serialization.SSHCertificate):
        cert_or_pubkey = cert_or_pubkey.public_key()
    return x509util.is_pair(cert_or_pubkey, _get_privkey(privkey))


def _signed_by(cert, privkey):
    cert.verify_cert_signature()
    return x509util.is_pair(cert.signature_key(), _get_privkey(privkey))


def _assert_pk_basic(ret, algo, passphrase=None):
    assert ret.result
    assert ret.changes
    pk = _get_privkey(ret.name, passphrase=passphrase)
    if algo == "rsa":
        assert isinstance(pk, rsa.RSAPrivateKey)
    elif algo == "ec":
        assert isinstance(pk, ec.EllipticCurvePrivateKey)
    elif algo == "ed25519":
        assert isinstance(pk, ed25519.Ed25519PrivateKey)
    else:
        raise ValueError(f"Algo {algo} is not a valid one")
    return pk


def _assert_not_changed(ret):
    assert ret.result
    assert not ret.changes
    assert "in the correct state" in ret.comment
