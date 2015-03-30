# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath
from salt.exceptions import CommandExecutionError

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import supervisord

supervisord.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SupervisordTestCase(TestCase):
    '''
    TestCase for salt.modules.supervisord
    '''
    # 'start' function tests: 1

    def test_start(self):
        '''
        Tests if it start the named service.
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.start())

    # 'restart' function tests: 1

    def test_restart(self):
        '''
        Tests if it restart the named service.
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.restart())

    # 'stop' function tests: 1

    def test_stop(self):
        '''
        Tests if it stop the named service.
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.stop())

    # 'add' function tests: 1

    def test_add(self):
        '''
        Tests if it activates any updates in config for process/group.
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.add('salt'))

    # 'remove' function tests: 1

    def test_remove(self):
        '''
        Tests if it removes process/group from active config
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.remove('salt'))

    # 'reread' function tests: 1

    def test_reread(self):
        '''
        Tests if it reload the daemon's configuration files
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.reread())

    # 'update' function tests: 1

    def test_update(self):
        '''
        Tests if it reload config and add/remove as necessary
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.update())

    # 'status' function tests: 1

    def test_status(self):
        '''
        Tests if it list programs and its state
        '''
        mock_all = MagicMock(return_value={'retcode': 0,
                                           'stdout': 'salt running '})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertDictEqual(supervisord.status(),
                                 {'salt': {'state': 'running', 'reason': ''}})

    # 'status_raw' function tests: 1

    def test_status_raw(self):
        '''
        Tests if it display the raw output of status
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.status_raw())

    # 'custom' function tests: 1

    def test_custom(self):
        '''
        Tests if it run any custom supervisord command
        '''
        mock_all = MagicMock(return_value={'retcode': 0, 'stdout': True})
        mock_bin = MagicMock(return_value='/tmp/bin_env')
        with patch.dict(supervisord.__salt__, {'cmd.run_all': mock_all,
                                               'cmd.which_bin': mock_bin}):
            self.assertTrue(supervisord.custom("mstop '*gunicorn*'"))

    # 'options' function tests: 1

    def test_options(self):
        '''
        Tests if it read the config file and return the config options
        for a given process
        '''
        class MockConfig(object):
            '''
            Mock Config class
            '''
            flag = None

            def __init__(self):
                self.name = None

            def sections(self):
                '''
                Mock sections methos
                '''
                if self.flag == 1:
                    return []
                return ['program:salt']

            def items(self, name):
                '''
                Mock sections methos
                '''
                self.name = name
                return [('salt', 'True')]

        with patch.object(supervisord, '_read_config',
                          MagicMock(return_value=MockConfig())):
            MockConfig.flag = 1
            self.assertRaises(CommandExecutionError, supervisord.options,
                              'salt')

            MockConfig.flag = 0
            self.assertDictEqual(supervisord.options('salt'), {'salt': True})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SupervisordTestCase, needs_daemon=False)
