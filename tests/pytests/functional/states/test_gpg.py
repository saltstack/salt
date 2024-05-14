import contextlib
import shutil
import subprocess
from pathlib import Path

import psutil
import pytest

gnupglib = pytest.importorskip("gnupg", reason="Needs python-gnupg library")
PYGNUPG_VERSION = tuple(int(x) for x in gnupglib.__version__.split("."))

pytestmark = [
    pytest.mark.skip_if_binaries_missing("gpg", reason="Needs gpg binary"),
]


@pytest.fixture
def gpghome(tmp_path):
    root = tmp_path / "gpghome"
    root.mkdir(mode=0o0700)
    try:
        yield root
    finally:
        # Make sure we don't leave any gpg-agents running behind
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
def gpg(loaders, states, gpghome):
    try:
        yield states.gpg
    finally:
        pass


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
def key_e_pub_notexpired():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

mI0EY4gjEQEEAKYpWezZQWiAUDvAMcMhBkjHGY2fM4MMiXc6+fRbNV4VCL9TtJYE
gjccYVu44DtIYQzMVimrPQ6xepUmFRalezCG0OO4v25Ciwyeg8LX+Tb3kyAYFAxi
qLXAJyr3aZ/539xBak/Vf5xdURIi7WF5qBGQxd87tRDDqyPFnr87JJtFABEBAAG0
LUtleSBFIChHZW5lcmF0ZWQgYnkgU2FsdFN0YWNrKSA8a2V5ZUBleGFtcGxlPojR
BBMBCAA7AhsvBQsJCAcCAiICBhUKCQgLAgQWAgMBAh4HAheAFiEEJAHEAndjKNeN
a0xdZ9NbyYUC2bkFAmYOi8gACgkQZ9NbyYUC2bmTyAP+Jo5WUP9LYtXgcbKdhcbz
Kt6Cgbk39rzpmAYpejRSmiu0VrSuSou5W+60YhPPLOVdNOOsKFK1n1wO6sNwCTRU
xrQwNI2yBnuCIV/ZmuOdXLRKc4L8nGXW4lmDKK1PqrXDNH14Bpw0e+FVOR+iR3nW
G5lpc2BZ/RGsECq/HcbpFIM=
=qG1x
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture
def gnupg(gpghome):
    return gnupglib.GPG(gnupghome=str(gpghome))


@pytest.fixture
def gnupg_keyring(gpghome, keyring):
    return gnupglib.GPG(gnupghome=str(gpghome), keyring=keyring)


