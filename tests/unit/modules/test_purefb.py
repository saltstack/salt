# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Simon Dodsley <simon@purestorage.com>`
"""

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.purefb as purefb

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import patch
from tests.support.unit import TestCase


class PureFBTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.purefb
    """

    def setup_loader_modules(self):
        return {purefb: {}}

    def test_fs_create(self):
        """
        Test for creation of a filesystem
        """
        with patch.object(purefb, "fs_create", return_value=True):
            self.assertEqual(purefb.fs_create("test"), True)

    def test_fs_delete(self):
        """
        Test for deletion of a filesystem
        """
        with patch.object(purefb, "fs_delete", return_value=True):
            self.assertEqual(purefb.fs_delete("test"), True)

    def test_fs_eradicate(self):
        """
        Test for eradication of a filesystem
        """
        with patch.object(purefb, "fs_eradicate", return_value=True):
            self.assertEqual(purefb.fs_eradicate("test"), True)

    def test_fs_extend(self):
        """
        Test for size extention of a filesystem
        """
        with patch.object(purefb, "fs_extend", return_value=True):
            self.assertEqual(purefb.fs_extend("test", "33G"), True)

    def test_snap_create(self):
        """
        Test for creation of a filesystem snapshot
        """
        with patch.object(purefb, "snap_create", return_value=True):
            self.assertEqual(purefb.snap_create("test", suffix="suffix"), True)

    def test_snap_delete(self):
        """
        Test for deletion of a filesystem snapshot
        """
        with patch.object(purefb, "snap_delete", return_value=True):
            self.assertEqual(purefb.snap_delete("test", suffix="suffix"), True)

    def test_snap_eradicate(self):
        """
        Test for eradication of a deleted filesystem snapshot
        """
        with patch.object(purefb, "snap_eradicate", return_value=True):
            self.assertEqual(purefb.snap_eradicate("test", suffix="suffix"), True)
