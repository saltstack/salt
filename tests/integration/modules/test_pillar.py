# -*- coding: utf-8 -*-

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class PillarModuleTest(ModuleCase):
    '''
    Validate the pillar module
    '''
    def test_data(self):
        '''
        pillar.data
        '''
        grains = self.run_function('grains.items')
        pillar = self.run_function('pillar.data')
        assert pillar['os'] == grains['os']
        assert pillar['monty'] == 'python'
        if grains['os'] == 'Fedora':
            assert pillar['class'] == 'redhat'
        else:
            assert pillar['class'] == 'other'

    def test_issue_5449_report_actual_file_roots_in_pillar(self):
        '''
        pillar['master']['file_roots'] is overwritten by the master
        in order to use the fileclient interface to read the pillar
        files. We should restore the actual file_roots when we send
        the pillar back to the minion.
        '''
        assert RUNTIME_VARS.TMP_STATE_TREE in \
            self.run_function('pillar.data')['master']['file_roots']['base']

    def test_ext_cmd_yaml(self):
        '''
        pillar.data for ext_pillar cmd.yaml
        '''
        assert self.run_function('pillar.data')['ext_spam'] == 'eggs'

    def test_issue_5951_actual_file_roots_in_opts(self):
        assert RUNTIME_VARS.TMP_STATE_TREE in \
            self.run_function('pillar.data')['ext_pillar_opts']['file_roots']['base']

    def test_pillar_items(self):
        '''
        Test to ensure we get expected output
        from pillar.items
        '''
        get_items = self.run_function('pillar.items')
        assert dict(get_items, **{'monty': 'python'}) == get_items
        assert dict(get_items, **{'knights': ['Lancelot', 'Galahad', 'Bedevere', 'Robin']}) == get_items

    def test_pillar_command_line(self):
        '''
        Test to ensure when using pillar override
        on command line works
        '''
        # test when pillar is overwriting previous pillar
        overwrite = self.run_function('pillar.items', pillar={"monty":
                                                              "overwrite"})
        assert dict(overwrite, **{'monty': 'overwrite'}) == overwrite

        # test when using additional pillar
        additional = self.run_function('pillar.items', pillar={"new":
                                                              "additional"})

        assert dict(additional, **{'new': 'additional'}) == additional
