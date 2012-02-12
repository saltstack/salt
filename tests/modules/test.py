import daemon

class TestModuleTest(daemon.ModuleCase):
    '''
    Validate the test module
    '''
    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))
