# -*- coding: utf-8 -*-
'''
    Test Salt's argument parser
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, requires_salt_modules

ensure_in_syspath('../../')

# Import Salt libs
import integration


@requires_salt_modules('test.ping', 'test.arg')
class ArgumentTestCase(integration.ModuleCase):
    def test_unsupported_kwarg(self):
        '''
        Test passing a non-supported keyword argument. The relevant code that
        checks for invalid kwargs is located in salt/minion.py, within the
        'load_args_and_kwargs' function.
        '''
        self.assertIn(
            ("ERROR executing 'test.ping': The following keyword arguments"),
            self.run_function('test.ping', ['foo=bar'])
        )

    def test_kwarg_name_containing_dashes(self):
        '''
        Tests the arg parser to ensure that kwargs with dashes in the arg name
        are properly identified as kwargs. If this fails, then the KWARG_REGEX
        variable in salt/utils/__init__.py needs to be fixed.
        '''
        self.assertEqual(
            self.run_function(
                'test.arg', ['foo-bar=baz']
            ).get('kwargs', {}).get('foo-bar'),
            'baz'
        )

    def test_argument_containing_pound_sign(self):
        '''
        Tests the argument parsing to ensure that a CLI argument with a pound
        sign doesn't have the pound sign interpreted as a comment and removed.
        See https://github.com/saltstack/salt/issues/8585 for more info.
        '''
        arg = 'foo bar #baz'
        self.assertEqual(
            self.run_function('test.echo', [arg]),
            arg
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ArgumentTestCase)
