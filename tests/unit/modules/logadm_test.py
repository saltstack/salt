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
from salt.modules import logadm

# Globals
logadm.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class LogadmTestCase(TestCase):
    '''
    Test cases for salt.modules.logadm
    '''
    def test_show_conf(self):
        '''
        Test for Show parsed configuration
        '''
        with patch.object(logadm, '_parse_conf', return_value=True):
            self.assertTrue(logadm.show_conf('conf_file'))

    def test_rotate(self):
        '''
        Test for Set up pattern for logging.
        '''
        with patch.dict(logadm.__salt__,
                        {'cmd.run_all':
                         MagicMock(return_value={'retcode': 1,
                                                 'stderr': 'stderr'})}):
            self.assertEqual(logadm.rotate('name'),
                             {'Output': 'stderr',
                              'Error': 'Failed in adding log'})

        with patch.dict(logadm.__salt__,
                        {'cmd.run_all':
                         MagicMock(return_value={'retcode': 0,
                                                 'stderr': 'stderr'})}):
            self.assertEqual(logadm.rotate('name'), {'Result': 'Success'})

    def test_remove(self):
        '''
        Test for Remove log pattern from logadm
        '''
        with patch.dict(logadm.__salt__,
                        {'cmd.run_all':
                         MagicMock(return_value={'retcode': 1,
                                                 'stderr': 'stderr'})}):
            self.assertEqual(logadm.remove('name'),
                             {'Output': 'stderr',
                              'Error': 'Failure in removing log. Possibly\
 already removed?'})

        with patch.dict(logadm.__salt__,
                        {'cmd.run_all':
                         MagicMock(return_value={'retcode': 0,
                                                 'stderr': 'stderr'})}):
            self.assertEqual(logadm.remove('name'), {'Result': 'Success'})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LogadmTestCase, needs_daemon=False)
