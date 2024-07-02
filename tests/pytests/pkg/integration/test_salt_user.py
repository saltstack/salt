import os
import pathlib
import subprocess
import sys

import packaging.version
import psutil
import pytest
from saltfactories.utils.tempfiles import temp_directory

pytestmark = [pytest.mark.skip_unless_on_linux]


@pytest.fixture
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
):
    """
    Fixture to set systemd for salt packages to enabled and active
    Note: assumes Salt packages already installed
    """
    install_salt.install()

    # ensure known state, enabled and active
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0


@pytest.fixture
def pkg_paths():
    """
    Paths created by package installs
    """
    paths = [
        "/etc/salt",
        "/var/cache/salt",
        "/var/log/salt",
        "/var/run/salt",
        "/opt/saltstack/salt",
    ]
    return paths


@pytest.fixture
def pkg_paths_salt_user():
    """
    Paths created by package installs and owned by salt user
    """
    return [
        "/etc/salt/cloud.deploy.d",
        "/var/log/salt/cloud",
        "/opt/saltstack/salt/lib/python{}.{}/site-packages/salt/cloud/deploy".format(
            *sys.version_info
        ),
        "/etc/salt/pki/master",
        "/etc/salt/master.d",
        "/var/log/salt/master",
        "/var/log/salt/api",
        "/var/log/salt/key",
        "/var/cache/salt/master",
        "/var/run/salt/master",
    ]


@pytest.fixture
def pkg_paths_salt_user_exclusions():
    """
    Exclusions from paths created by package installs and owned by salt user
    """
    paths = [
        "/var/cache/salt/master/.root_key"  # written by salt, salt-run and salt-key as root
    ]
    return paths


@pytest.fixture(autouse=True)
def _skip_on_non_relenv(install_salt):
    if not install_salt.relenv:
        pytest.skip("The salt user only exists on relenv versions of salt")


def test_salt_user_master(salt_master, install_salt):
    """
    Test the correct user is running the Salt Master
    """
    assert salt_master.is_running()

    match = False
    for proc in psutil.Process(salt_master.pid).children():
        assert proc.username() == "salt"
        match = True

    assert match


def test_salt_user_home(install_salt, salt_master):
    """
    Test the salt user's home is /opt/saltstack/salt
    """
    assert salt_master.is_running()

    proc = subprocess.run(
        ["getent", "passwd", "salt"], check=False, capture_output=True
    )
    assert proc.returncode == 0
    home = ""
    try:
        home = proc.stdout.decode().split(":")[5]
    except Exception:  # pylint: disable=broad-except
        pass
    assert home == "/opt/saltstack/salt"


def test_salt_user_group(install_salt, salt_master):
    """
    Test the salt user is in the salt group
    """
    assert salt_master.is_running()

    proc = subprocess.run(["id", "salt"], check=False, capture_output=True)
    assert proc.returncode == 0
    in_group = False
    try:
        for group in proc.stdout.decode().split(" "):
            if "salt" in group:
                in_group = True
    except Exception:  # pylint: disable=broad-except
        pass
    assert in_group is True


def test_salt_user_shell(install_salt, salt_master):
    """
    Test the salt user's login shell
    """
    assert salt_master.is_running()

    proc = subprocess.run(
        ["getent", "passwd", "salt"], check=False, capture_output=True
    )
    assert proc.returncode == 0
    shell = ""
    shell_exists = False
    try:
        shell = proc.stdout.decode().split(":")[6].strip()
        shell_exists = pathlib.Path(shell).exists()
    except Exception:  # pylint: disable=broad-except
        pass
    assert shell_exists is True


