# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.mock import (
    patch,
    mock_open,
    NO_MOCK,
    NO_MOCK_REASON
)

from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.modules import pam

MOCK_FILE = 'ok ok ignore '


@skipIf(NO_MOCK, NO_MOCK_REASON)
class PamTestCase(TestCase):
    '''
    Test cases for salt.modules.pam
    '''
    # 'read_file' function tests: 1

    def test_read_file(self):
        '''
        Test if the parsing function works
        '''
        with patch('salt.utils.fopen', mock_open(read_data=MOCK_FILE)):
            self.assertListEqual(pam.read_file('/etc/pam.d/login'),
                                 [{'arguments': [], 'control_flag': 'ok',
                                   'interface': 'ok', 'module': 'ignore'}])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(PamTestCase, needs_daemon=False)
