import pathlib
import re
import subprocess
import zipfile

import pytest


PATCHED_URLLIB3_VERSION = "2.6.3"


@pytest.fixture(autouse=True)
def skip_on_prev_version(install_salt):
    """
    Skip urllib3 patch tests when running against the previous (downgraded)
    Salt version, which does not contain the CVE backports.
    """
    if install_salt.use_prev_version:
        pytest.skip("urllib3 CVE patch is not present in the previous Salt version")


def _site_packages(install_salt) -> pathlib.Path:
    """Return the site-packages directory for the installed Salt Python."""
    ret = subprocess.run(
        install_salt.binary_paths["python"]
        + ["-c", "import pip, pathlib; print(pathlib.Path(pip.__file__).parent.parent)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0, ret.stderr
    return pathlib.Path(ret.stdout.strip())


def test_pip_vendored_urllib3_version(install_salt):
    """
    Verify that pip's vendored urllib3 in the installed Salt package
    reports the security-patched version string.
    """
    ret = subprocess.run(
        install_salt.binary_paths["python"]
        + [
            "-c",
            "import pip._vendor.urllib3; print(pip._vendor.urllib3.__version__)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0, ret.stderr
    version = ret.stdout.strip()
    assert version == PATCHED_URLLIB3_VERSION, (
        f"pip's vendored urllib3 is {version!r}; expected {PATCHED_URLLIB3_VERSION!r}"
    )


def test_virtualenv_embedded_pip_wheel_urllib3_version(install_salt):
    """
    Verify that the pip wheel bundled inside virtualenv's seed/wheels/embed
    directory also contains the security-patched urllib3.  New virtualenvs
    seeded from this wheel will inherit the CVE fixes.
    """
    site_packages = _site_packages(install_salt)
    embed_dir = site_packages / "virtualenv" / "seed" / "wheels" / "embed"

    if not embed_dir.is_dir():
        pytest.skip(f"virtualenv embed directory not found: {embed_dir}")

    pip_wheels = sorted(embed_dir.glob("pip-*.whl"))
    if not pip_wheels:
        pytest.skip(f"No pip wheel found in {embed_dir}")

    pip_wheel = pip_wheels[-1]
    with zipfile.ZipFile(pip_wheel) as zf:
        try:
            with zf.open("pip/_vendor/urllib3/_version.py") as f:
                content = f.read().decode("utf-8")
        except KeyError:
            pytest.fail(
                f"pip/_vendor/urllib3/_version.py not found inside {pip_wheel.name}"
            )

    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE
    )
    assert match, f"Could not parse __version__ from {pip_wheel.name}"
    version = match.group(1)
    assert version == PATCHED_URLLIB3_VERSION, (
        f"Embedded pip wheel {pip_wheel.name} contains urllib3 {version!r}; "
        f"expected {PATCHED_URLLIB3_VERSION!r}"
    )
