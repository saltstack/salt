import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform


def test_salt_upgrade(salt_call_cli, install_salt):
    """
    Test an upgrade of Salt.
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    if install_salt.relenv:
        original_py_version = install_salt.package_python_version()

    # Verify previous install version is setup correctly and works
    ret = salt_call_cli.run("test.version")
    assert ret.returncode == 0
    assert packaging.version.parse(ret.data) < packaging.version.parse(
        install_salt.artifact_version
    )

    # Test pip install before an upgrade
    dep = "PyGithub==1.56.0"
    install = salt_call_cli.run("--local", "pip.install", dep)
    assert install.returncode == 0

    # Verify we can use the module dependent on the installed package
    repo = "https://github.com/saltstack/salt.git"
    use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
    assert "Authentication information could" in use_lib.stderr

    # Verify there is a running minion by getting its PID
    if platform.is_windows():
        process_name = "salt-minion.exe"
    else:
        process_name = "salt-minion"
    old_pid = None
    for proc in psutil.process_iter():
        if process_name in proc.name():
            if psutil.Process(proc.ppid()).name() != process_name:
                old_pid = proc.pid
                break
    assert old_pid is not None

    # Upgrade Salt from previous version and test
    install_salt.install(upgrade=True)
    ret = salt_call_cli.run("test.version")
    assert ret.returncode == 0
    assert packaging.version.parse(ret.data) == packaging.version.parse(
        install_salt.artifact_version
    )

    # Verify there is a new running minion by getting its PID and comparing it
    # with the PID from before the upgrade
    new_pid = None
    for proc in psutil.process_iter():
        if process_name in proc.name():
            if psutil.Process(proc.ppid()).name() != process_name:
                new_pid = proc.pid
                break
    assert new_pid is not None
    assert new_pid != old_pid

    if install_salt.relenv:
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # test pip install after an upgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr
