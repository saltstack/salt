# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, unicode_literals, print_function
import sys

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    patch,
    mock_open,
)

# Import Salt Libs
import salt.modules.pam as pam

MOCK_FILE = 'ok ok ignore '


@skipIf(sys.platform.startswith('openbsd'), 'OpenBSD does not use PAM')
class PamTestCase(TestCase):
    '''
    Test cases for salt.modules.pam
    '''
    # 'read_file' function tests: 1

    def test_read_file(self):
        '''
        Test if the parsing function works
        '''
        with patch('os.path.exists', return_value=True), \
                patch('salt.utils.files.fopen', mock_open(read_data=MOCK_FILE)):
            self.assertListEqual(pam.read_file('/etc/pam.d/login'),
                                 [{'arguments': [], 'control_flag': 'ok',
                                   'interface': 'ok', 'module': 'ignore'}])
