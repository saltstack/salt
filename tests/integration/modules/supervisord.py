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
            self.skipTest('supervisor not installed')

    def test_start_all(self):
        '''
        Passing nothing into supervisord.start will start all services.
        '''
        ret = self.run_function('supervisord.start', [])
        self.assertEqual(len(list(ret.items())), 4)
        self.assertEqual(ret['retcode'], 0)

    def test_start_one(self):
        '''
        Start a specific service.
        '''
        ret = self.run_function('supervisord.start', ['null_service'])
        self.assertEqual(len(list(ret.items())), 4)
        self.assertEqual(ret['retcode'], 0)
