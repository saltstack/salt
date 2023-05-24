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


def test_salt_cloud_dirs(install_salt):
    """
    Test salt-cloud directories are owned by salt:salt
    """
    paths = [
        "/opt/saltstack/salt/lib/python{}.{}/site-packages/salt/cloud/deploy".format(
            *sys.version_info
        ),
        "/etc/salt/cloud.deploy.d",
    ]
    for name in paths:
        path = pathlib.Path(name)
        assert path.exists()
        assert path.owner() == "salt"
        assert path.group() == "salt"
