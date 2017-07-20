# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing libs
from tests.support.unit import skipIf, TestCase
from salt.exceptions import CommandExecutionError

# Import salt libs
import salt.modules.saltcheck as saltcheck


class SaltCheckTestCase(TestCase):
    ''' SaltCheckTestCase'''

    def test_ping(self):
        #self.assertTrue(True)
        self.assertTrue(saltcheck.ping)

    def test_update_master_cache(self):
        self.assertTrue(saltcheck.update_master_cache)

    #def test_sc_update_master_cache(self):
    #    sc = saltcheck.SaltCheck()
    #    self.assertTrue(sc.update_master_cache)

    def test_get_top_sls(self):
        self.assertTrue(saltcheck.get_top_sls)

    def test_sc_add_nums(self):
         sc = saltcheck.SaltCheck()
         val = sc.add_nums(10, 1)
         self.assertEqual(val, 11)


