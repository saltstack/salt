"""
    :codeauthor: :email:`Megan Wilhite (mwilhite@saltstack.com)`


    tests.unit.returners.test_syslog_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""


import salt.returners.syslog_return as syslog
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


class SyslogReturnerTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test Syslog returner
    """

    def setup_loader_modules(self):
        return {syslog: {}}

    @skipIf(not syslog.HAS_SYSLOG, "Skip when syslog not installed")
    def test_syslog_returner_unicode(self):
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
                self.fail("syslog.returner() failed with exception: {}".format(e))
