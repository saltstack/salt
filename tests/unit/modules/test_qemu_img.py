# -*- coding: utf-8 -*-
'''
    :codeauthor: Rupesh Tare <rupesht@saltstack.com>
'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch,
)

# Import Salt Libs
import salt.modules.qemu_img as qemu_img


class QemuimgTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.qemu_img
    '''
    def setup_loader_modules(self):
        return {qemu_img: {}}

    def test_make_image(self):
        '''
        Test for create a blank virtual machine image file
        of the specified size in megabytes
        '''
        with patch.object(os.path, 'isabs',
                          MagicMock(side_effect=[False, True, True, True])):
            self.assertEqual(qemu_img.make_image('location', 'size', 'fmt'), '')

            with patch.object(os.path, 'isdir',
                              MagicMock(side_effect=[False, True, True])):
                self.assertEqual(qemu_img.make_image('location', 'size', 'fmt'), '')

                with patch.dict(qemu_img.__salt__,
                                {'cmd.retcode': MagicMock(side_effect=[False, True])}):
                    self.assertEqual(qemu_img.make_image('location', 'size', 'fmt'), 'location')
                    self.assertEqual(qemu_img.make_image('location', 'size', 'fmt'), '')
