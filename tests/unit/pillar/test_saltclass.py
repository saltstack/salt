# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os

# Import Salt Testing libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import NO_MOCK, NO_MOCK_REASON

# Import Salt Libs
import salt.pillar.saltclass as saltclass


base_path = os.path.dirname(os.path.realpath(__file__))
fake_minion_id = 'fake_id'
fake_pillar = {}
fake_args = ({'path': os.path.abspath(
                        os.path.join(base_path, '..', '..', 'integration',
                                     'files', 'saltclass', 'examples'))})
fake_opts = {}
fake_salt = {}
fake_grains = {}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltclassPillarTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Tests for salt.pillar.saltclass
    '''
    def setup_loader_modules(self):
        return {saltclass: {'__opts__': fake_opts,
                            '__salt__': fake_salt,
                            '__grains__': fake_grains
                           }}

    def _runner(self, expected_ret):
        full_ret = {}
        parsed_ret = []
        try:
            full_ret = saltclass.ext_pillar(fake_minion_id, fake_pillar, fake_args)
            parsed_ret = full_ret['__saltclass__']['classes']
        # Fail the test if we hit our NoneType error
        except TypeError as err:
            self.fail(err)
        # Else give the parsed content result
        self.assertListEqual(parsed_ret, expected_ret)

    def test_succeeds(self):
        ret = ['default.users', 'default.motd', 'default', 'roles.app']
        self._runner(ret)
