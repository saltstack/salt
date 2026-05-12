import pytest

import salt.states.apache_site as apache_site
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {apache_site: {}}


def test_enabled():
    """
    Test to ensure an Apache site is enabled.
    """
    name = "saltstack.com"

    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, False, False])
    mock_str = MagicMock(return_value={"Status": ["enabled"]})
    with patch.dict(
        apache_site.__salt__,
        {"apache.check_site_enabled": mock, "apache.a2ensite": mock_str},
    ):
        comt = f"{name} already enabled."
        ret.update({"comment": comt})
        assert apache_site.enabled(name) == ret

        comt = f"Apache site {name} is set to be enabled."
        ret.update(
            {"comment": comt, "result": None, "changes": {"new": name, "old": None}}
        )
        with patch.dict(apache_site.__opts__, {"test": True}):
            assert apache_site.enabled(name) == ret

        comt = f"Failed to enable {name} Apache site"
        ret.update({"comment": comt, "result": False, "changes": {}})
        with patch.dict(apache_site.__opts__, {"test": False}):
            assert apache_site.enabled(name) == ret


def test_disabled():
    """
    Test to ensure an Apache site is disabled.
    """
    name = "saltstack.com"

    ret = {"name": name, "result": None, "changes": {}, "comment": ""}

    mock = MagicMock(side_effect=[True, True, False])
    mock_str = MagicMock(return_value={"Status": ["disabled"]})
    with patch.dict(
        apache_site.__salt__,
        {"apache.check_site_enabled": mock, "apache.a2dissite": mock_str},
    ):
        comt = f"Apache site {name} is set to be disabled."
        ret.update({"comment": comt, "changes": {"new": None, "old": name}})
        with patch.dict(apache_site.__opts__, {"test": True}):
            assert apache_site.disabled(name) == ret

        comt = f"Failed to disable {name} Apache site"
        ret.update({"comment": comt, "result": False, "changes": {}})
        with patch.dict(apache_site.__opts__, {"test": False}):
            assert apache_site.disabled(name) == ret

        comt = f"{name} already disabled."
        ret.update({"comment": comt, "result": True})
        assert apache_site.disabled(name) == ret
