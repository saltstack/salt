# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class TestSyndic(integration.SyndicCase):
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
                    ['20'],
                    )[0],
                6765
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestSyndic)
