# coding: utf-8

# Import Python libs
import os

# Import Salt Testing libs
import integration

# Import Salt libs
import salt.runner


class RunnerModuleTest(integration.ClientCase):
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
        self.runner.master_call(**{
            'client': 'runner',
            'fun': 'error.error',
            'eauth': 'auto',
            'username': 'saltdev',
            'password': 'saltdev',
        })

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
        token = auth.mk_token({
            'username': 'saltdev',
            'password': 'saltdev',
            'eauth': 'auto',
        })

        self.runner.master_call(**{
            'client': 'runner',
            'fun': 'error.error',
            'token': token['token'],
        })


if __name__ == '__main__':
    from integration import run_tests
    run_tests(RunnerModuleTest, needs_daemon=True)
