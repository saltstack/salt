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
        self.assertEqual(ret.items()[0][1]['result'], None)

    def test_restart(self):
        '''
        supervisord.running restart = True
        '''
        ret = self.run_state(
            'supervisord.running', name='null_service', restart=True)

        self.assertTrue(ret)
        self.assertEqual(ret.items()[0][1]['result'], None)

    def test_stop(self):
        '''
        supervisord.dead
        '''
        ret = self.run_state(
            'supervisord.dead', name='null_service')

        self.assertTrue(ret)
        self.assertEqual(ret.items()[0][1]['result'], None)
