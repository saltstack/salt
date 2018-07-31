# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Megan Wilhite (mwilhite@saltstack.com)`


    tests.unit.returners.test_syslog_return
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, MagicMock, patch

# Import salt libs
import salt.returners.syslog_return as syslog


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SyslogReturnerTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test Syslog returner
    '''
    def setup_loader_modules(self):
        return {syslog: {}}

    @skipIf(not syslog.HAS_SYSLOG, 'Skip when syslog not installed')
    def test_syslog_returner_unicode(self):
        '''
        test syslog returner with unicode
        '''
        ret = {'fun_args': [], 'jid': '20180713160901624786', 'return': True,
               'retcode': 0, 'success': True, 'fun': 'test.ping', 'id': '02e10e971a30'}
        opts = {u'level': u'LOG_INFO', u'options': [],
                u'facility': u'LOG_USER', u'tag': u'salt-minion'}

        with patch('salt.returners.syslog_return._get_options',
                   MagicMock(return_value=opts)):
            try:
                syslog.returner(ret)
            except Exception as e:
                self.fail('syslog.returner() failed with exception: {0}'.format(e))
