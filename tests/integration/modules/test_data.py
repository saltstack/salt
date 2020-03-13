# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.case import ModuleCase

import pytest


@pytest.mark.windows_whitelisted
class DataModuleTest(ModuleCase):
    '''
    Validate the data module
    '''
    def setUp(self):
        self.run_function('data.clear')
        self.addCleanup(self.run_function, 'data.clear')

    def test_load_dump(self):
        '''
        data.load
        data.dump
        '''
        assert self.run_function('data.dump', ['{"foo": "bar"}'])
        assert self.run_function('data.load') == {'foo': 'bar'}

    def test_get_update(self):
        '''
        data.get
        data.update
        '''
        assert self.run_function('data.update', ['spam', 'eggs'])
        assert self.run_function('data.get', ['spam']) == 'eggs'

        assert self.run_function('data.update', ['unladen', 'swallow'])
        assert self.run_function('data.get', [["spam", "unladen"]]) == ['eggs', 'swallow']

    def test_cas_update(self):
        '''
        data.update
        data.cas
        data.get
        '''
        assert self.run_function('data.update', ['spam', 'eggs'])
        assert self.run_function('data.cas', ['spam', 'green', 'eggs'])
        assert self.run_function('data.get', ['spam']) == 'green'
