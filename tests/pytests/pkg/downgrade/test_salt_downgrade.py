import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform


def test_salt_downgrade(salt_call_cli, install_salt):
    """
    Test an upgrade of Salt.
    """
    if not install_salt.downgrade:
        pytest.skip("Not testing a downgrade, do not run")

    is_downgrade_to_relenv = packaging.version.parse(
        install_salt.prev_version
    ) >= packaging.version.parse("3006.0")

    if is_downgrade_to_relenv:
        original_py_version = install_salt.package_python_version()

    # Verify current install version is setup correctly and works
    ret = salt_call_cli.run("test.version")
    assert ret.returncode == 0
    assert packaging.version.parse(ret.data) == packaging.version.parse(
        install_salt.artifact_version
    )

    # Test pip install before a downgrade
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

    # Downgrade Salt to the previous version and test
    install_salt.install(downgrade=True)
    bin_file = "salt"
    if platform.is_windows():
        if not is_downgrade_to_relenv:
            bin_file = install_salt.install_dir / "salt-call.bat"
        else:
            bin_file = install_salt.install_dir / "salt-call.exe"
    elif platform.is_darwin() and install_salt.classic:
        bin_file = install_salt.bin_dir / "salt-call"

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

    ret = install_salt.proc.run(bin_file, "--version")
    assert ret.returncode == 0
    assert packaging.version.parse(
        ret.stdout.strip().split()[1]
    ) < packaging.version.parse(install_salt.artifact_version)

    if is_downgrade_to_relenv:
        new_py_version = install_salt.package_python_version()
        if new_py_version == original_py_version:
            # test pip install after a downgrade
            use_lib = salt_call_cli.run("--local", "github.get_repo_info", repo)
            assert "Authentication information could" in use_lib.stderr
