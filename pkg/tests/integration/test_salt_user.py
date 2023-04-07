import psutil
import pytest

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_user_master(salt_master):
    """
    Test the correct user is running the Salt Master
    """
    user = "salt"
    match = False
    for _proc in psutil.process_iter(["username", "cmdline", "name"]):
        if any([x for x in _proc.info["cmdline"] if "salt-master" in x]):
            assert _proc.info["username"] == user
            match = True
    assert match
