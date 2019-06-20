# coding: utf-8

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt Testing libs
from tests.support.unit import TestCase
from tests.support.mixins import AdaptedConfigurationTestCaseMixin

# Import Salt libs
import salt.runner
import salt.utils.jid


class RunnerModuleTest(TestCase, AdaptedConfigurationTestCaseMixin):
    # This is really an integration test since it needs a salt-master running
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

        low = {'client': 'runner', 'fun': 'saltutil.sync_all'}
        low.update(self.eauth_creds)
        self.runner.cmd_sync(low)

    def teardown(self):
        '''
        Configure an eauth user to test with
        '''
        del self.runner

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

    def test_cmd_sync_arg_kwarg_parsing(self):
        low = {
            'client': 'runner',
            'fun': 'test.arg',
            'arg': [
                'foo',
                'bar=off',
                'baz={qux: 123}'
            ],
            'kwarg': {
                'quux': 'Quux',
            },
            'quuz': 'on',
        }
        low.update(self.eauth_creds)

        ret = self.runner.cmd_sync(low)
        self.assertEqual(ret, {
            'args': ['foo'],
            'kwargs': {
                'bar': False,
                'baz': {
                    'qux': 123,
                },
                'quux': 'Quux',
                'quuz': 'on',
            },
        })

    def test_invalid_kwargs_are_ignored(self):
        low = {
            'client': 'runner',
            'fun': 'test.metasyntactic',
            'thiskwargisbad': 'justpretendimnothere',
        }
        low.update(self.eauth_creds)

        ret = self.runner.cmd_sync(low)
        self.assertEqual(ret[0], 'foo')

    def test_globals_are_set_as_expected(self):
        low = {
            'client': 'runner',
            'fun': 'testrunner.return_globals',
        }
        low.update(self.eauth_creds)
        ret = self.runner.cmd_sync(low)

        for key in ['__jid__', '__user__', '__tag__', '__jid_event__']:
            self.assertIn(key, ret)

    def test_runner_calling_runner_works(self):
        low = {
            'client': 'runner',
            'fun': 'testrunner.call_other_runner',
        }
        low.update(self.eauth_creds)
        ret = self.runner.cmd_sync(low)
        self.assertTrue(salt.utils.jid.is_jid(ret), msg='got __jid__ from nested runner call')