@pytest.fixture(params=["a"])
def _pubkeys_present(gnupg, request):
    pubkeys = [request.getfixturevalue(f"key_{x}_pub") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    gnupg.import_keys("\n".join(pubkeys))
    present_keys = gnupg.list_keys()
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


@pytest.fixture(params=(False, True))
def testmode(request):
    return request.param


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_present_no_changes(gpghome, gpg, gnupg, key_a_fp, testmode):
    assert gnupg.list_keys(keys=key_a_fp)
    ret = gpg.present(
        key_a_fp[-16:],
        trust="unknown",
        gnupghome=str(gpghome),
        keyserver="nonexistent",
        test=testmode,
    )
    assert ret.result
    assert not ret.changes


def test_gpg_present_keyring_no_changes(
    gpghome, gpg, gnupg, gnupg_keyring, keyring, key_a_fp, testmode
):
    """
    The keyring tests are not whitelisted on Windows since they are just
    timing out, possibly because of the two separate GPG instances?
    """
    assert not gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    ret = gpg.present(
        key_a_fp[-16:],
        trust="unknown",
        gnupghome=str(gpghome),
        keyserver="nonexistent",
        keyring=keyring,
        test=testmode,
    )
    assert ret.result
    assert not ret.changes


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_present_trust_change(gpghome, gpg, gnupg, key_a_fp, testmode):
    assert gnupg.list_keys(keys=key_a_fp)
    ret = gpg.present(
        key_a_fp[-16:],
        gnupghome=str(gpghome),
        trust="ultimately",
        keyserver="nonexistent",
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert ret.changes == {key_a_fp[-16:]: {"trust": "ultimately"}}
    key_info = gnupg.list_keys(keys=key_a_fp)
    assert key_info
    assert (key_info[0]["trust"] == "u") is not testmode


def test_gpg_present_keyring_trust_change(
    gpghome, gpg, gnupg, gnupg_keyring, keyring, key_a_fp, testmode
):
    assert not gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    ret = gpg.present(
        key_a_fp[-16:],
        gnupghome=str(gpghome),
        trust="ultimately",
        keyserver="nonexistent",
        keyring=keyring,
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert ret.changes == {key_a_fp[-16:]: {"trust": "ultimately"}}
    key_info = gnupg_keyring.list_keys(keys=key_a_fp)
    assert key_info
    assert (key_info[0]["trust"] == "u") is not testmode


# Cannot whitelist source/text tests for Windows since it uses a
# keyring internally, which causes test timeouts for some reason.
def test_gpg_present_source(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp, testmode
):
    with pytest.helpers.temp_file(
        "keys", contents=key_a_pub + "\n" + key_b_pub
    ) as keyfile:
        ret = gpg.present(
            key_a_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            source=str(keyfile),
            test=testmode,
        )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert bool(gnupg.list_keys(keys=key_a_fp)) is not testmode
    assert not gnupg.list_keys(keys=key_b_fp)


@pytest.mark.parametrize("keyring", ((),), indirect=True)
def test_gpg_present_source_keyring(
    gpghome,
    gpg,
    gnupg,
    gnupg_keyring,
    keyring,
    key_a_fp,
    key_a_pub,
    key_b_pub,
    key_b_fp,
    testmode,
):
    """
    Ensure imports from a list of file sources to a keyring work
    """
    with pytest.helpers.temp_file(
        "keys", contents=key_a_pub + "\n" + key_b_pub
    ) as keyfile:
        ret = gpg.present(
            key_a_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            source=str(keyfile),
            keyring=keyring,
            test=testmode,
        )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert not gnupg.list_keys(keys=key_a_fp)
    assert bool(gnupg_keyring.list_keys(keys=key_a_fp)) is not testmode
    assert not gnupg_keyring.list_keys(keys=key_b_fp)


@pytest.mark.skipif(
    PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
)
def test_gpg_present_text(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp, testmode
):
    concat = key_a_pub + "\n" + key_b_pub
    ret = gpg.present(
        key_a_fp[-16:], gnupghome=str(gpghome), text=concat, test=testmode
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert bool(gnupg.list_keys(keys=key_a_fp)) is not testmode
    assert not gnupg.list_keys(keys=key_b_fp)


@pytest.mark.skipif(
    PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
)
@pytest.mark.parametrize("keyring", ((),), indirect=True)
def test_gpg_present_text_keyring(
    gpghome,
    gpg,
    gnupg,
    gnupg_keyring,
    keyring,
    key_a_fp,
    key_a_pub,
    key_b_pub,
    key_b_fp,
    testmode,
):
    """
    Ensure imports from a textual source to a keyring work
    """
    concat = key_a_pub + "\n" + key_b_pub
    ret = gpg.present(
        key_a_fp[-16:],
        gnupghome=str(gpghome),
        keyring=keyring,
        text=concat,
        test=testmode,
    )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert not gnupg.list_keys(keys=key_a_fp)
    assert bool(gnupg_keyring.list_keys(keys=key_a_fp)) is not testmode
    assert not gnupg_keyring.list_keys(keys=key_b_fp)


@pytest.mark.skipif(
    PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
)
def test_gpg_present_text_not_contained(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp, key_c_fp
):
    concat = key_a_pub + "\n" + key_b_pub
    ret = gpg.present(key_c_fp[-16:], gnupghome=str(gpghome), text=concat)
    assert not ret.result
    assert not ret.changes
    assert not gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_b_fp)
    assert "Passed text did not contain the requested key" in ret.comment


def test_gpg_present_multi_source(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp
):
    with pytest.helpers.temp_file("keyb", contents=key_b_pub) as keybfile:
        with pytest.helpers.temp_file("keya", contents=key_a_pub) as keyafile:
            ret = gpg.present(
                key_a_fp[-16:],
                gnupghome=str(gpghome),
                skip_keyserver=True,
                source=[str(keybfile), str(keyafile)],
            )
    assert ret.result
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_b_fp)


def test_gpg_present_source_not_contained(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp, key_c_fp
):
    with pytest.helpers.temp_file(
        "keys", contents=key_a_pub + "\n" + key_b_pub
    ) as keyfile:
        ret = gpg.present(
            key_c_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            source=str(keyfile),
        )
    assert not ret.result
    assert not ret.changes
    assert not gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_b_fp)
    assert (
        "none of the specified sources were found or contained the (unexpired) key"
        in ret.comment
    )


def test_gpg_present_source_bad_keyfile(
    gpghome, gpg, gnupg, key_a_fp, key_a_pub, key_b_pub, key_b_fp
):
    with pytest.helpers.temp_file(
        "keys", contents=key_a_pub + "\n" + key_b_pub
    ) as keyfile:
        with pytest.helpers.temp_file("badkeys", contents="foobar") as badkeyfile:
            ret = gpg.present(
                key_a_fp[-16:],
                gnupghome=str(gpghome),
                skip_keyserver=True,
                source=["/foo/bar/non/ex/is/tent", str(badkeyfile), str(keyfile)],
            )
    assert ret.result
    assert ret.changes
    assert key_a_fp[-16:] in ret.changes
    assert ret.changes[key_a_fp[-16:]]["added"]
    assert gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_b_fp)


