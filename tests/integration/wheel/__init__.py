# coding: utf-8

# Import Python libs
import os

# Import Salt Testing libs
import integration

# Import Salt libs
import salt.wheel


class WheelModuleTest(integration.ClientCase):
    def setUp(self):
        '''
        Configure an eauth user to test with
        '''
        self.wheel = salt.wheel.Wheel(self.get_opts())

    def test_eauth(self):
        '''
        Test executing master_call with lowdata

        The choice of using key.list_all for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        self.wheel.master_call(**{
            'client': 'wheel',
            'fun': 'key.list_all',
            'eauth': 'auto',
            'username': 'saltdev',
            'password': 'saltdev',
        })

    def test_eauth_async(self):
        '''
        Test executing async master_call with lowdata

        The choice of using key.list_all for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        self.wheel.master_call(**{
            'client': 'wheel',
            'fun': 'key.list_all',
            'eauth': 'auto',
            'username': 'saltdev',
            'password': 'saltdev',
            'mode': 'async',
        })

    def _get_token(self, low):
        import salt.auth

        opts = self.get_opts()
        self.mkdir_p(os.path.join(opts['root_dir'], 'cache', 'tokens'))

        auth = salt.auth.LoadAuth(opts)
        return auth.mk_token(low)

    def test_token(self):
        '''
        Test executing master_call with lowdata

        The choice of using key.list_all for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        token = self._get_token({
            'username': 'saltdev',
            'password': 'saltdev',
            'eauth': 'auto',
        })

        self.wheel.master_call(**{
            'client': 'wheel',
            'fun': 'key.list_all',
            'token': token['token'],
        })

    def test_token_async(self):
        '''
        Test executing async master_call with lowdata

        The choice of using key.list_all for this is arbitrary and should be
        changed to some mocked function that is more testing friendly.
        '''
        token = self._get_token({
            'username': 'saltdev',
            'password': 'saltdev',
            'eauth': 'auto',
        })

        self.wheel.master_call(**{
            'client': 'wheel',
            'fun': 'key.list_all',
            'token': token['token'],
            'mode': 'async',
        })


if __name__ == '__main__':
    from integration import run_tests
    run_tests(WheelModuleTest, needs_daemon=True)
