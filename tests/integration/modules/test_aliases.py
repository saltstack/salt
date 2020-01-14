# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class AliasesTest(ModuleCase):
    '''
    Validate aliases module
    '''
    def test_set_target(self):
        '''
        aliases.set_target and aliases.get_target
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        assert set_ret
        tgt_ret = self.run_function(
                'aliases.get_target',
                alias='fred')
        assert tgt_ret == 'bob'

    def test_has_target(self):
        '''
        aliases.set_target and aliases.has_target
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        assert set_ret
        tgt_ret = self.run_function(
                'aliases.has_target',
                alias='fred',
                target='bob')
        assert tgt_ret

    def test_list_aliases(self):
        '''
        aliases.list_aliases
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='fred',
                target='bob')
        assert set_ret
        tgt_ret = self.run_function(
                'aliases.list_aliases')
        assert isinstance(tgt_ret, dict)
        assert 'fred' in tgt_ret

    def test_rm_alias(self):
        '''
        aliases.rm_alias
        '''
        set_ret = self.run_function(
                'aliases.set_target',
                alias='frank',
                target='greg')
        assert set_ret
        self.run_function(
            'aliases.rm_alias',
            alias='frank')
        tgt_ret = self.run_function(
                'aliases.list_aliases')
        assert isinstance(tgt_ret, dict)
        assert 'alias=frank' not in tgt_ret
