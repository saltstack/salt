# -*- coding: utf-8 -*-
"""
    tests.integration.shell.call
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner, skipIf
import integration
from integration import TestDaemon


class CallTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-call'

    def test_default_output(self):
        out = self.run_call('test.fib 3')
        self.assertEqual(
            "local: !!python/tuple\n- [0, 1, 1, 2]", '\n'.join(out[:-3])
        )

    def test_text_output(self):
        out = self.run_call('--text-out test.fib 3')
        self.assertEqual("local: ([0, 1, 1, 2]", ''.join(out).rsplit(",", 1)[0])

    @skipIf(sys.platform.startswith('win'), 'This test does not apply on Win')
    def test_user_delete_kw_output(self):
        ret = self.run_call('-d user.delete')
        self.assertIn(
            'salt \'*\' user.delete name remove=True force=True',
            ''.join(ret)
        )


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(CallTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
