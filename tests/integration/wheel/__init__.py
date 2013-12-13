# coding: utf-8

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

    def test_master_call(self):
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

if __name__ == '__main__':
    from integration import run_tests
    run_tests(WheelModuleTest, needs_daemon=True)
