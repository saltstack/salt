# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Alexander Schwartz <alexander.schwartz@gmx.net>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase

# Import Salt Libs
from salt.cloud.clouds import saltify

# Globals
saltify.__opts__ = {}
saltify.__opts__['providers'] = {}


class SaltifyTestCase(TestCase):
    '''
    Test cases for salt.cloud.clouds.saltify
    '''
    # 'create' function tests: 1

    def test_create_no_deploy(self):
        '''
        Test if deployment fails. This is the most basic test as saltify doesn't contain much logic
        '''
        vm = {'deploy':  False,
              'provider': 'saltify',
              'name': 'dummy'
             }
        self.assertTrue(saltify.create(vm)['Error']['No Deploy'])


if __name__ == '__main__':
    from integration import run_tests
    run_tests(SaltifyTestCase, needs_daemon=False)
