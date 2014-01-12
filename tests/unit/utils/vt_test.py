# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.unit.utils.vt_test
    ~~~~~~~~~~~~~~~~~~~~~~~~

    VirtualTerminal tests
'''

# Import python libs
import random

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
from salt.utils import vt


class VTTestCase(TestCase):

    def test_vt_size(self):
        '''Confirm that the terminal size is being set'''
        self.skipTest('The code is not mature enough. Test disabled.')
        cols = random.choice(range(80, 250))
        terminal = vt.Terminal(
            'echo Foo!',
            shell=True,
            cols=cols
        )
        # First the assertion
        self.assertEqual(
            terminal.getwinsize(), (24, cols)
        )
        # Then wait for the terminal child to exit
        terminal.wait()

if __name__ == '__main__':
    from integration import run_tests
    run_tests(VTTestCase, needs_daemon=False)
