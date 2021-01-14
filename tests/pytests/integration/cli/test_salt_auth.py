"""
    tests.integration.shell.auth
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import logging

import pytest
import salt.utils.platform
import salt.utils.pycrypto

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.destructive_test,
    pytest.mark.skip_on_windows,
]

USERA = "saltdev-auth"
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


SALTOPS = "saltops"


@pytest.fixture(scope="module")
def saltops_group(sminion):
    try:
        assert sminion.functions.group.add(SALTOPS)
        # Run tests
        yield
    finally:
        sminion.functions.group.delete(SALTOPS)


USERB = "saltdev-adm"
USERB_PWD = USERA_PWD


@pytest.fixture(scope="module")
def saltadm_account(sminion, saltops_group):
    try:
        assert sminion.functions.user.add(USERB, groups=[SALTOPS], createhome=False)
        assert sminion.functions.shadow.set_password(
            USERB,
            USERB_PWD
            if salt.utils.platform.is_darwin()
            else salt.utils.pycrypto.gen_hash(password=USERB_PWD),
        )
        assert USERB in sminion.functions.user.list_users()
        # Run tests
        yield
    finally:
        sminion.functions.user.delete(USERB, remove=True)


def test_pam_auth_valid_user(salt_minion, salt_cli, saltdev_account):
    """
    test that pam auth mechanism works with a valid user
    """
    # test user auth against pam
    ret = salt_cli.run(
        "-a",
        "pam",
        "--username",
        USERA,
        "--password",
        USERA_PWD,
        "test.ping",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == 0
    assert ret.json is True


def test_pam_auth_invalid_user(salt_minion, salt_cli, saltdev_account):
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


def test_pam_auth_valid_group(salt_minion, salt_cli, saltadm_account):
    """
    test that pam auth mechanism works for a valid group
    """
    # test group auth against pam: saltadm is not configured in
    # external_auth, but saltops is and saldadm is a member of saltops
    ret = salt_cli.run(
        "-a",
        "pam",
        "--username",
        USERB,
        "--password",
        USERB_PWD,
        "test.ping",
        minion_tgt=salt_minion.id,
    )
    assert ret.exitcode == 0
    assert ret.json is True
