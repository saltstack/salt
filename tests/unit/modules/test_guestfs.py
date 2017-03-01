# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jayesh Kariya <jayeshk@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
from salt.modules import guestfs

# Globals
guestfs.__salt__ = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GuestfsTestCase(TestCase):
    '''
    Test cases for salt.modules.guestfs
    '''
    # 'mount' function tests: 1

    @patch('os.path.join', MagicMock(return_value=True))
    @patch('os.path.isdir', MagicMock(return_value=True))
    @patch('os.listdir', MagicMock(return_value=False))
    def test_mount(self):
        '''
        Test if it mount an image
        '''
        mock = MagicMock(return_value='')
        with patch.dict(guestfs.__salt__, {'cmd.run': mock}):
            self.assertTrue(guestfs.mount('/srv/images/fedora.qcow'))
