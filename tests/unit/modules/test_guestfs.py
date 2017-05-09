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
import salt.modules.guestfs as guestfs


@skipIf(NO_MOCK, NO_MOCK_REASON)
class GuestfsTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.guestfs
    '''
    def setup_loader_modules(self):
        return {guestfs: {}}

    # 'mount' function tests: 1
    def test_mount(self):
        '''
        Test if it mount an image
        '''
        with patch('os.path.join', MagicMock(return_value=True)), \
                patch('os.path.isdir', MagicMock(return_value=True)), \
                patch('os.listdir', MagicMock(return_value=False)), \
                patch.dict(guestfs.__salt__, {'cmd.run': MagicMock(return_value='')}):
            self.assertTrue(guestfs.mount('/srv/images/fedora.qcow'))
