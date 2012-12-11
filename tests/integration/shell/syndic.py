# -*- coding: utf-8 -*-
'''
    tests.integration.shell.syndic
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import sys

# Import salt libs
from saltunittest import TestLoader, TextTestRunner
import integration


class SyndicTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-syndic'


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(SyndicTest)
    print('Setting up Salt daemons to execute tests')
    with integration.TestDaemon():
        runner = TextTestRunner(verbosity=1).run(tests)
        sys.exit(runner.wasSuccessful())
