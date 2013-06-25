# -*- coding: utf-8 -*-
'''
    tests.integration.shell.minion
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012-2013 by the SaltStack Team, see AUTHORS for more details
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import sys

# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


class MinionTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-minion'


if __name__ == '__main__':
    from integration import run_tests
    run_tests(MinionTest)
