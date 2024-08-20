"""
    Test Syslog returner

    :codeauthor: :email:`Megan Wilhite (mwilhite@saltstack.com)`
"""

import pytest

import salt.returners.syslog_return as syslog
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {syslog: {}}


@pytest.mark.skipif(not syslog.HAS_SYSLOG, reason="Skip when syslog not installed")
def test_syslog_returner_unicode():
    """
    test syslog returner with unicode
    """
    ret = {
        "fun_args": [],
        "jid": "20180713160901624786",
        "return": True,
        "retcode": 0,
        "success": True,
        "fun": "test.ping",
        "id": "02e10e971a30",
    }
    opts = {
        "level": "LOG_INFO",
        "options": [],
        "facility": "LOG_USER",
        "tag": "salt-minion",
    }

    with patch(
        "salt.returners.syslog_return._get_options", MagicMock(return_value=opts)
    ):
        try:
            syslog.returner(ret)
        except Exception as e:  # pylint: disable=broad-except
            pytest.fail(f"syslog.returner() failed with exception: {e}")
