# -*- coding: utf-8 -*-
'''
Tests for the salt-run command
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ShellCase

import pytest


@pytest.mark.windows_whitelisted
class ManageTest(ShellCase):
    '''
    Test the manage runner
    '''
    def test_up(self):
        '''
        manage.up
        '''
        ret = self.run_run_plus('manage.up', timeout=60)
        assert 'minion' in ret['return']
        assert 'sub_minion' in ret['return']
        assert any('- minion' in out for out in ret['out'])
        assert any('- sub_minion' in out for out in ret['out'])

    def test_down(self):
        '''
        manage.down
        '''
        ret = self.run_run_plus('manage.down', timeout=60)
        assert 'minion' not in ret['return']
        assert 'sub_minion' not in ret['return']
        assert 'minion' not in ret['out']
        assert 'sub_minion' not in ret['out']
