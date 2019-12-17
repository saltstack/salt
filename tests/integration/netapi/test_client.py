# encoding: utf-8

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import time

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.unit import TestCase, skipIf

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
        opts = salt.config.client_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, 'master'))
        self.netapi = salt.netapi.NetapiClient(opts)

    def tearDown(self):
        del self.netapi

    def test_local(self):
        low = {'client': 'local', 'tgt': '*', 'fun': 'test.ping', 'timeout': 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        # If --proxy is set, it will cause an extra minion_id to be in the
        # response. Since there's not a great way to know if the test
        # runner's proxy minion is running, and we're not testing proxy
        # minions here anyway, just remove it from the response.
        ret.pop('proxytest', None)
        self.assertEqual(ret, {'minion': True, 'sub_minion': True})

    def test_local_batch(self):
        low = {'client': 'local_batch', 'tgt': '*', 'fun': 'test.ping', 'timeout': 300}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        rets = []
        for _ret in ret:
            rets.append(_ret)
        self.assertIn({'sub_minion': True}, rets)
        self.assertIn({'minion': True}, rets)

    def test_local_async(self):
        low = {'client': 'local_async', 'tgt': '*', 'fun': 'test.ping'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

        # Remove all the volatile values before doing the compare.
        self.assertIn('jid', ret)
        ret.pop('jid', None)
        ret['minions'] = sorted(ret['minions'])
        try:
            # If --proxy is set, it will cause an extra minion_id to be in the
            # response. Since there's not a great way to know if the test
            # runner's proxy minion is running, and we're not testing proxy
            # minions here anyway, just remove it from the response.
            ret['minions'].remove('proxytest')
        except ValueError:
            pass
        self.assertEqual(ret, {'minions': sorted(['minion', 'sub_minion'])})

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
        self.assertTrue(set(['master.pem', 'master.pub']).issubset(set(ret['data']['return']['local'])))

    def test_wheel_async(self):
        # Give this test a little breathing room
        time.sleep(3)
        low = {'client': 'wheel_async', 'fun': 'key.list_all'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
        self.assertIn('jid', ret)
        self.assertIn('tag', ret)

    @skipIf(True, 'This is not testing anything. Skipping for now.')
    def test_runner(self):
        # TODO: fix race condition in init of event-- right now the event class
        # will finish init even if the underlying zmq socket hasn't connected yet
        # this is problematic for the runnerclient's master_call method if the
        # runner is quick
        #low = {'client': 'runner', 'fun': 'cache.grains'}
        low = {'client': 'runner', 'fun': 'test.sleep', 'arg': [2]}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)

    @skipIf(True, 'This is not testing anything. Skipping for now.')
    def test_runner_async(self):
        low = {'client': 'runner', 'fun': 'cache.grains'}
        low.update(self.eauth_creds)

        ret = self.netapi.run(low)
