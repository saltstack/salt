'''
Tests for the supervisord state
'''
import integration


class SupervisordTest(integration.ModuleCase):
    '''
    Validate the supervisord states.
    '''
    def test_start(self):
        '''
        supervisord.running restart = False
        '''
        ret = self.run_state('supervisord.running', name='null_service')

        self.assertTrue(ret)
        # Unlikely we have a service called test on the test machine
        self.assertFalse(ret.items()[0][1]['result'])

    def test_restart(self):
        '''
        supervisord.running restart = True
        '''
        ret = self.run_state(
            'supervisord.running', name='null_service', restart=True)

        self.assertTrue(ret)
        # Unlikely we have a service called test on the test machine
        self.assertFalse(ret.items()[0][1]['result'])
