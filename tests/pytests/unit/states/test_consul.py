"""
Test case for the consul state module
"""

import logging

import pytest

import salt.states.consul as consul
from tests.support.mock import MagicMock, patch

log = logging.getLogger(__name__)


@pytest.fixture
def configure_loader_modules():
    return {
        consul: {
            "__opts__": {
                "consul": {"url": "http://127.0.0.1", "token": "test_token"},
                "test": False,
            },
            "__grains__": {"id": "test-minion"},
        }
    }


def test_acl_present():
    """
    Test salt.states.consul.acl_present function
    """
    acl_info = {
        "data": [
            {
                "ID": "1d53dcd6-8f4f-431e-818a-9987996701a1",
                "Name": "89530557-8f18-4e29-a2d6-5b2fc8bca713",
                "Type": "client",
                "Rules": "",
                "CreateIndex": 419,
                "ModifyIndex": 420,
            }
        ],
        "res": True,
    }

    acl_info_mock = MagicMock(return_value=acl_info)
    with patch.dict(consul.__salt__, {"consul.acl_info": acl_info_mock}):
        with patch.object(consul, "_acl_changes", MagicMock(return_value=False)):
            consul_return = consul.acl_present(
                "my_acl",
                id="1d53dcd6-8f4f-431e-818a-9987996701a1",
                token="89530557-8f18-4e29-a2d6-5b2fc8bca713",
                type="client",
                consul_url="http://localhost:8500",
            )

            _expected = {
                "changes": {},
                "comment": 'ACL "my_acl" exists and is up to date',
                "name": "my_acl",
                "result": True,
            }
            assert consul_return == _expected

        acl_update_mock = MagicMock(
            return_value={
                "data": {"ID": "1D53DCD6-8F4F-431E-818A-9987996701A1"},
                "res": True,
            }
        )
        with patch.object(consul, "_acl_changes", MagicMock(return_value=True)):
            with patch.dict(consul.__salt__, {"consul.acl_update": acl_update_mock}):
                consul_return = consul.acl_present(
                    "my_acl",
                    id="1d53dcd6-8f4f-431e-818a-9987996701a1",
                    token="89530557-8f18-4e29-a2d6-5b2fc8bca713",
                    type="client",
                    consul_url="http://localhost:8500",
                )

            _expected = {
                "changes": {},
                "comment": "The acl has been updated",
                "name": "my_acl",
                "result": True,
            }
            assert consul_return == _expected


def test_acl_absent():
    """
    Test salt.states.consul.acl_absent function
    """
    #
    # Test when the ACL does exist
    #
    acl_info = {
        "data": [
            {
                "ID": "1d53dcd6-8f4f-431e-818a-9987996701a1",
                "Name": "89530557-8f18-4e29-a2d6-5b2fc8bca713",
                "Type": "client",
                "Rules": "",
                "CreateIndex": 419,
                "ModifyIndex": 420,
            }
        ],
        "res": True,
    }
    acl_info_mock = MagicMock(return_value=acl_info)
    acl_delete_mock = MagicMock(
        return_value={
            "res": True,
            "message": "ACL 38AC8470-4A83-4140-8DFD-F924CD32917F deleted.",
        }
    )
    with patch.dict(consul.__salt__, {"consul.acl_info": acl_info_mock}):
        with patch.dict(consul.__salt__, {"consul.acl_delete": acl_delete_mock}):
            consul_return = consul.acl_absent(
                "my_acl",
                id="1d53dcd6-8f4f-431e-818a-9987996701a1",
                token="89530557-8f18-4e29-a2d6-5b2fc8bca713",
                consul_url="http://localhost:8500",
            )

            _expected = {
                "changes": {},
                "comment": "The acl has been deleted",
                "name": "1d53dcd6-8f4f-431e-818a-9987996701a1",
                "result": True,
            }
            assert consul_return == _expected

    #
    # Test when the ACL does not exist
    #
    acl_info = {"data": [], "res": True}
    acl_info_mock = MagicMock(return_value=acl_info)
    acl_delete_mock = MagicMock(
        return_value={
            "res": True,
            "message": "ACL 38AC8470-4A83-4140-8DFD-F924CD32917F deleted.",
        }
    )
    with patch.dict(consul.__salt__, {"consul.acl_info": acl_info_mock}):
        with patch.dict(consul.__salt__, {"consul.acl_delete": acl_delete_mock}):
            consul_return = consul.acl_absent(
                "my_acl",
                id="1d53dcd6-8f4f-431e-818a-9987996701a1",
                token="89530557-8f18-4e29-a2d6-5b2fc8bca713",
                consul_url="http://localhost:8500",
            )

            _expected = {
                "changes": {},
                "comment": 'ACL "1d53dcd6-8f4f-431e-818a-9987996701a1" does not exist',
                "name": "1d53dcd6-8f4f-431e-818a-9987996701a1",
                "result": True,
            }
            assert consul_return == _expected
