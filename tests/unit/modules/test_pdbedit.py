# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.modules.pdbedit as pdbedit

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase


class PdbeditTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.modules.pdbedit module
    '''

    def setup_loader_modules(self):
        return {pdbedit: {}}

    def test_generate_nt_hash(self):
        '''
        Test salt.modules.pdbedit.generate_nt_hash
        '''
        ret = pdbedit.generate_nt_hash('supersecret')
        assert b'43239E3A0AF748020D5B426A4977D7E5' == ret
