"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
"""

import pytest

import salt.states.apache_module as apache_module
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {apache_module: {}}


def test_enabled():
    """
    Test to ensure an Apache module is enabled.
    """
    name = "cgi"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False, False])
    mock_str = MagicMock(return_value={"Status": ["enabled"]})
    with patch.dict(
        apache_module.__salt__,
        {"apache.check_mod_enabled": mock, "apache.a2enmod": mock_str},
    ):
        comt = "{} already enabled.".format(name)
        ret.update({"comment": comt})
        assert apache_module.enabled(name) == ret

        comt = "Apache module {} is set to be enabled.".format(name)
        ret.update(
            {"comment": comt, "result": None, "changes": {"new": "cgi", "old": None}}
        )
        with patch.dict(apache_module.__opts__, {"test": True}):
            assert apache_module.enabled(name) == ret

        comt = "Failed to enable {} Apache module".format(name)
        ret.update({"comment": comt, "result": False, "changes": {}})
        with patch.dict(apache_module.__opts__, {"test": False}):
            assert apache_module.enabled(name) == ret


def test_disabled():
    """
    Test to ensure an Apache module is disabled.
    """
    name = "cgi"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, True, False])
    mock_str = MagicMock(return_value={"Status": ["disabled"]})
    with patch.dict(
        apache_module.__salt__,
        {"apache.check_mod_enabled": mock, "apache.a2dismod": mock_str},
    ):
        comt = "Apache module {} is set to be disabled.".format(name)
        ret.update({"comment": comt, "changes": {"new": None, "old": "cgi"}})
        with patch.dict(apache_module.__opts__, {"test": True}):
            assert apache_module.disabled(name) == ret

        comt = "Failed to disable {} Apache module".format(name)
        ret.update({"comment": comt, "result": False, "changes": {}})
        with patch.dict(apache_module.__opts__, {"test": False}):
            assert apache_module.disabled(name) == ret

        comt = "{} already disabled.".format(name)
        ret.update({"comment": comt, "result": True})
        assert apache_module.disabled(name) == ret
