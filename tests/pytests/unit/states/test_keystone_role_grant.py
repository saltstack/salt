"""
Test cases for salt.states.keystone_role_grant
"""

import pytest

import salt.states.keystone_role_grant as keystone_role_grant
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {keystone_role_grant: {}}


def _base_salt_dunder(**overrides):
    role = MagicMock()
    role.id = "role-id"
    salt_dunder = {
        "keystoneng.setup_clouds": MagicMock(),
        "keystoneng.role_get": MagicMock(return_value=role),
        "keystoneng.role_grant": MagicMock(),
        "keystoneng.role_revoke": MagicMock(),
    }
    salt_dunder.update(overrides)
    return salt_dunder


def test_present_test_mode_does_not_grant():
    """
    In test=True mode present() must not call role_grant and must
    report result=None with predicted changes.
    """
    salt_dunder = _base_salt_dunder()
    salt_dunder["keystoneng.role_assignment_list"] = MagicMock(return_value=[])

    with patch.dict(keystone_role_grant.__salt__, salt_dunder), patch.dict(
        keystone_role_grant.__opts__, {"test": True}
    ):
        ret = keystone_role_grant.present("myrole")

    assert salt_dunder["keystoneng.role_grant"].call_count == 0
    assert ret["result"] is None
    assert ret["changes"] == {"role": "role-id"}
    assert ret["comment"] == "Role assignment would be granted"


def test_absent_test_mode_does_not_revoke():
    """
    In test=True mode absent() must not call role_revoke and must
    report result=None with predicted changes.
    """
    salt_dunder = _base_salt_dunder()
    salt_dunder["keystoneng.role_assignment_list"] = MagicMock(
        return_value=["existing-grant"]
    )

    with patch.dict(keystone_role_grant.__salt__, salt_dunder), patch.dict(
        keystone_role_grant.__opts__, {"test": True}
    ):
        ret = keystone_role_grant.absent("myrole")

    assert salt_dunder["keystoneng.role_revoke"].call_count == 0
    assert ret["result"] is None
    assert ret["changes"] == {"role": "role-id"}
    assert ret["comment"] == "Role assignment would be revoked"
