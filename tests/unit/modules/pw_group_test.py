# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Rupesh Tare <rupesht@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import pw_group

# Globals
pw_group.__grains__ = {}
pw_group.__salt__ = {}
pw_group.__context__ = {}
pw_group.grinfo = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PwGroupTestCase(TestCase):
    '''
    Test for salt.module.pw_group
    '''
    def test_add(self):
        '''
        Tests to add the specified group
        '''
        mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(pw_group.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(pw_group.add('a'))

    def test_delete(self):
        '''
        Tests to remove the named group
        '''
        mock = MagicMock(return_value={'retcode': 0})
        with patch.dict(pw_group.__salt__, {'cmd.run_all': mock}):
            self.assertTrue(pw_group.delete('a'))

    def test_info(self):
        '''
        Tests to return information about a group
        '''
        self.assertDictEqual(pw_group.info('name'), {})

        mock = MagicMock(return_value={'gr_name': 'A',
                                       'gr_passwd': 'B',
                                       'gr_gid': 1,
                                       'gr_mem': ['C', 'D']})
        with patch.dict(pw_group.grinfo, mock):
            self.assertDictEqual(pw_group.info('name'), {})

    def test_getent(self):
        '''
        Tests for return info on all groups
        '''
        mock_getent = [{'passwd': 'x',
                        'gid': 0,
                        'name': 'root'}]
        with patch.dict(pw_group.__context__, {'group.getent': mock_getent}):
            self.assertDictContainsSubset({'passwd': 'x',
                                           'gid': 0,
                                           'name': 'root'}, pw_group.getent()[0])

        mock = MagicMock(return_value='A')
        with patch.object(pw_group, 'info', mock):
            self.assertEqual(pw_group.getent(True)[0], 'A')

    def test_chgid(self):
        '''
        tests to change the gid for a named group
        '''
        mock = MagicMock(return_value=1)
        with patch.dict(pw_group.__salt__, {'file.group_to_gid': mock}):
            self.assertTrue(pw_group.chgid('name', 1))

        mock = MagicMock(side_effect=[1, 0])
        with patch.dict(pw_group.__salt__, {'file.group_to_gid': mock}):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_group.__salt__, {'cmd.run': mock}):
                self.assertTrue(pw_group.chgid('name', 0))

        mock = MagicMock(side_effect=[1, 1])
        with patch.dict(pw_group.__salt__, {'file.group_to_gid': mock}):
            mock = MagicMock(return_value=None)
            with patch.dict(pw_group.__salt__, {'cmd.run': mock}):
                self.assertFalse(pw_group.chgid('name', 0))


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PwGroupTestCase, needs_daemon=False)
