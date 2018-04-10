# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration


class CLISummaryTest(integration.ShellCase, integration.ShellCaseCommonTestsMixIn):

    def test_single_minion_single_failure(self):
        '''
        Verify that a failure in any of the requisite states causes an overall retcode failure to be
        returned for the applied state.
        '''

        (ret, retcode) = self.run_salt(
            '-v --summary minion state.apply cli_summary',
            with_retcode=True,
        )

        self.assertTrue(isinstance(ret, list), 'Returned "ret" must be a list')
        self.assertNotEqual(ret, [], 'Returned "ret" must not be empty')
        self.assertTrue('# of minions targeted: 1' in ret, 'Missing or incorrect "targeted" count.')
        self.assertTrue('# of minions returned: 1' in ret, 'Missing or incorrect "returned" count.')
        self.assertTrue('# of minions with errors: 1' in ret, 'Missing or incorrect "errors" count.')
        self.assertTrue('Minions with failures: minion' in ret, 'Missing or incorrect failure list.')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(CLISummaryTest)
