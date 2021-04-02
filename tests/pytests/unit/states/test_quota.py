"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest
import salt.states.quota as quota
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {quota: {}}


def test_mode():
    """
    Test to set the quota for the system.
    """
    name = "/"
    mode = True
    quotatype = "user"

    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    mock_bool = MagicMock(side_effect=[True, False])
    mock = MagicMock(return_value={name: {quotatype: "on"}})
    with patch.dict(quota.__salt__, {"quota.get_mode": mock}):
        comt = "Quota for / already set to on"
        ret.update({"comment": comt, "result": True})
        assert quota.mode(name, mode, quotatype) == ret

    mock = MagicMock(return_value={name: {quotatype: "off"}})
    with patch.dict(quota.__salt__, {"quota.get_mode": mock, "quota.on": mock_bool}):
        with patch.dict(quota.__opts__, {"test": True}):
            comt = "Quota for / needs to be set to on"
            ret.update({"comment": comt, "result": None})
            assert quota.mode(name, mode, quotatype) == ret

        with patch.dict(quota.__opts__, {"test": False}):
            comt = "Set quota for / to on"
            ret.update({"comment": comt, "result": True, "changes": {"quota": name}})
            assert quota.mode(name, mode, quotatype) == ret

            comt = "Failed to set quota for / to on"
            ret.update({"comment": comt, "result": False, "changes": {}})
            assert quota.mode(name, mode, quotatype) == ret
