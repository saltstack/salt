# coding: utf-8

# Import Salt Testing libs
from __future__ import absolute_import
import integration

# Import Salt libs
import salt.wheel


class KeyWheelModuleTest(integration.TestCase, integration.AdaptedConfigurationTestCaseMixIn):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(dict(self.get_config('client_config')))

    def test_list_all(self):
        ret = self.wheel.cmd('key.list_all', print_event=False)
        for host in ['minion', 'sub_minion']:
            self.assertIn(host, ret['minions'])

    def test_gen(self):
        ret = self.wheel.cmd('key.gen', kwarg={'id_': 'soundtechniciansrock'}, print_event=False)

        self.assertIn('pub', ret)
        self.assertIn('priv', ret)
        try:
            self.assertTrue(
                ret.get('pub', '').startswith('-----BEGIN PUBLIC KEY-----'))
        except AssertionError:
            self.assertTrue(
                ret.get('pub', '').startswith('-----BEGIN RSA PUBLIC KEY-----'))

        self.assertTrue(
            ret.get('priv', '').startswith('-----BEGIN RSA PRIVATE KEY-----'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(KeyWheelModuleTest, needs_daemon=True)
