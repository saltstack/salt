import contextlib
import logging
import shutil
import subprocess
from pathlib import Path

import psutil
import pytest

import salt.utils.platform
from salt.modules.gpg import _homedir_fix

log = logging.getLogger(__name__)

gnupglib = pytest.importorskip("gnupg", reason="Needs python-gnupg library")
PYGNUPG_VERSION = tuple(int(x) for x in gnupglib.__version__.split("."))

pytestmark = [
    pytest.mark.skip_if_binaries_missing("gpg", reason="Needs gpg binary"),
]


@pytest.fixture
def gpghome(tmp_path, modules):
    user = modules.config.option("user")
    if salt.utils.platform.is_windows() and "\\" in user:
        # At least in the test suite, this config option is set
        # including the hostname, so split it off
        user = user.split("\\", maxsplit=1)[1]
    user_info = modules.user.info(user)
    root = tmp_path / "gpghome"
    if salt.utils.platform.is_windows():
        modules["file.mkdir"](
            str(root),
            owner=user_info["uid"],
            grant_perms={
                user_info["uid"]: {
                    "perms": "full_control",
                    "applies_to": "this_folder_subfolders_files",
                }
            },
        )
    else:
        modules["file.mkdir"](
            str(root), user=user_info["uid"], group=user_info["gid"], mode="0700"
        )

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
def key_f_pub():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
/h1WQBwSVWQ=
=zuag
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture
def key_f_pub_notexpired():
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
oY7iCpnP4fM=
=zfOS
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture
def key_f_pub_notexpired_partial():
    """
    This rotates the signing subkey and extends the encryption one.
    The auth subkey is still expired.
    """
    return """\
-----BEGIN PGP PUBLIC KEY BLOCK-----

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
1BEJqjdXgF8=
=CkL3
-----END PGP PUBLIC KEY BLOCK-----
"""


@pytest.fixture
def key_f_fp():
    return "6539A951EF21D76C0E756A522CD7B219B24BD62B"


@pytest.fixture
def gnupg(gpghome):
    _gnupg = gnupglib.GPG(gnupghome=str(gpghome), verbose=True)
    _gnupg.gnupghome = _homedir_fix(gpghome)
    # Force initialization
    _gnupg.list_keys()
    # log gpg binary path, maybe that gives us some hints
    log.error(_gnupg.gpgbinary)
    return _gnupg


@pytest.fixture
def gnupg_keyring(gpghome, keyring):
    _gnupg = gnupglib.GPG(gnupghome=str(gpghome), keyring=keyring)
    _gnupg.gnupghome = _homedir_fix(gpghome)
    return _gnupg


@pytest.fixture(params=["a"])
def _pubkeys_present(gnupg, request, gpghome):
    pubkeys = [request.getfixturevalue(f"key_{x}_pub") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    dir_gnupg = dir(gnupg)
    gnupg_version = gnupg.version
    import_result = gnupg.import_keys("\n".join(pubkeys))
    log.error("import result: %r", import_result.__dict__)
    log.error("gpghome stat: %r", gpghome.stat())
    home_contents = list(gpghome.glob("**/*"))
    log.error("gpghome list: %r", home_contents)
    if home_contents:
        log.error("gpg dir file stat: %r", home_contents[1].stat())
    import_count = import_result.count
    import_fingerprints = import_result.fingerprints
    present_keys = gnupg.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


@pytest.fixture(params=["a"])
def keyring(gpghome, tmp_path, request, gpg):
    keyring = tmp_path / "keys.gpg"
    _gnupg_keyring = gnupglib.GPG(gnupghome=str(gpghome), keyring=str(keyring))
    _gnupg_keyring.gnupghome = _homedir_fix(gpghome)

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
    assert "because it " + ("is" if testmode else "was") + " expired" in ret.comment
    assert ret.changes
    key_changes = ret.changes[key_e_fp[-16:]]
    assert "added" not in key_changes
    assert key_changes["refresh"]


@pytest.mark.usefixtures("_pubkeys_present")
@pytest.mark.parametrize("_pubkeys_present", (("f",),), indirect=True)
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
def test_gpg_present_expired_subkey_refresh(
    method, gpghome, gpg, gnupg, key_f_fp, key_f_pub_notexpired_partial, testmode
):
    """
    Ensure that when a present key has expired subkeys, an update attempt
    is performed.
    """

    def _gen_ctx():
        if method == "source":
            ctx = pytest.helpers.temp_file(
                "keys", contents=key_f_pub_notexpired_partial
            )
            params = {}
        else:
            ctx = contextlib.nullcontext()
            params = {"text": key_f_pub_notexpired_partial}
        return ctx, params

    # Subkey management is disabled. No changes.
    ctx, params = _gen_ctx()
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_f_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            subkey_maxage=False,
            **params,
            test=testmode,
        )
    assert ret.result is True
    assert not ret.changes
    assert "already in keychain" in ret.comment

    # This should update the signing subkey
    ctx, params = _gen_ctx()
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_f_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            subkey_maxage=25550,
            **params,
            test=testmode,
        )
    assert ret.result is not False
    assert (ret.result is None) is testmode
    assert (
        "because it " + ("has" if testmode else "had") + " expired subkeys"
    ) in ret.comment
    assert ret.changes
    key_changes = ret.changes[key_f_fp[-16:]]
    assert "added" not in key_changes
    assert key_changes["refresh"]
    if testmode:
        return
    assert key_changes["subkeys"] == {
        "added": ["C8439BC56681B29B"],
        "extended": ["3638BFFF230FCC4F"],
    }

    # This should attempt to update encryp/auth subkeys.
    # No changes should be reported because they cannot be updated from the provided source.
    ctx, params = _gen_ctx()
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_f_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            subkey_maxage=25550,
            **params,
            test=testmode,
        )
    assert ret.result is True
    assert not ret.changes
    assert (
        "because it has expired subkeys, but no new signatures or keys were found"
        in ret.comment
    )

    # This should report everything is fine since the
    # expired subkeys are filtered out (expired longer than 1 day).
    ctx, params = _gen_ctx()
    with ctx as inst:
        if method == "source":
            params = {"source": [str(inst)]}
        ret = gpg.present(
            key_f_fp[-16:],
            gnupghome=str(gpghome),
            skip_keyserver=True,
            subkey_maxage=1,
            **params,
            test=testmode,
        )
    assert ret.result is True
    assert not ret.changes
    assert "already in keychain" in ret.comment
    assert "subkey" not in ret.comment


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
    assert ret.changes == {key_e_fp[-16:]: {"refresh": True, "trust": "ultimately"}}
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
