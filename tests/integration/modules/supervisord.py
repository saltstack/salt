import os
import integration


class SupervisordModuleTest(integration.ModuleCase):
    '''
    Validates the supervisorctl functions.
    To run these tests, you will need to allow the current user to read/write
    to supervisor.sock.
    Note that these tests don't actually do anything, since supervisor
    will most likely not be configured on the test machine.
    '''
    def setUp(self):
        super(SupervisordModuleTest, self).setUp()
        ret = self.run_function('cmd.has_exec', ['supervisorctl'])
        if not ret:
            self.skipTest('Supervisor not installed')
        if os.geteuid() != 0:
            self.skipTest('You must be root to run this test')

    def test_start_all(self):
        '''
        Passing nothing into supervisord.start will start all services.
        '''
        ret = self.run_function('supervisord.start', [])
        self.assertEqual(ret, '')

    def test_start_one(self):
        '''
        Start a specific service.
        '''
        ret = self.run_function('supervisord.start', ['null_service'])
        self.assertTrue('ERROR' in ret)

    def test_restart_all(self):
        '''
        Restart all services
        '''
        ret = self.run_function('supervisord.restart', [])
        self.assertEqual(ret, '')

    def test_restart_one(self):
        '''
        Restart a specific service.
        '''
        ret = self.run_function('supervisord.restart', ['null_service'])
        self.assertTrue('ERROR' in ret)

    def test_stop_all(self):
        '''
        stop all services
        '''
        ret = self.run_function('supervisord.stop', [])
        self.assertEqual(ret, '')

    def test_stop_one(self):
        '''
        stop a specific service.
        '''
        ret = self.run_function('supervisord.stop', ['null_service'])
        self.assertTrue('ERROR' in ret)

    def test_status_all(self):
        '''
        status all services
        '''
        ret = self.run_function('supervisord.status', [])
        self.assertEqual(ret, '')

    def test_status_one(self):
        '''
        status a specific service.
        '''
        ret = self.run_function('supervisord.status', ['null_service'])
        self.assertTrue(ret)
