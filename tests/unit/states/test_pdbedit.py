# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Libs
import salt.states.pdbedit as pdbedit

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import patch, MagicMock


class PdbeditTestCase(TestCase, LoaderModuleMockMixin):
    '''
    TestCase for salt.states.pdbedit module
    '''

    def setup_loader_modules(self):
        return {pdbedit: {}}

    def test_generate_absent(self):
        '''
        Test salt.states.pdbedit.absent when
        user is already absent
        '''
        name = 'testname'
        with patch.object(pdbedit, '__salt__', return_value=MagicMock()):
            ret = pdbedit.absent(name)
        assert ret['comment'] == 'account {0} is absent'.format(name)
