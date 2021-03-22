"""
Tests for the salt-run command
"""


import re

import pytest
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
import salt.utils.yaml

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]

USERA = "saltdev-runner"
USERA_PWD = "saltdev"


@pytest.fixture(scope="module")
def saltdev_account(sminion):
    try:
        assert sminion.functions.user.add(USERA, createhome=False)
        assert sminion.functions.shadow.set_password(
            USERA,
            USERA_PWD
            if salt.utils.platform.is_darwin()
            else salt.utils.pycrypto.gen_hash(password=USERA_PWD),
        )
        assert USERA in sminion.functions.user.list_users()
        # Run tests
        yield
    finally:
        sminion.functions.user.delete(USERA, remove=True)


@pytest.fixture
def salt_run_cli(salt_master):
    """
    Override salt_run_cli fixture to provide an increased default_timeout to the calls
    """
    return salt_master.get_salt_run_cli(default_timeout=120)


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
    assert ret.exitcode != 0
    assert "You can only get documentation for one method at one time" in ret.stderr


def test_exit_status_unknown_argument(salt_run_cli):
    """
    Ensure correct exit status when an unknown argument is passed to salt-run.
    """
    ret = salt_run_cli.run("--unknown-argument")
    assert ret.exitcode == salt.defaults.exitcodes.EX_USAGE, ret
    assert "Usage" in ret.stderr
    assert "no such option: --unknown-argument" in ret.stderr


def test_exit_status_correct_usage(salt_run_cli):
    """
    Ensure correct exit status when salt-run starts correctly.
    """
    ret = salt_run_cli.run()
    assert ret.exitcode == salt.defaults.exitcodes.EX_OK, ret


@pytest.mark.skip_if_not_root
@pytest.mark.parametrize("flag", ["--auth", "--eauth", "--external-auth", "-a"])
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_salt_run_with_eauth_all_args(salt_run_cli, saltdev_account, flag):
    """
    test salt-run with eauth
    tests all eauth args
    """
    ret = salt_run_cli.run(
        flag,
        "pam",
        "--username",
        USERA,
        "--password",
        USERA_PWD,
        "test.arg",
        "arg",
        kwarg="kwarg1",
        _timeout=240,
    )
    assert ret.exitcode == 0, ret
    assert ret.json, ret
    expected = {"args": ["arg"], "kwargs": {"kwarg": "kwarg1"}}
    assert ret.json == expected, ret


@pytest.mark.skip_if_not_root
@pytest.mark.skip_on_windows(reason="PAM is not supported on Windows")
def test_salt_run_with_eauth_bad_passwd(salt_run_cli, saltdev_account):
    """
    test salt-run with eauth and bad password
    """
    ret = salt_run_cli.run(
        "-a",
        "pam",
        "--username",
        USERA,
        "--password",
        "wrongpassword",
        "test.arg",
        "arg",
        kwarg="kwarg1",
    )
    assert (
        ret.stdout
        == 'Authentication failure of type "eauth" occurred for user {}.'.format(USERA)
    )


def test_salt_run_with_wrong_eauth(salt_run_cli):
    """
    test salt-run with wrong eauth parameter
    """
    ret = salt_run_cli.run(
        "-a",
        "wrongeauth",
        "--username",
        USERA,
        "--password",
        USERA_PWD,
        "test.arg",
        "arg",
        kwarg="kwarg1",
    )
    assert ret.exitcode == 0, ret
    assert re.search(
        r"^The specified external authentication system \"wrongeauth\" is not available\nAvailable eauth types: auto, .*",
        ret.stdout.replace("\r\n", "\n"),
    )
