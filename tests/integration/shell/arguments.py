# -*- coding: utf-8 -*-
'''
    Test Salt's argument parser
'''

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath, requires_salt_modules

ensure_in_syspath('../../')

# Import Salt libs
from salt.exceptions import SaltInvocationError
import integration


@requires_salt_modules('test.ping')
class ArgumentTestCase(integration.ModuleCase):
    def test_unsupported_kwarg(self):
        '''
        Test passing a non-supported keyword argument
        '''
        self.assertEqual(
            self.run_function('test.ping', ['foo=bar']),
            ("ERROR executing 'test.ping': The following keyword arguments "
             "are not valid: foo=bar")
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArgumentTestCase)
