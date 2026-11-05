import pathlib
import re
import subprocess
import zipfile

import pytest

VERSION_RE = re.compile(
    r"""^__version__\s*=\s*(?:version\s*=\s*)?["']([^"']+)["']""", re.MULTILINE
)


@pytest.fixture(autouse=True)
def skip_on_prev_version(install_salt):
    """
    Skip these tests when running against the previous (downgraded) Salt
    version, which does not align pip's vendored urllib3 with Salt's.
    """
    if install_salt.use_prev_version:
        pytest.skip(
            "pip's vendored urllib3 is not aligned in the previous Salt version"
        )


def _python_output(install_salt, code):
    ret = subprocess.run(
        install_salt.binary_paths["python"] + ["-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ret.returncode == 0, ret.stderr
    return ret.stdout.strip()


@pytest.fixture
def salt_urllib3_version(install_salt):
    """
    The urllib3 version Salt itself ships in the onedir.
    """
    version = _python_output(install_salt, "import urllib3; print(urllib3.__version__)")
    if int(version.split(".")[0]) < 2:
        # Python 3.9 onedirs stay on urllib3 1.x and keep pip as shipped.
        pytest.skip(f"Salt ships urllib3 {version}; pip's vendored copy is not aligned")
    return version


def test_pip_vendored_urllib3_version(install_salt, salt_urllib3_version):
    """
    pip's vendored urllib3 must match the urllib3 Salt installs, so pip does
    not keep shipping a urllib3 with known vulnerabilities.
    """
    version = _python_output(
        install_salt,
        "import pip._vendor.urllib3; print(pip._vendor.urllib3.__version__)",
    )
    assert version == salt_urllib3_version, (
        f"pip's vendored urllib3 is {version!r}; "
        f"Salt ships {salt_urllib3_version!r}"
    )


def test_virtualenv_embedded_pip_wheel_urllib3_version(
    install_salt, salt_urllib3_version
):
    """
    The pip wheel bundled in virtualenv's seed/wheels/embed directory must
    carry the same urllib3, so new virtualenvs seeded from it inherit it.
    """
    site_packages = pathlib.Path(
        _python_output(
            install_salt,
            "import pip, pathlib; print(pathlib.Path(pip.__file__).parent.parent)",
        )
    )
    embed_dir = site_packages / "virtualenv" / "seed" / "wheels" / "embed"

    if not embed_dir.is_dir():
        pytest.skip(f"virtualenv embed directory not found: {embed_dir}")

    pip_wheels = sorted(embed_dir.glob("pip-*.whl"))
    if not pip_wheels:
        pytest.skip(f"No pip wheel found in {embed_dir}")

    pip_wheel = pip_wheels[-1]
    with zipfile.ZipFile(pip_wheel) as zf:
        try:
            content = zf.read("pip/_vendor/urllib3/_version.py").decode("utf-8")
        except KeyError:
            pytest.fail(
                f"pip/_vendor/urllib3/_version.py not found inside {pip_wheel.name}"
            )

    match = VERSION_RE.search(content)
    assert match, f"Could not parse __version__ from {pip_wheel.name}"
    version = match.group(1)
    assert version == salt_urllib3_version, (
        f"Embedded pip wheel {pip_wheel.name} contains urllib3 {version!r}; "
        f"Salt ships {salt_urllib3_version!r}"
    )
