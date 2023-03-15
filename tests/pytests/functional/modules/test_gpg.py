import shutil
import subprocess

import psutil
import pytest

try:
    import gnupg as gnupglib

    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


pytestmark = [
    pytest.mark.skipif(HAS_GNUPG is False, reason="Needs python-gnupg library"),
    pytest.mark.skip_if_binaries_missing("gpg", reason="Needs gpg binary"),
]


@pytest.fixture
def gpghome(tmp_path):
    root = tmp_path / "gpghome"
    root.mkdir(mode=0o0700)
    try:
        yield root
    finally:
        # Make sure we don't leave any gpg-agent's running behind
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
def gpg(loaders, modules, gpghome):
    try:
        yield modules.gpg
    finally:
        pass


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
def key_a_sig():
    return """\
-----BEGIN PGP SIGNATURE-----

iLMEAAEIAB0WIQTvA3ZfWe6QSTDIp4FVOoKgWMDHlQUCY4fz7QAKCRBVOoKgWMDH
lYH/A/9iRT4JqzZEfRGM6XUyVbLCoF2xyEc43yL06nxn1sMFjMdLOLUDsaZbppHB
vEo4XJ45+Xqu1h3RK6bDVdDURyacPzdef8v357rJHjT8tb68JcwSzCBXLh29Nasl
cOm6/gNVIVm3Uoe9mKXESRvpMYmNUp2UM7ZzzBstK/ViVR82UA==
=EZPV
-----END PGP SIGNATURE-----"""


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


@pytest.fixture(params=["a"])
def pubkeys_present(gnupg, request):
    pubkeys = [request.getfixturevalue(f"key_{x}_pub") for x in request.param]
    fingerprints = [request.getfixturevalue(f"key_{x}_fp") for x in request.param]
    gnupg.import_keys("\n".join(pubkeys))
    present_keys = gnupg.list_keys()
    for fp in fingerprints:
        assert any(x["fingerprint"] == fp for x in present_keys)
    yield
    # cleanup is taken care of by gpghome and tmp_path


@pytest.mark.usefixtures("pubkeys_present")
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
