# coding: utf-8

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin

# Import Salt libs
import salt.wheel


class KeyWheelModuleTest(TestCase, AdaptedConfigurationTestCaseMixin):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(dict(self.get_config('client_config')))

    def tearDown(self):
        del self.wheel

    def test_list_all(self):
        ret = self.wheel.cmd('key.list_all', print_event=False)
        for host in ['minion', 'sub_minion']:
            self.assertIn(host, ret['minions'])

    def test_gen(self):
        ret = self.wheel.cmd('key.gen', kwarg={'id_': 'soundtechniciansrock'}, print_event=False)

        self.assertIn('pub', ret)
        self.assertIn('priv', ret)
        self.assertTrue(
            ret.get('pub', '').startswith('-----BEGIN PUBLIC KEY-----'))
        self.assertTrue(
            ret.get('priv', '').startswith('-----BEGIN RSA PRIVATE KEY-----'))
