import base64
import hashlib
import os
import pathlib
import zipfile

import pytest

import salt.scripts
import salt.utils.platform
from tests.conftest import CODE_DIR
from tests.support.mock import MagicMock, patch


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


def _run_salt_pip_capturing_subprocess(tmp_path, monkeypatch, env_overrides):
    """
    Drive ``salt.scripts.salt_pip`` end-to-end while stubbing out the
    actual ``python -m pip`` invocation. Returns the ``env`` mapping
    that ``salt_pip`` handed to ``subprocess.run``.

    ``env_overrides`` is applied to ``os.environ`` via ``monkeypatch``
    *before* ``salt_pip`` runs so the test controls whether
    ``PIP_DISABLE_PIP_VERSION_CHECK`` is already set by the "operator".
    """
    # Scrub any inherited copy of the var first, then apply overrides.
    monkeypatch.delenv("PIP_DISABLE_PIP_VERSION_CHECK", raising=False)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    # Force a deterministic argv so _pip_args stays a no-op.
    monkeypatch.setattr("sys.argv", ["salt-pip", "--version"])

    # Pretend we're inside an onedir; the path only feeds the
    # ``extras-X.Y`` string appended to PYTHONPATH.
    fake_relenv = pathlib.Path(tmp_path)
    fake_subprocess_result = MagicMock()
    fake_subprocess_result.returncode = 0

    recorded = {}

    def fake_run(command, shell, check, env):
        recorded["command"] = command
        recorded["env"] = env
        return fake_subprocess_result

    with patch("salt.scripts._get_onedir_env_path", return_value=fake_relenv), patch(
        "salt.config.minion_config", return_value={"user": None}
    ), patch("salt.utils.user.get_user", return_value="root"), patch(
        "salt.scripts.subprocess.run", side_effect=fake_run
    ):
        with pytest.raises(SystemExit) as exc:
            salt.scripts.salt_pip()

    assert exc.value.code == 0
    assert "command" in recorded, "subprocess.run was never invoked"
    return recorded


def test_salt_pip_subprocess_gets_disable_version_check_env(tmp_path, monkeypatch):
    """
    Regression test for #70024, end-to-end.

    Drive ``salt.scripts.salt_pip`` with a stubbed ``subprocess.run`` and
    assert the ``env`` dict handed to the child ``python -m pip`` process
    has ``PIP_DISABLE_PIP_VERSION_CHECK=1``. This catches a future
    refactor that stopped routing ``salt_pip`` through
    ``_pip_environment`` — the unit test on ``_pip_environment`` alone
    would still pass in that case.
    """
    recorded = _run_salt_pip_capturing_subprocess(
        tmp_path, monkeypatch, env_overrides={}
    )
    assert recorded["env"].get("PIP_DISABLE_PIP_VERSION_CHECK") == "1"


def test_salt_pip_subprocess_respects_operator_override(tmp_path, monkeypatch):
    """
    Regression test for #70024, end-to-end.

    If an operator has already exported ``PIP_DISABLE_PIP_VERSION_CHECK=0``
    (i.e., they want pip's periodic version check back), ``salt-pip``
    must not stomp on it.
    """
    recorded = _run_salt_pip_capturing_subprocess(
        tmp_path,
        monkeypatch,
        env_overrides={"PIP_DISABLE_PIP_VERSION_CHECK": "0"},
    )
    assert recorded["env"].get("PIP_DISABLE_PIP_VERSION_CHECK") == "0"
