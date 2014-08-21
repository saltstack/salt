# coding: utf-8

# Import Python libs
import os

# Import Salt Testing libs
import integration

# Import Salt libs
import salt.runner


class RunnerModuleTest(integration.ClientCase):
    eauth_creds = {
        'username': 'saltdev_auto',
        'password': 'saltdev',
        'eauth': 'auto',
    }

    def setUp(self):
        '''
        Configure an eauth user to test with
        '''
        self.runner = salt.runner.RunnerClient(self.get_opts())

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

        opts = self.get_opts()
        self.mkdir_p(os.path.join(opts['root_dir'], 'cache', 'tokens'))

        auth = salt.auth.LoadAuth(opts)
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RunnerModuleTest, needs_daemon=True)
