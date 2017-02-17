# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    integration.loader.ext_modules
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test Salt's loader regarding external overrides
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import integration


class LoaderOverridesTest(integration.ModuleCase):

    def test_overridden_internal(self):
        funcs = self.run_function('sys.list_functions')

        # We placed a test module under _modules.
        # The previous functions should also still exist.
        self.assertIn('test.ping', funcs)

        # A non existing function should, of course, not exist
        self.assertNotIn('brain.left_hemisphere', funcs)

        # There should be a new function for the test module, recho
        self.assertIn('test.recho', funcs)

        text = 'foo bar baz quo qux'
        self.assertEqual(
            self.run_function('test.echo', arg=[text])[::-1],
            self.run_function('test.recho', arg=[text]),
        )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderOverridesTest)