def test_pkg_paths(
    install_salt,
    pkg_paths,
    pkg_paths_salt_user,
    pkg_paths_salt_user_exclusions,
):
    """
    Test package paths ownership
    """
    if packaging.version.parse(install_salt.version) <= packaging.version.parse(
        "3006.4"
    ):
        pytest.skip("Package path ownership was changed in salt 3006.4")

    salt_user_subdirs = []

    for _path in pkg_paths:
        pkg_path = pathlib.Path(_path)
        assert pkg_path.exists()
        for dirpath, sub_dirs, files in os.walk(pkg_path):
            path = pathlib.Path(dirpath)
            # Directories owned by salt:salt or their subdirs/files
            if (
                str(path) in pkg_paths_salt_user or str(path) in salt_user_subdirs
            ) and str(path) not in pkg_paths_salt_user_exclusions:
                assert path.owner() == "salt"
                assert path.group() == "salt"
                salt_user_subdirs.extend(
                    [str(path.joinpath(sub_dir)) for sub_dir in sub_dirs]
                )
                # Individual files owned by salt user
                for file in files:
                    file_path = path.joinpath(file)
                    if str(file_path) not in pkg_paths_salt_user_exclusions:
                        assert file_path.owner() == "salt"
            # Directories owned by root:root
            else:
                assert path.owner() == "root"
                assert path.group() == "root"
                for file in files:
                    if file.endswith("ipc"):
                        continue
                    file_path = path.joinpath(file)
                    # Individual files owned by salt user
                    if str(file_path) in pkg_paths_salt_user:
                        assert file_path.owner() == "salt"
                    else:
                        assert file_path.owner() == "root"
                        assert file_path.group() == "root"


