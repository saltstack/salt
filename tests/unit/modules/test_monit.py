# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.modules.monit as monit


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MonitTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.aptpkg
    '''
    def setup_loader_modules(self):
        return {monit: {}}

    def test_start(self):
        '''
        Test for start
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.start('name'))

    def test_stop(self):
        '''
        Test for Stops service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.stop('name'))

    def test_restart(self):
        '''
        Test for Restart service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.restart('name'))

    def test_unmonitor(self):
        '''
        Test for Unmonitor service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.unmonitor('name'))

    def test_monitor(self):
        '''
        Test for monitor service via monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.retcode': MagicMock(return_value=False)}):
            self.assertTrue(monit.monitor('name'))

    def test_summary(self):
        '''
        Test for Display a summary from monit
        '''
        mock = MagicMock(side_effect=['daemon is not running',
                                      'A\nB\nC\nD\nE'])
        with patch.dict(monit.__salt__, {'cmd.run': mock}):
            self.assertEqual(monit.summary(),
                             {'monit': 'daemon is not running',
                              'result': False})

            self.assertEqual(monit.summary(), {})

    def test_status(self):
        '''
        Test for Display a process status from monit
        '''
        with patch.dict(monit.__salt__,
                        {'cmd.run':
                         MagicMock(return_value='Process')}):
            self.assertEqual(monit.status('service'), 'No such service')

    def test_reload(self):
        '''
        Test for Reload configuration
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(monit.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(monit.reload_())

    def test_version(self):
        '''
        Test for Display version from monit -V
        '''
        mock = MagicMock(return_value="This is Monit version 5.14\nA\nB")
        with patch.dict(monit.__salt__, {'cmd.run': mock}):
            self.assertEqual(monit.version(), '5.14')

    def test_id(self):
        '''
        Test for Display unique id
        '''
        mock = MagicMock(
            return_value='Monit ID: d3b1aba48527dd599db0e86f5ad97120')
        with patch.dict(monit.__salt__, {'cmd.run': mock}):
            self.assertEqual(monit.id_(), 'd3b1aba48527dd599db0e86f5ad97120')

    def test_reset_id(self):
        '''
        Test for Regenerate a unique id
        '''
        expected = {
            'stdout': 'Monit id d3b1aba48527dd599db0e86f5ad97120 and ...'
        }
        mock = MagicMock(return_value=expected)
        with patch.dict(monit.__salt__, {'cmd.run_all': mock}):
            self.assertEqual(monit.id_(reset=True),
                             'd3b1aba48527dd599db0e86f5ad97120')

    def test_configtest(self):
        '''
        Test for Check configuration syntax
        '''
        excepted = {
            'stdout': 'Control file syntax OK',
            'retcode': 0,
            'stderr': ''
        }
        mock = MagicMock(return_value=excepted)
        with patch.dict(monit.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(monit.configtest()['result'])
            self.assertEqual(monit.configtest()['comment'], 'Syntax OK')

    def test_validate(self):
        '''
        Test for Check all services are monitored
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(monit.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(monit.validate())
