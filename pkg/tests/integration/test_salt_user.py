import os
import pathlib
import subprocess
import sys

import psutil
import pytest
import yaml
from pytestskipmarkers.utils import platform

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
    paths = [
        "/etc/salt/cloud.deploy.d",
        "/var/log/salt/cloud",
        "/opt/saltstack/salt/lib/python3.10/site-packages/salt/cloud/deploy",
        "/etc/salt/pki/master",
        "/etc/salt/master.d",
        "/etc/salt/minion.d",
        "/var/log/salt/master",
        "/var/log/salt/api",
        "/var/cache/salt/master",
        "/var/run/salt/master",
    ]
    return paths


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


def test_salt_cloud_dirs(install_salt):
    """
    Test the correct user is running the Salt Master
    """
    if platform.is_windows() or platform.is_darwin():
        pytest.skip("Package does not have user set. Not testing user")
    paths = [
        "/opt/saltstack/salt/lib/python3.10/site-packages/salt/cloud/deploy",
        "/etc/salt/cloud.deploy.d",
    ]
    for name in paths:
        path = pathlib.Path(name)
        assert path.exists()
        assert path.owner() == "salt"
        assert path.group() == "salt"


def test_pkg_paths(install_salt, pkg_paths, pkg_paths_salt_user):
    """
    Test package paths ownership
    """
    salt_user_subdirs = []
    for _path in pkg_paths:
        pkg_path = pathlib.Path(_path)
        assert pkg_path.exists()
        for dirpath, sub_dirs, files in os.walk(pkg_path):
            path = pathlib.Path(dirpath)
            # Directories owned by salt:salt or their subdirs/files
            if str(path) in pkg_paths_salt_user or str(path) in salt_user_subdirs:
                assert path.owner() == "salt"
                assert path.group() == "salt"
                salt_user_subdirs.extend(
                    [str(path.joinpath(sub_dir)) for sub_dir in sub_dirs]
                )
                for file in files:
                    file_path = path.joinpath(file)
                    assert file_path.owner() == "salt"
                    assert file_path.group() == "salt"
            # Directories owned by root:root
            else:
                assert path.owner() == "root"
                assert path.group() == "root"
                for file in files:
                    file_path = path.joinpath(file)
                    # Individual files owned by salt:salt
                    if str(file_path) in pkg_paths_salt_user:
                        assert file_path.owner() == "salt"
                        assert file_path.group() == "salt"
                    else:
                        assert file_path.owner() == "root"
                        assert file_path.group() == "root"
