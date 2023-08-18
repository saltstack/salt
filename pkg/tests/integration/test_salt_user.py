import os
import pathlib
import subprocess
import sys

import packaging.version
import psutil
import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
    pytest.mark.skip_on_darwin,
]


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
def skip_on_non_relenv(install_salt):
    if not install_salt.relenv:
        pytest.skip("The salt user only exists on relenv versions of salt")


def test_salt_user_master(salt_master, install_salt):
    """
    Test the correct user is running the Salt Master
    """
    match = False
    for proc in psutil.Process(salt_master.pid).children():
        assert proc.username() == "salt"
        match = True

    assert match


def test_salt_user_home(install_salt):
    """
    Test the salt user's home is /opt/saltstack/salt
    """
    proc = subprocess.run(
        ["getent", "passwd", "salt"], check=False, capture_output=True
    )
    assert proc.returncode == 0
    home = ""
    try:
        home = proc.stdout.decode().split(":")[5]
    except:
        pass
    assert home == "/opt/saltstack/salt"


def test_salt_user_group(install_salt):
    """
    Test the salt user is in the salt group
    """
    proc = subprocess.run(["id", "salt"], check=False, capture_output=True)
    assert proc.returncode == 0
    in_group = False
    try:
        for group in proc.stdout.decode().split(" "):
            if "salt" in group:
                in_group = True
    except:
        pass
    assert in_group is True


def test_salt_user_shell(install_salt):
    """
    Test the salt user's login shell
    """
    proc = subprocess.run(
        ["getent", "passwd", "salt"], check=False, capture_output=True
    )
    assert proc.returncode == 0
    shell = ""
    shell_exists = False
    try:
        shell = proc.stdout.decode().split(":")[6].strip()
        shell_exists = pathlib.Path(shell).exists()
    except:
        pass
    assert shell_exists is True


def test_pkg_paths(
    install_salt, pkg_paths, pkg_paths_salt_user, pkg_paths_salt_user_exclusions
):
    """
    Test package paths ownership
    """
    if packaging.version.parse(install_salt.version) <= packaging.version.parse(
        "3006.2"
    ):
        pytest.skip("Package path ownership was changed in salt 3006.3")
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
                    file_path = path.joinpath(file)
                    # Individual files owned by salt user
                    if str(file_path) in pkg_paths_salt_user:
                        assert file_path.owner() == "salt"
                    else:
                        assert file_path.owner() == "root"
                        assert file_path.group() == "root"
