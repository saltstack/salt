# -*- coding: utf-8 -*-
'''
    :codeauthor: Jayesh Kariya <jayeshk@saltstack.com>
'''

# Import Python libs
from __future__ import absolute_import, unicode_literals, print_function

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.guestfs as guestfs


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
