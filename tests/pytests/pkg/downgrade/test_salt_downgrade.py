import time

import packaging.version
import psutil
import pytest
from pytestskipmarkers.utils import platform


def _get_running_named_salt_pid(process_name):

    # need to check all of command line for salt-minion, salt-master, for example: salt-minion
    #
    # Linux: psutil process name only returning first part of the command '/opt/saltstack/'
    # Linux: ['/opt/saltstack/salt/bin/python3.10 /usr/bin/salt-minion MultiMinionProcessManager MinionProcessManager']
    #
    # MacOS: psutil process name only returning last part of the command '/opt/salt/bin/python3.10', that is 'python3.10'
    # MacOS: ['/opt/salt/bin/python3.10 /opt/salt/salt-minion', '']

    pids = []
    for proc in psutil.process_iter():
        cmdl_strg = " ".join(str(element) for element in proc.cmdline())
        print(
            f"DGM _get_running_named_salt_pid, process_name '{process_name}', cmdl_strg '{cmdl_strg}'",
            flush=True,
        )
        if process_name in cmdl_strg:
            pids.append(proc.pid)

    return pids


def test_salt_downgrade_minion(salt_call_cli, install_salt):
    """
    Test an downgrade of Salt Minion.
    """
    print(
        f"DGM test_salt_downgrade_minion entry, install_salt '{install_salt}'",
        flush=True,
    )

    is_restart_fixed = packaging.version.parse(
        install_salt.prev_version
    ) < packaging.version.parse("3006.9")

    if is_restart_fixed and install_salt.distro_id in ("ubuntu", "debian", "darwin"):
        pytest.skip(
            "Skip package test, since downgrade version is less than "
            "3006.9 which had fixes for salt-minion restarting, see PR 66218"
        )

    is_downgrade_to_relenv = packaging.version.parse(
        install_salt.prev_version
    ) >= packaging.version.parse("3006.0")

    if is_downgrade_to_relenv:
        original_py_version = install_salt.package_python_version()

    # Verify current install version is setup correctly and works
    ret = salt_call_cli.run("--local", "test.version")
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
    salt_name = "salt"
    if platform.is_windows():
        process_name = "salt-minion.exe"
    else:
        process_name = "salt-minion"

    print(
        f"DGM test_salt_downgrade_minion, getting old pids for process_name '{process_name}'",
        flush=True,
    )
    old_minion_pids = _get_running_named_salt_pid(process_name)
    assert old_minion_pids

    # Downgrade Salt to the previous version and test
    install_salt.install(downgrade=True)

    ## DGM test code
    time.sleep(10)  # give it some time
    # a downgrade install will stop services on Debian/Ubuntu (why they didn't worry about Redhat family)
    # This is probably due to RedHat systems are not active after an install, but Debian/Ubuntu are active after an install
    # this leads to issues depending on what the sequence of tests are run , leaving the systems systemd active or not

    # Q. why are RedHat systems passing these tests, perhaps there is a case being missed where the RedHat systems are active
    # since they were not explicitly stopped, but the Debian/Ubuntu are, but in testing Ubuntu 24.04 amd64 passed but arm64 did not ?
    # Also MacOS 13 also failed ????

    test_list = ["salt-syndic", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl status {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        print(
            f"DGM test_salt_downgrade_minion systemctl status for service '{test_item}' ret '{ret}'",
            flush=True,
        )

    # trying restart for Debian/Ubuntu to see the outcome
    if install.distro_id in ("ubuntu", "debian"):
        print(
            f"DGM test_salt_downgrade_minion, ubuntu or debian, restart services for distro id '{install.distro_id}'",
            flush=True,
        )
        install.restart_services()

    time.sleep(60)  # give it some time

    # Verify there is a new running minion by getting its PID and comparing it
    # with the PID from before the upgrade
    print(
        f"DGM test_salt_downgrade_minion, getting new pids for process_name '{process_name}'",
        flush=True,
    )
    new_minion_pids = _get_running_named_salt_pid(process_name)
    assert new_minion_pids
    assert new_minion_pids != old_minion_pids

    bin_file = "salt"
    if platform.is_windows():
        if not is_downgrade_to_relenv:
            bin_file = install_salt.install_dir / "salt-call.bat"
        else:
            bin_file = install_salt.install_dir / "salt-call.exe"
    elif platform.is_darwin() and install_salt.classic:
        bin_file = install_salt.bin_dir / "salt-call"

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
