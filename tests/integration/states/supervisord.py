'''
Tests for the supervisord state
'''
import os
import integration


class SupervisordTest(integration.ModuleCase):
    '''
    Validate the supervisord states.
    '''
    def setUp(self):
        super(SupervisordTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['supervisorctl'])
        if not ret:
            self.skipTest('supervisor not installed')
        if os.geteuid() != 0:
            self.skipTest('you must be this root to run this test')

    def test_start(self):
        '''
        supervisord.running restart = False
        '''
        ret = self.run_state('supervisord.running', name='null_service')

        self.assertTrue(ret)
        self.assertEqual(ret.items()[0][1]['result'], False)

    def test_restart(self):
        '''
        supervisord.running restart = True
        '''
        ret = self.run_state(
            'supervisord.running', name='null_service', restart=True)

        self.assertTrue(ret)
        self.assertEqual(ret.items()[0][1]['result'], False)

    def test_stop(self):
        '''
        supervisord.dead
        '''
        ret = self.run_state(
            'supervisord.dead', name='null_service')

        self.assertTrue(ret)
        self.assertEqual(ret.items()[0][1]['result'], False)
