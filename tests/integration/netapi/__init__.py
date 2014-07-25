# encoding: utf-8

# Import Python libs
import os

# Import Salt Testing libs
from integration import TMP_CONF_DIR
from salttesting import TestCase

# Import Salt libs
import salt.config
import salt.netapi


class NetapiClientTest(TestCase):
    eauth_creds = {
        'username': 'saltdev_auto',
        'password': 'saltdev',
        'eauth': 'auto',
    }

    def setUp(self):
        '''
        Set up a NetapiClient instance
        '''
        opts = salt.config.client_config(os.path.join(TMP_CONF_DIR, 'master'))
        self.netapi = salt.netapi.NetapiClient(opts)

    def test_local(self):
        low = {'client': 'local', 'tgt': '*', 'fun': 'test.ping'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        self.assertEqual(ret, {'minion': True, 'sub_minion': True})

    def test_local_async(self):
        low = {'client': 'local_async', 'tgt': '*', 'fun': 'test.ping'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn('jid', ret)
        ret.pop('jid', None)
        self.assertEqual(ret, {'minions': ['minion', 'sub_minion']})

    def test_wheel(self):
        low = {'client': 'wheel', 'fun': 'key.list_all'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn('tag', ret)
        ret.pop('tag')

        data = ret.get('data', {})
        self.assertIn('jid', data)
        data.pop('jid', None)

        self.assertIn('tag', data)
        data.pop('tag', None)

        ret.pop('_stamp', None)
        data.pop('_stamp', None)

        self.maxDiff = None
        self.assertEqual(ret, {
            'data': {
                'return': {
                    'minions_pre': [],
                    'minions_rejected': [],
                    'local': [
                        'master.pem', 'master.pub', 'minion.pem', 'minion.pub',
                        'minion_master.pub', 'syndic_master.pub'
                    ],
                    'minions': ['minion', 'sub_minion']},
                'success': True,
                'user': 'saltdev_auto',
                'fun': 'wheel.key.list_all'
            }})

    def test_wheel_async(self):
        low = {'client': 'wheel_async', 'fun': 'key.list_all'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        self.assertIn('jid', ret)
        self.assertIn('tag', ret)

    def test_runner(self):
        low = {'client': 'runner', 'fun': 'cache.grains'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    def test_runner_async(self):
        low = {'client': 'runner', 'fun': 'cache.grains'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(NetapiClientTest, needs_daemon=True)
