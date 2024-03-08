import re

import pytest
import saltfactories.utils

import salt.defaults.exitcodes
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
import salt.utils.yaml

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_if_not_root,
]


@pytest.fixture
def salt_run_cli(salt_master):
    """
    Override salt_run_cli fixture to provide an increased default_timeout to the calls
    """
    return salt_master.salt_run_cli(timeout=120)


@pytest.fixture
def user_and_password(salt_call_cli):
    user_name = saltfactories.utils.random_string("salt-test-", lowercase=False)
    user_pwd = saltfactories.utils.random_string("salt-test-", lowercase=False)
    try:
        salt_call_cli.run("user.add", user_name)
        salt_call_cli.run("shadow.set_password", user_name, user_pwd)
        yield (user_name, user_pwd)
    finally:
        salt_call_cli.run("user.delete", user_name, True, True)


@pytest.fixture
def username(user_and_password):
    return user_and_password[0]


@pytest.fixture
def userpwd(user_and_password):
    return user_and_password[1]


def test_in_docs(salt_run_cli):
    """
    test the salt-run docs system
    """
    ret = salt_run_cli.run("-d")
    assert "jobs.active:" in ret.stdout
    assert "jobs.list_jobs:" in ret.stdout
    assert "jobs.lookup_jid:" in ret.stdout
    assert "manage.down:" in ret.stdout
    assert "manage.up:" in ret.stdout
    assert "network.wol:" in ret.stdout
    assert "network.wollist:" in ret.stdout


def test_not_in_docs(salt_run_cli):
    """
    test the salt-run docs system
    """
    ret = salt_run_cli.run("-d")
    assert "jobs.SaltException:" not in ret.stdout


def test_salt_documentation_too_many_arguments(salt_run_cli):
    """
    Test to see if passing additional arguments shows an error
    """
    ret = salt_run_cli.run("-d", "virt.list", "foo")
    assert ret.returncode != 0
    assert "You can only get documentation for one method at one time" in ret.stderr


def test_exit_status_unknown_argument(salt_run_cli):
    """
    Ensure correct exit status when an unknown argument is passed to salt-run.
    """
    ret = salt_run_cli.run("--unknown-argument")
    assert ret.returncode == salt.defaults.exitcodes.EX_USAGE, ret
    assert "Usage" in ret.stderr
    assert "no such option: --unknown-argument" in ret.stderr


def test_exit_status_correct_usage(salt_run_cli):
    """
    Ensure correct exit status when salt-run starts correctly.
    """
    ret = salt_run_cli.run("test.arg", "arg1", kwarg1="kwarg1")
    assert ret.returncode == salt.defaults.exitcodes.EX_OK, ret


@pytest.mark.skip_if_not_root
@pytest.mark.parametrize("flag", ["--auth", "--eauth", "--external-auth", "-a"])
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_salt_run_with_eauth_all_args(salt_run_cli, salt_eauth_account, flag):
    """
    test salt-run with eauth
    tests all eauth args
    """
    ret = salt_run_cli.run(
        flag,
        "pam",
        "--username",
        salt_eauth_account.username,
        "--password",
        salt_eauth_account.password,
        "test.arg",
        "arg",
        kwarg="kwarg1",
        _timeout=240,
    )
    assert ret.returncode == 0, ret
    assert ret.data, ret
    expected = {"args": ["arg"], "kwargs": {"kwarg": "kwarg1"}}
    assert ret.data == expected, ret


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_salt_run_with_eauth_bad_passwd(salt_run_cli, salt_eauth_account):
    """
    test salt-run with eauth and bad password
    """
    ret = salt_run_cli.run(
        "-a",
        "pam",
        "--username",
        salt_eauth_account.username,
        "--password",
        "wrongpassword",
        "test.arg",
        "arg",
        kwarg="kwarg1",
    )
    assert (
        ret.stdout
        == 'Authentication failure of type "eauth" occurred for user {}.'.format(
            salt_eauth_account.username
        )
    )


@pytest.mark.skip_if_not_root
def test_salt_run_with_wrong_eauth(salt_run_cli, salt_eauth_account):
    """
    test salt-run with wrong eauth parameter
    """
    ret = salt_run_cli.run(
        "-a",
        "wrongeauth",
        "--username",
        salt_eauth_account.username,
        "--password",
        salt_eauth_account.password,
        "test.arg",
        "arg",
        kwarg="kwarg1",
    )
    assert ret.returncode == 0, ret
    assert re.search(
        r"^The specified external authentication system \"wrongeauth\" is not"
        r" available\nAvailable eauth types: auto, .*",
        ret.stdout.replace("\r\n", "\n"),
    )


def test_salt_run_timeout_success(salt_run_cli):
    """
    test salt-run with defined timeout (waiting for job results)
    It should simply succeed, as the timeout is greater than the executed sleep period
    """
    run_cmd = salt_run_cli.run("--timeout=5", "salt.cmd", "test.sleep", "1")
    assert run_cmd.data is True


def test_salt_run_timeout_failure(salt_run_cli):
    """
    test salt-run with defined timeout (waiting for job results)
    It should result in a timeout, as the executed sleep period is greater than the timeout
    """
    run_cmd = salt_run_cli.run("--timeout=1", "salt.cmd", "test.sleep", "5")
    expect = r"^RunnerClient job '[0-9]+' timed out"
    assert re.compile(expect).search(run_cmd.stdout)


@pytest.mark.skip_if_not_root
def test_salt_run_timeout_success_with_eauth(salt_run_cli, username, userpass):
    """
    test salt-run with defined timeout (waiting for job results).
    It should succeed, as the timeout is greater than the executed sleep period.
    The codepath for handling timeouts is different for eauth enabled, that's why
    this is additionally tested.
    """
    run_cmd = salt_run_cli.run(
        "-a",
        "pam",
        "--username",
        username,
        "--password",
        userpass,
        "--timeout=5",
        "salt.cmd",
        "test.sleep",
        "3",
    )
    assert run_cmd.data is True


@pytest.mark.skip_if_not_root
def test_salt_run_timeout_failure_with_eauth(salt_run_cli, username, userpass):
    """
    test salt-run with defined timeout (waiting for job results)
    It should result in a timeout, as the executed sleep period is greater than the timeout.
    The codepath for handling timeouts is different for eauth enabled, that's why
    this is additionally tested.
    """
    run_cmd = salt_run_cli.run(
        "-a",
        "pam",
        "--username",
        username,
        "--password",
        userpass,
        "--timeout=1",
        "salt.cmd",
        "test.sleep",
        "5",
    )
    expect = r"^RunnerClient job '[0-9]+' timed out"
    assert re.compile(expect).match(run_cmd.stdout)
