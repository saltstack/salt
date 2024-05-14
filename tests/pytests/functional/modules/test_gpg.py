import shutil
import subprocess

import psutil
import pytest

gnupglib = pytest.importorskip("gnupg", reason="Needs python-gnupg library")
PYGNUPG_VERSION = tuple(int(x) for x in gnupglib.__version__.split("."))

pytestmark = [
    pytest.mark.skip_if_binaries_missing("gpg", reason="Needs gpg binary"),
]


def _kill_gpg_agent(root):
    gpg_connect_agent = shutil.which("gpg-connect-agent")
    if gpg_connect_agent:
        gnupghome = root / ".gnupg"
        if not gnupghome.is_dir():
            gnupghome = root
        try:
            subprocess.run(
                [gpg_connect_agent, "killagent", "/bye"],
                env={"GNUPGHOME": str(gnupghome)},
                shell=False,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            # This is likely CentOS 7 or Amazon Linux 2
            pass

    # If the above errored or was not enough, as a last resort, let's check
    # the running processes.
    for proc in psutil.process_iter():
        try:
            if "gpg-agent" in proc.name():
                for arg in proc.cmdline():
                    if str(root) in arg:
                        proc.terminate()
        except Exception:  # pylint: disable=broad-except
            pass


@pytest.fixture
def gpghome(tmp_path):
    root = tmp_path / "gpghome"
    root.mkdir(mode=0o0700)
    try:
        yield root
    finally:
        # Make sure we don't leave any gpg-agents running behind
        _kill_gpg_agent(root)


@pytest.fixture
def gpg(loaders, modules, gpghome):
    yield modules.gpg


@pytest.fixture
def signed_data(tmp_path):
    signed_data = "What do you have if you have NaCl and NiCd? A salt and battery.\n"
    data = tmp_path / "signed_data"
    data.write_text(signed_data)
    assert data.read_bytes() == signed_data.encode()
    yield data
    data.unlink()


@pytest.fixture
def key_a_fp():
    return "EF03765F59EE904930C8A781553A82A058C0C795"


@pytest.fixture
def key_a_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4fxHQEEAJvXEaaw+o/yZCwMOJbt5FQHbVMMDX/0YI8UdzsE5YCC4iKnoC3x
FwFdkevKj3qp+45iBGLLnalfXIcVGXJGACB+tPHgsfHaXSDQPSfmX6jbZ6pHosSm
v1tTixY+NTJzGL7hDLz2sAXTbYmTbXeE9ifWWk6NcIwZivUbhNRBM+KxABEBAAG0
LUtleSBBIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5YUBleGFtcGxlPojR
BBMBCAA7FiEE7wN2X1nukEkwyKeBVTqCoFjAx5UFAmOH8R0CGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQVTqCoFjAx5XURAQAguOwI+49lG0Kby+Bsyv3
of3GgxvhS1Qa7+ysj088az5GVt0pqVe3SbRVvn/jyC6yZvWuv94KdL3R7hCeEz2/
JakCRJ4wxEsdeASE8t9H/oTqD0I5asMa9EMvn5ICEGeLsTeQb7OYYihTQj7HJLG6
pDEmK8EhJDvV/9o0lnhm/9w=
=Wc0O
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def key_a_priv():
    return """\
-----BEGIN PGP PRIVATE KEY BLOCK-----

lQHYBGOH8R0BBACb1xGmsPqP8mQsDDiW7eRUB21TDA1/9GCPFHc7BOWAguIip6At
8RcBXZHryo96qfuOYgRiy52pX1yHFRlyRgAgfrTx4LHx2l0g0D0n5l+o22eqR6LE
pr9bU4sWPjUycxi+4Qy89rAF022Jk213hPYn1lpOjXCMGYr1G4TUQTPisQARAQAB
AAP7BlQ9nKcZI/24hQPxi+qpMGL1VQ87IKBWiBURExHrtrSKFdV4N0lwcV8hGSIK
wfTzmRigvDjwBCQR9E/+brJKWLdGmmHjYHIU3m4fz26E4UlxEu2XfxZOSPKPTnzh
GqVSjmZ9TDdr5Ykpz5SyQ1YOUS9iRI6O5Dp0c4+6n2gyTYECAMQPCa8UnoHw1jgw
JHnK+XM3jinqgIOMS66i5nCGe3PItaAOvPIwA0lyl2Io06lGuiSVIqbJIUTsf2Mv
y14eJnECAMt8O6gMsjJdZ/dU9srqz4ZatPUHtQm2KBnvk311PmeErJ1FiiAqXTVq
Q9y3GvkEnENeuC/ac0XztiHsEC2eIEEB/iu1i5sP3zUZZnBNDbsmDZEy+HKHm8lL
Vg1+hHUdznMMmJ/PKq+WlB3KvdNzhEFd+0R+ylfRTMWnhNMWxL1atNyYC7QtS2V5
IEEgKEdlbmVyYXRlZCBieSBTYWx0U3RhY2spIDxrZXlhQGV4YW1wbGU+iNEEEwEI
ADsWIQTvA3ZfWe6QSTDIp4FVOoKgWMDHlQUCY4fxHQIbLwULCQgHAgIiAgYVCgkI
CwIEFgIDAQIeBwIXgAAKCRBVOoKgWMDHldREBACC47Aj7j2UbQpvL4GzK/eh/caD
G+FLVBrv7KyPTzxrPkZW3SmpV7dJtFW+f+PILrJm9a6/3gp0vdHuEJ4TPb8lqQJE
njDESx14BITy30f+hOoPQjlqwxr0Qy+fkgIQZ4uxN5Bvs5hiKFNCPscksbqkMSYr
wSEkO9X/2jSWeGb/3A==
=lVXx
-----END PGP PRIVATE KEY BLOCK-----"""


@pytest.fixture
def key_a_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQTvA3ZfWe6QSTDIp4FVOoKgWMDHlQUCY4fz7QAKCRBVOoKgWMDH
lYH/A/9iRT4JqzZEfRGM6XUyVbLCoF2xyEc43yL06nxn1sMFjMdLOLUDsaZbppHB
vEo4XJ45+Xqu1h3RK6bDVdDURyacPzdef8v357rJHjT8tb68JcwSzCBXLh29Nasl
cOm6/gNVIVm3Uoe9mKXESRvpMYmNUp2UM7ZzzBstK/ViVR82UA==
=EZPV
-----END PGP SIGNATURE-----"""


@pytest.fixture
def key_b_fp():
    return "118B4FAB78038CB2DF7B69E20F6C422647465C93"


@pytest.fixture
def key_b_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4fxNQEEAOgAzbpheJrOq4il5BrMVtP1G1kU94QX2+xLXEgW/wPdE4HD6Zbg
vliIg18v7Na4x8ubWy/7CkXC83EJ8SoSqcCccvuKjIWsm6tfeCidNstNCjewFMUR
7ZOQmAe/I2JAlz2SgNxS3ZDiCZpGkxqE0GZ+1N7Mz2WHImnExG149RVHABEBAAG0
LUtleSBCIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5YkBleGFtcGxlPojR
BBMBCAA7FiEEEYtPq3gDjLLfe2niD2xCJkdGXJMFAmOH8TUCGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQD2xCJkdGXJNR3AQAk5ZoN+/ViIX3vA/LbXPn
2VE1E7ETTeIGqsb5f98UfjIbYfkNE8+OtnPxnDbSOPWBEOT+XPPjmxnE0a2UNTfn
ECO71/ZUiyC3ZN50IZ0vgzwBH+DeIV6PDAAun5FGx4RI7v6n0CPlrUcWKYe8wY1F
COflOxnEyLVHXnX8wUIzZwo=
=Hq0X
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def key_b_priv():
    return """\
-----BEGIN PGP PRIVATE KEY BLOCK-----

lQHYBGOH8TUBBADoAM26YXiazquIpeQazFbT9RtZFPeEF9vsS1xIFv8D3ROBw+mW
4L5YiINfL+zWuMfLm1sv+wpFwvNxCfEqEqnAnHL7ioyFrJurX3gonTbLTQo3sBTF
Ee2TkJgHvyNiQJc9koDcUt2Q4gmaRpMahNBmftTezM9lhyJpxMRtePUVRwARAQAB
AAP5ARivbnABmWhchYCiwbnjKSljNvosHJ5seCaUIq34squWaRGH5rBccJiPrQvD
qJvmnWCp+CjNZTysH/eUcz+6xmoefzsB9YPfyWKYCM6yNaBbFceVER+TCRoLjlZi
Nw7VtD6t8Rrxq9T7fykmNU7PD1hOKEXacaHN04jCFtPsXdkCAPK9LkE3c9nVNxUS
17AtviMm2/9nC0wu+9W/Tub0VZjtsanwTyA87uwNlxrOyUeopZZrzSioJEa6b/Hq
RtUmvR8CAPSteh9vXM9D94jpmWzz2Hx1uo8OCDk86KovbEFLqNTEnnbaG8eXOH68
Y0BPKrLRY9lY1zkeudw+pPyg6Q1CetkB/0VbGbfswR15WkiAJnd/Cln07upDUYLD
bQ4C/w7YbfQndmnJ84gHqQH2T4xgULlEvl3+rg+x7vg4z1X7St31hD+kqLQtS2V5
IEIgKEdlbmVyYXRlZCBieSBTYWx0U3RhY2spIDxrZXliQGV4YW1wbGU+iNEEEwEI
ADsWIQQRi0+reAOMst97aeIPbEImR0ZckwUCY4fxNQIbLwULCQgHAgIiAgYVCgkI
CwIEFgIDAQIeBwIXgAAKCRAPbEImR0Zck1HcBACTlmg379WIhfe8D8ttc+fZUTUT
sRNN4gaqxvl/3xR+Mhth+Q0Tz462c/GcNtI49YEQ5P5c8+ObGcTRrZQ1N+cQI7vX
9lSLILdk3nQhnS+DPAEf4N4hXo8MAC6fkUbHhEju/qfQI+WtRxYph7zBjUUI5+U7
GcTItUdedfzBQjNnCg==
=kzV7
-----END PGP PRIVATE KEY BLOCK-----"""


@pytest.fixture
def key_b_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQQRi0+reAOMst97aeIPbEImR0ZckwUCY4f0gQAKCRAPbEImR0Zc
kwj5A/9Fj7JFdzu5CGvB7MGYPPUm7cBh231QuSLndlSFvv3ZBrvU9906fstzjQRB
6x4m1uc04bckEoZ/2WE6r5dP39sdvzlyMhGq5qAJZZiuiZF2EjzMnQ/dJoXYM8pM
674JLQ2VjsWCZjp7s3JnPh6+0VL9IoDx3QsfPSBKBjOHOSj0SA==
=1sKz
-----END PGP SIGNATURE-----"""


@pytest.fixture
def key_c_fp():
    return "96F136AC4C92D78DAF33105E35C03186001C6E31"


@pytest.fixture
def key_c_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4f2GgEEALToT23wZfLGM/JGCV4pWRlIXXqLwwEBSXral92HvsUjC8Vqsh1z
1n0K8/vIpS9OH2Q21emtht4y36rbahy+w6wRc1XXjPQ28Pyd+8v/jSKy/NKW3g+y
ZoB22vj4L35pAu/G6xs9+pKsLHGjMo+LsWZNEZ2Ar06aYA0dbTb0AqYfABEBAAG0
LUtleSBDIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5Y0BleGFtcGxlPojR
BBMBCAA7FiEElvE2rEyS142vMxBeNcAxhgAcbjEFAmOH9hoCGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQNcAxhgAcbjH2WAP/RtlUfN/novwmxxma6Zom
P6skFnCcRCs0vMU3OnNwuxZt9B+j0sUTu6noGi04Gcbd0eQs7v57DQHcRhNidZU/
8BJv5jD6E2yuzLK9lON+Yhgc6Pg6raA3hBeCY2HuzTEQLAThyV7ihboNILo7FJwo
y9KvnTFP2+oeDX2Z/m4SoWw=
=81Kb
-----END PGP PUBLIC KEY BLOCK-----"""


# the signature was made on different data
@pytest.fixture
def key_c_fail_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQSW8TasTJLXja8zEF41wDGGABxuMQUCY4f2pwAKCRA1wDGGABxu
MdtOA/0ROhdh1VgfZn94PWgcrlurwYE0ftI3AXbSI00FsrWviF8WZQtp7YjrUC3t
/a/P1UYZkbBR0EeKwbKGmersq8mfif1qejWpQXpmmx011KQ0AFl7vdZUtcj2n454
KQE7MX8ePBchpSyhmvXzEezyw2FJp+YVOUKhDsc1vbNWTxGYJw==
=6tkK
-----END PGP SIGNATURE-----"""


@pytest.fixture
def key_d_fp():
    return "0B33DC666FA1211311850D4F5F3CAF4AE7BF949D"


@pytest.fixture
def key_d_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4gB/AEEAK2iwXXY4rbykGMFsLxdcnUdWtglKBXyQl5Y2Mj71UedgGTZVNWP
4dvUnQNqthPCu3hFyD2I+USa80OuYw5k9MPMqZcu3xmJKneaEX07r829G2T8yllz
vgKd2+4aUZHsKFz9fId7lraCDhSpmS0zLeTab6jNDfYecVJB8JaQpJrNABEBAAG0
LUtleSBEIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5ZEBleGFtcGxlPojR
BBMBCAA7FiEECzPcZm+hIRMRhQ1PXzyvSue/lJ0FAmOIAfwCGy8FCwkIBwICIgIG
FQoJCAsCBBYCAwECHgcCF4AACgkQXzyvSue/lJ373AQAqKGhEfZ8Kx0s7L+T+6Ug
orxgvvQhbcc+eciA9alAptstkt9qg03yaii1InwJE5HjLNqOu8DWnhuBDTquWQUm
CWKUEicI6eZCFHVrjAcUKJcp/Lne9Ny/r1+14eE2vlsMf3oy0n0OpOTC+KhJzDpz
Mq2tZaSibjzjqQ32LiNJi3c=
=rjff
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def key_d_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQQLM9xmb6EhExGFDU9fPK9K57+UnQUCY4gCXwAKCRBfPK9K57+U
nYk/BACe4YUPaxHRuky8ya7k27P+RTynbuUGJ1w3AHaO1VXDTvoNTioyaqeDpO6C
NsMl5bIa7GkYEaeM/OPWQ9WlWPno6+nwOEL7/818J+JgxWVsLtGJNlYzuEwI7tDV
FUXLma7dvOw13LLY2RjtgaVbePTO+H+uCrAa4/O0YEIAE2C2fA==
=3m4o
-----END PGP SIGNATURE-----"""


@pytest.fixture
def key_e_fp():
    return "2401C402776328D78D6B4C5D67D35BC98502D9B9"


# expires 2022-12-01
@pytest.fixture
def key_e_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4gjEQEEAKYpWezZQWiAUDvAMcMhBkjHGY2fM4MMiXc6+fRbNV4VCL9TtJYE
gjccYVu44DtIYQzMVimrPQ6xepUmFRalezCG0OO4v25Ciwyeg8LX+Tb3kyAYFAxi
qLXAJyr3aZ/539xBak/Vf5xdURIi7WF5qBGQxd87tRDDqyPFnr87JJtFABEBAAG0
LUtleSBFIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5ZUBleGFtcGxlPojX
BBMBCABBFiEEJAHEAndjKNeNa0xdZ9NbyYUC2bkFAmOIIxECGy8FCQAAZh8FCwkI
BwICIgIGFQoJCAsCBBYCAwECHgcCF4AACgkQZ9NbyYUC2bmn1QP/WPVhj1bC9/9R
hifv29MG9maRNIkuEkZKtRJj7HMSaamD5IOtGoyMuBwicb38n2Z2KQZUiJbvyZTt
PS328F8YSUSyWQKqmhwL0iLlnDzx8l/nFr5tiss2b/ZzjlMP4iXtAgEdVMJnfjrM
J7xvL0cNSsHha4hUIrekvzM+SNwYkzs=
=nue4
-----END PGP PUBLIC KEY BLOCK-----"""


@pytest.fixture
def key_e_priv():
    return """\
-----BEGIN PGP PRIVATE KEY BLOCK-----

lQHYBGOIIxEBBACmKVns2UFogFA7wDHDIQZIxxmNnzODDIl3Ovn0WzVeFQi/U7SW
BII3HGFbuOA7SGEMzFYpqz0OsXqVJhUWpXswhtDjuL9uQosMnoPC1/k295MgGBQM
Yqi1wCcq92mf+d/cQWpP1X+cXVESIu1heagRkMXfO7UQw6sjxZ6/OySbRQARAQAB
AAP/Se3mE8qKHpvQlvUpbt83s5PaW7e0rJ8cXo8//SfDs+t5696rX3/8C9c1viCg
q9/FRnN39qw4y1vN5aR/B4dzKmlycWZ5Kk5NewRfNAyvD85uXA2VDDTCZQ7qDlwZ
A24s95xjWWC2urhMszYgWbT9Kzk4Q1aNhPIEs1QgYvIujjUCAMX8+w5FRrOZWYP+
K8qL9ZPUAbUIdg+dCN1rTQvrCbM2FtZquFw89EyzT+qmBkfHCKpczC0XHdqnhsZU
sGTdqXcCANbZEFCNldv6FwhYsDBitP48shoGk3SIsAIpzP3klz+3Eut6LCTzS5T4
t9OVEIpKCP5Ci5m/BoTO/rbKhKt5ECMB/14pYNJcKtolEwvE6w5j6h5f72N+3dTs
qGTpDjfpgrSTmpoZcqDcFg0ycfwFyDzBVI+Hn+6njc/FtMxH3JAA2kug6LQtS2V5
IEUgKEdlbmVyYXRlZCBieSBTYWx0U3RhY2spIDxrZXllQGV4YW1wbGU+iNcEEwEI
AEEWIQQkAcQCd2Mo141rTF1n01vJhQLZuQUCY4gjEQIbLwUJAABmHwULCQgHAgIi
AgYVCgkICwIEFgIDAQIeBwIXgAAKCRBn01vJhQLZuafVA/9Y9WGPVsL3/1GGJ+/b
0wb2ZpE0iS4SRkq1EmPscxJpqYPkg60ajIy4HCJxvfyfZnYpBlSIlu/JlO09Lfbw
XxhJRLJZAqqaHAvSIuWcPPHyX+cWvm2KyzZv9nOOUw/iJe0CAR1Uwmd+OswnvG8v
Rw1KweFriFQit6S/Mz5I3BiTOw==
=49zT
-----END PGP PRIVATE KEY BLOCK-----"""


@pytest.fixture
def key_e_exp_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQQkAcQCd2Mo141rTF1n01vJhQLZuQUCY4gjPgAKCRBn01vJhQLZ
ueNkBACa2JjXZjatAbW4wXZ6RKqgluNwvC12EzFbQK2oGh1JC9htS4mVYE2aroup
E5XNzlr8R1z9b5HmuqqSniTNXG5xpxDLvD+rZK3Ww6AIs5FR2R9e0Kr0kMayQFdO
UDJsV8u8GFP+76oGy4G4GU1NlcqWpmIAzst0G4q4ipx891Z10A==
=G8tZ
-----END PGP SIGNATURE-----"""


@pytest.fixture
def key_f_fp():
    return "D7D3F617EBD2113059914876F7D0B975BC8E7ED1"


# no pubkey for this one
@pytest.fixture
def key_f_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQTX0/YX69IRMFmRSHb30Ll1vI5+0QUCY4it3wAKCRD30Ll1vI5+
0Qf8A/4yI5nX0Q7kfR6rHvcDgB9HFlimiE15HOd8pW0RWK0YWvTtn+5vWyOZalS/
oHvSiXZCYIgjllvMSJbgxj22GrH621B5Q+SBSkQOVLLU8gBADcU0FAShV5BXgm35
kBGl+/D1MBJLt6q8GZWHMWIHOX4GN28A/PEemaKg3dZHEtPM3w==
=su9m
-----END PGP SIGNATURE-----"""


@pytest.fixture
def secret_message():
    return """\
-----BEGIN PGP MESSAGE-----

hIwDVTqCoFjAx5UBA/wIt5OUfsKV2VPB2P+c6r7xVvPIPiA1FjNpU2x1G8A/dxVq
kAOhXJ9KkM6yon0PJReF3w8QPgZCo5tCmwqMtin4OY/WTw1ExyIWIaS7XJh1ktPM
TJL7RpyeywGHiAveLs9rznZtVwi0xg+rTSWpoMS/8GbKpOyf3twWMsiFfndr09JJ
ASWYXtfsUT3IVA5dP0Mr3/Yg0v90d+X2RqUHM+sUiUtwh4mb+vUcm7UOQRyGAR4V
h7jTNclSQwWCGzx6OaWKnrCVafRXbH4aeA==
=tw4x
-----END PGP MESSAGE-----"""


@pytest.fixture(params=["a"])
def sig(request, tmp_path):
    sigs = "\n".join(request.getfixturevalue(f"key_{x}_sig") for x in request.param)
    sig = tmp_path / "sig.asc"
    sig.write_text(sigs)
    yield str(sig)
    sig.unlink()


@pytest.fixture
def gnupg(gpghome):
    return gnupglib.GPG(gnupghome=str(gpghome))


@pytest.fixture
def gnupg_keyring(gpghome, keyring):
    return gnupglib.GPG(gnupghome=str(gpghome), keyring=keyring)


@pytest.fixture
def gnupg_privkeyring(gpghome, keyring_privkeys):
    return gnupglib.GPG(gnupghome=str(gpghome), keyring=keyring_privkeys)


@pytest.fixture(params=["abcde"])
def _pubkeys_present(gnupg, request):
    pubkeys = [request.getfixturevalue(f"key_{x}_pub") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    gnupg.import_keys("\n".join(pubkeys))
    present_keys = gnupg.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


@pytest.fixture(params=["ab"])
def _privkeys_present(gnupg, request):
    privkeys = [request.getfixturevalue(f"key_{x}_priv") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    res = gnupg.import_keys("\n".join(privkeys))
    assert set(res.fingerprints) == set(fingerprints)
    present_keys = gnupg.list_keys(secret=True)
    assert present_keys
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


@pytest.fixture(params=["a"])
def keyring(gpghome, tmp_path, request):
    keyring = tmp_path / "keys.gpg"
    _gnupg_keyring = gnupglib.GPG(gnupghome=str(gpghome), keyring=str(keyring))
    pubkeys = [request.getfixturevalue(f"key_{x}_pub") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    _gnupg_keyring.import_keys("\n".join(pubkeys))
    present_keys = _gnupg_keyring.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield str(keyring)
    # cleanup is taken care of by gpghome and tmp_path


@pytest.fixture(params=["a"])
def keyring_privkeys(gpghome, gnupg, tmp_path, request):
    keyring = tmp_path / "keys.gpg"
    _gnupg_keyring = gnupglib.GPG(gnupghome=str(gpghome), keyring=str(keyring))
    privkeys = [request.getfixturevalue(f"key_{x}_priv") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    _gnupg_keyring.import_keys("\n".join(privkeys))
    present_privkeys = _gnupg_keyring.list_keys(secret=True)
    assert present_privkeys
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_privkeys)
    yield str(keyring)
    # cleanup is taken care of by gpghome and tmp_path


@pytest.mark.usefixtures("_pubkeys_present")
def test_list_keys(gpg, gpghome, gnupg):
    res = gpg.list_keys(gnupghome=str(gpghome))
    assert res
    assert len(res) == len(gnupg.list_keys())


def test_list_keys_in_keyring(gpg, gpghome, keyring, gnupg_keyring):
    res = gpg.list_keys(gnupghome=str(gpghome), keyring=keyring)
    assert len(res) == len(gnupg_keyring.list_keys())


@pytest.mark.usefixtures("_privkeys_present")
def test_list_secret_keys(gpghome, gpg, gnupg):
    res = gpg.list_secret_keys(gnupghome=str(gpghome))
    assert len(res) == len(gnupg.list_keys(secret=True))


def test_list_secret_keys_in_keyring(gpghome, gpg, keyring_privkeys, gnupg_privkeyring):
    res = gpg.list_secret_keys(gnupghome=str(gpghome), keyring=keyring_privkeys)
    assert len(res) == len(gnupg_privkeyring.list_keys(secret=True))


@pytest.mark.requires_random_entropy
def test_create_key(gpghome, gpg, gnupg):
    res = gpg.create_key(gnupghome=str(gpghome))
    assert res
    assert "message" in res
    assert "successfully generated" in res["message"]
    assert "fingerprint" in res
    assert res["fingerprint"]
    assert gnupg.list_keys(secret=True, keys=res["fingerprint"])


@pytest.mark.requires_random_entropy
def test_create_key_in_keyring(gpghome, gpg, gnupg, keyring, gnupg_keyring):
    res = gpg.create_key(gnupghome=str(gpghome), keyring=keyring)
    assert res
    assert "message" in res
    assert "successfully generated" in res["message"]
    assert "fingerprint" in res
    assert res["fingerprint"]
    assert not gnupg.list_keys(secret=True, keys=res["fingerprint"])
    assert gnupg_keyring.list_keys(secret=True, keys=res["fingerprint"])


@pytest.mark.usefixtures("_pubkeys_present")
def test_delete_key(gpghome, gpg, gnupg, key_a_fp):
    assert gnupg.list_keys(keys=key_a_fp)
    res = gpg.delete_key(
        fingerprint=key_a_fp, gnupghome=str(gpghome), use_passphrase=False
    )
    assert res["res"]
    assert not gnupg.list_keys(keys=key_a_fp)


@pytest.mark.usefixtures("_pubkeys_present")
def test_delete_key_from_keyring(gpghome, gpg, key_a_fp, keyring, gnupg, gnupg_keyring):
    assert gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    res = gpg.delete_key(
        fingerprint=key_a_fp,
        gnupghome=str(gpghome),
        keyring=keyring,
        use_passphrase=False,
    )
    assert res["res"]
    assert gnupg.list_keys(keys=key_a_fp)
    assert not gnupg_keyring.list_keys(keys=key_a_fp)


@pytest.mark.usefixtures("_pubkeys_present")
def test_get_key(gpghome, gpg, key_a_fp):
    res = gpg.get_key(fingerprint=key_a_fp, gnupghome=str(gpghome))
    assert res
    assert "keyid" in res
    assert res["keyid"] == key_a_fp[-16:]
    assert "keyLength" in res
    assert res["keyLength"] == "1024"


def test_get_key_from_keyring(gpghome, gpg, key_a_fp, keyring, gnupg):
    assert not gnupg.list_keys()
    res = gpg.get_key(fingerprint=key_a_fp, gnupghome=str(gpghome), keyring=keyring)
    assert res
    assert "keyid" in res
    assert res["keyid"] == key_a_fp[-16:]
    assert "keyLength" in res
    assert res["keyLength"] == "1024"


@pytest.mark.usefixtures("_privkeys_present")
def test_get_secret_key(gpghome, gpg, key_a_fp):
    res = gpg.get_secret_key(fingerprint=key_a_fp, gnupghome=str(gpghome))
    assert res
    assert "keyid" in res
    assert res["keyid"] == key_a_fp[-16:]
    assert "keyLength" in res
    assert res["keyLength"] == "1024"


def test_get_secret_key_from_keyring(gpghome, gpg, key_a_fp, keyring_privkeys, gnupg):
    assert not gnupg.list_keys(keys=key_a_fp, secret=True)
    res = gpg.get_secret_key(
        fingerprint=key_a_fp, gnupghome=str(gpghome), keyring=keyring_privkeys
    )
    assert res
    assert "keyid" in res
    assert res["keyid"] == key_a_fp[-16:]
    assert "keyLength" in res
    assert res["keyLength"] == "1024"


def test_import_key(gpghome, gnupg, gpg, key_a_pub, key_a_fp):
    assert not gnupg.list_keys(keys=key_a_fp)
    res = gpg.import_key(text=key_a_pub, gnupghome=str(gpghome))
    assert res
    assert res["res"]
    assert "Successfully imported" in res["message"]
    assert gnupg.list_keys(keys=key_a_fp)


@pytest.mark.parametrize("keyring", [""], indirect=True)
def test_import_key_to_keyring(
    gpghome, gnupg, gpg, key_d_pub, key_d_fp, keyring, gnupg_keyring
):
    assert not gnupg.list_keys(keys=key_d_fp)
    assert not gnupg_keyring.list_keys(keys=key_d_fp)
    res = gpg.import_key(text=key_d_pub, gnupghome=str(gpghome), keyring=keyring)
    assert res
    assert res["res"]
    assert "Successfully imported" in res["message"]
    assert not gnupg.list_keys(keys=key_d_fp)
    assert gnupg_keyring.list_keys(keys=key_d_fp)


@pytest.mark.parametrize("select", (False, True))
def test_import_key_select(
    gpghome, gnupg, gpg, key_a_pub, key_a_fp, key_b_pub, key_b_fp, select
):
    select = key_a_fp if select else None
    assert not gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_b_fp)
    res = gpg.import_key(
        text=key_a_pub + "\n" + key_b_pub, select=select, gnupghome=str(gpghome)
    )
    assert res
    assert res["res"]
    assert "Successfully imported" in res["message"]
    assert gnupg.list_keys(keys=key_a_fp)
    assert bool(gnupg.list_keys(keys=key_b_fp)) is not bool(select)


@pytest.mark.usefixtures("_pubkeys_present")
def test_export_key(gpghome, gpg, key_a_fp):
    res = gpg.export_key(keyids=key_a_fp, gnupghome=str(gpghome))
    assert res["res"]
    assert res["comment"].startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----")
    assert res["comment"].endswith("-----END PGP PUBLIC KEY BLOCK-----\n")


def test_export_key_from_keyring(gpghome, gnupg, gpg, key_a_fp, keyring, gnupg_keyring):
    assert not gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    res = gpg.export_key(keyids=key_a_fp, gnupghome=str(gpghome), keyring=keyring)
    assert res["res"]
    assert res["comment"].startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----")
    assert res["comment"].endswith("-----END PGP PUBLIC KEY BLOCK-----\n")


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.parametrize("use_keyid", [True, False])
def test_trust_key(gpghome, key_a_fp, gnupg, gpg, use_keyid):
    keyid = key_a_fp[-16:] if use_keyid else None
    fingerprint = None if keyid else key_a_fp
    res = gpg.trust_key(
        fingerprint=fingerprint,
        keyid=keyid,
        trust_level="ultimately",
        gnupghome=str(gpghome),
    )
    assert res["res"]
    assert "fingerprint" in res
    assert res["fingerprint"] == key_a_fp
    key_info = gnupg.list_keys(keys=key_a_fp)
    assert key_info
    assert key_info[0]["trust"] == "u"


@pytest.mark.parametrize("use_keyid", [True, False])
def test_trust_key_keyring(
    gpghome, key_a_fp, keyring, gnupg, gnupg_keyring, gpg, use_keyid
):
    assert not gnupg.list_keys(keys=key_a_fp)
    keyid = key_a_fp[-16:] if use_keyid else None
    fingerprint = None if keyid else key_a_fp
    res = gpg.trust_key(
        fingerprint=fingerprint,
        keyid=keyid,
        trust_level="ultimately",
        gnupghome=str(gpghome),
        keyring=keyring,
    )
    assert res["res"]
    assert "fingerprint" in res
    assert res["fingerprint"] == key_a_fp
    key_info = gnupg_keyring.list_keys(keys=key_a_fp)
    assert key_info
    assert key_info[0]["trust"] == "u"


@pytest.mark.usefixtures("_privkeys_present")
@pytest.mark.requires_random_entropy
def test_sign(gpghome, gpg, gnupg, key_a_fp):
    assert gnupg.list_keys(secret=True, keys=key_a_fp)
    res = gpg.sign(text="foo", keyid=key_a_fp, gnupghome=str(gpghome))
    assert res
    assert res.startswith(b"-----BEGIN PGP SIGNED MESSAGE-----")
    assert res.endswith(b"-----END PGP SIGNATURE-----\n")


@pytest.mark.requires_random_entropy
def test_sign_with_keyring(
    gpghome, gpg, gnupg, key_a_fp, gnupg_privkeyring, keyring_privkeys
):
    assert not gnupg.list_keys(keys=key_a_fp, secret=True)
    assert gnupg_privkeyring.list_keys(keys=key_a_fp, secret=True)
    res = gpg.sign(
        text="foo", keyid=key_a_fp, gnupghome=str(gpghome), keyring=keyring_privkeys
    )
    assert res
    assert res.startswith(b"-----BEGIN PGP SIGNED MESSAGE-----")
    assert res.endswith(b"-----END PGP SIGNATURE-----\n")


@pytest.mark.parametrize(
    "sig,expected",
    [
        (["a"], True),
        (["c_fail"], False),
    ],
    indirect=["sig"],
)
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_verify(gpg, gpghome, signed_data, sig, expected, key_a_fp):
    res = gpg.verify(filename=str(signed_data), gnupghome=str(gpghome), signature=sig)
    assert res["res"] is expected
    if not expected:
        assert "could not be verified" in res["message"]
    else:
        assert "is verified" in res["message"]
        assert "key_id" in res
        assert res["key_id"] == key_a_fp[-16:]


@pytest.mark.parametrize(
    "sig,by,expected",
    [
        ("a", "ab", True),
        ("bd", "ab", True),
        ("bd", "ad", True),
        ("a", "bcde", False),
        (["c_fail"], "bc", False),
        (["c_fail", "b"], "bc", True),
        # Bad signatures partly overwrite the preceding good one currently.
        # https://github.com/vsajip/python-gnupg/issues/214
        # The module contains a workaround for this issue though.
        # The following would not have an issue since we only rely on trust_level and fingerprint.
        (["b", "c_fail"], "bc", True),
        (["e_exp"], "e", False),
        (["e_exp", "a"], "a", True),
        (["a", "e_exp"], "a", True),
        ("f", "abcde", False),
        ("fa", "abcde", True),
        # The above mentioned issue also affects signatures
        # whose pubkeys are absent from the keychain, but they
        # also overwrite the previous one's fingerprint (which we compare to).
        # So the following would fail without the workaround:
        ("af", "abcde", True),
        # Without the workaround, the following would be accepted (= test failure),
        # even though the `f` signature was never verified because the pubkey
        # was missing.
        ("af", "f", False),
    ],
    indirect=["sig"],
)
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_verify_signed_by_any(
    gpg, gpghome, signed_data, sig, by, expected, request
):
    fps = [request.getfixturevalue(f"key_{x}_fp") for x in by]
    res = gpg.verify(
        filename=str(signed_data),
        gnupghome=str(gpghome),
        signature=sig,
        signed_by_any=fps,
    )
    assert res["res"] is expected


@pytest.mark.parametrize(
    "sig,by,expected",
    [
        ("a", "a", True),
        ("bd", "a", False),
        ("ad", "ad", True),
        ("ad", "ad", True),
        ("ad", "ac", False),
        (["a", "c_fail"], "ac", False),
        # Bad signatures partly overwrite the preceding good one currently.
        # https://github.com/vsajip/python-gnupg/issues/214
        # The module contains a workaround for this issue though.
        # The following would not have an issue since we only rely on trust_level and fingerprint.
        (["a", "b", "c_fail"], "ab", True),
        (["a", "b", "c_fail"], "abc", False),
        (["c_fail", "a", "b"], "ab", True),
        ("fad", "da", True),
        ("fd", "da", False),
        # The above mentioned issue also affects signatures
        # whose pubkeys are absent from the keychain, but they
        # also overwrite the previous one's fingerprint (which we compare to).
        # So the following would fail without the workaround:
        ("dfa", "da", True),
        # Without the workaround, the following would be accepted (= test fail),
        # even though the `f` signature was never verified because the pubkey
        # was missing.
        ("abf", "af", False),
    ],
    indirect=["sig"],
)
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_verify_signed_by_all(
    gpg, gpghome, signed_data, sig, by, expected, request
):
    fps = [request.getfixturevalue(f"key_{x}_fp") for x in by]
    res = gpg.verify(
        filename=str(signed_data),
        gnupghome=str(gpghome),
        signature=sig,
        signed_by_all=fps,
    )
    assert res["res"] is expected


@pytest.mark.usefixtures("_pubkeys_present")
def test_verify(gpghome, gpg, sig, signed_data, key_a_fp):
    res = gpg.verify(
        filename=str(signed_data),
        signature=str(sig),
        gnupghome=str(gpghome),
    )
    assert res["res"]
    assert "is verified" in res["message"]
    assert "key_id" in res
    assert res["key_id"] == key_a_fp[-16:]


def test_verify_with_keyring(gpghome, gnupg, gpg, keyring, sig, signed_data, key_a_fp):
    assert not gnupg.list_keys(keys=key_a_fp)
    res = gpg.verify(
        filename=str(signed_data),
        signature=str(sig),
        gnupghome=str(gpghome),
        keyring=keyring,
    )
    assert res["res"]
    assert "is verified" in res["message"]
    assert "key_id" in res
    assert res["key_id"] == key_a_fp[-16:]


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.requires_random_entropy
def test_encrypt(gpghome, gpg, gnupg, key_b_fp):
    assert gnupg.list_keys(keys=key_b_fp)
    res = gpg.encrypt(
        text="I like turtles",
        recipients=key_b_fp,
        gnupghome=str(gpghome),
        always_trust=True,
    )
    assert res
    assert res["res"]
    assert res["comment"]
    assert res["comment"].startswith(b"-----BEGIN PGP MESSAGE-----")
    assert res["comment"].endswith(b"-----END PGP MESSAGE-----\n")


@pytest.mark.requires_random_entropy
def test_encrypt_with_keyring(gpghome, gpg, gnupg, key_a_fp, keyring, gnupg_keyring):
    assert not gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    res = gpg.encrypt(
        text="I like turtles",
        recipients=key_a_fp,
        gnupghome=str(gpghome),
        keyring=keyring,
        always_trust=True,
    )
    assert res
    assert res["res"]
    assert res["comment"]
    assert res["comment"].startswith(b"-----BEGIN PGP MESSAGE-----")
    assert res["comment"].endswith(b"-----END PGP MESSAGE-----\n")


@pytest.mark.usefixtures("_privkeys_present")
def test_decrypt(gpghome, gpg, gnupg, secret_message, key_a_fp):
    assert gnupg.list_keys(secret=True, keys=key_a_fp)
    res = gpg.decrypt(text=secret_message, gnupghome=str(gpghome))
    assert res["res"]
    assert res["comment"]
    assert res["comment"] == b"I like turtles"


def test_decrypt_with_keyring(
    gpghome, gpg, gnupg, gnupg_privkeyring, keyring_privkeys, secret_message, key_a_fp
):
    assert not gnupg.list_keys(secret=True, keys=key_a_fp)
    assert gnupg_privkeyring.list_keys(secret=True, keys=key_a_fp)
    res = gpg.decrypt(
        text=secret_message, gnupghome=str(gpghome), keyring=keyring_privkeys
    )
    assert res["res"]
    assert res["comment"]
    assert res["comment"] == b"I like turtles"


@pytest.mark.parametrize(
    "text",
    (
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
            ),
        ),
    ),
)
def test_read_key(gpg, gpghome, key_a_pub, key_a_fp, text):
    if text:
        res = gpg.read_key(text=key_a_pub, gnupghome=str(gpghome))
    else:
        with pytest.helpers.temp_file("key", contents=key_a_pub) as keyfile:
            res = gpg.read_key(path=str(keyfile), gnupghome=str(gpghome))
    assert res
    assert len(res) == 1
    assert res[0]["fingerprint"] == key_a_fp


@pytest.mark.parametrize(
    "text",
    (
        False,
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
            ),
        ),
    ),
)
@pytest.mark.parametrize("fingerprint", (False, True))
@pytest.mark.parametrize("keyid", (False, True))
def test_read_key_multiple(
    gpg,
    gnupg,
    gpghome,
    key_a_pub,
    key_a_fp,
    key_b_pub,
    key_b_fp,
    text,
    fingerprint,
    keyid,
):
    params = {
        "gnupghome": str(gpghome),
    }
    if fingerprint:
        params["fingerprint"] = key_a_fp
    if keyid:
        params["keyid"] = key_a_fp[-8:]
    concat = key_a_pub + "\n" + key_b_pub
    if text:
        res = gpg.read_key(text=concat, **params)
    else:
        with pytest.helpers.temp_file("key", contents=concat) as keyfile:
            res = gpg.read_key(path=str(keyfile), **params)
    assert res
    if not (fingerprint or keyid):
        assert len(res) == 2
        assert any(key["fingerprint"] == key_b_fp for key in res)
    else:
        assert len(res) == 1
    assert any(key["fingerprint"] == key_a_fp for key in res)


def test_missing_gnupghome(gpg, tmp_path):
    """
    Ensure the directory passed as `gnupghome` is created before
    python-gnupg is invoked. Issue #66312.
    """
    gnupghome = tmp_path / "gnupghome"
    try:
        res = gpg.list_keys(gnupghome=tmp_path / "gnupghome")
        assert res == []
    finally:
        # Make sure we don't leave any gpg-agents running behind
        _kill_gpg_agent(gnupghome)
