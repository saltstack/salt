# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Schwartz <alexander.schwartz@gmx.net>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase
from tests.support.mock import (
    MagicMock,
    patch
)

# Import Salt Libs
from salt.cloud.clouds import saltify


class SaltifyTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.cloud.clouds.saltify
    '''
    # 'create' function tests: 1

    def setup_loader_modules(self):
        return {
            saltify: {
                '__active_provider_name__': '',
                '__utils__': {
                    'cloud.bootstrap': MagicMock()
                },
                '__opts__': {'providers': {}}
            }
        }

    def test_create_no_deploy(self):
        '''
        Test if deployment fails. This is the most basic test as saltify doesn't contain much logic
        '''
        with patch('salt.cloud.clouds.saltify._verify', MagicMock(return_value=True)):
            vm = {'deploy':  False,
                  'driver': 'saltify',
                  'name': 'dummy'
                 }
            self.assertTrue(saltify.create(vm))
