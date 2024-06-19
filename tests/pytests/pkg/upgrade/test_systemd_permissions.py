import time

import pytest

pytestmark = [
    pytest.mark.skip_unless_on_linux(reason="Only supported on Linux family"),
    pytest.mark.skipif(
        True,
        reason=(
            "Package permissions are getting reworked in "
            "https://github.com/saltstack/salt/pull/66218"
        ),
    ),
]


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


def test_salt_systemd_disabled_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve disabled state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl disable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for disabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "disabled"


def test_salt_systemd_enabled_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve enabled state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for enabled systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl show -p UnitFileState {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "enabled"


def test_salt_systemd_inactive_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve inactive state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # ensure known state, disabled
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl stop {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for inactive systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl is-active {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_active = ret.stdout.strip().split()[2].strip('"').strip()
        assert ret.returncode == 1
        assert test_active == "inactive"


def test_salt_systemd_active_preservation(
    salt_call_cli, install_salt, salt_systemd_setup
):
    """
    Test upgrade of Salt packages preserve active state of systemd
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test for active systemd state
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl is-active {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_active = ret.stdout.strip().split()[2].strip('"').strip()
        assert ret.returncode == 0
        assert test_active == "active"


def test_salt_ownership_permission(salt_call_cli, install_salt, salt_systemd_setup):
    """
    Test upgrade of Salt packages preserve existing ownership
    """
    if not install_salt.upgrade:
        pytest.skip("Not testing an upgrade, do not run")

    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    # test ownership for Minion, Master and Api
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == "salt"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == "salt"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == "root"
            else:
                assert test_user == "salt"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == "root"
            else:
                assert test_group == "salt"

    # create master user, and minion user, change conf, restart and test ownership
    test_master_user = "horse"
    test_minion_user = "donkey"
    ret = salt_call_cli.run("--local", "user.list_users")
    user_list = ret.stdout.strip().split(":")[1]

    if test_master_user not in user_list:
        ret = salt_call_cli.run("--local", "user.add", f"{test_master_user}")

    if test_minion_user not in user_list:
        ret = salt_call_cli.run("--local", "user.add", f"{test_minion_user}")

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/master", "^user:"
    )
    assert ret.returncode == 0

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/minion", "^user:"
    )
    assert ret.returncode == 0

    test_string = f"\nuser: {test_master_user}\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = f"\nuser: {test_minion_user}\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart

    # test ownership for Minion, Master and Api - horse and donkey
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == f"{test_master_user}"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == f"{test_master_user}"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == f"{test_minion_user}"
            else:
                assert test_user == f"{test_master_user}"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == f"{test_minion_user}"
            else:
                assert test_group == f"{test_master_user}"

    # Upgrade Salt (inc. minion, master, etc.) from previous version and test
    # pylint: disable=pointless-statement
    install_salt.install(upgrade=True)
    time.sleep(60)  # give it some time

    # test ownership for Minion, Master and Api
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        if "salt-api" == test_item:
            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            assert test_user == f"{test_master_user}"

            test_cmd = f"ls -dl /run/{test_item}.pid"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            assert test_group == f"{test_master_user}"
        else:
            test_name = test_item.strip().split("-")[1]
            test_cmd = f"ls -dl /run/salt/{test_name}"
            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_user = ret.stdout.strip().split()[4]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_user == f"{test_minion_user}"
            else:
                assert test_user == f"{test_master_user}"

            ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
            test_group = ret.stdout.strip().split()[5]
            assert ret.returncode == 0
            if test_item == "salt-minion":
                assert test_group == f"{test_minion_user}"
            else:
                assert test_group == f"{test_master_user}"

    # restore to defaults to ensure further tests run fine
    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/master", "^user:"
    )
    assert ret.returncode == 0

    ret = salt_call_cli.run(
        "--local", "file.comment_line", "/etc/salt/minion", "^user:"
    )
    assert ret.returncode == 0

    test_string = "\nuser: salt\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/master", test_string)

    test_string = "\nuser: root\n"
    ret = salt_call_cli.run("--local", "file.append", "/etc/salt/minion", test_string)

    # restart and check ownership is correct
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)

    time.sleep(10)  # allow some time for restart
