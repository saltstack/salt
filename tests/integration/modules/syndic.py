# Import python libs
import os

# Import salt libs
import integration

class TestSyndicTest(integration.SyndicCase):
    '''
    Validate the syndic interface by testing the test module
    '''
    def test_ping(self):
        '''
        test.ping
        '''
        self.assertTrue(self.run_function('test.ping'))

    def test_fib(self):
        '''
        test.fib
        '''
        self.assertEqual(
                self.run_function(
                    'test.fib',
                    ['40'],
                    )[0][-1],
                34
                )

