"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.chef as chef
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {chef: {}}


def test_client():
    """
    Test to run chef-client
    """
    name = "my-chef-run"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "error"})
    with patch.dict(chef.__salt__, {"chef.client": mock}):
        with patch.dict(chef.__opts__, {"test": True}):
            comt = "\nerror"
            ret.update({"comment": comt})
            assert chef.client(name) == ret


def test_solo():
    """
    Test to run chef-solo
    """
    name = "my-chef-run"

    ret = {"name": name, "result": False, "changes": {}, "comment": ""}

    mock = MagicMock(return_value={"retcode": 1, "stdout": "", "stderr": "error"})
    with patch.dict(chef.__salt__, {"chef.solo": mock}):
        with patch.dict(chef.__opts__, {"test": True}):
            comt = "\nerror"
            ret.update({"comment": comt})
            assert chef.solo(name) == ret
