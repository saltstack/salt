# -*- coding: utf-8 -*-
"""
    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

# Import python libs
import os
import sys
import yaml

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class CopyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-cp'

    def test_cp_testfile(self):
        '''
        test salt-cp
        '''
        minions = []
        for line in self.run_salt('--yaml-out "*" test.ping'):
            if not line:
                continue
            data = yaml.load(line)
            minions.extend(data.keys())

        self.assertNotEqual(minions, [])

        testfile = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'files', 'file', 'base', 'testfile'
            )
        )
        testfile_contents = open(testfile, 'r').read()

        for minion in minions:
            minion_testfile = os.path.join(
                integration.TMP, "{0}_testfile".format(minion)
            )
            self.run_cp('{0} {1} {2}'.format(minion, testfile, minion_testfile))
            self.assertTrue(os.path.isfile(minion_testfile))
            self.assertTrue(open(minion_testfile, 'r').read() == testfile_contents)
            os.unlink(minion_testfile)

if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(CopyTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
