# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    integration.loader
    ~~~~~~~~~~~~~~~~~~

    Test Salt's loader
'''

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../')

# Import salt libs
import integration


class LoaderTest(integration.ModuleCase):

    def test_overridden_int_module(self):
        funcs = self.run_function('sys.list_functions')

        # We placed a test module under _modules.
        # There should be a new function for the test module, recho
        self.assertIn('test.recho', funcs)

        # The previous functions should also still exist.
        self.assertIn('test.ping', funcs)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(LoaderTest)
