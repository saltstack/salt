"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.states.keystone
"""

import pytest

import salt.states.keystone as keystone
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {keystone: {}}


def test_user_present():
    """
    Test to ensure that the keystone user is present
    with the specified properties.
    """
    name = "nova"
    password = "$up3rn0v4"
    email = "nova@domain.com"
    tenant = "demo"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock_f = MagicMock(return_value=False)
    mock_lst = MagicMock(return_value=["Error"])
    with patch.dict(keystone.__salt__, {"keystone.tenant_get": mock_lst}):
        comt = f'Tenant / project "{tenant}" does not exist'
        ret.update({"comment": comt})
        assert keystone.user_present(name, password, email, tenant) == ret

    mock_dict = MagicMock(
        side_effect=[
            {name: {"email": "a@a.com"}},
            {name: {"email": email, "enabled": False}},
            {name: {"email": email, "enabled": True}},
            {name: {"email": email, "enabled": True}},
            {"Error": "error"},
            {"Error": "error"},
        ]
    )
    mock_l = MagicMock(return_value={tenant: {"id": "abc"}})
    with patch.dict(
        keystone.__salt__,
        {
            "keystone.user_get": mock_dict,
            "keystone.tenant_get": mock_l,
            "keystone.user_verify_password": mock_f,
            "keystone.user_create": mock_f,
        },
    ):
        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'User "{name}" will be updated'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {
                        "Email": "Will be updated",
                        "Enabled": "Will be True",
                        "Password": "Will be updated",
                    },
                }
            )
            assert keystone.user_present(name, password, email) == ret

            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {
                        "Enabled": "Will be True",
                        "Password": "Will be updated",
                    },
                }
            )
            assert keystone.user_present(name, password, email) == ret

            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {
                        "Tenant": 'Will be added to "demo" tenant',
                        "Password": "Will be updated",
                    },
                }
            )
            assert keystone.user_present(name, password, email, tenant) == ret

            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"Password": "Will be updated"},
                }
            )
            assert keystone.user_present(name, password, email) == ret

            comt = 'Keystone user "nova" will be added'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"User": "Will be created"},
                }
            )
            assert keystone.user_present(name, password, email) == ret

        with patch.dict(keystone.__opts__, {"test": False}):
            comt = f"Keystone user {name} has been added"
            ret.update(
                {"comment": comt, "result": True, "changes": {"User": "Created"}}
            )
            assert keystone.user_present(name, password, email) == ret


def test_user_absent():
    """
    Test to ensure that the keystone user is absent.
    """
    name = "nova"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'User "{name}" is already absent',
    }

    mock_lst = MagicMock(side_effect=[["Error"], []])
    with patch.dict(keystone.__salt__, {"keystone.user_get": mock_lst}):
        assert keystone.user_absent(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'User "{name}" will be deleted'
            ret.update({"comment": comt, "result": None})
            assert keystone.user_absent(name) == ret


def test_tenant_present():
    """
    Test to ensures that the keystone tenant exists
    """
    name = "nova"
    description = "OpenStack Compute Service"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Tenant / project "{name}" already exists',
    }

    mock_dict = MagicMock(
        side_effect=[
            {name: {"description": "desc"}},
            {name: {"description": description, "enabled": False}},
            {"Error": "error"},
            {"Error": "error"},
        ]
    )
    mock_t = MagicMock(return_value=True)
    with patch.dict(
        keystone.__salt__,
        {"keystone.tenant_get": mock_dict, "keystone.tenant_create": mock_t},
    ):
        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Tenant / project "{name}" will be updated'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"Description": "Will be updated"},
                }
            )
            assert keystone.tenant_present(name) == ret

            comt = f'Tenant / project "{name}" will be updated'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"Enabled": "Will be True"},
                }
            )
            assert keystone.tenant_present(name, description) == ret

            comt = f'Tenant / project "{name}" will be added'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"Tenant": "Will be created"},
                }
            )
            assert keystone.tenant_present(name) == ret

        with patch.dict(keystone.__opts__, {"test": False}):
            comt = f'Tenant / project "{name}" has been added'
            ret.update(
                {"comment": comt, "result": True, "changes": {"Tenant": "Created"}}
            )
            assert keystone.tenant_present(name) == ret


def test_tenant_absent():
    """
    Test to ensure that the keystone tenant is absent.
    """
    name = "nova"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Tenant / project "{name}" is already absent',
    }

    mock_lst = MagicMock(side_effect=[["Error"], []])
    with patch.dict(keystone.__salt__, {"keystone.tenant_get": mock_lst}):
        assert keystone.tenant_absent(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Tenant / project "{name}" will be deleted'
            ret.update({"comment": comt, "result": None})
            assert keystone.tenant_absent(name) == ret


def test_role_present():
    """
    Test to ensures that the keystone role exists
    """
    name = "nova"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Role "{name}" already exists',
    }

    mock_lst = MagicMock(side_effect=[[], ["Error"]])
    with patch.dict(keystone.__salt__, {"keystone.role_get": mock_lst}):
        assert keystone.role_present(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Role "{name}" will be added'
            ret.update({"comment": comt, "result": None})
            assert keystone.role_present(name) == ret


def test_role_absent():
    """
    Test to ensure that the keystone role is absent.
    """
    name = "nova"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Role "{name}" is already absent',
    }

    mock_lst = MagicMock(side_effect=[["Error"], []])
    with patch.dict(keystone.__salt__, {"keystone.role_get": mock_lst}):
        assert keystone.role_absent(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Role "{name}" will be deleted'
            ret.update({"comment": comt, "result": None})
            assert keystone.role_absent(name) == ret


def test_service_present():
    """
    Test to ensure service present in Keystone catalog
    """
    name = "nova"
    service_type = "compute"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Service "{name}" already exists',
    }

    mock_lst = MagicMock(side_effect=[[], ["Error"]])
    with patch.dict(keystone.__salt__, {"keystone.service_get": mock_lst}):
        assert keystone.service_present(name, service_type) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Service "{name}" will be added'
            ret.update({"comment": comt, "result": None})
            assert keystone.service_present(name, service_type) == ret


def test_service_absent():
    """
    Test to ensure that the service doesn't exist in Keystone catalog
    """
    name = "nova"

    ret = {
        "name": name,
        "changes": {},
        "result": True,
        "comment": f'Service "{name}" is already absent',
    }

    mock_lst = MagicMock(side_effect=[["Error"], []])
    with patch.dict(keystone.__salt__, {"keystone.service_get": mock_lst}):
        assert keystone.service_absent(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Service "{name}" will be deleted'
            ret.update({"comment": comt, "result": None})
            assert keystone.service_absent(name) == ret


def test_endpoint_present():
    """
    Test to ensure the specified endpoints exists for service
    """
    name = "nova"
    region = "RegionOne"

    ret = {"name": name, "changes": {}, "result": True, "comment": ""}

    endpoint = {
        "adminurl": None,
        "region": None,
        "internalurl": None,
        "publicurl": None,
        "id": 1,
        "service_id": None,
    }

    mock_lst = MagicMock(
        side_effect=[endpoint, ["Error"], {"id": 1, "service_id": None}, []]
    )
    mock = MagicMock(return_value=True)
    with patch.dict(
        keystone.__salt__,
        {"keystone.endpoint_get": mock_lst, "keystone.endpoint_create": mock},
    ):

        comt = f'Endpoint for service "{name}" already exists'
        ret.update({"comment": comt, "result": True, "changes": {}})
        assert keystone.endpoint_present(name) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Endpoint for service "{name}" will be added'
            ret.update(
                {
                    "comment": comt,
                    "result": None,
                    "changes": {"Endpoint": "Will be created"},
                }
            )
            assert keystone.endpoint_present(name) == ret

            comt = f'Endpoint for service "{name}" already exists'
            ret.update({"comment": comt, "result": True, "changes": {}})
            assert keystone.endpoint_present(name) == ret

        with patch.dict(keystone.__opts__, {"test": False}):
            comt = f'Endpoint for service "{name}" has been added'
            ret.update({"comment": comt, "result": True, "changes": True})
            assert keystone.endpoint_present(name) == ret


def test_endpoint_absent():
    """
    Test to ensure that the endpoint for a service doesn't
     exist in Keystone catalog
    """
    name = "nova"
    region = "RegionOne"
    comment = f'Endpoint for service "{name}" is already absent'
    ret = {"name": name, "changes": {}, "result": True, "comment": comment}

    mock_lst = MagicMock(side_effect=[[], ["Error"]])
    with patch.dict(keystone.__salt__, {"keystone.endpoint_get": mock_lst}):
        assert keystone.endpoint_absent(name, region) == ret

        with patch.dict(keystone.__opts__, {"test": True}):
            comt = f'Endpoint for service "{name}" will be deleted'
            ret.update({"comment": comt, "result": None})
            assert keystone.endpoint_absent(name, region) == ret
