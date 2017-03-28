# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

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
import salt.modules.incron as incron


@skipIf(NO_MOCK, NO_MOCK_REASON)
class IncronTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.incron
    '''
    def setup_loader_modules(self):
        return {incron: {}}

    # 'write_incron_file' function tests: 1

    @patch('salt.modules.incron._get_incron_cmdstr',
           MagicMock(return_value='incrontab'))
    def test_write_incron_file(self):
        '''
        Test if it writes the contents of a file to a user's crontab
        '''
        mock = MagicMock(return_value=0)
        with patch.dict(incron.__salt__, {'cmd.retcode': mock}):
            self.assertTrue(incron.write_incron_file('cybage',
                                                     '/home/cybage/new_cron'))

    # 'write_cron_file_verbose' function tests: 1

    @patch('salt.modules.incron._get_incron_cmdstr',
           MagicMock(return_value='incrontab'))
    def test_write_cron_file_verbose(self):
        '''
        Test if it writes the contents of a file to a user's crontab and
        return error message on error
        '''
        mock = MagicMock(return_value=True)
        with patch.dict(incron.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(incron.write_incron_file_verbose
                            ('cybage', '/home/cybage/new_cron'))

    # 'raw_system_incron' function tests: 1

    @patch('salt.modules.incron._read_file',
           MagicMock(return_value='salt'))
    def test_raw_system_incron(self):
        '''
        Test if it return the contents of the system wide incrontab
        '''
        self.assertEqual(incron.raw_system_incron(), 'salt')

    # 'raw_incron' function tests: 1

    def test_raw_incron(self):
        '''
        Test if it return the contents of the user's incrontab
        '''
        mock = MagicMock(return_value='incrontab')
        with patch.dict(incron.__grains__, {'os_family': mock}):
            mock = MagicMock(return_value='salt')
            with patch.dict(incron.__salt__, {'cmd.run_stdout': mock}):
                self.assertEqual(incron.raw_incron('cybage'), 'salt')

    # 'list_tab' function tests: 1

    def test_list_tab(self):
        '''
        Test if it return the contents of the specified user's incrontab
        '''
        mock = MagicMock(return_value='incrontab')
        with patch.dict(incron.__grains__, {'os_family': mock}):
            mock = MagicMock(return_value='salt')
            with patch.dict(incron.__salt__, {'cmd.run_stdout': mock}):
                self.assertDictEqual(incron.list_tab('cybage'),
                                     {'pre': ['salt'], 'crons': []})

    # 'set_job' function tests: 1

    def test_set_job(self):
        '''
        Test if it sets a cron job up for a specified user.
        '''
        self.assertEqual(incron.set_job('cybage', '/home/cybage', 'TO_MODIFY',
                                        'echo "$$ $@ $# $% $&"'),
                         'Invalid mask type: TO_MODIFY')

        val = {'pre': [], 'crons': [{'path': '/home/cybage',
                                     'mask': 'IN_MODIFY',
                                     'cmd': 'echo "SALT"', 'comment': ''}]}
        with patch.object(incron, 'list_tab',
                          MagicMock(return_value=val)):
            self.assertEqual(incron.set_job('cybage', '/home/cybage',
                                            'IN_MODIFY',
                                            'echo "SALT"'), 'present')

        with patch.object(incron, 'list_tab',
                          MagicMock(return_value={'pre': ['salt'],
                                                  'crons': []})):
            mock = MagicMock(return_value='incrontab')
            with patch.dict(incron.__grains__, {'os_family': mock}):
                with patch.object(incron, '_write_incron_lines',
                                  MagicMock(return_value={'retcode': True,
                                                          'stderr': 'error'})):
                    self.assertEqual(incron.set_job('cybage', '/home/cybage',
                                                    'IN_MODIFY',
                                                    'echo "SALT"'), 'error')

        with patch.object(incron, 'list_tab',
                          MagicMock(return_value={'pre': ['salt'],
                                                  'crons': []})):
            mock = MagicMock(return_value='incrontab')
            with patch.dict(incron.__grains__, {'os_family': mock}):
                with patch.object(incron, '_write_incron_lines',
                                  MagicMock(return_value={'retcode': False,
                                                          'stderr': 'error'})):
                    self.assertEqual(incron.set_job('cybage', '/home/cybage',
                                                    'IN_MODIFY',
                                                    'echo "SALT"'), 'new')

        val = {'pre': [], 'crons': [{'path': '/home/cybage',
                                     'mask': 'IN_MODIFY,IN_DELETE',
                                     'cmd': 'echo "SALT"', 'comment': ''}]}
        with patch.object(incron, 'list_tab',
                          MagicMock(return_value=val)):
            mock = MagicMock(return_value='incrontab')
            with patch.dict(incron.__grains__, {'os_family': mock}):
                with patch.object(incron, '_write_incron_lines',
                                  MagicMock(return_value={'retcode': False,
                                                          'stderr': 'error'})):
                    self.assertEqual(incron.set_job('cybage', '/home/cybage',
                                                    'IN_DELETE',
                                                    'echo "SALT"'), 'updated')

    # 'rm_job' function tests: 1

    def test_rm_job(self):
        '''
        Test if it remove a cron job for a specified user. If any of the
        day/time params are specified, the job will only be removed if
        the specified params match.
        '''
        self.assertEqual(incron.rm_job('cybage', '/home/cybage', 'TO_MODIFY',
                                       'echo "$$ $@ $# $% $&"'),
                         'Invalid mask type: TO_MODIFY')

        with patch.object(incron, 'list_tab',
                          MagicMock(return_value={'pre': ['salt'],
                                                  'crons': []})):
            mock = MagicMock(return_value='incrontab')
            with patch.dict(incron.__grains__, {'os_family': mock}):
                with patch.object(incron, '_write_incron_lines',
                                  MagicMock(return_value={'retcode': True,
                                                          'stderr': 'error'})):
                    self.assertEqual(incron.rm_job('cybage', '/home/cybage',
                                                   'IN_MODIFY',
                                                   'echo "SALT"'), 'error')

        with patch.object(incron, 'list_tab',
                          MagicMock(return_value={'pre': ['salt'],
                                                  'crons': []})):
            mock = MagicMock(return_value='incrontab')
            with patch.dict(incron.__grains__, {'os_family': mock}):
                with patch.object(incron, '_write_incron_lines',
                                  MagicMock(return_value={'retcode': False,
                                                          'stderr': 'error'})):
                    self.assertEqual(incron.rm_job('cybage', '/home/cybage',
                                                   'IN_MODIFY',
                                                   'echo "SALT"'), 'absent')
