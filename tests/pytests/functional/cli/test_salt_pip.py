import base64
import hashlib
import os
import zipfile

import pytest

import salt.scripts
import salt.utils.platform
from tests.conftest import CODE_DIR
from tests.support.mock import patch


def _onedir_script_path():
    script_name = "salt-pip"
    if salt.utils.platform.is_windows():
        script_name += ".exe"
    return CODE_DIR / "artifacts" / "salt" / script_name


def _onedir_extras_dir():
    """
    Locate the onedir's extras-<major>.<minor> directory dynamically,
    since the bundled relenv Python's version can differ from the version
    running the test suite.
    """
    root = CODE_DIR / "artifacts" / "salt"
    matches = sorted(root.glob("extras-*"))
    assert matches, f"No extras-* directory found under {root}"
    return matches[0]


def _build_wheel(dest_dir, name, version, requires=()):
    """
    Hand-build a minimal, valid, pure-Python wheel using only the stdlib
    (no setuptools/build backend, no network access) so tests can install
    a disposable fake package via salt-pip.
    """
    dist_info = f"{name}-{version}.dist-info"
    wheel_path = dest_dir / f"{name}-{version}-py3-none-any.whl"

    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
    ]
    for req in requires:
        metadata_lines.append(f"Requires-Dist: {req}")
    metadata = "\n".join(metadata_lines) + "\n"

    wheel_metadata = (
        "Wheel-Version: 1.0\n"
        "Generator: salt-test-suite\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    )

    files = {
        f"{name}/__init__.py": "# test fixture package\n",
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": wheel_metadata,
    }

    record_lines = []
    for path, content in files.items():
        data = content.encode("utf-8")
        digest = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()
        ).rstrip(b"=").decode("ascii")
        record_lines.append(f"{path},{digest},{len(data)}")
    record_lines.append(f"{dist_info}/RECORD,,")

    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
        zf.writestr(f"{dist_info}/RECORD", "\n".join(record_lines) + "\n")

    return wheel_path


def test_within_onedir_env(shell):
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        return

    script_path = _onedir_script_path()
    assert script_path.exists()

    ret = shell.run(str(script_path), "list")
    assert ret.returncode == 0


def test_outside_onedir_env(capsys):
    with patch("salt.scripts._get_onedir_env_path", return_value=None):
        with pytest.raises(SystemExit) as exc:
            salt.scripts.salt_pip()
    captured = capsys.readouterr()
    assert "'salt-pip' is only meant to be used from a Salt onedir." in captured.err


def test_extension_dependency_already_bundled_is_not_duplicated(shell, tmp_path):
    """
    Installing a salt extension whose dependency (jinja2, which Salt
    itself depends on) is already present in the onedir's own
    site-packages should not install a second copy of that dependency
    into the extras directory.

    Regression test for #70151: confirms the PYTHONPATH isolation fix in
    salt/scripts.py::_pip_environment() didn't change this expected
    behavior for ordinary extension installs.
    """
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        return

    script_path = _onedir_script_path()
    assert script_path.exists()

    wheel_path = _build_wheel(tmp_path, "faketestext", "0.1.0", requires=["jinja2"])

    try:
        ret = shell.run(str(script_path), "install", str(wheel_path))
        assert ret.returncode == 0, ret.stderr

        installed = {p.name for p in _onedir_extras_dir().iterdir()}
        assert any(name.startswith("faketestext") for name in installed)
        assert not any(
            name.lower().startswith("jinja2") for name in installed
        ), installed
    finally:
        shell.run(str(script_path), "uninstall", "-y", "faketestext")


def test_no_system_python_leakage(shell, tmp_path):
    """
    salt-pip must not see or touch packages belonging to an unrelated
    ("system") Python installation, even when PYTHONPATH points at it and
    --force-reinstall is used. This is the exact scenario from #70151: a
    PYTHONPATH inherited from an unrelated Python installation must not be
    visible to salt-pip's pip subprocess.
    """
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        return

    script_path = _onedir_script_path()
    assert script_path.exists()

    fake_system_site_packages = tmp_path / "fake-system-site-packages"
    fake_system_site_packages.mkdir()

    old_wheel = _build_wheel(tmp_path, "fakesyspkg", "1.0")
    with zipfile.ZipFile(old_wheel) as zf:
        zf.extractall(fake_system_site_packages)

    original_files = {
        path: path.read_bytes()
        for path in fake_system_site_packages.rglob("*")
        if path.is_file()
    }

    new_wheel = _build_wheel(tmp_path, "fakesyspkg", "2.0")

    try:
        ret = shell.run(
            str(script_path),
            "install",
            "--force-reinstall",
            str(new_wheel),
            env={"PYTHONPATH": str(fake_system_site_packages)},
        )
        assert ret.returncode == 0, ret.stderr

        # The fake "system" install must be completely untouched.
        current_files = {
            path: path.read_bytes()
            for path in fake_system_site_packages.rglob("*")
            if path.is_file()
        }
        assert current_files == original_files

        # The real install landed in extras, at the new version.
        installed = [
            p.name for p in _onedir_extras_dir().iterdir() if "fakesyspkg" in p.name
        ]
        assert any("2.0" in name for name in installed), installed
    finally:
        shell.run(str(script_path), "uninstall", "-y", "fakesyspkg")
