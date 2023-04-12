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