@pytest.mark.parametrize(
    "method",
    (
        "source",
        pytest.param(
            "text",
            marks=pytest.mark.skipif(
                PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
            ),
        ),
    ),
)
def test_gpg_present_import_expired_key(
    method, gpghome, gpg, gnupg, key_e_fp, key_e_pub
):
    """
    Ensure that when a newly imported key is expired, the state fails.
    The key should be imported though if it was not present before.
    """
    if method == "source":
        ctx = pytest.helpers.temp_file("keys", contents=key_e_pub)
    else:
        ctx = contextlib.nullcontext()
        params = {"text": key_e_pub}
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_e_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            **params,
        )
    assert ret.result is False
    assert "is expired" in ret.comment
    assert ret.changes
    assert ret.changes[key_e_fp[-16:]]["added"]
    assert gnupg.list_keys(keys=key_e_fp)


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.parametrize("_pubkeys_present", (("e",),), indirect=True)
@pytest.mark.parametrize(
    "method",
    (
        "source",
        pytest.param(
            "text",
            marks=pytest.mark.skipif(
                PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
            ),
        ),
    ),
)
def test_gpg_present_expired_key_already_present_fails(
    method, gpghome, gpg, gnupg, key_e_fp, key_e_pub
):
    """
    Ensure that when a present key is expired and no new one can be found,
    the state fails without changes.
    """
    if method == "source":
        ctx = pytest.helpers.temp_file("keys", contents=key_e_pub)
    else:
        ctx = contextlib.nullcontext()
        params = {"text": key_e_pub}
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_e_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            **params,
        )
    assert ret.result is False
    if method == "source":
        assert "contained the (unexpired) key" in ret.comment
    else:
        assert "but it's expired" in ret.comment
    assert not ret.changes


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.parametrize("_pubkeys_present", (("e",),), indirect=True)
@pytest.mark.parametrize(
    "method",
    (
        "source",
        pytest.param(
            "text",
            marks=pytest.mark.skipif(
                PYGNUPG_VERSION < (0, 5, 1), reason="Text requires python-gnupg >=0.5.1"
            ),
        ),
    ),
)
def test_gpg_present_expired_key_already_present_refresh(
    method, gpghome, gpg, gnupg, key_e_fp, key_e_pub_notexpired, testmode
):
    """
    Ensure that when a present key is expired and a new one is available,
    the key is reimported.
    """
    if method == "source":
        ctx = pytest.helpers.temp_file("keys", contents=key_e_pub_notexpired)
    else:
        ctx = contextlib.nullcontext()
        params = {"text": key_e_pub_notexpired}
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_e_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            **params,
            test=testmode,
        )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert "the existing one was expired" in ret.comment
    assert ret.changes
    assert ret.changes[key_e_fp[-16:]]["added"]
    assert ret.changes[key_e_fp[-16:]]["refresh"]


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.parametrize("_pubkeys_present", (("e",),), indirect=True)
def test_gpg_present_expired_key_trust_change(
    gpghome, gpg, gnupg, key_e_fp, key_e_pub_notexpired, testmode
):
    """
    Test that key expiry updates and trust changes work together
    """
    assert gnupg.list_keys(keys=key_e_fp)
    with pytest.helpers.temp_file("keys", contents=key_e_pub_notexpired) as keyfile:
        ret = gpg.present(
            key_e_fp[-16:],
            gnupghome=str(gpghome),
            trust="ultimately",
            skip_keyserver=True,
            source=[str(keyfile)],
            test=testmode,
        )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert ret.changes
    assert ret.changes == {
        key_e_fp[-16:]: {"added": True, "refresh": True, "trust": "ultimately"}
    }
    key_info = gnupg.list_keys(keys=key_e_fp)
    assert key_info
    assert (key_info[0]["trust"] == "u") is not testmode


