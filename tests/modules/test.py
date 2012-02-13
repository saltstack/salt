import saltunittest

class TestModuleTest(saltunittest.ModuleCase):
    '''
    Validate the test module
    '''
    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))

    def test_echo(self):
        '''
        test.echo
        '''
        self.assertEqual(self.run_function('test.echo', ['text']), 'text')