@pytest.mark.skip_if_binaries_missing("logrotate")
def test_paths_log_rotation(
    salt_master,
    salt_minion,
    salt_call_cli,
    install_salt,
    pkg_tests_account,
):
    """
    Test the correct ownership is assigned when log rotation occurs
    Change the user in the Salt Master, chage ownership, force logrotation
    Check ownership and premissions.
    Assumes test_pkg_paths successful
    """
    if packaging.version.parse(install_salt.version) <= packaging.version.parse(
        "3006.4"
    ):
        pytest.skip("Package path ownership was changed in salt 3006.4")

    if install_salt.distro_id not in (
        "almalinux",
        "rocky",
        "centos",
        "redhat",
        "amzn",
        "fedora",
    ):
        pytest.skip(
            "Only tests RedHat family packages till logrotation paths are resolved on Ubuntu/Debian, see issue 65231"
        )

    match = False
    for proc in psutil.Process(salt_master.pid).children():
        assert proc.username() == "salt"
        match = True

    assert match

    # Paths created by package installs with adjustment for current conf_dir /etc/salt
    log_pkg_paths = [
        install_salt.conf_dir,  # "bkup0"
        "/var/cache/salt",  # "bkup1"
        "/var/log/salt",  # "bkup2"
        "/var/run/salt",  # "bkup3"
        "/opt/saltstack/salt",  # "bkup4"
    ]

    # backup those about to change
    bkup_count = 0
    bkup_count_max = 5
    with temp_directory("bkup0") as temp_dir_path_0:
        with temp_directory("bkup1") as temp_dir_path_1:
            with temp_directory("bkup2") as temp_dir_path_2:
                with temp_directory("bkup3") as temp_dir_path_3:
                    with temp_directory("bkup4") as temp_dir_path_4:

                        assert temp_dir_path_0.is_dir()
                        assert temp_dir_path_1.is_dir()
                        assert temp_dir_path_2.is_dir()
                        assert temp_dir_path_3.is_dir()
                        assert temp_dir_path_4.is_dir()

                        # stop the salt_master, so can change user
                        with salt_master.stopped():
                            assert salt_master.is_running() is False

                            for _path in log_pkg_paths:
                                if bkup_count == 0:
                                    cmd_to_run = (
                                        f"cp -a {_path}/* {str(temp_dir_path_0)}/"
                                    )
                                elif bkup_count == 1:
                                    cmd_to_run = (
                                        f"cp -a {_path}/* {str(temp_dir_path_1)}/"
                                    )
                                elif bkup_count == 2:
                                    cmd_to_run = (
                                        f"cp -a {_path}/* {str(temp_dir_path_2)}/"
                                    )
                                elif bkup_count == 3:
                                    cmd_to_run = (
                                        f"cp -a {_path}/* {str(temp_dir_path_3)}/"
                                    )
                                elif bkup_count == 4:
                                    cmd_to_run = (
                                        f"cp -a {_path}/* {str(temp_dir_path_4)}/"
                                    )
                                elif bkup_count > 5:
                                    # force assertion
                                    assert bkup_count < bkup_count_max

                                ret = salt_call_cli.run(
                                    "--local", "cmd.run", cmd_to_run
                                )
                                bkup_count += 1
                                assert ret.returncode == 0

                            # change the user in the master's config file.
                            ret = salt_call_cli.run(
                                "--local",
                                "file.replace",
                                f"{install_salt.conf_dir}/master",
                                "user: salt",
                                f"user: {pkg_tests_account.username}",
                                "flags=['IGNORECASE']",
                                "append_if_not_found=True",
                            )
                            assert ret.returncode == 0

                            # change ownership of appropriate paths to user
                            for _path in log_pkg_paths:
                                chg_ownership_cmd = (
                                    f"chown -R {pkg_tests_account.username} {_path}"
                                )
                                ret = salt_call_cli.run(
                                    "--local", "cmd.run", chg_ownership_cmd
                                )
                                assert ret.returncode == 0

                            # restart the salt_master
                            with salt_master.started():
                                assert salt_master.is_running() is True

                                # ensure some data in files
                                log_files_list = [
                                    "/var/log/salt/api",
                                    "/var/log/salt/key",
                                    "/var/log/salt/master",
                                ]
                                for _path in log_files_list:
                                    log_path = pathlib.Path(_path)
                                    assert log_path.exists()
                                    with log_path.open("a", encoding="utf-8") as f:
                                        f.write("This is a log rotation test\n")

                                # force log rotation
                                logr_conf_file = "/etc/logrotate.d/salt"
                                logr_conf_path = pathlib.Path(logr_conf_file)
                                if not logr_conf_path.exists():
                                    logr_conf_file = "/etc/logrotate.conf"
                                    logr_conf_path = pathlib.Path(logr_conf_file)
                                    assert logr_conf_path.exists()

                                # force log rotation
                                log_rotate_cmd = f"logrotate -f  {logr_conf_file}"
                                ret = salt_call_cli.run(
                                    "--local", "cmd.run", log_rotate_cmd
                                )
                                assert ret.returncode == 0

                                for _path in log_files_list:
                                    log_path = pathlib.Path(_path)
                                    assert log_path.exists()
                                    assert (
                                        log_path.owner() == pkg_tests_account.username
                                    )
                                    assert log_path.stat().st_mode & 0o7777 == 0o640

                            # cleanup
                            assert salt_master.is_running() is False

                            # change the user in the master's config file.
                            ret = salt_call_cli.run(
                                "--local",
                                "file.replace",
                                f"{install_salt.conf_dir}/master",
                                f"user: {pkg_tests_account.username}",
                                "user: salt",
                                "flags=['IGNORECASE']",
                                "append_if_not_found=True",
                            )
                            assert ret.returncode == 0

                            # restore from backed up
                            bkup_count = 0
                            for _path in log_pkg_paths:
                                if bkup_count == 0:
                                    cmd_to_run = f"cp -a --force {str(temp_dir_path_0)}/* {_path}/"
                                elif bkup_count == 1:
                                    cmd_to_run = f"cp -a --force {str(temp_dir_path_1)}/* {_path}/"
                                elif bkup_count == 2:
                                    cmd_to_run = f"cp -a --force {str(temp_dir_path_2)}/* {_path}/"
                                elif bkup_count == 3:
                                    cmd_to_run = f"cp -a --force {str(temp_dir_path_3)}/* {_path}/"
                                elif bkup_count == 4:
                                    # use --update since /opt/saltstack/salt and would get SIGSEGV since mucking with running code
                                    cmd_to_run = f"cp -a --update --force {str(temp_dir_path_4)}/* {_path}/"
                                elif bkup_count > 5:
                                    # force assertion
                                    assert bkup_count < bkup_count_max

                                ret = salt_call_cli.run(
                                    "--local", "cmd.run", cmd_to_run
                                )

                                bkup_count += 1
                                assert ret.returncode == 0