@pytest.mark.windows_whitelisted
def test_gpg_absent_no_changes(gpghome, gpg, gnupg, key_a_fp):
    assert not gnupg.list_keys(keys=key_a_fp)
    ret = gpg.absent(key_a_fp[-16:], gnupghome=str(gpghome))
    assert ret.result
    assert not ret.changes


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_absent(gpghome, gpg, gnupg, key_a_fp):
    assert gnupg.list_keys(keys=key_a_fp)
    assert not gnupg.list_keys(keys=key_a_fp, secret=True)
    ret = gpg.absent(key_a_fp[-16:], gnupghome=str(gpghome))
    assert ret.result
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"]


@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_absent_from_keyring(gpghome, gpg, gnupg, gnupg_keyring, keyring, key_a_fp):
    assert gnupg.list_keys(keys=key_a_fp)
    assert gnupg_keyring.list_keys(keys=key_a_fp)
    ret = gpg.absent(key_a_fp[-16:], gnupghome=str(gpghome), keyring=keyring)
    assert ret.result
    assert ret.changes
    assert gnupg.list_keys(keys=key_a_fp)
    assert not gnupg_keyring.list_keys(keys=key_a_fp)


@pytest.mark.parametrize("keyring", [""], indirect=True)
def test_gpg_absent_from_keyring_delete_keyring(
    gpghome, gpg, gnupg, gnupg_keyring, keyring, key_a_fp
):
    assert not gnupg_keyring.list_keys()
    assert Path(keyring).exists()
    ret = gpg.absent(
        "abc", gnupghome=str(gpghome), keyring=keyring, keyring_absent_if_empty=True
    )
    assert ret.result
    assert ret.changes
    assert "removed" in ret.changes
    assert ret.changes["removed"] == keyring
    assert not Path(keyring).exists()


@pytest.mark.windows_whitelisted
@pytest.mark.usefixtures("_pubkeys_present")
def test_gpg_absent_test_mode_no_changes(gpghome, gpg, gnupg, key_a_fp):
    assert gnupg.list_keys(keys=key_a_fp)
    ret = gpg.absent(key_a_fp[-16:], gnupghome=str(gpghome), test=True)
    assert ret.result is None
    assert ret.changes
    assert "deleted" in ret.changes
    assert ret.changes["deleted"]
    assert gnupg.list_keys(keys=key_a_fp)
