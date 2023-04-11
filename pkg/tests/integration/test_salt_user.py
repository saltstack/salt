import psutil
import pytest
import yaml

pytestmark = [
    pytest.mark.skip_on_windows,
]


def test_salt_user_master(salt_master, install_salt):
    """
    Test the correct user is running the Salt Master
    """
    master_conf = install_salt.config_path / "master"
    with open(master_conf) as fp:
        data = yaml.safe_load(fp)
        if "user" not in data:
            pytest.skip("Package does not have user set. Not testing user")
    user = data["user"]
    match = False
    for proc in psutil.process_iter(["username", "cmdline", "name"]):
        if any([x for x in proc.info["cmdline"] if "salt-master" in x]):
            for child_proc in psutil.Process(proc.ppid()).children(recursive=True):
                if child_proc.is_running():
                    assert child_proc.username() == user
                    match = True
    assert match
