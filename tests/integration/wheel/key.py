# coding: utf-8

# Import Salt Testing libs
import integration

# Import Salt libs
import salt.wheel


class KeyWheelModuleTest(integration.ClientCase):
    def setUp(self):
        self.wheel = salt.wheel.Wheel(self.get_opts())

    def test_list_all(self):
        ret = self.wheel.call_func('key.list_all')
        self.assertEqual(ret, {
            'local': [
                'master.pem',
                'master.pub',
                'minion.pem',
                'minion.pub',
                'minion_master.pub',
                'syndic_master.pub'
            ],
            'minions_rejected': [],
            'minions_pre': [],
            'minions': ['minion', 'sub_minion'],
        })

    def test_gen(self):
        ret = self.wheel.call_func('key.gen', id_='soundtechniciansrock')

        self.assertIn('pub', ret)
        self.assertIn('priv', ret)
        self.assertTrue(
            ret.get('pub', '').startswith('-----BEGIN PUBLIC KEY-----'))
        self.assertTrue(
            ret.get('priv', '').startswith('-----BEGIN RSA PRIVATE KEY-----'))

if __name__ == '__main__':
    from integration import run_tests
    run_tests(KeyWheelModuleTest, needs_daemon=True)
