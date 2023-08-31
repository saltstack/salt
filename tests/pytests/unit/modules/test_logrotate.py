"""
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>

    Test cases for salt.modules.logrotate
"""


import pytest

import salt.modules.logrotate as logrotate
from salt.exceptions import SaltInvocationError
from tests.support.mock import MagicMock, patch


@pytest.fixture
def PARSE_CONF():
    return {
        "include files": {"rsyslog": ["/var/log/syslog"]},
        "rotate": 1,
        "/var/log/wtmp": {"rotate": 1},
    }


@pytest.fixture
def configure_loader_modules():
    return {logrotate: {}}


# 'show_conf' function tests: 1


def test_show_conf():
    """
    Test if it show parsed configuration
    """
    with patch("salt.modules.logrotate._parse_conf", MagicMock(return_value=True)):
        assert logrotate.show_conf()


# 'set_' function tests: 4


def test_set(PARSE_CONF):
    """
    Test if it set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ), patch.dict(logrotate.__salt__, {"file.replace": MagicMock(return_value=True)}):
        assert logrotate.set_("rotate", "2")


def test_set_failed(PARSE_CONF):
    """
    Test if it fails to set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        kwargs = {"key": "/var/log/wtmp", "value": 2}
        pytest.raises(SaltInvocationError, logrotate.set_, **kwargs)


def test_set_setting(PARSE_CONF):
    """
    Test if it set a new value for a specific configuration line
    """
    with patch.dict(
        logrotate.__salt__, {"file.replace": MagicMock(return_value=True)}
    ), patch("salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)):
        assert logrotate.set_("/var/log/wtmp", "rotate", "2")


def test_set_setting_failed(PARSE_CONF):
    """
    Test if it fails to set a new value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        kwargs = {"key": "rotate", "value": "/var/log/wtmp", "setting": "2"}
        pytest.raises(SaltInvocationError, logrotate.set_, **kwargs)


def test_get(PARSE_CONF):
    """
    Test if get a value for a specific configuration line
    """
    with patch(
        "salt.modules.logrotate._parse_conf", MagicMock(return_value=PARSE_CONF)
    ):
        # A single key returns the right value
        assert logrotate.get("rotate") == 1

        # A single key returns the wrong value
        assert logrotate.get("rotate") != 2

        # A single key returns the right stanza value
        assert logrotate.get("/var/log/wtmp", "rotate") == 1

        # A single key returns the wrong stanza value
        assert logrotate.get("/var/log/wtmp", "rotate") != 2

        # Ensure we're logging the message as debug not warn
        with patch.object(logrotate, "_LOG") as log_mock:
            res = logrotate.get("/var/log/utmp", "rotate")
            assert log_mock.debug.called
            assert not log_mock.warn.called
