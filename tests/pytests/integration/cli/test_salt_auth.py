import logging

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.skip_on_windows,
]


@pytest.fixture(scope="module")
def salt_auth_account_1(salt_auth_account_1_factory):
    with salt_auth_account_1_factory as account:
        yield account


@pytest.fixture(scope="module")
def salt_auth_account_2(salt_auth_account_2_factory):
    with salt_auth_account_2_factory as account:
        yield account


def test_pam_auth_valid_user(salt_minion, salt_cli, salt_auth_account_1):
    """
    test that pam auth mechanism works with a valid user
    """
    # test user auth against pam
    ret = salt_cli.run(
        "-a",
        "pam",
        "--username",
        salt_auth_account_1.username,
        "--password",
        salt_auth_account_1.password,
        "test.ping",
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == 0
    assert ret.data is True


def test_pam_auth_invalid_user(salt_minion, salt_cli):
    """
    test pam auth mechanism errors for an invalid user
    """
    ret = salt_cli.run(
        "-a",
        "pam",
        "--username",
        "nouser",
        "--password",
        "1234",
        "test.ping",
        minion_tgt=salt_minion.id,
    )
    assert ret.stdout == "Authentication error occurred."


def test_pam_auth_valid_group(salt_minion, salt_cli, salt_auth_account_2):
    """
    test that pam auth mechanism works for a valid group
    """
    # test group auth against pam: saltadm is not configured in
    # external_auth, but saltops is and saldadm is a member of saltops
    ret = salt_cli.run(
        "-a",
        "pam",
        "--username",
        salt_auth_account_2.username,
        "--password",
        salt_auth_account_2.password,
        "test.ping",
        minion_tgt=salt_minion.id,
    )
    assert ret.returncode == 0
    assert ret.data is True
