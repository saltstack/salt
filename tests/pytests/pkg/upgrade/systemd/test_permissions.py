import logging
import time

import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
]

log = logging.getLogger(__name__)


def test_salt_ownership_permission(call_cli, install_salt_systemd, salt_systemd_setup):
    """
    Test upgrade of Salt packages preserve existing ownership
    """
    if not install_salt_systemd.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    test_list = ["salt-api", "salt-minion", "salt-master"]

    # ensure services are started
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    time.sleep(10)  # allow some time for restart

    # test ownership for Minion, Master and Api
    for test_item in test_list:
        test_cmd = f"ls -dl /run/{test_item}.pid"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_user = ret.stdout.strip().split()[4]
        test_group = ret.stdout.strip().split()[5]

        if test_item == "salt-minion":
            assert test_user == "root"
            assert test_group == "root"
        else:
            assert test_user == "salt"
            assert test_group == "salt"

    # create master user, and minion user, change conf, restart and test ownership
    test_master_user = "horse"
    test_minion_user = "donkey"
    ret = call_cli.run("--local", "user.list_users")
    user_list = ret.stdout.strip().split(":")[1]

    if test_master_user not in user_list:
        ret = call_cli.run("--local", "user.add", f"{test_master_user}", usergroup=True)

    if test_minion_user not in user_list:
        ret = call_cli.run("--local", "user.add", f"{test_minion_user}", usergroup=True)

    ret = call_cli.run("--local", "file.comment_line", "/etc/salt/master", "^user:")
    assert ret.returncode == 0

    ret = call_cli.run("--local", "file.comment_line", "/etc/salt/minion", "^user:")
    assert ret.returncode == 0

    test_string = f"\nuser: {test_master_user}\n"
    ret = call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = f"\nuser: {test_minion_user}\n"
    ret = call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart

    # test ownership for Minion, Master and Api - horse and donkey
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"ls -dl /run/{test_item}.pid"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_user = ret.stdout.strip().split()[4]
        test_group = ret.stdout.strip().split()[5]

        if test_item == "salt-minion":
            assert test_user == f"{test_minion_user}"
            assert test_group == f"{test_minion_user}"
        else:
            assert test_user == f"{test_master_user}"
            assert test_group == f"{test_master_user}"

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt_systemd.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test ownership for Minion, Master and Api
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"ls -dl /run/{test_item}.pid"
        ret = call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_user = ret.stdout.strip().split()[4]
        test_group = ret.stdout.strip().split()[5]

        if test_item == "salt-minion":
            assert test_user == f"{test_minion_user}"
            assert test_group == f"{test_minion_user}"
        else:
            assert test_user == f"{test_master_user}"
            assert test_group == f"{test_master_user}"

    # restore to defaults to ensure further tests run fine
    ret = call_cli.run("--local", "file.comment_line", "/etc/salt/master", "^user:")
    assert ret.returncode == 0

    ret = call_cli.run("--local", "file.comment_line", "/etc/salt/minion", "^user:")
    assert ret.returncode == 0

    test_string = "\nuser: salt\n"
    ret = call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = "\nuser: root\n"
    ret = call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart
