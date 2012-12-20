# -*- coding: utf-8 -*-
'''
    tests.integration.states.match
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os

# Import salt libs
import salt.utils
import integration

from saltunittest import skipIf

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class StateMatchTest(integration.ModuleCase):
    '''
    Validate the file state
    '''

    def test_issue_2167_exsel_no_AttributeError(self):
        ret = self.run_function('state.top', ['issue-2167-exsel-match.sls'])
        self.assertNotIn(
            "AttributeError: 'Matcher' object has no attribute 'functions'",
            ret
        )

    @skipIf(os.geteuid() is not 0, 'you must be root to run this test')
    def test_issue_2167_ipcidr_no_AttributeError(self):
        subnets = self.run_function('network.subnets')
        self.assertTrue(len(subnets) > 0)
        top_filename = 'issue-2167-ipcidr-match.sls'
        top_file = os.path.join(STATE_DIR, top_filename)
        try:
            salt.utils.fopen(top_file, 'w').write(
                'base:\n'
                '  {0}:\n'
                '    - match: ipcidr\n'
                '    - test\n'.format(subnets[0])
            )
            ret = self.run_function('state.top', [top_filename])
            self.assertNotIn(
                'AttributeError: \'Matcher\' object has no attribute '
                '\'functions\'',
                ret
            )
        finally:
            os.remove(top_file)
