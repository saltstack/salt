# -*- coding: utf-8 -*-
'''
Tests for the state runner
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting.helpers import (
    ensure_in_syspath,
)
ensure_in_syspath('../../')

# Import Salt Libs
import integration


class StateRunnerTest(integration.ShellCase):
    '''
    Test the state runner.
    '''

    def test_orchestrate_output(self):
        '''
        Ensure the orchestrate runner outputs useful state data.

        In Issue #31330, the output only contains ['outputter:', '    highstate'],
        and not the full stateful return. This tests ensures we don't regress in that
        manner again.

        Also test against some sample "good" output that would be included in a correct
        orchestrate run.
        '''
        ret = self.run_run_plus('state.orchestrate', '', 'orch.simple')
        bad_out = ['outputter:', '    highstate']
        good_out = ['    Function: salt.state',
                    '      Result: True',
                    'Succeeded: 1 (changed=1)',
                    'Failed:    0',
                    'Total states run:     1']
        ret_output = ret.get('out')

        # First, check that we don't have the "bad" output that was displaying in
        # Issue #31330 where only the highstate outputter was listed
        self.assertIsNot(bad_out, ret_output)

        # Now test that some expected good sample output is present in the return.
        for item in good_out:
            self.assertIn(item, ret_output)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateRunnerTest)
