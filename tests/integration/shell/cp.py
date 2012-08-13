# -*- coding: utf-8 -*-
"""
    tests.integration.shell.cp
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: © 2012 UfSoft.org - :email:`Pedro Algarvio (pedro@algarvio.me)`
    :license: Apache 2.0, see LICENSE for more details.
"""

# Import python libs
import os
import re
import sys
import string
import random

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration
from integration import TestDaemon


class CopyTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-cp'

    def setUp(self):
        self.testfile = os.path.join(integration.TMP, 'testfile')
        self.testcontents = ''.join(
            random.choice(string.ascii_uppercase) for x in range(128)
        )
        open(self.testfile, 'w').write(self.testcontents)

    def tearDown(self):
        os.unlink(self.testfile)

    def test_cp_testfile(self):
        '''
        test salt-cp
        '''
        data = ''.join(self.run_salt('"*" test.ping'))
        for minion in re.findall(r"{['|\"]([^:]+)['|\"]: True}", data):
            minion_testfile = os.path.join(
                integration.TMP, "{0}_testfile".format(minion)
            )
            self.run_cp("minion {0} {1}".format(self.testfile, minion_testfile))
            self.assertTrue(os.path.isfile(minion_testfile))
            self.assertTrue(open(minion_testfile, 'r').read()==self.testcontents)
            os.unlink(minion_testfile)


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(CopyTest)
    print('Setting up Salt daemons to execute tests')
    with TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())