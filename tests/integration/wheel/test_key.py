# coding: utf-8

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin

# Import Salt libs
import salt.wheel

import pytest


@pytest.mark.windows_whitelisted
class KeyWheelModuleTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(dict(self.get_config('client_config')))

    def tearDown(self):
        del self.wheel

    def test_list_all(self):
        ret = self.wheel.cmd('key.list_all', print_event=False)
        for host in ['minion', 'sub_minion']:
            assert host in ret['minions']

    def test_gen(self):
        ret = self.wheel.cmd('key.gen', kwarg={'id_': 'soundtechniciansrock'}, print_event=False)

        assert 'pub' in ret
        assert 'priv' in ret
        try:
            assert ret.get('pub', '').startswith('-----BEGIN PUBLIC KEY-----')
        except AssertionError:
            assert ret.get('pub', '').startswith('-----BEGIN RSA PUBLIC KEY-----')

        assert ret.get('priv', '').startswith('-----BEGIN RSA PRIVATE KEY-----')
