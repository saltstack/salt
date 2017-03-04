# coding: utf-8

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
import tests.integration as integration
from tests.support.unit import skipIf

# Import Salt libs
import salt.runner


class RunnerModuleTest(integration.TestCase, integration.AdaptedConfigurationTestCaseMixIn):
    eauth_creds = {
        'username': 'saltdev_auto',
        'password': 'saltdev',
        'eauth': 'auto',
    }

    def setUp(self):
        '''
        Configure an eauth user to test with
        '''
        self.runner = salt.runner.RunnerClient(self.get_config('client_config'))

    def test_eauth(self):
        '''
        Test executing master_call with lowdata

        The choice of using error.error for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        low = {
            'client': 'runner',
            'fun': 'error.error',
        }
        low.update(self.eauth_creds)

        self.runner.master_call(**low)

    def test_token(self):
        '''
        Test executing master_call with lowdata

        The choice of using error.error for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        import salt.auth

        auth = salt.auth.LoadAuth(self.get_config('client_config'))
        token = auth.mk_token(self.eauth_creds)

        self.runner.master_call(**{
            'client': 'runner',
            'fun': 'error.error',
            'token': token['token'],
        })

    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_cmd_sync(self):
        low = {
            'client': 'runner',
            'fun': 'error.error',
        }
        low.update(self.eauth_creds)

        self.runner.cmd_sync(low)

    def test_cmd_async(self):
        low = {
            'client': 'runner',
            'fun': 'error.error',
        }
        low.update(self.eauth_creds)

        self.runner.cmd_async(low)

    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_cmd_sync_w_arg(self):
        low = {
            'fun': 'test.arg',
            'foo': 'Foo!',
            'bar': 'Bar!',
        }
        low.update(self.eauth_creds)

        ret = self.runner.cmd_sync(low)
        self.assertEqual(ret['kwargs']['foo'], 'Foo!')
        self.assertEqual(ret['kwargs']['bar'], 'Bar!')

    @skipIf(True, 'to be reenabled when #23623 is merged')
    def test_wildcard_auth(self):
        low = {
            'username': 'the_s0und_of_t3ch',
            'password': 'willrockyou',
            'eauth': 'auto',
            'fun': 'test.arg',
            'foo': 'Foo!',
            'bar': 'Bar!',
        }
        self.runner.cmd_sync(low)

    def test_full_return_kwarg(self):
        low = {'fun': 'test.arg'}
        low.update(self.eauth_creds)
        ret = self.runner.cmd_sync(low, full_return=True)
        self.assertIn('success', ret['data'])
