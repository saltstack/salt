# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    tests.integration.states.match
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''

# Import python libs
from __future__ import absolute_import
import os

# Import Salt Testing libs
from salttesting import skipIf
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.utils

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')


class StateMatchTest(integration.ModuleCase):
    '''
    Validate the file state
    '''

    @skipIf(os.geteuid() != 0, 'you must be root to run this test')
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


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateMatchTest)
