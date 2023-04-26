import subprocess

import psutil
import pytest
import yaml
from pytestskipmarkers.utils import platform

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_user_master(salt_master, install_salt):
    """
    Test the correct user is running the Salt Master
    """
    if platform.is_windows() or platform.is_darwin():
        pytest.skip("Package does not have user set. Not testing user")
    match = False
    for proc in psutil.Process(salt_master.pid).children():
        assert proc.username() == "salt"
        match = True

    assert match


def test_salt_user_home(install_salt):
    """
    Test the correct user is running the Salt Master
    """
    proc = subprocess.run(["getent", "salt"], check=False, capture=True)
    assert proc.exitcode() == 0
    home = ""
    try:
        home = proc.stdout.decode().split(":")[5]
    except:
        pass
    assert home == "/opt/saltstack/salt"


def test_salt_user_group(install_salt):
    """
    Test the salt user is the salt group
    """
    proc = subprocess.run(["id", "salt"], check=False, capture=True)
    assert proc.exitcode() == 0
    in_group = False
    try:
        for group in proc.stdout.decode().split(" "):
            if group == "salt":
                in_group = True
    except:
        pass
    assert in_group is True
